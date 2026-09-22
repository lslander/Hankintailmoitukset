"""
Hilman AVP-hakurajapinnan asiakas.

Rajapinta on Azure Cognitive Search, eli kyselyt tehdaan GET-parametreilla
$filter, $orderby, $top ja $skip. Indeksi on "eformnotices-v2", jossa on
kaikki ilmoitukset eForms-siirtymasta (31.8.2023) lahtien.

Kaksi asiaa, jotka poikkeavat Hilman omasta hakulomakkeesta:

1. Aikaikkuna haetaan vesirajan mukaan, ei nimellisen viikon mukaan.
   Kasin tehdyssa ohjeessa "Julkaistu ennen" asetetaan huomiselle, jolloin
   maanantai-iltapaivan ilmoitukset jaavat kahden ajon valiin. Tassa
   haetaan kaikki, mita on julkaistu edellisen ajon katkaisuhetken
   jalkeen, joten valiin ei jaa mitaan.

2. CPV-suodatus tehdaan paikallisesti, ei rajapinnassa. Syy on se, etta
   ilmoituksen osa-alueilla (lots) on omat CPV-koodinsa, ja ohje varoittaa
   erikseen monilohkoisista ilmoituksista: otsikko voi olla taysin muusta
   aiheesta, vaikka yksi osa-alue olisi oikeudellista osaamista vaativa.
   Kun koodit katsotaan paikallisesti, nama tulevat mukaan.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

UTC = dt.timezone.utc


# ---------------------------------------------------------------------------
# Tietorakenteet
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class Lot:
    """Ilmoituksen osa-alue. Naytetaan sivulla vain, jos se osui hakuun."""

    lot_id: str
    title: str
    description: str
    cpv: list[str]
    deadline: dt.datetime | None
    estimated_value: float | None
    currency: str
    matched_cpv: list[str] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class Notice:
    notice_id: int
    procedure_id: int
    notice_number: str
    main_type: str
    title: str
    organisation: str
    organisation_type: str
    description: str
    published: dt.datetime
    deadline: dt.datetime | None
    estimated_value: float | None
    currency: str
    cpv: list[str]
    nuts: list[str]
    url: str
    documents_url: str
    is_corrigendum: bool
    is_cancelled: bool
    framework: bool
    dps: bool
    lots: list[Lot]
    matched_cpv: list[str]
    matched_lots: list[Lot]
    # Taytetaan scoring.py:ssa.
    level: str = "heikko"
    reasons: list[str] = dataclasses.field(default_factory=list)

    @property
    def key(self) -> str:
        """Tunniste tilassa. Ilmoitustunnus on pysyva ja yksilollinen."""
        return f"EF-{self.notice_id}"


@dataclasses.dataclass
class FetchResult:
    ok: bool
    notices: list[Notice]
    total_seen: int
    error: str = ""


# ---------------------------------------------------------------------------
# Seurantajakso
# ---------------------------------------------------------------------------


def period_bounds(now: dt.datetime, cfg: dict) -> tuple[dt.datetime, dt.datetime]:
    """Palauttaa nimellisen seurantajakson alun ja lopun paikallisessa ajassa.

    Jakso paattyy konfiguraation "ends_on_weekday"-paivaan (1 = maanantai)
    ja kestaa "length_days" vuorokautta. Oletuksilla tama on tiistai 00:00
    - maanantai 23:59:59.999.

    Paatospaiva haetaan ETEENPAIN, tama paiva mukaan lukien. Maanantaina
    ajettaessa jakso on siis kuluva tiistai-maanantai, kuten pitaakin.
    Keskiviikkona kasin ajettaessa jakso on seuraava tiistai-maanantai,
    eli se jakso, jota ollaan parhaillaan keraamassa. Jos paivaa haettaisiin
    taaksepain, keskiviikon ajo kirjaisi loydot jo lahetettyyn viikkoon,
    jolloin ne eivat paatyisi yhteenkaan viestiin.
    """
    period = cfg.get("period", {})
    end_weekday = int(period.get("ends_on_weekday", 1))
    length = int(period.get("length_days", 7))

    today = now.date()
    ahead = (end_weekday - today.isoweekday()) % 7
    end_day = today + dt.timedelta(days=ahead)
    start_day = end_day - dt.timedelta(days=length - 1)

    tz = now.tzinfo
    start = dt.datetime.combine(start_day, dt.time.min, tzinfo=tz)
    end = dt.datetime.combine(end_day, dt.time.max, tzinfo=tz)
    return start, end


def fmt_period(start: dt.datetime, end: dt.datetime) -> str:
    """Otsikkomuoto: '15.9.2026 - 21.9.2026'."""
    return f"{start.day}.{start.month}.{start.year} - {end.day}.{end.month}.{end.year}"


# ---------------------------------------------------------------------------
# Apufunktiot
# ---------------------------------------------------------------------------


def parse_dt(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        stamp = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    return stamp


def split_codes(value: str | None) -> list[str]:
    """Hilma tallettaa CPV- ja NUTS-koodit valilyonnein erotettuna."""
    if not value:
        return []
    return [part for part in str(value).replace(",", " ").split() if part]


def pick_text(record: dict, base: str) -> str:
    """Suomi ensin, sitten ruotsi ja englanti.

    Ahvenanmaan ja rannikon hankintayksikot julkaisevat ilmoituksia vain
    ruotsiksi, jolloin titleFi on tyhja merkkijono. Ilman varalaskua rivi
    nakyisi sivulla nimettomana.
    """
    for suffix in ("Fi", "Sv", "En", "Other"):
        text = record.get(base + suffix)
        if text and str(text).strip():
            return str(text).strip()
    return ""


def cpv_matches(codes: list[str], prefixes: list[str]) -> list[str]:
    """Etuliitetasmays.

    Hilman indeksissa on varsinaiset koodit, ei koodipuuta, joten emokoodi
    79000000 ei tuo lapsikoodeja mukanaan. Siksi tasmays tehdaan
    etuliitteena: "79" kattaa koko haaran.
    """
    hits = []
    for code in codes:
        for prefix in prefixes:
            if code.startswith(str(prefix)):
                hits.append(code)
                break
    return hits


# ---------------------------------------------------------------------------
# Haku
# ---------------------------------------------------------------------------


def build_filter(main_types: list[str], since: dt.datetime, until: dt.datetime | None) -> str:
    """OData-suodatin. Tyypit ja aikavali rajataan rajapinnassa, koska ne
    karsivat suurimman osan pois. CPV hoidetaan paikallisesti."""
    parts = [f"datePublished ge {since.astimezone(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}"]
    if until is not None:
        parts.append(f"datePublished le {until.astimezone(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}")
    if main_types:
        types = " or ".join(f"mainType eq '{t}'" for t in main_types)
        parts.append(f"({types})")
    return " and ".join(parts)


def _request(url: str, key: str | None, timeout: int) -> dict:
    headers = {
        "Accept": "application/json",
        "User-Agent": "hankintaseuranta/1.0 (+github actions)",
    }
    if key:
        headers["Ocp-Apim-Subscription-Key"] = key
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def to_notice(record: dict, cfg: dict, prefixes: list[str], match_lots: bool) -> Notice | None:
    """Muuntaa rajapinnan tietueen ja tekee CPV-tasmayksen.

    Palauttaa None, jos ilmoitus ei osu CPV-suodattimeen lainkaan.
    """
    top_cpv = split_codes(record.get("cpvCodes"))
    matched = cpv_matches(top_cpv, prefixes)

    lots: list[Lot] = []
    matched_lots: list[Lot] = []
    for raw in record.get("lots") or []:
        lot_cpv = split_codes(raw.get("cpvCodes"))
        lot = Lot(
            lot_id=str(raw.get("id") or ""),
            title=pick_text(raw, "title"),
            description=pick_text(raw, "description"),
            cpv=lot_cpv,
            deadline=parse_dt(raw.get("deadline") or raw.get("expirationDate")),
            estimated_value=raw.get("estimatedValue") or None,
            currency=str(raw.get("currency") or ""),
        )
        lot.matched_cpv = cpv_matches(lot_cpv, prefixes)
        lots.append(lot)
        if lot.matched_cpv:
            matched_lots.append(lot)

    if not matched and not (match_lots and matched_lots):
        return None

    notice_id = int(record.get("noticeId") or 0)
    procedure_id = int(record.get("procedureId") or 0)
    template = cfg.get(
        "notice_url",
        "https://www.hankintailmoitukset.fi/fi/public/procurement/{procedure}/notice/{notice}/overview",
    )
    url = template.format(procedure=procedure_id, notice=notice_id)

    published = parse_dt(record.get("datePublished")) or dt.datetime.now(UTC)

    # Paatason maaraaika puuttuu joskus, vaikka osa-alueilla se on.
    # Otetaan silloin aikaisin osa-alueen maaraaika, koska se on se,
    # johon tarjoajan on ehdittava.
    deadline = parse_dt(record.get("deadline") or record.get("expirationDate"))
    if deadline is None:
        lot_deadlines = [lot.deadline for lot in lots if lot.deadline]
        if lot_deadlines:
            deadline = min(lot_deadlines)

    value = record.get("estimatedValue")
    if not value:
        value = record.get("overallMaximumFrameworkContractsAmount") or None
    if not value:
        lot_values = [lot.estimated_value for lot in lots if lot.estimated_value]
        value = sum(lot_values) if lot_values else None

    currency = str(
        record.get("currency")
        or record.get("overallMaximumFrameworkContractsCurrency")
        or ""
    )

    return Notice(
        notice_id=notice_id,
        procedure_id=procedure_id,
        notice_number=str(record.get("noticeNumber") or ""),
        main_type=str(record.get("mainType") or ""),
        title=pick_text(record, "title") or f"(nimeton ilmoitus {notice_id})",
        organisation=pick_text(record, "organisationName"),
        organisation_type=str(record.get("organisationType") or ""),
        description=pick_text(record, "description"),
        published=published,
        deadline=deadline,
        estimated_value=float(value) if value else None,
        currency=currency,
        cpv=top_cpv,
        nuts=split_codes(record.get("nutsCodes")),
        url=url,
        documents_url=str(record.get("procurementDocumentsUrl") or ""),
        is_corrigendum=bool(record.get("isCorrigendum")),
        is_cancelled=bool(record.get("isCancelled")),
        framework=bool(record.get("includesFrameworkAgreement")),
        dps=bool(record.get("includesDynamicPurcharingSystem")),
        lots=lots,
        matched_cpv=matched,
        matched_lots=matched_lots,
    )


def fetch(cfg: dict, since: dt.datetime, until: dt.datetime | None = None) -> FetchResult:
    """Hakee kaikki ilmoitukset aikavalilta ja suodattaa CPV:lla.

    "since" on vesiraja: kaikki, mita on julkaistu sen jalkeen. "until"
    on yleensa None, jolloin haetaan ajohetkeen asti.
    """
    api = cfg.get("api", {})
    search = cfg.get("search", {})
    key = os.environ.get(api.get("key_env", "HILMA_API_KEY"), "").strip() or None

    prefixes = [str(p) for p in search.get("cpv_prefixes", [])]
    match_lots = bool(search.get("match_lot_cpv", True))
    exclude_cancelled = bool(search.get("exclude_cancelled", True))

    page_size = int(api.get("page_size", 200))
    max_pages = int(api.get("max_pages", 40))
    timeout = int(api.get("timeout", 60))
    pause = float(api.get("sleep_between_pages", 0.5))

    odata = build_filter([str(t) for t in search.get("main_types", [])], since, until)

    notices: list[Notice] = []
    seen_ids: set[int] = set()
    total_seen = 0

    for page in range(max_pages):
        params = {
            "search": "*",
            "$filter": odata,
            # Vanhin ensin, jotta sivutus pysyy vakaana: uusia ilmoituksia
            # voi julkaista kesken ajon, ja laskevassa jarjestyksessa ne
            # siirtaisivat kaikkia rivejä yhden eteenpain.
            "$orderby": "datePublished asc",
            "$top": str(page_size),
            "$skip": str(page * page_size),
            "$count": "true",
        }
        if api.get("api_version"):
            params["api-version"] = str(api["api_version"])
        url = api.get("search_url", "") + "?" + urllib.parse.urlencode(params)

        try:
            payload = _request(url, key, timeout)
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", "replace")[:200]
            except Exception:
                pass
            return FetchResult(False, notices, total_seen, f"HTTP {exc.code} {detail}")
        except Exception as exc:  # verkkovirhe, aikakatkaisu
            return FetchResult(False, notices, total_seen, f"{type(exc).__name__}: {exc}")

        batch = payload.get("value") or []
        if not batch:
            break
        total_seen += len(batch)

        for record in batch:
            if exclude_cancelled and record.get("isCancelled"):
                continue
            notice = to_notice(record, cfg, prefixes, match_lots)
            if notice is None or notice.notice_id in seen_ids:
                continue
            seen_ids.add(notice.notice_id)
            notices.append(notice)

        if len(batch) < page_size:
            break
        if pause:
            time.sleep(pause)

    notices.sort(key=lambda n: n.published, reverse=True)
    return FetchResult(True, notices, total_seen)


def local(stamp: dt.datetime | None, tz: ZoneInfo) -> dt.datetime | None:
    return stamp.astimezone(tz) if stamp else None
