"""
Sivun kirjoitus.

Sivulla on kaksi osaa:

1. Sahkopostimalli ylhaalla. Se paivittyy sita mukaa kun ruksaat rivejä
   listasta, eli valmis viesti on aina nakyvissa. Kopiointi tehdaan
   ClipboardItemilla, joka vie leikepoydalle seka text/html- etta
   text/plain-version. Outlook ottaa HTML-version, jolloin linkit
   sailyvat klikattavina. Jos selain ei anna lupaa, varalla on vanha
   document.execCommand("copy").

2. Ilmoituslista. Jokainen rivi on ruksattavissa. Koodi ehdottaa
   varilla, mista aloittaa, mutta se ei valitse puolestasi eika piilota
   mitaan: ohjeen mukaan on parempi lahettaa muutama turha kuin
   menettaa iso tarjouskilpailu.

Valinnat talletetaan selaimen localStorageen jaksoittain, jotta sivun
voi sulkea kesken tyon. Tallennus on try/catch-suojattu, koska osa
selaimista estaa sen.
"""

from __future__ import annotations

import datetime as dt
import html
import json
import pathlib
from zoneinfo import ZoneInfo

# ---------------------------------------------------------------------------
# Ulkoasu. Varit ovat Hilman omasta teemasta.
# ---------------------------------------------------------------------------

