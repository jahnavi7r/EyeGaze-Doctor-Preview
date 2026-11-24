import sys
import cv2
import numpy as np
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QThread, pyqtSignal
from ui.main_window import AACMainWindow
from ui.calibration_widget import CalibrationOverlay
from core.eye_tracker import DualModalityEyeTracker, configure_bell
from ui.bell_button import bell_fraction


class GazeTrackingThread(QThread):
    gaze_updated = pyqtSignal(int, int, bool)
    frame_updated = pyqtSignal(np.ndarray)

    def __init__(self, screen_w, screen_h):
        super().__init__()
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.running = True
        self.tracker = DualModalityEyeTracker()

    def open_camera(self):
        print("[Camera Init] Connecting directly to primary webcam...")
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(0)

        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            cap.set(cv2.CAP_PROP_FPS, 30)
            return cap

        return None

    def run(self):
        cap = self.open_camera()
        if cap is None:
            err_img = np.zeros((120, 180, 3), dtype=np.uint8)
            cv2.putText(err_img, "Camera Blocked", (15, 65),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
            self.frame_updated.emit(err_img)
            return

        while self.running:
            ret, frame = cap.read()
            if not ret or frame is None:
                self.msleep(10)
                continue

            gaze_coords, debug_frame, is_blinking = self.tracker.process_frame(
                frame, self.screen_w, self.screen_h
            )

            if debug_frame is not None:
                self.frame_updated.emit(debug_frame)

            if gaze_coords is not None:
                self.gaze_updated.emit(gaze_coords[0], gaze_coords[1], is_blinking)

            self.msleep(15)

        cap.release()

    def stop(self):
        self.running = False
        self.wait()


def main():
    if sys.platform.startswith("linux"):
        import os
        from espeakng_loader import get_data_path
        os.environ.setdefault("ESPEAK_DATA_PATH", get_data_path())
    app = QApplication(sys.argv)
    app.setApplicationName("EyeGazeCommunication")
    window = AACMainWindow()
    window.show()

    if "--mouse-only" in sys.argv:
        window.stage = "running"
        window.cam_preview.setText("Mouse only")
        if window.cursor_overlay:
            window.cursor_overlay.hide()
        window.render_language_menu()
        sys.exit(app.exec())

    screen_geometry = app.primaryScreen().geometry()
    screen_w = screen_geometry.width()
    screen_h = screen_geometry.height()
    configure_bell(*bell_fraction(screen_w, screen_h))

    tracker_thread = GazeTrackingThread(screen_w, screen_h)
    tracker_thread.gaze_updated.connect(window.update_gaze_point)
    tracker_thread.frame_updated.connect(window.update_camera_preview)

    # 9-point calibration. Start-up order:
    #   splash (in the window) -> calibration -> language page -> menus
    # The window asks for calibration when its splash ends (and when C is pressed).
    calib = CalibrationOverlay(tracker_thread.tracker, screen_w, screen_h)

    def on_calibration_finished(accuracy):
        if accuracy is None:
            print("Calibration failed - press C to try again")
        window.on_calibration_done(accuracy)

    calib.settings_requested.connect(lambda: window.open_settings(calib))
    calib.finished.connect(on_calibration_finished)
    window.recalibrate_requested.connect(calib.start)

    tracker_thread.start()
    window.start_flow()              # begins with the LooknVoice splash

    app.aboutToQuit.connect(tracker_thread.stop)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()