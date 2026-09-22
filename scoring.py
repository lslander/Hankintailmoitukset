"""
Relevanssiehdotus.

Tama moduuli EI paata, mika ilmoitus lahetetaan markkinoinnille. Se vain
varittaa rivin, jotta tiedat mista aloittaa lukemisen. Valinta tehdaan
sivulla ruksilla, ja jokainen rivi on ruksattavissa tasosta riippumatta.

Tasot:
    vahva    CPV on oikeudellisten palvelujen haarassa (791x) tai tekstissa
             on vahva avainsana. Aloita naista.
    tarkista Heikko avainsana osui. Sisalto pitaa lukea ennen paatosta.
    heikko   CPV-suodatin lapaisty, mutta mikaan ei viittaa juridiikkaan.
    kohina   Osui kohinasanaan (siivous, ateria, vartiointi). Rivi nakyy
             harmaana, mutta se on yha ruksattavissa.

Ohjeen periaate on matala kynnys: "Parempi laittaa muutama turha mukaan
kuin mahdollisesti antaa isojen voittojen mennä ohi." Siksi mikaan rivi ei
katoa listalta, vaan kohina vain siirtyy visuaalisesti taakse.
"""

from __future__ import annotations

import unicodedata

from hilma import Notice

LEVEL_ORDER = {"vahva": 0, "tarkista": 1, "heikko": 2, "kohina": 3}

LEVEL_LABEL = {
    "vahva": "Vahva osuma",
    "tarkista": "Tarkista",
    "heikko": "Heikko",
    "kohina": "Tuskin meille",
}


def normalize(text: str) -> str:
    """Pienet kirjaimet ja aksentit pois.

    Nain avainsanan voi kirjoittaa sources.yaml:iin joko muodossa
    "tyooikeu" tai "tyooikeu" ilman, etta a:n ja a:n ero rikkoo osuman.
    Hankintayksikot kirjoittavat otsikoita vaihtelevasti, ja osa
    julkaisujarjestelmista riisuu aakkoset itsekin.
    """
    lowered = str(text or "").lower()
    decomposed = unicodedata.normalize("NFKD", lowered)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def headline(notice: Notice) -> str:
    """Otsikkoteksti: ilmoituksen ja osa-alueiden otsikot.

    Osa-alueiden otsikot ovat mukana tarkoituksella. Ohje varoittaa, etta
    monilohkoisessa ilmoituksessa vain yksi osa-alue voi olla
    oikeudellista osaamista vaativa, eika se nay paaotsikossa.
    """
    parts = [notice.title, notice.organisation]
    parts.extend(lot.title for lot in notice.lots)
    return normalize(" \n ".join(p for p in parts if p))


def bodytext(notice: Notice) -> str:
    """Kuvaustekstit.

    Kuvaus on paljon epaluotettavampi signaali kuin otsikko. Lahes joka
    ilmoituksessa lukee "hankintalain (1397/2016) mukaisesti" ja
    vaatimuksissa mainitaan tietosuoja ja GDPR, vaikka itse hankinta
    olisi hoitajakutsujarjestelma. Siksi kuvausosuma kasitellaan
    heikompana kuin otsikko-osuma.
    """
    parts = [notice.description]
    parts.extend(lot.description for lot in notice.lots)
    return normalize(" \n ".join(p for p in parts if p))


def matching(terms: list[str], text: str) -> list[str]:
    hits = []
    for term in terms:
        needle = normalize(term)
        if needle and needle in text:
            hits.append(str(term))
    return hits


def cpv_prefix_hits(notice: Notice, prefixes: list[str]) -> list[str]:
    codes = list(notice.cpv)
    for lot in notice.lots:
        codes.extend(lot.cpv)
    hits = []
    for code in codes:
        for prefix in prefixes:
            if code.startswith(str(prefix)) and code not in hits:
                hits.append(code)
                break
    return hits


def score(notice: Notice, cfg: dict) -> Notice:
    rules = cfg.get("scoring", {})
    head = headline(notice)
    body = bodytext(notice)
    text = head + " \n " + body

    strong_list = [str(w) for w in rules.get("strong_keywords", [])]
    strong_cpv = cpv_prefix_hits(notice, [str(p) for p in rules.get("strong_cpv_prefixes", [])])
    strong_head = matching(strong_list, head)
    # Vain ne kuvausosumat, jotka eivat jo osuneet otsikkoon.
    strong_body = [w for w in matching(strong_list, body) if w not in strong_head]
    weak_words = matching([str(w) for w in rules.get("weak_keywords", [])], text)
    noise_words = matching([str(w) for w in rules.get("noise_keywords", [])], head)

    reasons: list[str] = []
    if strong_cpv:
        reasons.append("CPV " + ", ".join(strong_cpv[:3]))
    if strong_head:
        reasons.append(", ".join(strong_head[:4]))

    # CPV on rakenteista dataa, jonka hankintayksikko on valinnut
    # tarkoituksella, joten se riittaa yksin vahvaksi osumaksi.
    # Avainsana riittaa vain otsikossa.
    if strong_cpv or strong_head:
        level = "vahva"
    elif strong_body:
        # Vahva sana loytyi vain kuvauksesta. Se voi olla oikea osuma tai
        # pelkkaa vakiotekstia, joten sita ei voi paattaa lukematta.
        level = "tarkista"
        reasons.append("kuvauksessa: " + ", ".join(strong_body[:4]))
    elif weak_words:
        level = "tarkista"
        reasons.append(", ".join(weak_words[:4]))
    elif noise_words:
        level = "kohina"
        reasons.append(", ".join(noise_words[:3]))
    else:
        level = "heikko"

    # Kohinasana ei koskaan kumoa vahvaa osumaa, ja se luetaan vain
    # otsikosta. Vartiointipalvelun hankinnassa voi olla oikeudellinen
    # osa-alue, ja "tulkkauspalvelu" esiintyy tuomioistuinten
    # hankinnoissa, joissa on myos juridiikkaa.
    if level == "tarkista" and noise_words:
        reasons.append("myos: " + ", ".join(noise_words[:2]))

    # Osa-alueosuma on itsessaan syy nostaa rivi esiin, koska se on juuri
    # se tapaus, jonka kasin tehty haku jattaa huomaamatta.
    if notice.matched_lots and not notice.matched_cpv:
        reasons.insert(0, f"osa-alue ({len(notice.matched_lots)} kpl)")
        if level == "heikko":
            level = "tarkista"

    notice.level = level
    notice.reasons = reasons
    return notice


def score_all(notices: list[Notice], cfg: dict) -> list[Notice]:
    scored = [score(n, cfg) for n in notices]
    scored.sort(key=lambda n: (LEVEL_ORDER.get(n.level, 9), -n.published.timestamp()))
    return scored
