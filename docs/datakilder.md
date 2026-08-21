# Datakilder for norske bedriftsdata

Kartlagt 2026-08-21. Fakta merket *verifisert* er testet mot levende endepunkter
(se skriptene i `explore/`); resten er fra offisiell dokumentasjon.

## Oversikt og anbefaling

| Behov | Kilde | Tilgang | Vurdering |
|---|---|---|---|
| Grunndata om alle bedrifter | Enhetsregisteret (Brønnøysund) | Åpent API + nattlige bulk-filer, NLOD-lisens | ✅ Bruk som ryggrad |
| Regnskapstall (siste år) | Regnskapsregisteret åpne API | Åpent API, kun siste årgang | ✅ Høst årlig for å bygge historikk |
| Årsrapporter (PDF, historikk) | Regnskapsregisteret kopi-API | Åpent API, gratis, ca. 9–15 årganger | ✅ Verifisert – krever OCR for tall |
| Roller (styre/leder/revisor) | Enhetsregisteret roller-API | Åpent API + totalbestand + endringsstrøm | ✅ Kun nåsituasjon – start snapshotting |
| Konkurser og hendelser | Enhetsregisteret-flagg + oppdateringer | Åpent | ✅ Dekker det meste gratis |
| Kunngjøringer (full detalj) | Brønnøysund kunngjøringer | Kun HTML-søk eller betalt XML/SFTP-abonnement | ⚠️ Ingen åpen JSON-API |
| Aksjekurser | yfinance (utforskning) / EODHD el.l. (produksjon) | Gratis uoffisielt / ~€20 per mnd | ⚠️ Se lisensmerknad |
| Børsmeldinger | NewsWeb (Euronext Oslo) | Åpent JSON-API, historikk til 2010 | ⚠️ Vilkår begrenser lagring/deling |
| Eierskap/aksjonærer | Skatteetatens aksjonærregister | Årlig datasett på forespørsel | ✅ Anbefalt tillegg |
| Flerårig regnskapshistorikk samlet, kredittdata | Proff Premium API (Enento) | Kommersielt, kontakt salg | 💰 Kun hvis OCR/oppbygging ikke holder |

**Hovedkonklusjon:** Brønnøysundregistrene dekker grunndata, regnskap og roller
gratis med god kvalitet. Proff.no kan ikke skrapes (se nederst), men er heller
ikke nødvendig: Proff henter selv dataene fra Brønnøysund og Skatteetaten.

---

## 1. Enhetsregisteret (Brønnøysundregistrene)

- **Base-URL:** `https://data.brreg.no/enhetsregisteret/api`
- **Auth:** ingen. **Lisens:** NLOD. **Rate limits:** ingen dokumentert; etiketten er å bruke bulk-filene til masseuttrekk.
- **Dokumentasjon:** <https://data.brreg.no/enhetsregisteret/api/dokumentasjon/no/index.html>

### Søk og oppslag (verifisert)

- `GET /enheter?navn=...`, filtre: `organisasjonsform` (kommaliste), `fraAntallAnsatte`/`tilAntallAnsatte`, `naeringskode`, `kommunenummer`, datointervaller, boolske flagg (`konkurs`, `registrertIMvaregisteret`, ...).
- Batch-oppslag: `?organisasjonsnummer=` med **inntil 2000 orgnr per kall**.
- Paginering: `page`/`size`, men **maks 10 000 treff per søk** – bruk smalere filtre eller bulk.
- `GET /enheter/{orgnr}` gir bl.a. `sisteInnsendteAarsregnskap` (år), `erIKonsern`, sektorkode, næringskoder 1–3.

### Bulk (dokumentert)

- `GET /enheter/lastned` (gzip JSON), `/lastned/csv`, `/lastned/regneark` – bygges hver natt.
- Tilsvarende for `/underenheter` (arbeidssteder – gir ansatte per lokasjon).

### Endringsstrøm (verifisert)

