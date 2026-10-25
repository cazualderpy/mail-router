"""Synthetischer Generator für Trainings-/Validierungsdaten (nur *.example-Domains)."""

import json
import random
import re
import unicodedata
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path

from faker import Faker

from mail_router.schema import MAIL_TYPES, TYPE_FIELDS, Fields


@dataclass
class Example:
    sender: str
    subject: str
    body: str
    type: str
    fields: Fields


DOMAINS = ["freemail.example", "post.example", "netz-mail.example", "mailbox.example",
           "web-adresse.example", "online.example", "privat.example", "kontakt.example"]

# --- Werte der typspezifischen Felder -------------------------------------------------

MEDIKAMENTE = ["Ramipril 5 mg", "Metformin 1000", "Ibuprofen 600", "L-Thyroxin 75", "Pantoprazol 40 mg",
               "Bisoprolol 2,5", "Atorvastatin 20 mg", "Amlodipin 5 mg", "Salbutamol Spray", "Candesartan 8 mg",
               "Simvastatin 40", "Levothyroxin 100 µg", "Torasemid 10 mg", "Novaminsulfon Tropfen",
               "Diclofenac 75 mg", "Cetirizin 10 mg", "Insulin Lantus", "Omeprazol 20", "Blutdrucktabletten",
               "die Schilddrüsentabletten", "meine Asthma-Medikamente", "Eliquis 5 mg", "Sertralin 50 mg"]
FACHRICHTUNGEN = ["Kardiologie", "Orthopädie", "Dermatologie", "Neurologie", "Urologie", "Gastroenterologie",
                  "Augenheilkunde", "HNO", "Radiologie", "Gynäkologie", "Endokrinologie", "Pneumologie",
                  "Rheumatologie", "Psychiatrie", "Physiotherapie", "Orthopäde", "Hautarzt", "Augenarzt",
                  "Kardiologen", "Neurologen"]
FACHRICHTUNGEN_EN = ["cardiologist", "dermatologist", "orthopaedic surgeon", "neurologist", "ENT specialist",
                     "radiology", "gastroenterology"]
WOCHENTAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag"]
WEEKDAYS_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
MONATE_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
             "October", "November", "December"]
MONATE_DE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September",
             "Oktober", "November", "Dezember"]


def _wunschtermin(rng: random.Random, en: bool) -> str:
    d = date(2026, 11, 1) + timedelta(days=rng.randint(0, 90))
    if en:
        return rng.choice([f"next {rng.choice(WEEKDAYS_EN)} morning", f"{rng.choice(WEEKDAYS_EN)} afternoon",
                           f"the week of {d.day} {MONATE_EN[d.month - 1]}", f"{d.day} {MONATE_EN[d.month - 1]} at {rng.randint(8, 16)}:00",
                           "early next month", "any time after 3 pm"])
    return rng.choice([f"nächsten {rng.choice(WOCHENTAGE)} vormittags", f"{rng.choice(WOCHENTAGE)} nachmittags",
                       f"in der Woche ab dem {d.day}.{d.month}.", f"am {d.day:02d}.{d.month:02d}. um {rng.randint(8, 16)} Uhr",
                       f"Anfang {MONATE_DE[d.month % 12]}", "so bald wie möglich", "nach 16 Uhr",
                       f"Mitte {MONATE_DE[d.month - 1]}", f"{rng.choice(WOCHENTAGE)} oder {rng.choice(WOCHENTAGE)} früh",
                       f"im Zeitraum {d.day}.{d.month}. bis {d.day + 4 if d.day < 24 else d.day}.{d.month}."])


def _au_zeitraum(rng: random.Random, en: bool) -> str:
    d = date(2026, 10, 26) + timedelta(days=rng.randint(0, 40))
    e = d + timedelta(days=rng.randint(1, 10))
    if en:
        return rng.choice([f"from {d.day} {MONATE_EN[d.month - 1]} to {e.day} {MONATE_EN[e.month - 1]}",
                           f"{rng.randint(2, 7)} days", f"{rng.choice(WEEKDAYS_EN)} to {rng.choice(WEEKDAYS_EN)}",
                           "this whole week"])
    return rng.choice([f"vom {d.day}.{d.month}. bis {e.day}.{e.month}.", f"{rng.randint(2, 7)} Tage",
                       f"{d.day:02d}.{d.month:02d}.-{e.day:02d}.{e.month:02d}.{d.year}",
                       f"bis {rng.choice(WOCHENTAGE)}", "diese ganze Woche", f"seit {rng.choice(WOCHENTAGE)}",
                       f"{rng.randint(1, 3)} Wochen", f"ab {d.day}.{d.month}. für eine Woche"])


