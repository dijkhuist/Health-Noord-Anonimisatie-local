# Gebruiksaanwijzing — Health Noord Anonymizer (Windows .exe)

Deze handleiding is bedoeld voor gebruikers die de **Windows executable (.exe)** draaien, zonder Python of installatie-stappen.

## Benodigdheden

- Windows 10/11
- Een invoerbestand in **.txt** formaat (UTF-8 is aanbevolen)
- (Optioneel) Eén of meer extra lijsten in **.txt** formaat:
  - **patienten-namenbestand**
  - **medewerkers-namenbestand**
  - **locaties-namenbestand**
- (Optioneel) Een **whitelistbestand** met medische of andere domeintermen die ongewijzigd moeten blijven.

## Bestandsformaten

### Invoerbestand
- Een enkel `.txt` bestand met te anonimiseren tekst.

### Extra lijsten (optioneel)
- Eén item per regel
- Lege regels worden genegeerd
- De lijsten worden vóór Deduce toegepast: een naam uit je lijst wordt in zijn geheel vervangen (inclusief tussenvoegsels en dubbele achternaam), daarna anonimiseert Deduce de rest van de tekst
- Een voor- of achternaam die meerdere mensen in de lijst delen (bijvoorbeeld twee keer `Wil`), wordt ook los vervangen, met een eigen pseudoniem
- Deduce kent zelf ruim 150.000 Nederlandse straatnamen (BAG). Een voornaam uit de namenlijst die deel is van zo'n straat (`Willem` in `Prins Willem-Alexanderstraat`) blijft staan voor Deduce, dat de hele straat met huisnummer vervangt. Straten hoef je daarom alleen in de locatielijst te zetten als Deduce ze niet kent (bijvoorbeeld een afwijkende spelling of afkorting)
- Alle lijsten worden in één keer doorlopen en de langste treffer wint: een straat uit de locatielijst gaat voor op een voornaam uit de namenlijst
- Bij een straat uit de locatielijst (eindigend op bijvoorbeeld -straat, -weg, -laan, -singel, -plein) wordt het huisnummer meegenomen, ook met toevoeging (`12a`, `12 A`, `258-K`)
- Een locatie wordt alleen als hele regel herkend; zet varianten (zoals `Zorgcentrum De Bolder` en `De Bolder`) als aparte regels in de lijst
- Matching is case-insensitive (hoofd-/kleine letters maakt niet uit); spaties, regelafbrekingen, koppeltekens en apostroffen mogen verschillen
- Een dubbele achternaam blijft één geheel, ook met spaties rond het koppelteken (`van den Broek - Zoon`)
- Een losse voor- of achternaam, of een naam van één woord (eventueel met tussenvoegsel, zoals `Arts` of `de Goede`), wordt alleen vervangen als die in de tekst met een hoofdletter staat (`Arts` wel, `arts` niet; `de Goede` wel, `de goede` niet); volledige namen van meer woorden worden altijd vervangen
- Een achternaam of naam van één woord die ook een gewoon Nederlands woord is (zoals `Linker` of `Anders`) wordt aan het begin van een zin niet vervangen; na een titel of voorletter (`mevr. Anders`) en midden in een zin wel. Voornamen uit een volledige naam (zoals `Wil` uit `Wil Bakker`) worden ook aan het begin van een zin vervangen
- Wordt een gewoon woord midden in een zin toch als naam vervangen (zoals `Kamer` of `Zondag`), zet het dan op de whitelist of haal het uit de namenlijst

### Whitelist (optioneel)
- Eén term of woordgroep per regel
- Lege regels worden genegeerd
- Matching is case-insensitive en vereist een volledige woordgroep
- Een match wordt na verwerking exact teruggezet zoals die in de invoertekst stond
- Whitelist-termen worden bewust niet geanonimiseerd; voeg alleen termen toe die in de uitvoer mogen blijven staan
- Staat een term ook in de patiënten-, medewerkers- of locatielijst, dan gaat die lijst voor en wordt de term toch geanonimiseerd; uitzondering is een term van één woord die ook een gewoon Nederlands woord is (zoals `Kamer`): die blijft staan als hij op de whitelist staat

Voorbeeld `patienten.txt`:
```text
Jan Jansen
Mevrouw De Vries
```

