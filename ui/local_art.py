"""Optional text-to-image generation on the caregiver's own computer."""
import base64
import hashlib
import json
from PyQt6.QtCore import QObject, QTimer, QUrl, pyqtSignal
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PyQt6.QtGui import QImage
from ui.card_words import picture_dir


class LocalArt(QObject):
    changed = pyqtSignal()

    def __init__(self, parent):
        super().__init__(parent)
        self.network = QNetworkAccessManager(self)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.generate)
        self.word = ""
        self.reply = None
        self.status = ""

    def key(self):
        return "photo_" + hashlib.sha256(("local-art-v1:" + self.word).encode()).hexdigest()

    def picture(self):
        if self.word and (picture_dir() / (self.key()+".png")).exists():
            return self.key()
        return ""

    def request(self, word):
        if word == self.word:
            return
        self.word = word
        self.timer.stop()
        if self.reply:
            reply, self.reply = self.reply, None
            reply.abort()
        self.status = ""
        if word and not self.picture():
            self.timer.start(1200)

    def generate(self):
        word = self.word
        req = QNetworkRequest(QUrl("http://127.0.0.1:7860/sdapi/v1/txt2img"))
        req.setTransferTimeout(120000)
        req.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,QNetworkRequest.RedirectPolicy.ManualRedirectPolicy)
        req.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader,"application/json")
        payload = dict(prompt=f"A simple recognizable AAC picture of {word}, one centered subject, plain white background, flat illustration, no lettering",
                       negative_prompt="words, captions, collage",width=512,height=512,steps=16,batch_size=1)
        reply = self.network.post(req,json.dumps(payload).encode())
        self.reply = reply
        self.status = "Generating a local illustration…"
        self.changed.emit()

        def finished():
            try:
                if self.reply is not reply or self.word != word:
                    return
                self.reply = None
                self.status = "Category picture suggested. You can choose another picture or upload one."
                if reply.error() == QNetworkReply.NetworkError.NoError:
                    data = json.loads(bytes(reply.readAll()))["images"][0]
                    image = QImage.fromData(base64.b64decode(data.split(",")[-1]))
                    if not image.isNull() and image.save(str(picture_dir()/(self.key()+".png"))):
                        self.status = "Generated illustration. Check that it represents the word."
                self.changed.emit()
            except (ValueError, KeyError, IndexError, OSError):
                self.status = "Using the category picture."
                self.changed.emit()
            finally:
                reply.deleteLater()
        reply.finished.connect(finished)
