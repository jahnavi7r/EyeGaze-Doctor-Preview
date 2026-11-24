from pathlib import Path
import hashlib
import uuid
from PyQt6.QtGui import QImage
from PyQt6.QtCore import Qt, QStandardPaths
from PyQt6.QtWidgets import QWidget, QTabWidget, QFileDialog, QHBoxLayout, QScrollArea, QVBoxLayout, QAbstractItemView
from ui.local_art import LocalArt
from ui.card_words import words_for, draw_concept
from ui.dwell_card import DwellCard
from ui.theme import CARD_PALETTE
from ui.symbols import get_icon
from PyQt6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFormLayout, QLabel, QLineEdit, QListWidget, QMessageBox, QPushButton)
from audio.custom_voice import render_wave
from nlp.languages import LANGUAGES
from ui.symbols import ICON_DIR


def sentence_for(lang, category, label):
    templates = {
        "en": ("I want {}.", "I want to go to {}.", "I have pain in this area: {}.", "I need help with {}."),
        "te": ("నాకు {} కావాలి.", "నేను {} వెళ్లాలి.", "నాకు {} దగ్గర నొప్పిగా ఉంది.", "నాకు {} విషయంలో సహాయం కావాలి."),
        "hi": ("मुझे {} चाहिए।", "मुझे {} जाना है।", "मुझे {} में दर्द है।", "मुझे {} में मदद चाहिए।"),
    }
    return templates[lang][{"go": 1, "pain": 2, "help": 3}.get(category, 0)].format(label)


def symbol_for(category, label):
    words = label.casefold().strip()
    if words in ("tea", "టీ", "చాయ్", "चाय", "coffee", "కాఫీ", "कॉफी"):
        return "cup"
    if words in ("upma", "ఉప్మా", "उपमा"):
        return "upma"
    for language in LANGUAGES.values():
        for entry in language["menu"]:
            for item in [entry, *entry.get("items", [])]:
                if item["label"].casefold() == words and (ICON_DIR / (item["id"] + ".png")).exists():
                    return item["id"]
    return category if (ICON_DIR / (category + ".png")).exists() else "something_else"


# Concept-indexed local vocabulary. Unknown translations are entered by the caregiver.
def vocabulary(category):
    rows = [dict(en="Upma", te="ఉప్మా", hi="उपमा"), dict(en="Tea", te="టీ", hi="चाय"),
            dict(en="Coffee", te="కాఫీ", hi="कॉफी"), dict(en="Milk", te="పాలు", hi="दूध")]
    concepts = {}
    for code, lang in LANGUAGES.items():
        for entry in lang["menu"]:
            for item in [entry, *entry.get("items", [])]:
                concepts.setdefault((entry["id"], item["id"]), {})[code] = item["label"]
    return rows + [v for (group, _), v in concepts.items() if group == category and len(v) == 3]


