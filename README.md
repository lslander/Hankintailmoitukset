# Hankintailmoitusten seuranta

Automatisoi viikoittaisen hankintailmoitusten läpikäynnin. Ajo hakee Hilman
rajapinnasta kaikki uudet hankintailmoitukset, suodattaa ne CPV-koodeilla,
ehdottaa relevanssia ja julkaisee GitHub Pages -sivun. Sivulla ruksaat
haluamasi ilmoitukset ja kopioit valmiin sähköpostin Outlookiin.

Seurantajakso on aina tiistai 00.00 alkaen maanantai 23.59 asti.

---

## 1. Mitä tämä tekee

Manuaalisessa työssä menee noin tunti viikossa: Hilman haku, kuuden CPV-koodin
läpikäynti, ilmoitusten avaaminen yksi kerrallaan ja sähköpostin kirjoittaminen
käsin. Tämä putki hoitaa haun ja koostamisen. Sinä teet edelleen valinnan.

Putki tekee kolme asiaa, joita käsin tehty Hilma-haku ei tee:

**Osa-alueiden CPV-täsmäys.** Hilman käyttöliittymän haku katsoo ilmoituksen
pääkoodia. Monilohkoisessa hankinnassa vain yksi osa-alue voi olla
oikeudellista osaamista vaativa, eikä se näy pääotsikossa. Ajo lukee jokaisen
osa-alueen koodit erikseen. Esimerkiksi ilmoitus "IT-tukipalvelut" pääkoodilla
72000000 nousee esiin, jos sen osa-alue 2 on "Sopimusoikeudellinen neuvonta"
koodilla 79110000. Tämä on koko putken tärkein yksittäinen lisä.

**Vesiraja.** Ajo ei kysy nimellistä viikkoa vaan hakee kaiken, mitä on
julkaistu edellisen ajon katkaisuhetken jälkeen. Maanantaiaamuna ajettaessa
maanantai-iltapäivän ilmoitukset eivät ehdi mukaan, mutta ne eivät myöskään
katoa. Seuraava ajo poimii ne. Yhtään ilmoitusta ei jää väliin eikä mikään
raportoidu kahdesti, vaikka ajo myöhästyisi viikolla.

**Relevanssiehdotus.** Rivi väritetään, jotta tiedät mistä aloittaa. Koodi ei
päätä puolestasi, ja jokainen rivi on ruksattavissa tasosta riippumatta. Tasot
ovat kuvattu kohdassa 6.

---

## 2. Käyttöönotto

### 2.1 Hae API-avain

Avain on ilmainen ja sen saa muutamassa minuutissa.

1. Mene osoitteeseen https://hns-hilma-prod-apim.developer.azure-api.net
2. Sign up, vahvista sähköposti
3. Products, valitse **avp-read**, Subscribe
4. Profile-sivulta näet avaimen (Primary key). Kopioi se.

Avain on Azure API Managementin tilausavain. Se lähetetään otsakkeessa
`Ocp-Apim-Subscription-Key`.

### 2.2 Luo repo ja vie tiedostot

Luo GitHubiin uusi repo, esimerkiksi `hankintaseuranta`. Vie siihen tämän
kansion sisältö. Repo voi olla yksityinen, mutta GitHub Pages toimii
yksityisessä repossa vain maksullisissa tileissä. Jos sivu ei aukea, tee
reposta julkinen. Sivulla ei näy mitään salaista, koska kaikki hankinta-
ilmoitukset ovat jo julkisia.

### 2.3 Tallenna avain salaisuudeksi

Repon asetuksissa: Settings, Secrets and variables, Actions, New repository
secret.

- Name: `HILMA_API_KEY`
- Secret: avain kohdasta 2.1

Älä koskaan kirjoita avainta `sources.yaml`-tiedostoon. Se päätyisi
versionhallintaan.

### 2.4 Ota GitHub Pages käyttöön

Settings, Pages:

- Source: Deploy from a branch
- Branch: `main`, kansio `/docs`

Tallenna. Osoitteeksi tulee `https://KAYTTAJATUNNUS.github.io/hankintaseuranta/`.
Päivitä sama osoite `sources.yaml`-tiedoston kohtaan `site.base_url`.

### 2.5 Tila on valmiiksi oikeassa kohdassa

