"""Device-local doctor-preview preferences, cards and their offline audio."""
from pathlib import Path
import sqlite3
from PyQt6.QtCore import QStandardPaths

WORDS = {
    "en": ("Dwell time", "My cards", "Add card", "Faster", "Slower", "Default", "Card label", "Spoken sentence", "Save", "Cancel"),
    "te": ("ఎంపిక సమయం", "నా కార్డులు", "కార్డు జోడించు", "వేగంగా", "నెమ్మదిగా", "డిఫాల్ట్", "కార్డు పేరు", "చెప్పే వాక్యం", "సేవ్", "రద్దు"),
    "hi": ("चयन समय", "मेरे कार्ड", "कार्ड जोड़ें", "तेज़", "धीमा", "डिफ़ॉल्ट", "कार्ड का नाम", "बोला जाने वाला वाक्य", "सहेजें", "रद्द करें"),
}


class Preferences:
    def __init__(self):
        root = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))
        root.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(root / "aac-personal.sqlite3")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS preference (name TEXT PRIMARY KEY, value INTEGER);
            CREATE TABLE IF NOT EXISTS card (
                id INTEGER PRIMARY KEY, lang TEXT, category TEXT, label TEXT, sentence TEXT, wav BLOB);
            CREATE INDEX IF NOT EXISTS card_scope ON card(lang, category, id);
        """)

        if "icon" not in {row[1] for row in self.db.execute("PRAGMA table_info(card)")}:
            with self.db:
                self.db.execute("ALTER TABLE card ADD COLUMN icon TEXT")

        if "family" not in {r[1] for r in self.db.execute("PRAGMA table_info(card)")}:
            with self.db:
                self.db.execute("ALTER TABLE card ADD COLUMN family TEXT")
        self.db.execute("CREATE UNIQUE INDEX IF NOT EXISTS card_language ON card(family,lang)")

    def dwell(self):
        row = self.db.execute("SELECT value FROM preference WHERE name='dwell'").fetchone()
        return row[0] if row else 1300

    def set_dwell(self, value):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO preference VALUES ('dwell', ?)", (value,))

    def cards(self, lang, category=None):
        from ui.caregiver import symbol_for
        sql = "SELECT id,label,category,icon FROM card WHERE lang=?"
        args = [lang]
        if category is not None:
            sql += " AND category=?"
            args.append(category)
        rows = self.db.execute(sql + " ORDER BY id", args)
        return [dict(id=f"custom-{key}", label=name, icon=icon or symbol_for(group, name))
                for key, name, group, icon in rows]

    def message(self, key, lang):
        from audio.custom_voice import render_wave
        from ui.caregiver import sentence_for, symbol_for
        ident = int(key[7:])
        row = self.db.execute("SELECT sentence,wav,label,category,icon FROM card WHERE id=? AND lang=?",
                              (ident, lang)).fetchone()
        if row is None:
            return None
        sentence, audio, label, category, icon = row
        if icon is None and sentence.strip() == label.strip():
            sentence = sentence_for(lang, category, label)
            audio = render_wave(sentence, lang)
            with self.db:
                self.db.execute("UPDATE card SET sentence=?,wav=?,icon=? WHERE id=?",
                                (sentence, audio, symbol_for(category,label), ident))
        return sentence, audio