class CaregiverDialog(QDialog):
    def __init__(self, owner, parent):
        super().__init__(parent)
        self.store = owner.preferences
        self.setWindowTitle("Caregiver settings")
        self.setMinimumWidth(460)
        self.setStyleSheet("QDialog {background:#14161D;} QLabel {color:#DDE3EA;} QPushButton,QComboBox,QDoubleSpinBox,QLineEdit {padding:5px;}")
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        panel = QWidget()
        scroll.setWidget(panel)
        form = QFormLayout(panel)
        self.resize(640,min(800,self.screen().availableGeometry().height()-60))
        self.pending = {}
        self.art = LocalArt(self)
        self.art.changed.connect(self.update_example)

        speed = QDoubleSpinBox()
        speed.setRange(.4, 4)
        speed.setDecimals(1)
        speed.setSingleStep(.1)
        speed.setSuffix(" s")
        speed.setValue(owner.dwell_ms / 1000)
        speed.valueChanged.connect(lambda v: owner.change_speed(round(v * 1000)))
        form.addRow("Selection dwell time", speed)
        self.language, self.category, self.symbol = QComboBox(), QComboBox(), QComboBox()
        for code, lang in LANGUAGES.items():
            self.language.addItem(lang["name"], code)
        self.language.setCurrentIndex(self.language.findData((owner.lang or LANGUAGES["en"])["code"]))
        form.addRow("Settings list language", self.language)
        form.addRow("Category", self.category)
        self.tabs = QTabWidget()
        self.fields = {}
        for code in ("en", "te", "hi"):
            pane = QWidget()
            layout = QFormLayout(pane)
            label, override, example = QLineEdit(), QLineEdit(), QLabel()
            label.setMaxLength(48)
            override.setMaxLength(240)
            example.setTextFormat(Qt.TextFormat.PlainText)
            example.setWordWrap(True)
            layout.addRow("Card label", label)
            layout.addRow("Sentence override", override)
            layout.addRow("Will say", example)
            self.tabs.addTab(pane, LANGUAGES[code]["name"])
            self.fields[code] = label, override, example
            label.textEdited.connect(lambda text, c=code: self.translate(c, text))
            label.editingFinished.connect(lambda c=code: self.commit_script(c))
            override.textChanged.connect(self.update_example)
        form.addRow("Three language versions", self.tabs)
        self.notice = QLabel("Enter a label. Review all three language tabs before saving.")
        self.notice.setWordWrap(True)
        form.addRow(self.notice)
        self.symbol.addItem("Automatic", "")
        for path in sorted(ICON_DIR.glob("*.png")):
            self.symbol.addItem(path.stem.replace("_", " ").title(), path.stem)
        form.addRow("Picture", self.symbol)
        self.preview = QLabel()
        form.addRow("Selected picture", self.preview)
        upload = QPushButton("Use a photo or drawing…")
        upload.clicked.connect(self.choose_photo)
        form.addRow(upload)
        self.symbol.currentIndexChanged.connect(self.update_example)
        self.save = QPushButton("Create card in all three languages")
        form.addRow(self.save)
        self.list = QListWidget()
        review = QHBoxLayout()
        self.list.setMinimumHeight(105)
        review.addWidget(self.list,1)
        self.sample = DwellCard("", bg_color=CARD_PALETTE[0],font_px=22)
        self.sample.setMinimumSize(145,105)
        self.sample.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        review.addWidget(self.sample,1)
        self.sample.hide()
        form.addRow("Custom cards in category", review)
        self.remove = QPushButton("Delete selected card")
        form.addRow(self.remove)
        self.list.currentRowChanged.connect(self.select_saved)
        self.save.clicked.connect(self.add_card)
        self.remove.clicked.connect(self.delete_card)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.accept)
        outer.addWidget(buttons)
        self.language.currentIndexChanged.connect(self.load_categories)
        self.category.currentIndexChanged.connect(self.refresh)
        self.tabs.setCurrentIndex(list(self.fields).index(self.language.currentData()))
        self.load_categories()

    def load_categories(self):
        self.category.blockSignals(True)
        self.category.clear()
        for entry in LANGUAGES[self.language.currentData()]["menu"]:
            self.category.addItem(entry["label"], entry["id"])
        self.category.setCurrentIndex(self.category.findData("food"))
        self.category.blockSignals(False)
        self.refresh()

    def translate(self, code, text):
        match = words_for(text, vocabulary(self.category.currentData())) if text.strip() else {}
        last = getattr(self, "suggested", {})
        self.pending.pop(code, None)
        if match and text.isascii() and code != "en":
            self.pending[code] = match[code]
        for other, (field, _, _) in self.fields.items():
            if other != code and (not field.text() or field.text() == last.get(other)):
                field.setText(match.get(other, ""))
                self.pending.pop(other,None)
        self.suggested = match
        self.update_example()

    def commit_script(self, code):
        if code in self.pending:
            self.fields[code][0].setText(self.pending.pop(code))
            self.update_example()

    def select_saved(self, row):
        selected = 0 <= row < len(getattr(self,"rows",[]))
        self.remove.setEnabled(selected)
        self.sample.setVisible(selected)
        if selected:
            item = self.rows[row]
            self.sample.icon_name = item["icon"]
            self.sample.setText(item["label"])
            self.sample.setAccessibleName(item["label"])

    def icon_name(self):
        category = self.category.currentData()
        text = self.fields["en"][0].text().strip()
        icon = symbol_for(category,text)
        choice = self.symbol.currentData()
        matched = draw_concept(text) if text and not choice and icon in (category,"something_else") else ""
        unknown = text if text and not choice and not matched and icon in (category,"something_else") else ""
        self.art.request(unknown)
        return choice or matched or self.art.picture() or icon

    def choose_photo(self):
        file, _ = QFileDialog.getOpenFileName(self, "Card picture", "", "Pictures (*.png *.jpg *.jpeg)")
        if not file:
            return
        image = QImage(file)
        if image.isNull():
            QMessageBox.warning(self, "Picture", "This picture could not be opened.")
            return
        folder = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)) / "pictures"
        key = "photo_" + hashlib.sha256(Path(file).read_bytes()).hexdigest()
        folder.mkdir(parents=True, exist_ok=True)
        if not image.scaled(320, 320, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation).save(str(folder / (key + ".png"))):
            QMessageBox.warning(self, "Picture", "The picture could not be saved.")
            return
        self.symbol.addItem(Path(file).stem, key)
        self.symbol.setCurrentIndex(self.symbol.count()-1)

    def update_example(self):
        for code, (label, override, example) in self.fields.items():
            name = self.pending.get(code, label.text()).strip()
            example.setText((override.text().strip() or sentence_for(code, self.category.currentData(), name)) if name else "")
        complete = all(label.text().strip() for label, _, _ in self.fields.values())
        self.save.setEnabled(complete)
        self.notice.setText("Review the suggested spellings, sentences and picture, then create." if complete else "Enter missing labels in the language tabs. Known words fill automatically.")
        pix = get_icon(self.icon_name())
        if self.art.status:
            self.notice.setText(self.art.status)
        if pix:
            self.preview.setPixmap(pix.scaled(64,64,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))

    def refresh(self):
        self.list.clear()
        self.rows = self.store.cards(self.language.currentData(), self.category.currentData())
        self.list.addItems([r["label"] for r in self.rows])
        self.list.setCurrentRow(0 if self.rows else -1)
        self.select_saved(self.list.currentRow())
        self.update_example()

    def add_card(self):
        for code in list(self.pending):
            self.commit_script(code)
        group, category, icon = uuid.uuid4().hex, self.category.currentData(), self.icon_name()
        try:
            with self.store.db:
                for lang, (field, _, example) in self.fields.items():
                    label, sentence = field.text().strip(), example.text()
                    audio = render_wave(sentence, lang)
                    old = self.store.db.execute("SELECT id,family FROM card WHERE lang=? AND category=? AND lower(label)=lower(?)", (lang,category,label)).fetchall()
                    if len(old) > 1 or any(family for _, family in old):
                        raise ValueError(f"A card named {label} already exists in this category.")
                    if old:
                        self.store.db.execute("UPDATE card SET sentence=?,wav=?,icon=?,family=? WHERE id=?", (sentence,audio,icon,group,old[0][0]))
                    else:
                        self.store.db.execute("INSERT INTO card(lang,category,label,sentence,wav,icon,family) VALUES(?,?,?,?,?,?,?)", (lang,category,label,sentence,audio,icon,group))
        except Exception as exc:
            QMessageBox.warning(self, "Could not save card", str(exc))
            return
        for label, override, _ in self.fields.values():
            label.clear()
            override.clear()
        self.suggested = {}
        self.symbol.setCurrentIndex(0)
        self.refresh()
        record = self.store.db.execute("SELECT id FROM card WHERE family=? AND lang=?",(group,self.language.currentData())).fetchone()
        if record:
            self.list.setCurrentRow(next(i for i,r in enumerate(self.rows) if r["id"] == f"custom-{record[0]}"))

    def delete_card(self):
        row = self.list.currentRow()
        if row < 0:
            return
        item = self.rows[row]
        if QMessageBox.question(self, "Delete card", f"Delete {item['label']} and its linked translations?") != QMessageBox.StandardButton.Yes:
            return
        with self.store.db:
            self.store.db.execute("DELETE FROM card WHERE id=? OR family=(SELECT family FROM card WHERE id=?)", (int(item["id"][7:]),)*2)
        self.refresh()