Repossa oleva `state.json` on alustettu kuluvan jakson alkuun. Sinun ei
tarvitse tehdä sille mitään. Se sisältää vesirajan ja jo raportoidut
ilmoitukset, ja se commitoidaan takaisin repoon jokaisen ajon jälkeen.

Jos joskus haluat aloittaa alusta, tyhjennä se näin:

```bash
echo '{"last_run": null, "watermark": null, "periods": {}, "seen": {}}' > state.json
```

Tyhjällä tilalla ajo hakee kuluvan jakson alusta eteenpäin, ei kauempaa.
Se on turvallinen oletus, koska edellinen viikko on jo lähetetty käsin.

### 2.6 Testaa ajo

Actions-välilehdellä valitse "Hankintailmoitusten seuranta", Run workflow.
Voit antaa `since`-kentässä päivämäärän muodossa `2026-09-15`, jolloin ajo
hakee siitä eteenpäin. Tyhjänä ajo käyttää vesirajaa.

Ajo kestää noin puoli minuuttia. Sen jälkeen sivu on osoitteessa, jonka annoit
kohdassa 2.4.

---

## 3. Viikkorutiini

Ajo käynnistyy automaattisesti maanantaisin klo 07.30 Suomen aikaa
(kesäaika, talvella 06.30). Maanantaiaamuna teet näin:

1. Avaa sivu.
2. Paina **Valitse vahvat**. Tämä ruksaa rivit, joissa CPV on oikeudellisten
   palvelujen haarassa tai otsikossa on vahva avainsana.
3. Käy läpi **Tarkista**-rivit. Avaa epäselvät Hilmassa. Muista matala kynnys:
   parempi laittaa muutama turha mukaan kuin antaa ison voiton mennä ohi.
4. Vilkaise vielä **Heikko**-rivit otsikkotasolla.
5. Paina **Kopioi viesti**. Avaa Outlook, liitä. Linkit ja muotoilu säilyvät,
   koska kopiointi käyttää HTML-leikepöytää.
6. Otsikko ja vastaanottajat näkyvät sivulla omina kenttinään, kopioi ne
   erikseen.

Ruksit tallentuvat selaimen muistiin, joten voit jättää työn kesken ja palata
siihen. Ruksit ovat selainkohtaisia.

Jos ilmoituksia ei tule yhtään, sivu näyttää tyhjän jakson viestin ja
sähköpostimalli vaihtuu muotoon "Ajalta x ei löytynyt toimistoamme
kiinnostavia ilmoituksia."

---

## 4. Tiedostot

| Tiedosto | Mitä tekee |
|---|---|
| `sources.yaml` | Kaikki säädettävä. Tätä muokkaat, et koodia. |
| `hilma.py` | Rajapintakutsut, sivutus, CPV-täsmäys, jakson laskenta |
| `scoring.py` | Relevanssiehdotus, tasot vahva, tarkista, heikko, kohina |
| `render.py` | HTML, CSS ja sivun JavaScript, sähköpostimallin rakennus |
| `main.py` | Ohjaus, tilanhallinta, vesiraja |
| `state.json` | Tila: vesiraja, jaksot, jo nähdyt ilmoitukset |
| `docs/index.html` | Julkaistava sivu, syntyy ajossa |
| `.github/workflows/seuranta.yml` | Ajastus ja julkaisu |

`state.json` on ainoa tiedosto, jota ajo muokkaa `docs`-kansion lisäksi.
Se commitoidaan takaisin repoon, ja juuri siksi seuranta muistaa, mitä on jo
raportoitu.

---

## 5. Konfiguraatio

Kaikki säädöt ovat `sources.yaml`-tiedostossa. Muutokset tulevat voimaan
seuraavassa ajossa.

### CPV-koodit

```yaml
search:
  cpv_prefixes:
    - "79000000"  # Liiketoimintapalvelut (vain tämä koodi)
    - "791"       # Oikeudelliset palvelut
    - "794"       # Yrityskonsultointi ja johdon konsultointi
    - "804"       # Aikuiskoulutus ja muut koulutuspalvelut
    - "79632"     # Henkilöstökoulutus
    - "73"        # Tutkimus- ja kehityspalvelut
```

Lista vastaa alkuperäisen ohjeen kuutta koodia lapsikoodeineen.

