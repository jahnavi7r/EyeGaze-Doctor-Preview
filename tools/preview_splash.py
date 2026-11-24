import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtWidgets import QApplication
from ui.splash import SplashPage

app = QApplication(sys.argv)
splash = SplashPage()
splash.resize(1280, 720)
splash.setWindowTitle("Splash preview")
splash.finished.connect(app.quit)
splash.show()
splash.start()
sys.exit(app.exec())