- `GET /oppdateringer/enheter?dato=...` eller `?oppdateringsid=` – monotont stigende id egnet som synk-markør. Finnes også for `underenheter` og `roller`.
- Typisk volum: ~5 000 endringer per døgn.

## 2. Regnskapsregisteret

### Åpent regnskaps-API (verifisert)

- `GET https://data.brreg.no/regnskapsregisteret/regnskap/{orgnr}` – ingen auth.
- **Gir kun siste innsendte årsregnskap.** Parametrene `år`/`regnskapstype` finnes i spesifikasjonen, men historiske år returneres ikke (testet).
- **Kun selskapsregnskap:** `regnskapstype=KONSERN` ignoreres (testet på Equinor/Telenor) – konserntall må hentes fra PDF-kopiene eller kommersielle kilder.
- Innhold: nøkkeltall fra resultat og balanse (sum driftsinntekter, driftsresultat, årsresultat, eiendeler, egenkapital, gjeld m/underinndeling), regnskapsprinsipper, revisjonsstatus, periode, valuta. **Ikke** notenivå.
- NB: API-et har skrivefeil i egne feltnavn som må håndteres som de er: `regnkapsprinsipper`, `sumInnskuttEgenkaptial`.
- **Finansforetak (banker, forsikring) gir vedvarende HTTP 500** i stedet for data
  (verifisert på bl.a. DNB Bank, Gjensidige, alle 19 feilende orgnr i utvalget var
  finansforetak, næringskode 64/65). De leverer etter egne oppstillingsplaner som
  API-et ikke håndterer. Pipeline må tåle og logge dette.
- **Aggregatfeltene for gjeld kan være materielt ufullstendige** for store/komplekse
  regnskap: hos ~1 % av utvalget avviker balanseidentiteten med > 0,1 % av
  balansesummen (Telenor ASA: 73 mrd. kr manglet på gjeldssiden). Eiendelssiden
  fremstår pålitelig – bruk `sumEiendeler` som balansesum og flagg avvik.
- Ingen bulk-nedlasting av strukturerte tall. Skal man ha historikk i strukturert form må man enten høste årlig fremover, OCR-e PDF-ene (under), eller kjøpe (f.eks. Proff Premium).

### Gratis PDF-kopier av årsregnskap (verifisert) ⭐

- `GET .../regnskap/aarsregnskap/kopi/{orgnr}/aar` → liste over tilgjengelige årganger (JSON).
- `GET .../regnskap/aarsregnskap/kopi/{orgnr}/{aar}` → komplett innsendt årsregnskap som PDF, inkl. noter/årsberetning slik de ble levert.
- Historikk ca. 9–15 år (Equinor: 2011–2025). Gratis, ingen auth.
- Eldre dokumenter er skannede bilder → tall må ev. hentes ut med OCR.
- Tekniske finurligheter (verifisert): send `Accept: */*` (endepunktet svarer 406
  på `application/pdf`), og bruk lang timeout – store rapporter genereres på
  forespørsel og kan ta over ett minutt (Equinor 2015: 7,5 MB).
- Dette dekker «årsrapporter»-behovet for alle regnskapspliktige, ikke bare børsnoterte.

## 3. Roller (styre, daglig leder, revisor)

- `GET /enhetsregisteret/api/enheter/{orgnr}/roller` – åpent (verifisert). Personer identifiseres med navn + fødselsdato (ikke fødselsnummer).
- Bulk: `GET /api/roller/totalbestand`. Endringsstrøm: `/api/oppdateringer/roller`.
- **Ingen historikk** i åpent API – databasen bør snapshotte fra dag én.
- Rollehistorikk og fødselsnummer krever Maskinporten-autoriserte varianter (offentlige/finansaktører).

## 4. Kunngjøringer og konkurser

- **Ingen åpen JSON-API.** Alternativer:
  - HTML-søk: <https://w2.brreg.no/kunngjoring/> (fusjoner, kapitalendringer, konkursåpninger, sletting m.m.).
  - Betalt XML-abonnement levert som daglige zip via SFTP, priset per kunngjøringstype.
  - Konkursregisterets JSON-API er begrenset til aktører med hjemmel til fødselsnummer.