# --- Kerntexte (Platzhalter {v} = typspezifischer Wert); (Text, anliegen) für befund/sonstiges -----

CORE_DE = {
    "termin": [
        "ich würde gerne einen Termin bei Ihnen vereinbaren, am liebsten {v}.",
        "Könnten wir bitte einen Termin ausmachen? Mir würde {v} gut passen.",
        "Ich brauche einen Termin zur Kontrolle. Bei mir geht es {v}.",
        "wir möchten einen Termin für eine Untersuchung buchen, idealerweise {v}.",
        "Gibt es noch freie Termine? Ich könnte {v}.",
        "Bitte um Terminvergabe, gern {v}. Die Beschwerden bestehen seit ein paar Wochen.",
        "Ich möchte meinen Termin verschieben und bräuchte einen neuen, am besten {v}.",
        "Wann hätten Sie Zeit für einen Check-up? Ich dachte an {v}.",
        "Für die Vorsorgeuntersuchung hätte ich gern einen Termin {v}.",
        "Mein Rücken macht Probleme, deshalb bitte ich um einen zeitnahen Termin, passend wäre {v}.",
        "Termin wegen Impfberatung? Bei mir ginge {v}.",
        "wäre es möglich, kurzfristig einen Termin zu bekommen? {v} hätte ich Zeit.",
    ],
    "rezept": [
        "ich bräuchte ein neues Rezept für {v}.",
        "Könnten Sie mir bitte {v} noch einmal verschreiben? Die Packung ist fast leer.",
        "Bitte um Folgerezept: {v}. Ich nehme es unverändert weiter.",
        "Mir geht das Medikament aus, es handelt sich um {v}. Kann ich das Rezept abholen?",
        "Wir benötigen dringend ein Rezept über {v}, am besten zum Abholen.",
        "Ich habe heute Morgen festgestellt, dass {v} aufgebraucht ist. Wäre ein Rezept bis Ende der Woche möglich?",
        "Rezeptanfrage: {v}. Bitte direkt an meine Apotheke schicken.",
        "Dürfte ich ein Wiederholungsrezept für {v} bekommen? Ein Termin ist nicht nötig, oder?",
        "Mein Arzt hat mir damals {v} verordnet, jetzt brauche ich Nachschub.",
        "Ich fahre nächste Woche in den Urlaub und brauche vorher noch ein Rezept für {v}.",
        "kann ich bitte {v} auf Rezept haben? danke",
    ],
    "ueberweisung": [
        "ich bräuchte eine Überweisung zum Facharzt, genauer {v}.",
        "Könnten Sie mir bitte eine Überweisung für {v} ausstellen?",
        "Mein Hausarzt-Befund liegt vor, jetzt soll ich zur {v}. Bitte um Überweisung.",
        "Für den Termin beim Facharzt brauche ich eine Überweisung: {v}.",
        "Wir benötigen eine Überweisung, es geht um {v}. Die Praxis verlangt sie zwingend.",
        "Bitte stellen Sie mir einen Überweisungsschein aus. Zuständig wäre {v}.",
        "Ich möchte mich gern weiter abklären lassen und bitte um Überweisung zu {v}.",
        "Der Arzt hatte bei der letzten Untersuchung erwähnt, dass ich zu {v} gehen sollte. Kann ich die Überweisung abholen?",
        "wegen der anhaltenden Beschwerden hätte ich gern eine Überweisung, {v} wäre sinnvoll.",
        "Überweisung {v} bitte, vielen Dank.",
    ],
    "au": [
        "ich bin erkältet und brauche eine Krankschreibung, und zwar {v}.",
        "Bitte um Ausstellung einer Arbeitsunfähigkeitsbescheinigung für {v}.",
        "Ich war krank und benötige die AU für meinen Arbeitgeber, Zeitraum: {v}.",
        "Könnte ich eine Krankmeldung bekommen? Ich bin {v} nicht arbeitsfähig.",
        "Meine Krankschreibung läuft aus, ich brauche eine Verlängerung, {v}.",
        "Hiermit melde ich mich krank und bitte um eine AU: {v}. Der Arbeitgeber wartet auf den gelben Schein.",
        "Magen-Darm seit gestern, ich kann nicht arbeiten. Bitte AU für {v} ausstellen.",
        "Wir brauchen eine Bescheinigung für die Schule bzw. den Arbeitgeber wegen Krankheit, {v}.",
        "Kann die Krankschreibung per Post kommen? Es geht um {v}.",
        "AU-Bescheinigung bitte, {v}. Danke!",
    ],
    "befund": [
        ("ich wollte nachfragen, ob mein Befund vom Labor schon vorliegt.", "Fragt nach dem Laborbefund."),
        ("Liegen die Ergebnisse meiner Blutuntersuchung schon vor? Ich wurde letzte Woche abgenommen.", "Fragt nach den Blutergebnissen."),
        ("Könnten Sie mir bitte den Befund meines MRT zuschicken?", "Bittet um Zusendung des MRT-Befunds."),
        ("Ich warte noch auf das Ergebnis der Untersuchung und wollte fragen, ob etwas gekommen ist.", "Fragt nach einem ausstehenden Untersuchungsergebnis."),
        ("Bitte um Kopie des Röntgenbefundes für meinen Facharzt.", "Bittet um eine Kopie des Röntgenbefunds."),
        ("Der Arzt sagte, die Befunde seien in einer Woche da. Sind sie schon eingetroffen?", "Fragt, ob die angekündigten Befunde eingetroffen sind."),
        ("Ich möchte die Ergebnisse meiner Langzeit-EKG-Auswertung erfahren.", "Möchte die Auswertung des Langzeit-EKGs erfahren."),
        ("Wir hätten gern den Befund der Biopsie, können Sie ihn uns übermitteln?", "Bittet um Übermittlung des Biopsiebefunds."),
        ("Gibt es schon was Neues zu meinem Befund? Bin etwas nervös.", "Fragt nach dem aktuellen Stand seines Befunds."),
        ("Bitte schicken Sie mir die Laborwerte per Post, ich brauche sie für meine Unterlagen.", "Bittet um Zusendung der Laborwerte."),
    ],
    "sonstiges": [
        ("wie sind Ihre Öffnungszeiten über die Feiertage?", "Fragt nach den Öffnungszeiten an Feiertagen."),
        ("Ich habe eine Rechnung erhalten, die ich nicht nachvollziehen kann. Können Sie sie prüfen?", "Bittet um Prüfung einer Rechnung."),
        ("Ich bin umgezogen und möchte meine Adresse ändern lassen.", "Teilt eine Adressänderung mit."),
        ("Meine Krankenkasse hat gewechselt. Wohin soll ich die neue Versichertenkarte schicken?", "Meldet einen Krankenkassenwechsel."),
        ("Ich möchte mich über die lange Wartezeit am Montag beschweren.", "Beschwert sich über die Wartezeit."),
        ("Haben Sie einen Parkplatz oder eine Haltestelle in der Nähe? Ich komme das erste Mal.", "Fragt nach Anfahrt und Parkmöglichkeiten."),
        ("Wir würden Ihnen gern unser neues Praxisverwaltungssystem vorstellen. Hätten Sie Interesse an einem Gespräch?", "Werbeanfrage für ein Praxisverwaltungssystem."),
        ("Ich möchte mich für die gute Behandlung bedanken.", "Bedankt sich für die Behandlung."),
        ("Können Sie mir die Bescheinigung über meine Impfungen ausstellen? Mein Impfpass ist weg.", "Bittet um Ersatzbescheinigung für den Impfpass."),
        ("Ist Dr. Weber nächste Woche im Urlaub? Dann würde ich meinen Besuch verschieben.", "Fragt nach der Urlaubsvertretung."),
        ("Mein Sohn braucht eine Bescheinigung für den Sportverein. Muss ich dafür einen Termin machen oder reicht ein Formular?", "Fragt nach einer Sportbescheinigung."),
        ("Bitte streichen Sie mich aus Ihrem Newsletter-Verteiler.", "Bittet um Löschung aus dem Newsletter."),
    ],
}

