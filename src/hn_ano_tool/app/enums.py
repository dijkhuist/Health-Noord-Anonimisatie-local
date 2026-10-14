from enum import Enum

class administrative_unit(Enum):
    GEMEENTE = 3 
    PROVINCIE = 2
    LAND = 1

# Hoofdgroepen die je als “filters” in de GUI toont
DEDUCE_FILTER_GROUPS: dict[str, str] = {
    "names": "Namen (persoon/patiënt)",
    "locations": "Locaties (plaats, straat, postcode, huisnummer)",
    "institutions": "Instellingen (ziekenhuis / zorginstelling)",
    "dates": "Datums",
    "ages": "Leeftijden",
    "identifiers": "Identificatie (BSN / ID / patiëntnr)",
    "phone_numbers": "Telefoonnummers",
    "email_addresses": "E-mailadressen",
    "urls": "URL’s / websites",
    # "post_processing": "Post-processing"  # bewust NIET in de GUI, altijd aan laten
}