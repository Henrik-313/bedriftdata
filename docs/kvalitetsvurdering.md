# Kvalitetsvurdering av datakildene

Målt 2026-08-21 med skriptene i `explore/`. Utvalget er stratifisert:
150 AS per ansattgruppe (0, 1–9, 10–49, 50–249, 250+), alle 215 ASA,
og 150 hver av ENK, NUF og SA — totalt 1 415 enheter. Merk at utvalget per
gruppe er de første treffene i API-ets sortering (lav orgnr-ende), ikke
tilfeldig trukket; tallene bør leses som gode anslag, ikke presise estimater.

## Bestand (hele registeret)

| Organisasjonsform | Antall registrert |
|---|---:|
| ENK (enkeltpersonforetak) | 460 999 |
| AS | 431 344 |
| FLI (forening) | 128 651 |
| NUF (norskreg. utenlandsk foretak) | 25 818 |
| DA / ANS / SAM / SA / STI | 5 000–11 000 hver |
| ASA | 215 |

AS etter ansatte: 284 695 uten registrerte ansatte, 110 523 med 1–9,
30 399 med 10–49, 4 817 med 50–249, 910 med 250+.

## Enhetsregisteret: feltdekning (n = 1 415)

| Felt | Andel utfylt |
|---|---:|
| orgnr, navn, orgform, registreringsdato | 100 % |
| næringskode | 99,9 % |
| institusjonell sektorkode | 92,1 % |
| kommunenummer (forretningsadresse) | 91,7 % |
| stiftelsesdato | 78,8 % |
| siste innsendte årsregnskap (år) | 72,5 % |
| antall ansatte | 44,5 % |
| hjemmeside | 26,3 % |

Ansattetall finnes i praksis bare der NAV/Aa-registeret har meldt inn tall:
100 % i AS-gruppene med ansatte, 0–5 % for ENK/NUF. `antallAnsatte` betyr
altså «registrerte ansatte», ikke «bedriften har ingen ansatte».

**Vurdering: svært god.** Grunndataene er komplette på identifikatorer og
klassifisering; hullene er strukturelle (småforetak har ikke plikt til alt),
ikke tilfeldige.

## Regnskaps-API: treffrate og innhold (n = 1 015)

| Gruppe | Treffrate | API-feil (500) |
|---|---:|---:|
| AS 10–49 og 250+ | 100 % | 0 |
| AS 50–249 | 99 % | 0 |
| AS 1–9 | 98 % | 0 |
| AS 0 ansatte | 89 % | 0 |
| ASA | 90,7 % | **18** |
| SA | 37 % | 1 |
| NUF | 16 % | 0 |
| ENK | 2 % | 0 |

- **Kun siste år:** alle 736 treff inneholdt nøyaktig ett regnskap. Historikk må
  bygges over tid eller hentes fra PDF-kopiene.
- **Ferskhet:** 88 % av regnskapene gjaldt regnskapsåret 2025, 11 % 2024
  (målt aug. 2026 – dvs. normal innsendingssyklus), enkelttilfeller tilbake
  til 2017 (sovende selskaper).
- **Finansforetak feiler:** alle de 18 ASA-feilene (og SA-feilen) er banker og
  forsikringsforetak (næringskode 64/65) – bl.a. DNB Bank og Gjensidige. Det
  åpne API-et håndterer ikke deres oppstillingsplaner og svarer vedvarende 500.
- **Nøkkeltallsdekning blant treff:** årsresultat og sum eiendeler 100 %,
  egenkapital 99,6 %, gjeld 98,9 %, driftsresultat 99 %, driftsinntekter 90,8 %
  (holdingselskaper o.l. mangler legitimt omsetning).
- **Valuta:** 95 % NOK, resten USD (4 %), EUR, CAD, DKK – databasen må håndtere
  valutakode per regnskap.
- **Regnskapsregler:** 88 % regnskapsloven, 7,5 % forenklet IFRS, 4,3 % IFRS.

### Balansekontroll (eiendeler = egenkapital + gjeld)

- 90 % av regnskapene balanserer på kronen.
- 9,9 % har avvik > 1 kr, men 89 % av avvikene er < 0,1 % av balansesummen
  (avrunding til hele tusen i innsendte tall).