CORE_EN = {
    "termin": [
        "I would like to book an appointment, ideally {v}.",
        "Could I get an appointment with the doctor? {v} would work for me.",
        "Do you have any free slots? I am available {v}.",
    ],
    "rezept": [
        "Could you please issue a repeat prescription for {v}?",
        "I am running out of {v}. May I pick up a new prescription?",
        "I need a prescription for {v}, please send it to my pharmacy.",
    ],
    "ueberweisung": [
        "I need a referral to see a specialist, specifically {v}.",
        "Could you please write me a referral for {v}?",
        "Please issue a referral: {v}.",
    ],
    "au": [
        "I am ill and need a sick note covering {v}.",
        "Could you please issue a certificate of incapacity for work for {v}?",
        "I have the flu and cannot work. Please send me a sick note, {v}.",
    ],
    "befund": [
        ("I would like to know whether my lab results have come in yet.", "Fragt, ob die Laborergebnisse eingetroffen sind."),
        ("Could you send me the report of my last MRI scan, please?", "Bittet um den MRT-Befund."),
        ("Are my blood test results ready? The doctor said they would arrive this week.", "Fragt nach den Blutergebnissen."),
    ],
    "sonstiges": [
        ("what are your opening hours on public holidays?", "Fragt nach den Öffnungszeiten an Feiertagen."),
        ("I recently moved and need to update my address in your records.", "Teilt eine Adressänderung mit."),
        ("I received an invoice that I do not understand. Could you check it?", "Bittet um Prüfung einer Rechnung."),
    ],
}