- **Gratis dekning i praksis:** flaggene `konkurs`, `underKonkursbehandling`, `underTvangsavviklingEllerTvangsopplosning` i Enhetsregisteret + endringsstrømmen fanger konkursstatus på foretaksnivå.

## 5. Andre Brønnøysund-registre (kort)

- **Fullmakt/signatur:** åpen oppslagstjeneste (hvem kan signere/prokura).
- **Reelle rettighetshavere (UBO):** kun for aktører med hjemmel (AML, myndigheter, media, akademia) – søknad kreves.
- **Løsøreregisteret (pant/utlegg):** kun Maskinporten (kredittopplysningsforetak).
- **Registeret for offentlig støtte:** offentlig søk + API (Swagger: `stottetiltak-registerinfo-api.app.brreg.no/swagger-ui/`) – støttetildelinger ≥ 100 000 € med mottakers orgnr og beløp.
- **Kompensasjonsordningen (covid-støtte 2020–22):** åpen innsynsløsning.

## 6. Proff.no – konklusjon: ikke en kilde

Verifisert 2026-08-21:

- Vilkårene (sidefot på alle sider + rettighetsside) forbyr eksplisitt «regelmessig, systematisk eller kontinuerlig innhenting» uten skriftlig samtykke. Databasevernet i åndsverkloven § 24 gir dette rettslig tyngde.
- `robots.txt` blokkerer `/api/*`, paginert søk, scraping-rammeverk (Scrapy) og AI-crawlere; scripted klienter får tom `202`-respons (verifisert i `explore/06_proff_robots.py`).
- Proffs egne kilder (oppgitt på proff.no/info/kilder): Brønnøysundregistrene (daglig), Skatteetatens aksjonærregister (årlig), aksjeeierbøker, Patentstyret, eiendomsdata m.m. Kredittdata kommer fra eier-konsernet Enento.
- Det Proff har som åpne kilder mangler: ferdig flerårig regnskapshistorikk (~28 år for store selskaper), aksjonærlister på tvers av år, kredittrating/betalingsanmerkninger. Lovlig vei til dette: **Proff Premium API** (kommersielt, via forvalt.no) eller bygge historikk selv (PDF-OCR + årlig høsting).
- Alternativ med offisiell API: 1881.no (kommersiell, «Næringsdata»-produkt).

## 7. Skatteetatens aksjonærregister (anbefalt tillegg)

Årlig datasett over aksjonærer i norske AS/ASA (Proffs egen eierskapskilde).
Utleveres som åpne data på forespørsel til Skatteetaten; brukes mye av
journalister. Gir eierskapsanalyse som Brønnøysund ikke dekker. (Prosess for
bestilling: se skatteetaten.no, «aksjonærregisteret – innsyn».)

## 8. Aksjekurser (Oslo Børs / Euronext Oslo)

### Instrumentliste (verifisert)

Euronext publiserer listen over noterte aksjer åpent, inkl. underliggende
JSON-endepunkt (ingen auth):

```
https://live.euronext.com/en/product_directory/data/stocks-all-places?mics=XOSL,XOAS,MERK
```

295 instrumenter (aug. 2026) med navn, ISIN, ticker, marked (MIC: `XOSL` =
Oslo Børs, `XOAS` = Euronext Expand, `MERK` = Euronext Growth) og siste kurs.
Kan polles daglig som EOD-snapshot; merk at Euronexts vilkår begrenser
videredistribusjon.

### Historiske kurser

- **yfinance** (verifisert i `explore/05_aksjekurs.py`): 2 års daglige kurser for
  15 `.OL`-tickere, 99,8 % dekning (kun helligdager «mangler»). Uoffisielt API;
  Yahoos vilkår tillater kun personlig bruk – greit i utforskning, ikke som
  lisensiert ryggrad i produksjon.