CSS = """
:root{
  --green:#108465;
  --green-dark:#0c6a51;
  --green-light:#79BF8A;
  --slate:#383F52;
  --ink:#1d2433;
  --muted:#5b6478;
  --line:#dfe3ea;
  --bg:#f4f6f8;
  --card:#ffffff;
  --amber:#b7791f;
  --amber-bg:#fdf6e7;
  --green-bg:#eaf5f0;
  --grey-bg:#f7f8fa;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{
  margin:0;background:var(--bg);color:var(--ink);
  font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
}
a{color:var(--green-dark)}
.wrap{max-width:1080px;margin:0 auto;padding:0 20px 64px}

/* Ylapalkki */
header.top{background:var(--green);color:#fff}
header.top .wrap{padding:26px 20px 22px}
header.top h1{margin:0;font-size:26px;font-weight:700;letter-spacing:-.2px}
header.top p{margin:6px 0 0;opacity:.9;font-size:14px}
.periodbar{
  background:var(--slate);color:#fff;
}
.periodbar .wrap{
  padding:10px 20px;display:flex;flex-wrap:wrap;gap:10px;align-items:center;
  font-size:13px;
}
.periodbar label{opacity:.8}
.periodbar select{
  font:inherit;padding:5px 8px;border-radius:5px;border:1px solid rgba(255,255,255,.35);
  background:rgba(255,255,255,.1);color:#fff;
}
.periodbar select option{color:#000}
.periodbar .grow{flex:1}
.periodbar .meta{opacity:.75}

/* Kortit */
.card{
  background:var(--card);border:1px solid var(--line);border-radius:10px;
  margin-top:20px;
}
.card > h2{
  margin:0;padding:14px 18px;border-bottom:1px solid var(--line);
  font-size:16px;font-weight:700;
}

/* Sahkopostimalli */
.mailbox .row{
  display:flex;flex-wrap:wrap;gap:10px;align-items:center;
  padding:12px 18px;border-bottom:1px solid var(--line);font-size:13px;
}
.mailbox .row .k{color:var(--muted);min-width:64px}
.mailbox .row .v{
  font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  background:var(--grey-bg);border:1px solid var(--line);border-radius:5px;
  padding:4px 8px;flex:1;min-width:220px;overflow-wrap:anywhere;
}
#preview{
  padding:16px 18px;min-height:90px;font-size:14px;
}
#preview p{margin:0 0 10px}
#preview ul{margin:0 0 12px;padding-left:20px}
#preview li{margin:0 0 10px}
#preview .lbl{color:var(--muted)}
.mailbox .actions{
  display:flex;flex-wrap:wrap;gap:8px;align-items:center;
  padding:12px 18px;border-top:1px solid var(--line);background:var(--grey-bg);
  border-radius:0 0 10px 10px;
}
button{
  font:inherit;cursor:pointer;border-radius:6px;border:1px solid var(--line);
  background:#fff;color:var(--ink);padding:7px 13px;
}
button:hover{border-color:#b9c0cd}
button.primary{background:var(--green);border-color:var(--green);color:#fff;font-weight:600}
button.primary:hover{background:var(--green-dark);border-color:var(--green-dark)}
#status{color:var(--green-dark);font-size:13px;min-height:19px}

/* Suodattimet */
.tools{
  display:flex;flex-wrap:wrap;gap:8px;align-items:center;
  padding:12px 18px;border-bottom:1px solid var(--line);
}
.tools input[type=search]{
  font:inherit;padding:7px 10px;border:1px solid var(--line);border-radius:6px;
  min-width:220px;flex:1;
}
.chip{
  font-size:13px;padding:5px 11px;border-radius:999px;border:1px solid var(--line);
  background:#fff;cursor:pointer;
}
.chip[aria-pressed=true]{background:var(--slate);border-color:var(--slate);color:#fff}
.tools .sep{width:1px;height:22px;background:var(--line)}

/* Lista */
.list{list-style:none;margin:0;padding:0}
.item{
  display:flex;gap:12px;padding:14px 18px;border-bottom:1px solid var(--line);
  border-left:4px solid transparent;
}
.item:last-child{border-bottom:0}
.item.vahva{border-left-color:var(--green);background:var(--green-bg)}
.item.tarkista{border-left-color:var(--amber);background:var(--amber-bg)}
.item.kohina{background:var(--grey-bg);opacity:.72}
.item.on{box-shadow:inset 3px 0 0 var(--slate)}
.item input[type=checkbox]{width:18px;height:18px;margin-top:3px;flex:none;accent-color:var(--green)}
.item .body{flex:1;min-width:0}
.item h3{margin:0 0 4px;font-size:15px;font-weight:600;line-height:1.4}
.item h3 a{text-decoration:none}
.item h3 a:hover{text-decoration:underline}
.org{color:var(--muted);font-size:13px}
.facts{
  margin:7px 0 0;display:flex;flex-wrap:wrap;gap:6px 14px;
  font-size:13px;color:var(--muted);
}
.facts b{color:var(--ink);font-weight:600}
.tags{margin:7px 0 0;display:flex;flex-wrap:wrap;gap:6px}
.tag{
  font-size:11.5px;letter-spacing:.2px;padding:2px 8px;border-radius:999px;
  border:1px solid var(--line);background:#fff;color:var(--muted);
}
.tag.lvl-vahva{background:var(--green);border-color:var(--green);color:#fff}
.tag.lvl-tarkista{background:var(--amber);border-color:var(--amber);color:#fff}
.tag.lvl-kohina{background:#e7e9ee}
.tag.warn{background:#fdecec;border-color:#f3c3c3;color:#a12a2a}
.lots{
  margin:9px 0 0;padding:9px 11px;border-left:3px solid var(--green-light);
  background:#fff;border-radius:0 6px 6px 0;font-size:13px;
}
.lots b{display:block;margin-bottom:3px;font-size:12px;color:var(--muted);
  text-transform:uppercase;letter-spacing:.4px}
.lots div{margin:3px 0}
details.desc{margin:7px 0 0;font-size:13px;color:var(--muted)}
details.desc summary{cursor:pointer;color:var(--green-dark)}
details.desc p{margin:6px 0 0;white-space:pre-wrap}
.empty{padding:26px 18px;color:var(--muted)}

footer{margin-top:26px;color:var(--muted);font-size:12.5px;line-height:1.7}
footer code{background:#fff;border:1px solid var(--line);border-radius:4px;padding:1px 5px}
.err{
  margin-top:20px;padding:12px 16px;border-radius:8px;
  background:#fdecec;border:1px solid #f3c3c3;color:#8c2222;font-size:13.5px;
}
@media (max-width:640px){
  .item{padding:12px 14px}
  .mailbox .row{padding:10px 14px}
}
@media print{
  .tools,.mailbox .actions,.periodbar,button{display:none}
}
"""