ANLIEGEN = {
    "termin": ["Möchte einen Termin vereinbaren, Wunsch: {v}.", "Bittet um einen Termin ({v}).",
               "Terminanfrage, gewünscht ist {v}."],
    "rezept": ["Bittet um ein Rezept für {v}.", "Benötigt ein Folgerezept ({v}).", "Rezeptanfrage: {v}."],
    "ueberweisung": ["Bittet um eine Überweisung ({v}).", "Benötigt Überweisung zum Facharzt: {v}.",
                     "Möchte eine Überweisung für {v}."],
    "au": ["Bittet um eine Krankschreibung ({v}).", "Benötigt eine AU für den Zeitraum {v}.",
           "Meldet sich krank, AU gewünscht: {v}."],
}

SUBJECTS = {
    "termin": ["Terminanfrage", "Termin", "Termin vereinbaren", "Terminwunsch", "Anfrage Termin", "termin?",
               "Neuer Termin", "Termin bitte"],
    "rezept": ["Rezept", "Rezeptanfrage", "Folgerezept", "Medikament", "Rezept bestellen", "rezept",
               "Wiederholungsrezept"],
    "ueberweisung": ["Überweisung", "Überweisungswunsch", "Anfrage Überweisung", "Überweisung zum Facharzt",
                     "ueberweisung", "Überweisungsschein"],
    "befund": ["Befund", "Befund angefordert", "Laborergebnisse", "Frage zu meinem Befund", "Ergebnisse",
               "Untersuchungsergebnis", "befund?"],
    "au": ["Krankschreibung", "AU", "AU-Bescheinigung", "Krankmeldung", "Arbeitsunfähigkeit", "krank",
           "Krankschreibung bitte"],
}

SUBJECTS_EN = {
    "termin": ["Appointment request", "Appointment"],
    "rezept": ["Prescription", "Repeat prescription"],
    "ueberweisung": ["Referral request", "Referral"],
    "befund": ["Test results", "Lab results"],
    "au": ["Sick note", "Sick leave certificate"],
}

GENERIC_DE = ["", "Anfrage", "Frage", "Hallo", "Re: Ihre Praxis", "Kurze Frage", "Nachricht", "Anliegen",
              "Guten Tag", "Bitte um Rückmeldung", "Ihre Praxis", "Kurze Anfrage", "Info", "Hilfe"]
GENERIC_EN = ["", "Question", "Hello", "Quick question", "Message", "Request", "Re: your practice", "Inquiry"]
KEYWORD_SUBJECT_SHARE = 0.28
# Themenspezifische Betreffs für sonstiges, gebunden an den gewählten Kerntext (Präfix des Kerntexts)
SONSTIGES_SUBJECT = {
    "wie sind Ihre Öffnungszeiten": "Öffnungszeiten",
    "Ich habe eine Rechnung": "Rechnung unklar",
    "Ich bin umgezogen": "Adressänderung",
    "Meine Krankenkasse hat gewechselt": "Neue Krankenkasse",
    "Ich möchte mich über die lange": "Beschwerde Wartezeit",
    "Haben Sie einen Parkplatz": "Anfahrt",
    "Wir würden Ihnen gern unser neues": "Software für Ihre Praxis",
    "Ich möchte mich für die gute": "Dankeschön",
    "Können Sie mir die Bescheinigung über meine Impfungen": "Impfbescheinigung",
    "Ist Dr. Weber": "Urlaub",
    "Mein Sohn braucht eine Bescheinigung für den Sportverein": "Sportbescheinigung",
    "Bitte streichen Sie mich": "Newsletter abbestellen",
    "what are your opening hours": "Opening hours",
    "I recently moved": "Change of address",
    "I received an invoice": "Invoice",
}