- **Euronext** selger historikk kommersielt; gratis bulk-nedlasting finnes ikke.
- **EODHD** (~€20/mnd) dekker Oslo tilbake til ~2000 – beste rimelige betalte
  alternativ. Marketstack har rapporterte kvalitetsproblemer for Oslo etter
  plattformbyttet; Alpha Vantage/Nasdaq Data Link dekker ikke Oslo gratis.

### Kobling ticker ↔ ISIN ↔ orgnr

Navnesøk i Enhetsregisteret traff eksakt for 13 av 15 testselskaper, men ga
**feilaktige** treff for utenlandskregistrerte utstedere (Subsea 7 S.A.,
Frontline plc) – navnematching alene er ikke trygt. Robust, gratis kjede:

1. Euronext-listen: navn ↔ ISIN ↔ ticker (verifisert)
2. ESMA FIRDS (gratis referansefiler): ISIN → utsteders LEI
3. GLEIF (gratis, CC0): LEI → norsk orgnr (feltet RegistrationAuthority
   RA000472 = Enhetsregisteret)

Nyttig ekstra: Finanstilsynets shortregister-API
(`ssr.finanstilsynet.no/api/v2/instruments`, åpent JSON) gir ISIN ↔
utstedernavn for Oslo-noterte.

## 9. Børsmeldinger og årsrapporter for noterte selskaper (NewsWeb)

NewsWeb (<https://newsweb.oslobors.no>) er den offisielle meldingsportalen
(OAM) for Oslo Børs/Expand/Growth. Frontenden bruker et åpent JSON-API uten
auth (verifisert):

| Endepunkt (base `https://api3.oslo.oslobors.no`) | Innhold |
|---|---|
| `GET /v1/newsreader/list?fromDate=&toDate=&issuer=&category=` | meldingsliste (~155/dag) |
| `GET /v1/newsreader/message?messageId=` | full melding: tittel, brødtekst, kategori, utsteder, vedleggsliste |
| `GET /v1/newsreader/attachment?messageId=&attachmentId=` | vedlegg (PDF – bl.a. årsrapporter) |
| `POST /v1/newsreader/issuers` | utstederliste (uten ISIN/orgnr) |

Historikk verifisert tilbake til minst 2010.

**Viktig vilkårsbegrensning:** databasen er vernet etter åndsverkloven, og
disclaimer-siden sier innholdet ikke kan kopieres/gjøres tilgjengelig utover
privat bruk uten skriftlig samtykke fra Oslo Børs. Metadata (titler, lenker)
er lav risiko; masseinnhøsting av meldingstekster/vedlegg til en delt database
krever avklaring med Oslo Børs først.

## 10. Flere aktuelle åpne kilder (forslag)

| Kilde | Innhold | Tilgang |
|---|---|---|
| SSB PxWeb-API + Klass | Offisiell statistikk (bransjetall til benchmarking), kodeverk for NACE/kommuner | Åpent, NLOD/CC-BY |
| Norges Bank API | Valutakurser (viktig: en del regnskap føres i USD/EUR), renter | Åpent SDMX/REST (krever ordentlig User-Agent) |
| Doffin API v2 | Offentlige anskaffelser med oppdragsgivers orgnr, oppdateres hvert 30. min | Åpent, NLOD 2.0 |
| Støtteregisteret | Offentlig støtte ≥ 100 000 € per mottaker-orgnr | Åpent API (BRREG) |
| Patentstyret | Patenter, varemerker, design per søker | Gratis API-nøkkel |
| NAV stillingsfeed | Alle utlyste stillinger siden ~2019 med arbeidsgivers orgnr | Åpen feed (token) |
| NVE | Konsesjoner og kraftdata (energiselskaper) | Gratis API (registrering) |
| Medietilsynet | Eierskap og støtte for mediebedrifter | Nettside/database |

**GDPR-merknad:** aksjonærregisteret og rolledata inneholder personopplysninger
(navn, fødselsdato/-år). Ved lagring blir man behandlingsansvarlig – lagre
sikkert, ikke publiser persondata, slett ved behov.