# ---------------------------------------------------------------------------
# Selainlogiikka
# ---------------------------------------------------------------------------

JS = r"""
const DATA = JSON.parse(document.getElementById("data").textContent);
const LEVELS = ["vahva", "tarkista", "heikko", "kohina"];

let periodId = DATA.periods.length ? DATA.periods[0].id : "";
let levelFilter = "kaikki";
let query = "";
/* Valinnat jaksoittain: {"2026-09-15": ["EF-123", ...]} */
let picked = load();

function load(){
  try {
    return JSON.parse(localStorage.getItem("hankintaseuranta.picked") || "{}");
  } catch (e){ return {}; }
}
function save(){
  try {
    localStorage.setItem("hankintaseuranta.picked", JSON.stringify(picked));
  } catch (e){ /* yksityinen ikkuna tai esto, valinnat elavat vain istunnon */ }
}

function period(){
  return DATA.periods.find(p => p.id === periodId) || {id:"", label:"", notices:[]};
}
function chosen(){
  return new Set(picked[periodId] || []);
}
function toggle(key, on){
  const set = chosen();
  if (on) set.add(key); else set.delete(key);
  picked[periodId] = Array.from(set);
  save();
}

function esc(s){
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function fiDate(iso){
  if (!iso) return "";
  const d = new Date(iso);
  return d.getDate() + "." + (d.getMonth() + 1) + "." + d.getFullYear();
}
function fiDateTime(iso){
  if (!iso) return "";
  const d = new Date(iso);
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return fiDate(iso) + " klo " + hh + "." + mm;
}
function money(value, currency){
  if (!value) return "";
  const n = Math.round(Number(value));
  const s = String(n).replace(/\B(?=(\d{3})+(?!\d))/g, "\u00a0");
  return s + "\u00a0" + (currency === "EUR" || !currency ? "\u20ac" : currency);
}

/* Lyhyt kuvaus viestiin. Kaksi siivousta:

   1. Hilman kuvauskentta alkaa hyvin usein samalla otsikolla, joka on jo
      linkin tekstina. Ilman poistoa viestissa lukisi otsikko kahdesti.
   2. Hankintayksikot kirjoittavat kuvauskenttaan joskus koko
      tarjouspyynnon, joten teksti katkaistaan lauseen rajalta. */
function shortDesc(rec){
  let text = (rec.desc || "").replace(/\s+/g, " ").trim();
  if (!text) return "";
  const title = (rec.title || "").replace(/\s+/g, " ").trim();
  if (title && text.toLowerCase().startsWith(title.toLowerCase())){
    text = text.slice(title.length).replace(/^[\s:;.,\u2013\u2014-]+/, "");
  }
  if (!text) return "";
  if (text.length <= 240) return text;
  const cut = text.slice(0, 240);
  const stop = Math.max(cut.lastIndexOf(". "), cut.lastIndexOf("! "), cut.lastIndexOf("? "));
  return (stop > 120 ? cut.slice(0, stop + 1) : cut.trim() + "\u2026");
}

/* -------------------------------------------------------------------------
   Sahkopostin rakentaminen
   Kentat ovat ohjeen NB-kohdan mukaisessa jarjestyksessa: linkki,
   tarjouspyynnon tekija, maaraaika, otsikko tai lyhyt kuvaus, ja
   kokonaisarvo silloin kun se on ilmoitettu.
   ------------------------------------------------------------------------- */

function buildSubject(){
  return DATA.email.subject_prefix + " " + period().label;
}

function buildBody(){
  const p = period();
  const set = chosen();
  const recs = p.notices.filter(r => set.has(r.key));

  const html = [];
  const text = [];

  html.push("<p>" + esc(DATA.email.greeting) + "</p>");
  text.push(DATA.email.greeting);

  if (!recs.length){
    const line = DATA.email.empty_body.replace("{period}", p.label);
    html.push("<p>" + esc(line) + "</p>");
    text.push(line);
  } else {
    html.push("<p>" + esc(DATA.email.intro) + "</p>");
    text.push(DATA.email.intro);
    html.push("<ul>");

    for (const rec of recs){
      const bits = [];
      const lines = [];

      bits.push('<a href="' + esc(rec.url) + '">' + esc(rec.title) + "</a>");
      lines.push("- " + rec.title);
      lines.push("  " + rec.url);

      if (rec.org){
        bits.push('<span class="lbl">Tarjouspyynn\u00f6n tekij\u00e4:</span> ' + esc(rec.org));
        lines.push("  Tarjouspyynn\u00f6n tekij\u00e4: " + rec.org);
      }
      if (rec.deadline){
        bits.push('<span class="lbl">M\u00e4\u00e4r\u00e4aika:</span> ' + esc(fiDateTime(rec.deadline)));
        lines.push("  M\u00e4\u00e4r\u00e4aika: " + fiDateTime(rec.deadline));
      }
      const desc = shortDesc(rec);
      if (desc){
        bits.push('<span class="lbl">Hankinnan kohde:</span> ' + esc(desc));
        lines.push("  Hankinnan kohde: " + desc);
      }
      const value = money(rec.value, rec.currency);
      if (value){
        bits.push('<span class="lbl">Kokonaisarvo:</span> ' + esc(value));
        lines.push("  Kokonaisarvo: " + value);
      }
      /* Osa-aluehuomautus on olennainen: se kertoo lukijalle, ettei
         ilmoituksen otsikko yksin kerro, miksi rivi on mukana. */
      if (rec.lot_only && rec.lots.length){
        const names = rec.lots.map(l => l.title).filter(Boolean).slice(0, 3);
        const note = "Relevantti osa-alue: " + (names.length ? names.join("; ")
                     : rec.lots.length + " osa-aluetta");
        bits.push('<span class="lbl">Huom:</span> ' + esc(note));
        lines.push("  Huom: " + note);
      }

      html.push("<li>" + bits.join("<br>") + "</li>");
      text.push(lines.join("\n"));
    }
    html.push("</ul>");
  }

  html.push("<p>" + esc(DATA.email.signature).replace(/\n/g, "<br>") + "</p>");
  text.push(DATA.email.signature);

  return {html: html.join("\n"), text: text.join("\n\n"), count: recs.length};
}

/* -------------------------------------------------------------------------
   Lista
   ------------------------------------------------------------------------- */

function passes(rec){
  if (levelFilter === "valitut") return chosen().has(rec.key);
  if (levelFilter !== "kaikki" && rec.level !== levelFilter) return false;
  if (!query) return true;
  const hay = (rec.title + " " + rec.org + " " + rec.desc + " " + rec.cpv.join(" ")).toLowerCase();
  return hay.includes(query);
}

function itemHtml(rec, on){
  const tags = ['<span class="tag lvl-' + rec.level + '">' + esc(DATA.labels[rec.level]) + "</span>"];
  if (rec.reasons.length) tags.push('<span class="tag">' + esc(rec.reasons.join(" \u00b7 ")) + "</span>");
  if (rec.corrigendum) tags.push('<span class="tag warn">KORJAUS</span>');
  if (rec.framework) tags.push('<span class="tag">puitej\u00e4rjestely</span>');
  if (rec.dps) tags.push('<span class="tag">DPS</span>');
  if (rec.main_type === "NationalNotices") tags.push('<span class="tag">kansallinen</span>');
  if (rec.cpv.length) tags.push('<span class="tag">CPV ' + esc(rec.cpv.slice(0, 4).join(", ")) + "</span>");

  const facts = [];
  facts.push("Julkaistu <b>" + esc(fiDate(rec.published)) + "</b>");
  if (rec.deadline) facts.push("M\u00e4\u00e4r\u00e4aika <b>" + esc(fiDateTime(rec.deadline)) + "</b>");
  const value = money(rec.value, rec.currency);
  if (value) facts.push("Arvo <b>" + esc(value) + "</b>");
  if (rec.docs_url) facts.push('<a href="' + esc(rec.docs_url) + '">Tarjouspyynt\u00f6asiakirjat</a>');

  let lots = "";
  if (rec.lots.length){
    const rows = rec.lots.slice(0, 5).map(l =>
      "<div>" + esc(l.title || "(nimet\u00f6n osa-alue)") +
      (l.cpv.length ? ' <span class="tag">' + esc(l.cpv.join(", ")) + "</span>" : "") +
      "</div>").join("");
    lots = '<div class="lots"><b>Osuvat osa-alueet</b>' + rows + "</div>";
  }

  let desc = "";
  if (rec.desc){
    desc = '<details class="desc"><summary>Kuvaus</summary><p>' +
           esc(rec.desc.slice(0, 2500)) + "</p></details>";
  }

  return '<li class="item ' + rec.level + (on ? " on" : "") + '">' +
    '<input type="checkbox" data-key="' + esc(rec.key) + '"' + (on ? " checked" : "") +
      ' aria-label="Valitse viestiin">' +
    '<div class="body">' +
      "<h3><a href=\"" + esc(rec.url) + "\" target=\"_blank\" rel=\"noopener\">" +
        esc(rec.title) + "</a></h3>" +
      '<div class="org">' + esc(rec.org || "(hankintayksikk\u00f6\u00e4 ei ilmoitettu)") + "</div>" +
      '<div class="facts">' + facts.join("") + "</div>" +
      '<div class="tags">' + tags.join("") + "</div>" +
      lots + desc +
    "</div></li>";
}

/* Lista piirretaan uudelleen vain kun rajaus muuttuu. Ruksi ei piirra
   listaa, koska innerHTML:n korvaaminen veisi kohdistuksen pois juuri
   painetusta ruudusta ja sulkisi avatut kuvaukset. Silloin listaa ei voisi
   kayda lapi nappaimistolla sarkaimella ja valilyonnilla. */
function renderList(){
  const set = chosen();
  const rows = period().notices.filter(passes);
  document.getElementById("list").innerHTML = rows.length
    ? rows.map(r => itemHtml(r, set.has(r.key))).join("")
    : '<li class="empty">Ei ilmoituksia t\u00e4ll\u00e4 rajauksella.</li>';
  document.getElementById("shown").textContent = rows.length + " n\u00e4kyy";
  for (const c of document.querySelectorAll("[data-level]")){
    c.setAttribute("aria-pressed", String(c.dataset.level === levelFilter));
  }
}

function renderMail(){
  const body = buildBody();
  document.getElementById("preview").innerHTML = body.html;
  document.getElementById("subject-text").textContent = buildSubject();
  document.getElementById("count").textContent =
    body.count + " valittu / " + period().notices.length + " ilmoitusta jaksolla";
}

function render(){
  renderList();
  renderMail();
}

function say(msg){
  const el = document.getElementById("status");
  el.textContent = msg;
  clearTimeout(say._t);
  say._t = setTimeout(() => { el.textContent = ""; }, 3500);
}

/* Outlook sailyttaa linkit vain jos leikepoydalla on text/html. */
async function copyBody(){
  const body = buildBody();
  try {
    await navigator.clipboard.write([new ClipboardItem({
      "text/html": new Blob([body.html], {type: "text/html"}),
      "text/plain": new Blob([body.text], {type: "text/plain"}),
    })]);
    say("Viesti kopioitu. Liit\u00e4 Outlookiin (Ctrl+V).");
    return;
  } catch (e){ /* vanha selain tai ei lupaa, jatketaan alle */ }

  const sel = window.getSelection();
  const range = document.createRange();
  range.selectNodeContents(document.getElementById("preview"));
  sel.removeAllRanges();
  sel.addRange(range);
  const ok = document.execCommand("copy");
  sel.removeAllRanges();
  say(ok ? "Viesti kopioitu." : "Kopiointi ei onnistunut, valitse teksti k\u00e4sin.");
}

async function copyText(text, msg){
  try {
    await navigator.clipboard.writeText(text);
    say(msg);
  } catch (e){
    say("Kopiointi ei onnistunut, valitse teksti k\u00e4sin.");
  }
}

/* -------------------------------------------------------------------------
   Kytkennat
   ------------------------------------------------------------------------- */

document.getElementById("list").addEventListener("change", ev => {
  const box = ev.target.closest("input[type=checkbox]");
  if (!box) return;
  toggle(box.dataset.key, box.checked);
  box.closest(".item").classList.toggle("on", box.checked);
  renderMail();
  /* "Valitut"-rajauksessa rivi katoaa listalta, kun ruksi otetaan pois,
     joten silloin lista on piirrettava uudelleen. */
  if (levelFilter === "valitut") renderList();
});

document.getElementById("period").addEventListener("change", ev => {
  periodId = ev.target.value;
  render();
});

document.getElementById("q").addEventListener("input", ev => {
  query = ev.target.value.trim().toLowerCase();
  render();
});

for (const c of document.querySelectorAll("[data-level]")){
  c.addEventListener("click", () => { levelFilter = c.dataset.level; render(); });
}

document.getElementById("pick-strong").addEventListener("click", () => {
  const set = chosen();
  let added = 0;
  for (const rec of period().notices){
    if (rec.level === "vahva" && !set.has(rec.key)){ set.add(rec.key); added++; }
  }
  picked[periodId] = Array.from(set);
  save();
  render();
  /* Nollatulos sanotaan aaneen. Hiljainen "valittu" antaisi ymmartaa,
     etta jotain tapahtui, ja viikko voi hyvin olla ilman vahvoja osumia. */
  say(added
    ? added + " vahvaa osumaa valittu. Tarkista loput k\u00e4sin."
    : "T\u00e4ll\u00e4 jaksolla ei ole vahvoja osumia. K\u00e4y \u201dTarkista\u201d-rivit l\u00e4pi.");
});

document.getElementById("clear").addEventListener("click", () => {
  picked[periodId] = [];
  save();
  render();
});

document.getElementById("copy-body").addEventListener("click", copyBody);
document.getElementById("copy-subject").addEventListener("click",
  () => copyText(buildSubject(), "Otsikko kopioitu."));
document.getElementById("copy-to").addEventListener("click",
  () => copyText(DATA.email.to, "Vastaanottajat kopioitu."));
document.getElementById("copy-cc").addEventListener("click",
  () => copyText(DATA.email.cc, "Kopio-kentt\u00e4 kopioitu."));

render();
"""