## Stappenplan

1. Start `HealthNoordAnonymizer.exe`.
2. Wacht tot de knop **Anonimiseer bestand** verschijnt (bij het opstarten staat er even *Bezig met initialiseren...*).
3. Klik op **📁 Invoer .txt** en selecteer het tekstbestand.
4. Klik op **📁 Uitvoermap** en selecteer de map waar het resultaat opgeslagen moet worden.
5. (Optioneel) Klik op **📁 Logmap** en selecteer de map voor het logbestand.  
   - Als je dit overslaat, wordt het logbestand in dezelfde map als de uitvoer opgeslagen.
6. (Optioneel) Voeg extra lijsten toe:
   - **📁 Patiëntenlijst**
   - **📁 Medewerkerslijst**
   - **📁 Locatielijst**
7. (Optioneel) Kies met **📁 Whitelist** een bestand met termen die behouden moeten blijven.  
   Met de knop **✖** naast een keuze maak je die keuze weer leeg.
8. Vink onder **Filter op** aan welke categorieën Deduce moet anonimiseren: namen, locaties, instellingen, datums, leeftijden, identificatienummers (BSN/ID/patiëntnr), telefoonnummers, e-mailadressen en URL's. Standaard staan alle categorieën aan. Vink je **Namen (persoon)** uit, dan worden ook de patiënten- en medewerkerslijst niet gebruikt; vink je **Locaties** uit, dan ook de locatielijst niet. Onder Locaties valt ook een postcode op `MG` in hoofdletters (`9257MG`, `9257 MG`), die Deduce zelf overslaat; `1000 mg` in kleine letters blijft staan als dosering. Kamernummers zoals `K412` worden niet herkend. Onder **Datums** vallen ook datums zonder jaartal (`9 mei`, `27 okt.`), die Deduce zelf overslaat.
9. Klik op **Anonimiseer bestand**. De voorcontrole controleert de gekozen bestanden en mappen en toont de invoernaam, bestandsgrootte en uitvoerlocaties. Tijdens de verwerking zijn de bestandskeuzes en filters vergrendeld. De voortgang toont de huidige fase; na ongeveer tien seconden verschijnt ook een resterende-tijdschatting.
10. Gebruik **Annuleer verwerking** als je wilt stoppen. De huidige tekstchunk wordt eerst afgemaakt; daarna wordt de run gestopt zonder gedeeltelijk uitvoerbestand.

## Resultaten

Na het uitvoeren worden twee bestanden weggeschreven:

1) **Geanonimiseerde tekst**
- Naam: `<invoernaam>_anonymized_<tijdstempel>.txt`, bijv. `verslag_anonymized_2026_10_14_H14_M39_S57_123456.txt`
- Door de tijdstempel wordt een eerder resultaat nooit overschreven
- Locatie: in de gekozen uitvoermap

2) **Logbestand**
- Naam: `<invoernaam>_log_<tijdstempel>.txt` (zelfde tijdstempel als het resultaat)
- Locatie: in de gekozen logmap (of uitvoermap als geen logmap is gekozen)

Na een geslaagde run verschijnt automatisch een scrollbaar venster met de volledige logresultaten, waaronder per filtergroep of die aan of uit stond. Onderin dat venster open je met **Open resultaat** het geanonimiseerde bestand, met **Open uitvoermap** de map en met **Open log** het logbestand. Sluit het venster met **Sluiten**, `Esc` of het kruisje. Daarna blijven dezelfde drie acties beschikbaar als kleine links (**Resultaat · Uitvoermap · Log**) rechts op de statusregel onder de oranje knop, tot je een nieuwe run start.

Filterkeuzes worden lokaal onthouden. Bestandspaden worden niet onthouden: selecteer na het opnieuw openen van de tool het invoerbestand, de uitvoer- en logmap, eventuele extra lijsten en de whitelist opnieuw.

### Wat betekenen de placeholders?
- Deduce vervangt herkende gegevens door een code tussen blokhaken met het type en een volgnummer, bijv. `[PERSOON-1]`, `[LOCATIE-2]` of `[DATUM-3]`.
- Extra lijsten (als opgegeven) vervangen wat Deduce heeft gemist door een code tussen punthaken:
  - patiënten- en medewerkerslijst -> `<PERSOON_001>`, `<PERSOON_002>`, …
  - locatielijst -> `<LOCATIE_001>`, …
