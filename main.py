"""
Hankintailmoitusten seuranta: paaohjelma.

Ajo:
    python main.py                normaali viikkoajo (maanantaisin)
    python main.py --dry-run      hakee ja tulostaa, ei kirjoita tiedostoja
    python main.py --since 2026-09-15
                                  pakota vesiraja, esim. ensimmaisella
                                  ajolla tai jos ajo on ollut pois paalta

Tila on state.json. Siina on kaksi asiaa:

    watermark  Hetki, johon asti ilmoitukset on jo haettu. Seuraava ajo
               hakee kaiken sen jalkeen julkaistun. Tama on syy siihen,
               ettei yksikaan ilmoitus jaa kahden ajon valiin, vaikka
               maanantain ajo tehtaisiin aamulla ja ilmoitus julkaistaisiin
               samana iltapaivana. Kasin tehdyssa haussa tallainen
               ilmoitus katoaa, koska seuraava viikko alkaa vasta
               tiistaista.

    periods    Jaksoittain ryhmitellyt ilmoitukset. Ilmoitus kuuluu siihen
               jaksoon, jolla se LOYTYI, ei siihen, jolla se julkaistiin.
               Nain edella kuvattu myohassa loytynyt ilmoitus paatyy
               viestiin kerran eika putoa raportoimatta.

Ilmoituksen tunniste on Hilman ilmoitustunnus (noticeId), joka on pysyva.
Korjausilmoitus saa oman tunnuksensa, joten se nakyy uutena rivina
merkinnalla KORJAUS. Se on tarkoitus: korjaus voi muuttaa maaraaikaa.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys
from zoneinfo import ZoneInfo

import yaml

import hilma
import scoring
from render import render_all

ROOT = pathlib.Path(__file__).parent
STATE_PATH = ROOT / "state.json"
CONFIG_PATH = ROOT / "sources.yaml"
DOCS = ROOT / "docs"


def load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print("state.json on rikki, aloitetaan tyhjasta", file=sys.stderr)
    return {"last_run": None, "watermark": None, "periods": {}, "seen": {}}


def iso(stamp: dt.datetime | None) -> str | None:
    return stamp.isoformat(timespec="seconds") if stamp else None


def to_record(notice: hilma.Notice, tz: ZoneInfo) -> dict:
    """Sivun JSON-kuorman rivi.

    Paivamaarat annetaan paikallisessa ajassa aikavyohykesiirtymineen,
    jotta selaimen new Date() nayttaa maaraajan Suomen aikaa riippumatta
    siita, missa sivua katsotaan.
    """
    return {
        "key": notice.key,
        "id": notice.notice_id,
        "number": notice.notice_number,
        "title": notice.title,
        "org": notice.organisation,
        "desc": notice.description,
        "url": notice.url,
        "docs_url": notice.documents_url,
        "published": iso(notice.published.astimezone(tz)),
        "deadline": iso(notice.deadline.astimezone(tz)) if notice.deadline else None,
        "value": notice.estimated_value,
        "currency": notice.currency,
        "cpv": notice.matched_cpv or notice.cpv,
        "main_type": notice.main_type,
        "corrigendum": notice.is_corrigendum,
        "framework": notice.framework,
        "dps": notice.dps,
        "level": notice.level,
        "reasons": notice.reasons,
        # Osa-aluetieto kulkee viestiin asti: se kertoo lukijalle, miksi
        # rivi on mukana, kun otsikko ei sita kerro.
        "lot_only": bool(notice.matched_lots and not notice.matched_cpv),
        "lots": [
            {"title": lot.title, "cpv": lot.matched_cpv or lot.cpv}
            for lot in notice.matched_lots
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="ala kirjoita tiedostoja")
    ap.add_argument("--since", help="pakota vesiraja, muoto YYYY-MM-DD")
    args = ap.parse_args()

    cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    tz = ZoneInfo(cfg["site"].get("timezone", "Europe/Helsinki"))
    now = dt.datetime.now(tz)

    start, end = hilma.period_bounds(now, cfg)
    label = hilma.fmt_period(start, end)
    period_id = start.date().isoformat()
    print(f"Seurantajakso {label}  (tunnus {period_id})")

    state = load_state()
    periods: dict = state.setdefault("periods", {})
    seen: dict = state.setdefault("seen", {})

    # Vesiraja. Ensimmaisella ajolla se on jakson alku, jolloin
    # ensimmainen viesti kattaa kuluvan viikon.
    if args.since:
        since = dt.datetime.combine(
            dt.date.fromisoformat(args.since), dt.time.min, tzinfo=tz
        )
    elif state.get("watermark"):
        since = dt.datetime.fromisoformat(state["watermark"])
    else:
        since = start
    print(f"Haetaan kaikki, mika on julkaistu {since:%-d.%-m.%Y klo %H:%M} jalkeen")

    result = hilma.fetch(cfg, since)
    if not result.ok:
        print(f"VIRHE: {result.error}", file=sys.stderr)
        # Sivu kirjoitetaan silti vanhalla datalla ja virheilmoituksella,
        # jotta maanantaiaamuna nakee heti, etta haku epaonnistui eika
        # sita erehdy luulemaan hiljaiseksi viikoksi.
        if not args.dry_run:
            render_all(cfg, state, now, DOCS,
                       error=f"Haku ep\u00e4onnistui {fi(now)}: {result.error}. "
                             "Sivulla on edellisen onnistuneen ajon tiedot.")
        return 1

    notices = scoring.score_all(result.notices, cfg)
    print(f"Rajapinnasta {result.total_seen} ilmoitusta, CPV-suodattimen lapaisi {len(notices)}")

    period = periods.setdefault(period_id, {
        "id": period_id,
        "label": label,
        "start": iso(start),
        "end": iso(end),
        "notices": [],
    })
    period["label"] = label

    existing = {rec["key"] for rec in period["notices"]}
    added = 0
    for notice in notices:
        if notice.key in existing:
            # Sama ajo ajettu uudelleen: paivitetaan rivi, koska
            # maaraaika tai kuvaus on voinut tarkentua.
            period["notices"] = [
                to_record(notice, tz) if rec["key"] == notice.key else rec
                for rec in period["notices"]
            ]
            continue
        if notice.key in seen:
            # Jo raportoitu aiemmalla jaksolla, ei nosteta uudelleen.
            continue
        period["notices"].append(to_record(notice, tz))
        seen[notice.key] = period_id
        existing.add(notice.key)
        added += 1

    period["notices"].sort(
        key=lambda r: (scoring.LEVEL_ORDER.get(r["level"], 9), r["published"] or ""),
    )

    state["last_run"] = iso(now)
    # Vesiraja on ajohetki, ei jakson loppu: kaikki tahan asti julkaistu
    # on nyt kasitelty.
    state["watermark"] = iso(now)

    # Karsi vanhat jaksot ja niiden tunnisteet.
    keep = int(cfg["site"].get("keep_periods", 12))
    for old in sorted(periods.keys(), reverse=True)[keep:]:
        del periods[old]
    state["seen"] = {k: v for k, v in seen.items() if v in periods}

    print(f"\nUusia t\u00e4lle jaksolle: {added} | jaksolla yhteens\u00e4: {len(period['notices'])}")
    for rec in period["notices"][:40]:
        mark = {"vahva": "**", "tarkista": " ?", "heikko": "  ", "kohina": " -"}[rec["level"]]
        print(f"  {mark} {rec['title'][:72]}")

    if args.dry_run:
        print("\n--dry-run: tiedostoja ei kirjoitettu")
        return 0

    render_all(cfg, state, now, DOCS)
    STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"\nKirjoitettu {DOCS/'index.html'}")
    return 0


def fi(now: dt.datetime) -> str:
    return f"{now.day}.{now.month}.{now.year} klo {now:%H:%M}"


if __name__ == "__main__":
    raise SystemExit(main())