# ---------------------------------------------------------------------------
# Apufunktiot
# ---------------------------------------------------------------------------

MONTHS_FI = [
    "tammikuuta", "helmikuuta", "maaliskuuta", "huhtikuuta", "toukokuuta",
    "kesäkuuta", "heinäkuuta", "elokuuta", "syyskuuta", "lokakuuta",
    "marraskuuta", "joulukuuta",
]


def fi_datetime(now: dt.datetime) -> str:
    return f"{now.day}. {MONTHS_FI[now.month - 1]} {now.year} klo {now:%H:%M}"


def e(text: str) -> str:
    return html.escape(str(text or ""), quote=True)


# ---------------------------------------------------------------------------
# Sivu
# ---------------------------------------------------------------------------


def build_payload(cfg: dict, state: dict) -> dict:
    """Kokoaa sivun JSON-kuorman tilasta.

    Jaksot ovat uusin ensin, jotta sivun avatessa on nakyvissa se, jota
    ollaan juuri lahettamassa.
    """
    keep = int(cfg["site"].get("keep_periods", 12))
    periods = sorted(state.get("periods", {}).values(), key=lambda p: p["id"], reverse=True)[:keep]
    return {
        "periods": periods,
        "email": cfg.get("email", {}),
        "labels": {
            "vahva": "Vahva osuma",
            "tarkista": "Tarkista",
            "heikko": "Heikko",
            "kohina": "Tuskin meille",
        },
    }