- Dezelfde naam of waarde krijgt binnen één run overal dezelfde code. Zo blijft leesbaar dat het om dezelfde persoon gaat.

Het log bevat de runstatus, starttijd en duur, invoernaam en grootte, de actieve en uitgeschakelde filtergroepen (elk op een eigen regel), of whitelist/extra lijsten zijn gebruikt, en vervangingstotalen apart voor Deduce en extra lijsten plus aantallen per type. Ook mislukte en geannuleerde runs krijgen een log; gedeeltelijke uitvoer wordt niet bewaard. Logs bevatten geen volledige paden, bronfragmenten, whitelist-termen of lijstinhoud.

## Oefenen en testen met synthetische data

In de map `testdata\synthetisch` staat een synthetische testset: een nagemaakte EPD-export (`epd_synthetisch.txt`) met zorgnotities waarin alle personen, adressen, telefoonnummers, e-mailadressen, BSN's en datums verzonnen zijn. Het formaat is gelijk aan een echte export. Gebruik deze set om te oefenen, voor een demonstratie of om te controleren hoe goed de tool werkt, zonder echte gegevens.

- `epd_synthetisch.txt`: invoerbestand (1000 records, ongeveer 550 met een notitie)
- `patienten.txt`, `medewerkers.txt`, `locaties.txt`, `whitelist.txt`: bijpassende lijsten
- `sleutel.json`: antwoordsleutel met per notitie de gevoelige gegevens en de gewone woorden die moeten blijven staan

Kies `epd_synthetisch.txt` als invoerbestand en eventueel de lijsten en de whitelist, en klik op **Anonimiseer bestand**. Draai de set ook eens zonder lijsten om het verschil te zien. Voor technisch beheer: `scripts\evaluate_testset.py` telt per soort gegeven wat er nog in de uitvoer staat; `scripts\make_synthetic_testset.py` maakt een nieuwe testset (`--seed` voor een andere variant).

## Praktische tips

- Controleer de output steekproefsgewijs (AVG/GDPR): ook met volledige extra lijsten is er geen 100% garantie.
- Voeg varianten toe aan je extra lijsten (bijv. volledige naam en veelgebruikte afkorting) als dezelfde persoon op verschillende manieren wordt genoemd.
- Hoofdletters maken voor de lijsten niet uit, maar andere schrijfwijzen wel: zet ook varianten in de locatielijst (bijv. “Sint Jacobiparochie” én “St. Jacobiparochie”).

## Probleemoplossing

**Melding bij de voorcontrole (bijv. “Invoerbestand: selecteer een bestand.” of “Uitvoermap: map is niet beschrijfbaar.”)**  
De voorcontrole noemt per bestand of map wat er mis is: niets gekozen, geen `.txt`-bestand, bestand bestaat niet of kan niet gelezen worden, of de map is niet beschrijfbaar. Pas de genoemde keuze aan en klik opnieuw op **Anonimiseer bestand**.

**Geen logmap gekozen**  
Dat is toegestaan; het log wordt dan in de uitvoermap opgeslagen.

**Geen output bestand zichtbaar**  
Controleer of je schrijft naar een map waar je rechten hebt (bijv. niet naar een beveiligde systeemplocatie).

**Verwerking duurt langer dan verwacht**

De voortgang en tijdsinschatting worden bijgewerkt na iedere verwerkte tekstchunk. Sluit de tool niet voordat de melding aangeeft dat de verwerking klaar is.

**Run annuleren**

Bevestig annuleren in de tool. De huidige chunk mag afronden; er wordt geen gedeeltelijk uitvoerbestand bewaard.

**Antivirus/SmartScreen waarschuwing**  
Windows kan onbekende executables markeren. Gebruik alleen een exe die via de interne uitgifte is verstrekt en controleer de herkomst.

## Privacy

De tool verwerkt bestanden lokaal op de pc.  
De gebruiker blijft verantwoordelijk voor:
- het controleren van de output vóór delen,
- veilige opslag/transport van de geanonimiseerde output.
