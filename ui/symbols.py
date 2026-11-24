"""Picture symbols for the cards.

Symbols are PNG files in assets/symbols/, named after the card id
(water.png, head.png, yes.png ...).  Most come from Mulberry Symbols
(CC BY-SA 4.0, https://mulberrysymbols.org, by Steve Lee and contributors).
A card whose picture is missing simply shows its text only.

"pain_back" (pain in the back of the body) is stored inside this file, so no
extra picture file is needed.
"""
import base64
from pathlib import Path
from PyQt6.QtGui import QPixmap

ICON_DIR = Path(__file__).resolve().parent.parent / "assets" / "symbols"

_PAIN_BACK_PNG = (
    "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"
    "170AAAAASUVORK5CYII="
)
EMBEDDED = {"pain_back": _PAIN_BACK_PNG}
_cache = {}


def get_icon(name):
    """Return a QPixmap for a card id, or None if there is no picture for it."""
    if not name:
        return None
    if name not in _cache:
        pm = None
        if name in EMBEDDED:
            pm = QPixmap()
            pm.loadFromData(base64.b64decode(EMBEDDED[name]), "PNG")
        else:
            path = ICON_DIR / f"{name}.png"
            if name.startswith("photo_") and len(name) == 70 and all(c in "0123456789abcdef" for c in name[6:]):
                from PyQt6.QtCore import QStandardPaths
                root = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
                path = Path(root) / "pictures" / f"{name}.png"
            if path.exists():
                pm = QPixmap(str(path))
        _cache[name] = pm if (pm is not None and not pm.isNull()) else None
    return _cache[name]