# Gebruiksaanwijzing — Health Noord Anonymizer (Windows .exe)

Deze handleiding is bedoeld voor gebruikers die de **Windows executable (.exe)** draaien, zonder Python of installatie-stappen.

## Benodigdheden

- Windows 10/11
- Een invoerbestand in **.txt** formaat (UTF-8 is aanbevolen)
- (Optioneel) Eén of meer extra lijsten in **.txt** formaat:
  - **patienten-namenbestand**
  - **medewerkers-namenbestand**
  - **locaties-namenbestand**

## Bestandsformaten

### Invoerbestand
- Een enkel `.txt` bestand met te anonimiseren tekst.

### Extra lijsten (optioneel)
- Eén item per regel
- Lege regels worden genegeerd
- Matching is case-insensitive (hoofd-/kleine letters maakt niet uit)

Voorbeeld `patienten.txt`:
```text
Jan Jansen
Mevrouw De Vries
```

## Stappenplan

1. Start `HealthNoordAnonymizer.exe`.
2. Klik op **📁 Invoer .txt bestand** en selecteer het tekstbestand.
3. Klik op **📁 Uitvoer locatie** en selecteer de map waar het resultaat opgeslagen moet worden.
4. (Optioneel) Klik op **📁 Uitvoer locatie log** en selecteer de map voor het logbestand.  
   - Als je dit overslaat, wordt het logbestand in dezelfde map als de uitvoer opgeslagen.
5. Stel de instellingen in:
   - **Leeftijdsanonimisatie inschakelen**: aan/uit  
     - *Het bereik*: standaard 10 (bijv. 34 → 30-40)
   - **Locatie-precisie aanpassen**: aan/uit  
     - *precisie*: `GEMEENTE`, `PROVINCIE` of `LAND`
6. (Optioneel) Voeg extra lijsten toe:
   - **📁 Invoer .txt patienten-namenbestand**
   - **📁 Invoer .txt medewerkers-namenbestand**
   - **📁 Invoer .txt locaties-namenbestand**
7. Stel onder **Deduce filters** in welke categorieën Deduce moet verwerken (checkboxes).
8. Klik op **Anonimiseer file**.

## Resultaten

Na het uitvoeren worden twee bestanden weggeschreven:

1) **Geanonimiseerde tekst**
- Naam: `<invoernaam>_anonymized.txt`
- Locatie: in de gekozen uitvoermap

2) **Logbestand**
- Naam: `<invoernaam>_log.txt`
- Locatie: in de gekozen logmap (of uitvoermap als geen logmap is gekozen)

### Wat betekenen de placeholders?
- Deduce vervangt standaard herkende entiteiten (bijv. personen/BSN/e-mail etc.) volgens Deduce’s tagging.
- Extra lijsten (als opgegeven) vervangen gemiste items met:
  - extra_patient, extra_medewerker -> `<PATIENT_001>`, `<PATIENT_002>`, …
  - extra_locatie -> `<LOCATIE_001>`, …

Het log bevat tellingen per type, inclusief de extra vervangingen (bijv. `extra_patient`, `extra_medewerker`, `extra_locatie`).

## Praktische tips

- Controleer de output steekproefsgewijs (AVG/GDPR): extra lijsten zijn een aanvullende vangnet-stap, geen 100% garantie.
- Voeg varianten toe aan je extra lijsten (bijv. volledige naam en veelgebruikte afkorting) als dezelfde persoon op verschillende manieren wordt genoemd.
- Voor locaties werkt een extra locaties-lijst het best als de schrijfwijze in de tekst overeenkomt met de lijst (bijv. “Drachten” vs “drachten”).

## Probleemoplossing

**“Please select both input file and output folder.”**  
Je hebt nog geen invoerbestand en/of uitvoermap gekozen.

**Geen logmap gekozen**  
Dat is toegestaan; het log wordt dan in de uitvoermap opgeslagen.

**Geen output bestand zichtbaar**  
Controleer of je schrijft naar een map waar je rechten hebt (bijv. niet naar een beveiligde systeemplocatie).

**Antivirus/SmartScreen waarschuwing**  
Windows kan onbekende executables markeren. Gebruik alleen een exe die via de interne uitgifte is verstrekt en controleer de herkomst.

## Privacy

De tool verwerkt bestanden lokaal op de pc.  
De gebruiker blijft verantwoordelijk voor:
- het controleren van de output vóór delen,
- veilige opslag/transport van de geanonimiseerde output.