Koodit täsmätään etuliitteenä. Hilman indeksissä on aina varsinainen
8-numeroinen koodi, eikä emokoodi tuo lapsikoodeja mukanaan. Koska koodi on
aina 8 numeroa, täysimittainen etuliite `"79000000"` täsmää vain tuohon yhteen
koodiin, kun taas `"791"` kattaa koko ryhmän eli 79110000, 79111000, 79130000
ja niin edelleen.

| Ohjeen koodi | Etuliite | Kattaa |
|---|---|---|
| 79000000 | `79000000` | vain tämän koodin |
| 79100000 | `791` | 79110000, 79111000, 79130000, 79140000 ... |
| 79400000 | `794` | 79410000, 79411000, 79418000 ... |
| 80400000 | `804` | 80411100, 80412000, 80420000 ... |
| 79632000 | `79632` | 79632000 alakoodeineen |
| 73000000 | `73` | 73100000, 73210000, 73220000, 73300000 ... |

Älä kirjoita tähän pelkkää `"79"`. Se vetäisi mukaan koko 79-haaran eli myös
painopalvelut, käännökset, rekrytoinnin ja tilintarkastuksen. Testiajossa
1.9.-22.9.2026 pelkkä `"79"` tuotti 69 ilmoitusta ja nykyinen lista 25.
Poisputoavista 44:stä yksikään ei ollut juridisesti vahva. Lähimmäksi tuli
79634000 eli uudelleensijoituspalvelut, joka näkyi otsikolla "Työnantajan
lakisääteinen muutosturvavalmennus". Jos työoikeuspuoli haluaa sen mukaan,
lisää listaan rivi `- "79634"`.

### Ilmoitustyypit

```yaml
  main_types:
    - ContractNotices
    - NationalNotices
```

`ContractAwardNotices` eli jälki-ilmoitukset on jätetty tarkoituksella pois.
Ne kertovat jo ratkenneista kilpailutuksista, joissa tarjousaika on umpeutunut.

### Avainsanat

`strong_keywords` nostaa rivin vahvaksi, jos sana on ilmoituksen tai
osa-alueen **otsikossa**. `weak_keywords` tuottaa aina tason tarkista.
`noise_keywords` harmaannuttaa rivin, mutta rivi ei katoa.

Avainsanat kirjoitetaan pieninä ja mieluiten katkaistuna sanan vartaloon, jotta
taivutusmuodot osuvat. `oikeudelli` osuu muotoihin oikeudellinen, oikeudellisia
ja oikeudellisten. Aksentit eivät haittaa, koska teksti normalisoidaan
molemmista päistä.

### Sähköpostimalli

```yaml
email:
  subject_prefix: "Hankintailmot"
  to: "HKI.MARKETING@twobirds.com; Maria Carlsson"
  cc: "HKI.STUDENT@twobirds.com; Maria Carlsson"
  greeting: "Hei!"
  intro: "Ohessa uusia mahdollisesti toimistolle relevantteja hankintailmoituksia:"
  empty_body: "Ajalta {period} ei löytynyt toimistoamme kiinnostavia ilmoituksia."
  signature: "Yst. terv.\nRaul"
```

`{period}` korvautuu muodolla `15.9.2026 - 21.9.2026`. Otsikoksi tulee
`Hankintailmot 15.9.2026 - 21.9.2026`.

---

## 6. Miten relevanssi päätellään

| Taso | Ehto | Väri |
|---|---|---|
| Vahva osuma | CPV alkaa 791 tai vahva avainsana ilmoituksen tai osa-alueen otsikossa | vihreä |
| Tarkista | Vahva avainsana vain kuvauksessa, tai heikko avainsana, tai osa-aluetäsmäys | keltainen |
| Heikko | CPV-suodatin läpäisty, muuta ei | harmaa |
| Tuskin meille | Kohinasana otsikossa | vaalean harmaa |

Otsikon ja kuvauksen ero on tarkoituksellinen. Lähes jokaisessa ilmoituksessa
lukee "hankintalain (1397/2016) mukaisesti", ja vaatimuksissa mainitaan
tietosuoja ja GDPR. Jos kuvausosuma riittäisi vahvaksi, puolet
hoitajakutsujärjestelmistä olisi vihreitä. Testiajossa kuvausosumien
salliminen tuotti 19 vahvaa osumaa, joista suurin osa oli vääriä. Otsikkoon
rajaaminen pudotti luvun viiteen, ja ne olivat aidosti juridisia.

Kuvausosuma ei kuitenkaan katoa. Se näkyy rivillä merkinnällä
"kuvauksessa: tietosuoja", jolloin näet miksi rivi on listalla.