SECONDARY_DE = {
    "termin": ["Außerdem wüsste ich gern, ob ein Termin auch online buchbar ist.",
               "Übrigens: Brauche ich für den Termin meine Versichertenkarte noch einmal?"],
    "rezept": ["Und bräuchte ich zusätzlich noch ein Rezept?", "Ach ja, bitte schicken Sie mir auch ein Rezept zu."],
    "ueberweisung": ["Falls nötig, bräuchte ich auch noch eine Überweisung zum Facharzt.",
                     "Außerdem bräuchte ich eventuell eine Überweisung."],
    "befund": ["Außerdem würde mich interessieren, ob die Laborwerte schon da sind.",
               "Und gibt es schon Ergebnisse meiner letzten Untersuchung?"],
    "au": ["Außerdem bräuchte ich eventuell eine Krankschreibung.", "Eine AU bräuchte ich dann auch noch."],
    "sonstiges": ["Noch eine Frage: Bis wann haben Sie heute geöffnet?", "Außerdem hätte ich eine Frage zur Rechnung.",
                  "Und wo kann ich die Praxisgebühr bezahlen?"],
}
SECONDARY_EN = {
    "termin": ["Also, can I book online?"],
    "rezept": ["I might need a prescription as well."],
    "ueberweisung": ["I may also need a referral."],
    "befund": ["Also, are my results ready?"],
    "au": ["I might need a sick note too."],
    "sonstiges": ["One more question: until when are you open today?"],
}

GREET_FORMAL = ["Sehr geehrte Damen und Herren,", "Guten Tag,", "Sehr geehrtes Praxisteam,", "Guten Morgen,",
                "Sehr geehrte Frau Doktor,", "Sehr geehrter Herr Doktor,"]
GREET_INFORMAL = ["Hallo,", "Hallo zusammen,", "Moin,", "Liebes Praxisteam,", "Hi,", "Hallo liebes Team,", ""]
GREET_EN = ["Dear Sir or Madam,", "Hello,", "Hi,", "Dear practice team,", "Good morning,"]
SIGN_FORMAL = ["Mit freundlichen Grüßen", "Freundliche Grüße", "Viele Grüße", "Mit besten Grüßen", "Hochachtungsvoll"]
SIGN_INFORMAL = ["LG", "Viele Grüße", "Danke und Gruß", "Beste Grüße", "Gruß", "Bis bald", "Schönen Tag noch"]
SIGN_EN = ["Kind regards", "Best regards", "Thanks", "Sincerely", "Many thanks"]
THANKS_DE = ["Vielen Dank im Voraus.", "Danke für Ihre Hilfe!", "Vielen Dank und einen schönen Tag.", "Danke."]
THANKS_EN = ["Thank you in advance.", "Thanks for your help!"]
INTRO_DE = ["", "", "", "ich schreibe Ihnen, weil ", "kurze Nachricht: ", "ich melde mich, da ", "Entschuldigen Sie die Störung, "]

# Beziehungen: (Text de, Text en)
RELATIONS = [("meinen Sohn", "my son", "m"), ("meine Tochter", "my daughter", "f"), ("mein Kind", "my child", "x"),
             ("meine Mutter", "my mother", "f"), ("meinen Vater", "my father", "m"), ("meinen Mann", "my husband", "m"),
             ("meine Frau", "my wife", "f")]


def _slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss"))
    return re.sub(r"[^a-z0-9]+", ".", s.encode("ascii", "ignore").decode().lower()).strip(".") or "user"


