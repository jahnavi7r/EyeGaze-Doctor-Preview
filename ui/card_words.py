"""Local word matching, script suggestions and picture rendering."""
import json
import re
import hashlib
import zipfile
from functools import lru_cache
from pathlib import Path
from PyQt6.QtCore import Qt, QStandardPaths
from PyQt6.QtGui import QImage, QPainter
from ui.symbols import ICON_DIR

ARCHIVE = ICON_DIR.parent / "card-art.zip"


@lru_cache(maxsize=1)
def concepts():
    with zipfile.ZipFile(ARCHIVE) as z:
        return json.loads(z.read("words.json"))


def words_for(text, vocabulary):
    word = text.strip().casefold()
    if word == "ukma":
        word = "upma"
    for row in vocabulary:
        if word and word in (x.casefold() for x in row.values()):
            return row
    for row in concepts():
        if word and any(word == row[k].casefold() for k in ("en", "hi", "te")):
            return {k: row[k] or phonetic(row["en"], k) for k in ("en","te","hi")}
    return {k: phonetic(text.strip(), k) for k in ("en", "te", "hi")} if word.isascii() else {}


def phonetic(text, code):
    if code == "en":
        return text
    vowels = dict(zip("a aa i ee ii u oo uu e ai o au".split(), ["अ","आ","इ","ई","ई","उ","ऊ","ऊ","ए","ऐ","ओ","औ"]))
    marks = dict(zip(vowels, ["","ा","ि","ी","ी","ु","ू","ू","े","ै","ो","ौ"]))
    consonants = dict(zip("kh gh chh ch jh th dh ph bh sh ng ny k g c j t d n p b m y r l v w s h f z q x".split(),
                         "ख घ छ च झ थ ध फ भ श ङ ञ क ग क ज त द न प ब म य र ल व व स ह फ ज क क्स".split()))
    tokens = re.findall("|".join(sorted([*vowels,*consonants],key=len,reverse=True))+"|.", text.casefold())
    out = ""
    pending = False
    for token in tokens:
        if token in vowels:
            out += marks[token] if pending else vowels[token]
            pending = False
        elif token in consonants:
            out += ("्" if pending else "") + consonants[token]
            pending = True
        else:
            out += token
            pending = False
    if code == "te":
        out = "".join(chr(ord(c)+0x300) if 0x905<=ord(c)<=0x94d else c for c in out)
    return out


def picture_dir():
    folder = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)) / "pictures"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


@lru_cache(maxsize=256)
def draw_concept(text):
    words = re.findall(r"[a-z]+", text.casefold())
    if not words:
        return ""
    phrase = " ".join(words)
    entries = concepts()
    exact = next((r for r in entries if r["en"].casefold()==phrase), None)
    matches = [exact] if exact else []
    if not exact:
        for word in words:
            candidates = [r for r in entries if word in re.findall(r"[a-z]+",r["en"].casefold()) or word in r["tags"]]
            if candidates:
                best = min(candidates,key=lambda r:(r["en"].lower()!=word,word not in r["en"].lower().split(),len(r["en"])))
                if best not in matches: matches.append(best)
    if not matches:
        return ""
    matches = matches[:2]
    key = "photo_"+hashlib.sha256(("art-v1:"+"+".join(r["id"] for r in matches)).encode()).hexdigest()
    dest = picture_dir() / (key+".png")
    if not dest.exists():
        image = QImage(192,192,QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        try:
            with zipfile.ZipFile(ARCHIVE) as z:
                for i,row in enumerate(matches):
                    from PyQt6.QtSvg import QSvgRenderer
                    from PyQt6.QtCore import QByteArray,QRectF
                    renderer = QSvgRenderer(QByteArray(z.read(row["id"]+".svg")))
                    box = QRectF(8,8,176,176) if len(matches)==1 else QRectF(8+i*85,25+i*48,100,100)
                    renderer.render(painter,box)
        finally:
            painter.end()
        if not image.save(str(dest)):
            return ""
    return key