Kohinasana ei koskaan kumoa vahvaa osumaa. Vartiointipalvelun hankinnassa voi
olla oikeudellinen osa-alue, ja tulkkauspalveluita hankkivat tuomioistuimet.

---

## 7. Jakson laskenta

Jakso päättyy seuraavaan maanantaihin, tämä päivä mukaan lukien. Maanantaina
ajettaessa jakso on siis kuluva tiistai-maanantai. Keskiviikkona käsin
ajettaessa jakso on seuraava tiistai-maanantai, eli se jakso, jota ollaan
parhaillaan keräämässä.

| Ajopäivä | Jakso |
|---|---|
| ma 21.9. | 15.9.2026 - 21.9.2026 |
| ti 22.9. | 22.9.2026 - 28.9.2026 |
| ke 23.9. | 22.9.2026 - 28.9.2026 |
| su 27.9. | 22.9.2026 - 28.9.2026 |
| ma 28.9. | 22.9.2026 - 28.9.2026 |

Päivää haetaan eteenpäin eikä taaksepäin. Jos sitä haettaisiin taaksepäin,
keskiviikon ajo kirjaisi löydöt jo lähetettyyn viikkoon, jolloin ne eivät
päätyisi yhteenkään viestiin.

Ilmoitus kuuluu siihen jaksoon, jolla se **löytyi**, ei siihen jolla se
julkaistiin. Juuri tämä tekee vesirajasta turvallisen.

Jaksoja säilytetään sivulla `site.keep_periods` kappaletta, oletuksena 12
viikkoa. Vanhat jaksot löytyvät sivun arkistovalikosta.

---

## 8. Paikallinen ajo

Jos haluat kokeilla ennen kuin viet repon GitHubiin:

```bash
pip install -r requirements.txt
export HILMA_API_KEY="avaimesi"
python3 main.py --dry-run          # hakee ja tulostaa, ei kirjoita tiedostoja
python3 main.py                    # normaali ajo
python3 main.py --since 2026-09-01 # pakota vesiraja
```

Normaali ajo kirjoittaa sivun tiedostoon `docs/index.html`. Avaa se suoraan
selaimessa. `--dry-run` ei kirjoita `state.json`-tilaa eikä sivua, joten sillä
voi kokeilla CPV-muutoksia rikkomatta seurannan muistia.

---

## 9. Vianetsintä

**Sivulla on punainen palkki "Haku epäonnistui".** Ajo ei saanut yhteyttä
Hilmaan. Sivu piirretään silti vanhoilla tiedoilla, jotta hiljainen maanantai
ei mene sekaisin oikeasti rauhallisen viikon kanssa. Tarkista ensin, onko
avain vanhentunut tai kiintiö täynnä. Aja sitten workflow uudelleen käsin.

**Ajo onnistuu, mutta ilmoituksia ei tule.** Tarkista Actions-lokista rivi
"Rajapinnasta N ilmoitusta, CPV-suodattimen läpäisi M". Jos N on nolla,
vesiraja on liian tuore. Aja `since`-kentällä. Jos N on iso ja M on nolla,
CPV-etuliitteet ovat liian kapeat.

**Sähköposti liittyy Outlookiin ilman linkkejä.** Selain ei tukenut
HTML-leikepöytää ja käytti varamenetelmää. Kokeile Chromea tai Edgeä. Firefox
vaatii asetuksen `dom.events.asyncClipboard.clipboardItem`.

**Ruksit katosivat.** Ne ovat selaimen paikallisessa muistissa ja
selainkohtaisia. Yksityinen ikkuna tai selaindatan tyhjennys nollaa ne.

**Workflow kaatuu commit-vaiheeseen.** Tarkista, että repon asetuksissa
Settings, Actions, General, Workflow permissions on "Read and write
permissions".

---

## 10. Mitä tämä ei tee

Putki ei lähetä sähköpostia puolestasi eikä päätä, mikä ilmoitus on
relevantti. Molemmat on jätetty käsin tehtäväksi tarkoituksella. Lähetys
vaatii toimiston sähköpostijärjestelmän oikeudet, ja valinta vaatii
harkintaa, jota avainsanalista ei korvaa.

Putki ei myöskään seuraa jälki-ilmoituksia, pienhankintoja kynnysarvon alta
eikä muita ilmoituskanavia kuin Hilmaa.