def _fmt_dob(rng: random.Random, d: date, en: bool) -> str:
    if en:
        return rng.choice([f"{d.day} {MONATE_EN[d.month - 1]} {d.year}", d.isoformat(), f"born {d.day} {MONATE_EN[d.month - 1]} {d.year}"])
    dmy = f"{d.day:02d}.{d.month:02d}.{d.year}"
    return rng.choice([dmy, f"*{dmy}", f"geb. am {dmy}", f"geb. {dmy}", d.isoformat(), f"{d.day}. {MONATE_DE[d.month - 1]} {d.year}",
                       f"Geburtsdatum: {dmy}"])


def _typo(rng: random.Random, text: str) -> str:
    """Tippfehler in Wörtern ohne Platzhalter einstreuen (Spans bleiben unangetastet)."""
    out = []
    for w in text.split(" "):
        if "{" not in w and len(w) > 4 and w.isalpha() and rng.random() < 0.12:
            i = rng.randrange(1, len(w) - 2)
            kind = rng.choice(["swap", "drop", "double"])
            if kind == "swap":
                w = w[:i] + w[i + 1] + w[i] + w[i + 2:]
            elif kind == "drop":
                w = w[:i] + w[i + 1:]
            else:
                w = w[:i] + w[i] + w[i:]
        out.append(w)
    return " ".join(out)


def _make(rng: random.Random, fakers: dict[str, Faker], mtype: str) -> Example:
    en = rng.random() < 0.15
    fk = fakers["en_GB" if en else "de_DE"]
    formal = rng.random() < 0.55
    typo_mode = rng.random() < 0.15
    lower_mode = rng.random() < 0.15

    # Wert des typspezifischen Feldes
    value = None
    if mtype == "termin":
        value = _wunschtermin(rng, en)
    elif mtype == "rezept":
        value = rng.choice(MEDIKAMENTE)
    elif mtype == "ueberweisung":
        value = rng.choice(FACHRICHTUNGEN_EN if en else FACHRICHTUNGEN)
    elif mtype == "au":
        value = _au_zeitraum(rng, en)

    core = rng.choice((CORE_EN if en else CORE_DE)[mtype])
    if isinstance(core, tuple):
        core_text, anliegen = core
    else:
        core_text, anliegen = core, rng.choice(ANLIEGEN[mtype])
    core_text_raw = core_text
    intro = "" if en else rng.choice(INTRO_DE)
    if intro:
        core_text = intro + (core_text[0].lower() + core_text[1:] if core_text[0].isupper() and not core_text.startswith(("Dr", "Ich")) else core_text)
    elif not en and rng.random() < 0.3:
        core_text = core_text[0].upper() + core_text[1:]
    if en:
        core_text = core_text[0].upper() + core_text[1:]

    # Personen: Absender, Patient (evtl. Dritter), Geburtsdatum
    sender_first, sender_last = fk.first_name(), fk.last_name()
    sender_name = f"{sender_first} {sender_last}"
    third = rng.random() < 0.2
    name_known = rng.random() > 0.12
    dob_known = rng.random() < 0.5
    if third:
        rel_de, rel_en, sex = rng.choice(RELATIONS)
        pfirst = {"m": fk.first_name_male, "f": fk.first_name_female, "x": fk.first_name}[sex]()
        patient_name = f"{pfirst} {sender_last}"
        child = rel_de in ('meinen Sohn', 'meine Tochter', 'mein Kind')
        bd = date(rng.randint(2008, 2023) if child else rng.randint(1940, 1990), rng.randint(1, 12), rng.randint(1, 28))
    else:
        patient_name = sender_name
        bd = date(rng.randint(1945, 2003), rng.randint(1, 12), rng.randint(1, 28))
    dob_str = _fmt_dob(rng, bd, en) if dob_known else None

    lines: list[str] = []
    greet = rng.choice(GREET_EN if en else (GREET_FORMAL if formal else GREET_INFORMAL))
    if greet:
        lines.append(greet)
        lines.append("")

    pieces: list[str] = []
    if third:
        who = "{pn}" if name_known else ""
        if en:
            pieces.append(f"I am writing on behalf of {rel_en}" + (f", {who}" if who else "") + ".")
        else:
            pieces.append(f"Ich schreibe für {rel_de}" + (f", {who}" if who else "") + ".")
    pieces.append(core_text)
    if rng.random() < 0.2:
        sec = rng.choice((SECONDARY_EN if en else SECONDARY_DE)[rng.choice([t for t in MAIL_TYPES if t != mtype])])
        pieces.append(sec)
    if dob_str:
        label = rng.choice(["Mein Geburtsdatum:", "Geburtsdatum:", "(", ""]) if not en else rng.choice(["Date of birth:", "DOB:", "("])
        if label == "(":
            pieces.append("({dob})")
        else:
            pieces.append((label + " {dob}").strip() + ("." if label and rng.random() < 0.3 else ""))
    if not third and name_known and rng.random() < 0.25:
        pieces.insert(0, ("My name is {pn}." if en else rng.choice(["Mein Name ist {pn}.", "Hier schreibt {pn}.", "Ich bin {pn}."])))
    if rng.random() < 0.4:
        pieces.append(rng.choice(THANKS_EN if en else THANKS_DE))

    sep = rng.choice([" ", "\n", "\n\n"])
    lines.append(sep.join(pieces))
    lines.append("")
    sign = rng.choice(SIGN_EN if en else (SIGN_FORMAL if formal else SIGN_INFORMAL))
    lines.append(sign)
    if not third and name_known and rng.random() < 0.85:
        lines.append("{pn}")
    elif not third and not name_known:
        pass
    else:
        lines.append(sender_name)
    template = "\n".join(lines)
    if not third and name_known and "{pn}" not in template:
        template += "\n{pn}"
    if typo_mode:
        template = _typo(rng, template)
        if rng.random() < 0.5:
            template = template.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
    # Platzhalter erst nach den Tippfehlern ersetzen, damit Spans wörtlich bleiben
    body = template.replace("{v}", value or "").replace("{pn}", patient_name).replace("{dob}", dob_str or "")
    if lower_mode:
        body = body.lower()
    if "{" in body:  # Absicherung
        raise AssertionError(body)

    if rng.random() < KEYWORD_SUBJECT_SHARE:
        if mtype == "sonstiges":
            subject = next(v for k, v in SONSTIGES_SUBJECT.items() if core_text_raw.startswith(k))
        else:
            subject = rng.choice(SUBJECTS_EN[mtype] if en else SUBJECTS[mtype])
    else:
        subject = rng.choice(GENERIC_EN if en else GENERIC_DE)
    if subject and not subject.startswith("Re:") and rng.random() < 0.1:
        subject = "Re: " + subject
    if lower_mode:
        subject = subject.lower()
    sender = f"{_slug(sender_name)}@{rng.choice(DOMAINS)}"
    if rng.random() < 0.3:
        sender = f"{_slug(sender_first)[:1]}{_slug(sender_last)}{rng.randint(1, 99)}@{rng.choice(DOMAINS)}"

    anliegen = anliegen.replace("{v}", f"„{value}“" if en and value else (value or ""))
    fields = Fields(
        patient_name=patient_name if name_known else None,
        geburtsdatum=bd.isoformat() if dob_known else None,
        anliegen=anliegen,
    )
    tf = TYPE_FIELDS[mtype]
    if tf:
        setattr(fields, tf, value)
    return Example(sender=sender, subject=subject, body=body, type=mtype, fields=fields)