- **~1 % har materielle avvik.** Verste tilfelle: Telenor ASA, der API-ets
  gjeldsside mangler 73 mrd. kr (35 % av balansen) – eiendelssiden er internt
  konsistent, og `sumEgenkapitalGjeld` er konsistent med EK + gjeld (avvik hos
  bare 1,1 %), så manglene ligger i hvilke gjeldsposter som aggregeres inn.
- **Anbefaling:** bruk `sumEiendeler` som balansesum, lagre alltid rå-JSON, og
  flagg regnskap der identiteten avviker > 0,1 % før tallene brukes analytisk.

**Vurdering: god for brede analyser av ikke-finansielle AS/ASA; ubrukelig for
banker/forsikring (bruk PDF eller andre kilder for dem); nøkkeltall må
valideres med balansesjekk.**

## Roller (n = 360)

- 100 % treffrate i alle grupper – også ENK (innehaver) og NUF (representanter).
- Gjennomsnittlig antall roller: 1,3 (ENK) til 10,4 (ASA).
- Typiske kombinasjoner: daglig leder + styre (+ revisor + regnskapsfører).
- Alle personroller hadde fødselsdato; personer identifiseres med navn +
  fødselsdato (ikke fødselsnummer). NB: persondata → GDPR-ansvar ved lagring.
- Åpent API gir **kun nåsituasjonen** – historikk må bygges med egne snapshots.

**Vurdering: svært god dekning; viktigste svakhet er manglende historikk.**

## Årsregnskap som PDF (n = 135)

| Gruppe | Andel med PDF | Årganger (snitt) | Eldste år |
|---|---:|---:|---:|
| ASA | 100 % | 13,3 | 2011 |
| AS 50–249 | 100 % | 12,9 | 2011 |
| AS 250+ | 87 % | 11,9 | 2011 |
| AS 10–49 | 87 % | 6,5 | 2011 |
| AS 0 / 1–9 | 93 % | 5–6 | 2011 |
| SA | 40 % | 3,3 | 2011 |
| ENK / NUF | 13 % | ~0–1 | – |

- Historikken går maksimalt tilbake til 2011 (15 årganger).
- Lavere snitt hos små AS skyldes at selskapene er yngre, ikke hull i arkivet.
- Nedlasting verifisert: Equinor 2015 (7,4 MB) og 2024 (24,9 MB). Store
  rapporter genereres på forespørsel og kan ta over ett minutt.

**Vurdering: utmerket kilde til årsrapporter med historikk – men dokumentene
er PDF (delvis skannede bilder), så strukturerte tall krever OCR/parsing.**

## Endringsstrøm (oppdaterings-API)

Døgnvolum målt: 4 819 endringer (2 035 «Endring», 314 «Ny», 151 «Sletting» i
de første 2 500). Monoton `oppdateringsid` egner seg som synk-markør.
**Vurdering: velegnet for inkrementell vedlikehold av databasen.**

## Aksjekurser (yfinance, 15 tickere, 2 år)

- 501 handelsdager per ticker, 99,8 % dekning på sluttkurs, 100 % på volum;
  de 22 «manglende» virkedagene er norske helligdager.
- Kobling ticker → orgnr via navnesøk: eksakt treff for 13 av 15; de to
  utenlandskregistrerte (Subsea 7, Frontline) ga **feil** treff → bruk
  ISIN/LEI-kjeden (se datakilder.md §8) + manuell kontroll.

**Vurdering: god nok kvalitet til utforskning/backtesting; lisens krever
annen kilde i produksjon.**

## Feilhåndtering som kreves i produksjon (observert)

1. Vedvarende HTTP 500 for finansforetak i regnskaps-API-et → hopp over og logg.
2. Sporadiske transportfeil/timeouts → retry med backoff (implementert i
   `PoliteClient`).
3. PDF-endepunktet svarer 406 på `Accept: application/pdf` – bruk `Accept: */*`.
   Store rapporter (f.eks. Equinor) tar >30 s å generere → lang timeout.
4. API-ets skrivefeil i feltnavn (`regnkapsprinsipper`, `sumInnskuttEgenkaptial`)
   må beholdes som de er i parsing.
5. Søke-API-ets 10 000-treffsvindu → bruk bulk-filer til masseuttrekk.