def render_index(cfg: dict, state: dict, now: dt.datetime, error: str = "") -> str:
    site = cfg["site"]
    email = cfg.get("email", {})
    payload = build_payload(cfg, state)

    options = "\n".join(
        f'<option value="{e(p["id"])}">{e(p["label"])}</option>' for p in payload["periods"]
    ) or '<option value="">(ei jaksoja viel\u00e4)</option>'

    chips = "".join(
        f'<button class="chip" data-level="{key}" aria-pressed="false">{e(label)}</button>'
        for key, label in [
            ("kaikki", "Kaikki"),
            ("vahva", "Vahvat"),
            ("tarkista", "Tarkista"),
            ("heikko", "Heikot"),
            ("kohina", "Kohina"),
            ("valitut", "Valitut"),
        ]
    )

    err_block = f'<div class="err">{e(error)}</div>' if error else ""

    search = cfg.get("search", {})
    cpv_text = ", ".join(str(p) for p in search.get("cpv_prefixes", []))

    return f"""<!doctype html>
<html lang="fi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>{e(site.get('title', 'Hankintailmoitusten seuranta'))}</title>
<style>{CSS}</style>
</head>
<body>

<header class="top">
  <div class="wrap">
    <h1>{e(site.get('title', 'Hankintailmoitusten seuranta'))}</h1>
    <p>{e(site.get('subtitle', ''))}</p>
  </div>
</header>

<div class="periodbar">
  <div class="wrap">
    <label for="period">Seurantajakso</label>
    <select id="period">{options}</select>
    <span class="meta" id="count"></span>
    <span class="grow"></span>
    <span class="meta">P\u00e4ivitetty {e(fi_datetime(now))}</span>
  </div>
</div>

<div class="wrap">
{err_block}

  <section class="card mailbox">
    <h2>S\u00e4hk\u00f6postiviesti</h2>

    <div class="row">
      <span class="k">Vastaanottaja</span>
      <span class="v">{e(email.get('to', ''))}</span>
      <button id="copy-to">Kopioi</button>
    </div>
    <div class="row">
      <span class="k">Kopio</span>
      <span class="v">{e(email.get('cc', ''))}</span>
      <button id="copy-cc">Kopioi</button>
    </div>
    <div class="row">
      <span class="k">Aihe</span>
      <span class="v" id="subject-text"></span>
      <button id="copy-subject">Kopioi</button>
    </div>

    <div id="preview"></div>

    <div class="actions">
      <button class="primary" id="copy-body">Kopioi viesti</button>
      <button id="pick-strong">Valitse vahvat</button>
      <button id="clear">Tyhjenn\u00e4 valinnat</button>
      <span id="status" role="status"></span>
    </div>
  </section>

  <section class="card">
    <h2>Ilmoitukset</h2>
    <div class="tools">
      {chips}
      <span class="sep"></span>
      <input type="search" id="q" placeholder="Hae otsikosta, hankintayksik\u00f6st\u00e4 tai kuvauksesta">
      <span class="meta" id="shown" style="color:var(--muted);font-size:13px"></span>
    </div>
    <ul class="list" id="list"></ul>
  </section>

  <footer>
    <p>
      Haku kattaa hankintailmoitukset ja kansalliset ilmoitukset. J\u00e4lki-ilmoitukset
      (jo ratkaistut kilpailutukset) on rajattu pois. CPV-etuliitteet: {e(cpv_text)}.
      Osa-alueiden CPV-koodit tarkistetaan erikseen, joten mukaan tulee my\u00f6s
      ilmoituksia, joiden otsikko ei viittaa juridiikkaan.
    </p>
    <p>
      V\u00e4ri on ehdotus, ei p\u00e4\u00e4t\u00f6s. Jokainen rivi on ruksattavissa tasosta riippumatta.
      Hakusanoja, CPV-koodeja ja viestin tekstej\u00e4 muutetaan tiedostossa
      <code>sources.yaml</code>.
    </p>
    <p>L\u00e4hde: Hilma, hankintailmoitukset.fi (avoin AVP-hakurajapinta).</p>
  </footer>
</div>

<script type="application/json" id="data">{json.dumps(payload, ensure_ascii=False)}</script>
<script>{JS}</script>
</body>
</html>
"""


def render_all(cfg: dict, state: dict, now: dt.datetime, docs: pathlib.Path,
               error: str = "") -> None:
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "index.html").write_text(render_index(cfg, state, now, error), encoding="utf-8")
    # GitHub Pages ohittaa Jekyllin, jolloin alaviivalla alkavat tiedostot
    # eivat katoa ja julkaisu on nopeampi.
    (docs / ".nojekyll").write_text("", encoding="utf-8")