def generate(n_per_type: int, seed: int) -> list[Example]:
    rng = random.Random(seed)
    fakers = {loc: Faker(loc) for loc in ("de_DE", "en_GB")}
    for i, fk in enumerate(fakers.values()):
        fk.seed_instance(seed + i)
    out = [_make(rng, fakers, t) for t in MAIL_TYPES for _ in range(n_per_type)]
    rng.shuffle(out)
    return out


def split(examples: list[Example], val_ratio: float, seed: int) -> tuple[list[Example], list[Example]]:
    """Stratifiziert nach Typ."""
    rng = random.Random(seed)
    train, val = [], []
    for t in MAIL_TYPES:
        group = [e for e in examples if e.type == t]
        rng.shuffle(group)
        k = round(len(group) * val_ratio)
        val += group[:k]
        train += group[k:]
    rng.shuffle(train)
    rng.shuffle(val)
    return train, val


def _write(path: Path, examples: list[Example]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for e in examples:
            f.write(json.dumps({**asdict(e), "fields": e.fields.model_dump()}, ensure_ascii=False) + "\n")


def main() -> None:
    root = Path(__file__).resolve().parents[2] / "data"
    train, val = split(generate(150, seed=42), 0.2, seed=42)
    _write(root / "train.jsonl", train)
    _write(root / "val.jsonl", val)
    print(f"train: {len(train)}, val: {len(val)}")


if __name__ == "__main__":
    main()
