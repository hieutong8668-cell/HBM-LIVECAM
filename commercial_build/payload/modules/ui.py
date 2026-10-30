"""PySide6 UI for Deep-Live-Cam.

Public API kept stable for the rest of the codebase:
    init(start, destroy, lang) -> _Window
        Returned object has .mainloop() that core.py calls.
    update_status(text)
        Thread-safe; routed through Qt signal when called off-UI.
    check_and_ignore_nsfw(target, destroy=None) -> bool
"""

from __future__ import annotations

import os
import platform
import queue
import sys
import tempfile
import threading
import time
import webbrowser
from typing import Callable, List, Optional, Tuple

import cv2
import numpy as np
import requests
from PIL import Image, ImageOps
from PySide6.QtCore import (
    QObject,
    QThread,
    QTimer,
    Qt,
    Signal,
)
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

import modules.globals
import modules.metadata
import modules.licensing
import modules.device_identity
from modules.capturer import get_video_frame, get_video_frame_total
from modules.face_analyser import (
    add_blank_map,
    detect_many_faces_fast,
    detect_one_face_fast,
    ensure_landmarks,
    get_one_face,
    get_unique_faces_from_target_image,
    get_unique_faces_from_target_video,
    has_valid_map,
    reset_face_analyser,
    simplify_maps,
)
from modules.gettext import LanguageManager
from modules.gpu_processing import gpu_cvt_color, gpu_flip, gpu_resize
from modules.processors.frame.core import get_frame_processors_modules
from modules.utilities import (
    has_image_extension,
    is_image,
    is_video,
)
from modules import imread_unicode
from modules.video_capture import VideoCapturer
from modules.portrait import compose_portrait

if platform.system() == "Windows":
    from pygrabber.dshow_graph import FilterGraph

import json


# --- constants ------------------------------------------------------------

ROOT_HEIGHT = 640
ROOT_WIDTH = 600

PREVIEW_MAX_HEIGHT = 700
PREVIEW_MAX_WIDTH = 1200
PREVIEW_DEFAULT_WIDTH = 640
PREVIEW_DEFAULT_HEIGHT = 360

POPUP_WIDTH = 750
POPUP_HEIGHT = 810
POPUP_SCROLL_WIDTH = 720
POPUP_SCROLL_HEIGHT = 700

POPUP_LIVE_WIDTH = 900
POPUP_LIVE_HEIGHT = 820
POPUP_LIVE_SCROLL_WIDTH = 870
POPUP_LIVE_SCROLL_HEIGHT = 700

MAPPER_PREVIEW_SIZE = 100
SOURCE_TARGET_PREVIEW_SIZE = 110


# --- modern dark stylesheet -----------------------------------------------

QSS = """
QMainWindow, QDialog {
    background-color: #070b16;
    color: #e5e7eb;
}
QWidget {
    color: #e5e7eb;
    font-family: "Segoe UI Variable", "Segoe UI", "Inter", "Helvetica Neue", Arial, sans-serif;
    font-size: 9.5pt;
}
QWidget#appRoot, QScrollArea#appScroll, QScrollArea#appScroll > QWidget > QWidget {
    background-color: #070b16;
}

QGroupBox {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #141b2e, stop:1 #0c1220);
    border: 1px solid #4a3d1c;
    border-radius: 18px;
    margin-top: 12px;
    padding: 10px 10px 9px 10px;
    font-weight: 700;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 12px;
    color: #f0d488;
    background-color: transparent;
    font-weight: 700;
}

QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #c9a227, stop:1 #f0d488);
    background-color: #c9a227;
    color: #171204;
    border: none;
    border-radius: 10px;
    padding: 7px 14px;
    font-weight: 700;
}
QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d4af37, stop:1 #f7e3ae); background-color: #d4af37; }
QPushButton:pressed { background: #a8892a; }
QPushButton:disabled { background: #2a2f3a; color: #8a8fa0; }
QPushButton#secondary {
    background-color: rgba(20, 27, 46, 0.92);
    color: #f5f1e6;
    border: 1px solid #4a3d1c;
}
QPushButton#secondary:hover { background-color: #1c2440; border-color: #d4af37; }
QPushButton#danger { background-color: #7a1f2b; }
QPushButton#danger:hover { background-color: #9c2836; }

QComboBox {
    background-color: rgba(20, 27, 46, 0.92);
    border: 1px solid #4a3d1c;
    border-radius: 10px;
    padding: 7px 12px;
    min-height: 28px;
}
QComboBox:hover { border-color: #d4af37; }
QComboBox:focus { border-color: #f0d488; }
QComboBox QAbstractItemView {
    background-color: #141a2b;
    selection-background-color: #8a6d1f;
    border: 1px solid #4a3d1c;
    padding: 4px;
}

QCheckBox {
    spacing: 10px;
    padding: 4px 0;
}
QCheckBox::indicator {
    width: 34px;
    height: 18px;
    border-radius: 9px;
    background-color: #232a3d;
    border: 1px solid #4a3d1c;
}
QCheckBox::indicator:checked {
    background-color: #c9a227;
    border-color: #f0d488;
}

QSlider::groove:horizontal {
    height: 6px;
    background: #232a3d;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #f0d488;
    width: 16px;
    height: 16px;
    margin: -5px 0;
    border-radius: 8px;
    border: 2px solid #c9a227;
}
QSlider::sub-page:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #c9a227, stop:1 #f0d488);
    border-radius: 3px;
}

QLabel#imageDrop {
    background-color: #0f172a;
    border: 2px dashed #334155;
    border-radius: 12px;
}
QLabel#statusLabel {
    color: #9ca3af;
    font-size: 10pt;
    font-style: italic;
}
QLabel#linkLabel {
    color: #93c5fd;
    text-decoration: underline;
}

QScrollArea { border: none; background: transparent; }

QFrame#card {
    background-color: rgba(16, 22, 38, 0.92);
    border: 1px solid #2c2440;
    border-radius: 16px;
}

QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 4px 0;
}
QScrollBar::handle:vertical {
    background: #374151;
    border-radius: 5px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover { background: #4b5563; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background: transparent;
    height: 10px;
    margin: 0 4px;
}
QScrollBar::handle:horizontal {
    background: #374151;
    border-radius: 5px;
    min-width: 30px;
}
QScrollBar::handle:horizontal:hover { background: #4b5563; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

QToolTip {
    background-color: #111827;
    color: #e5e7eb;
    border: 1px solid #374151;
    border-radius: 8px;
    padding: 6px 8px;
}

QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #0a1120;
    border: 1px solid #32415d;
    border-radius: 10px;
    padding: 5px 9px;
    selection-background-color: #4f46e5;
}
QFrame#heroCard, QFrame#activationCard {
    background-color: rgba(16, 22, 38, 0.92);
    border: 1px solid #4a3d1c;
    border-radius: 18px;
}
QLabel#heroTitle { color: #f5f1e6; font-size: 14pt; font-weight: 700; }
QLabel#heroSubtitle { color: #b8b0a0; font-size: 9pt; }
QLabel#badgePrimary {
    color: #f0d488; background-color: rgba(201, 162, 39, 0.14);
    border: 1px solid #8a6d1f; border-radius: 8px; padding: 4px 8px;
}
QLabel#badgeSuccess {
    color: #a7f3d0; background-color: rgba(22, 99, 78, 0.35);
    border: 1px solid #16634e; border-radius: 8px; padding: 4px 8px;
}
QLabel#sectionEyebrow { color: #d4af37; font-size: 9pt; font-weight: 700; letter-spacing: 1px; }
QLabel#deviceValue { color: #f5f1e6; font-size: 16pt; font-weight: 700; }
QLabel#activationHint { color: #b8b0a0; font-size: 10pt; }
QLabel#successText { color: #6ee7b7; font-weight: 600; }
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border-color: #818cf8;
}
"""


# --- module-level state ---------------------------------------------------

_APP: Optional[QApplication] = None
_MAIN: Optional["MainWindow"] = None
_PREVIEW: Optional["PreviewWindow"] = None
_WEBCAM_PREVIEW: Optional["WebcamPreviewWindow"] = None
# How long to wait quietly for a live-preview worker to notice the stop flag
# before saying so. Shutdown then keeps waiting: it has to finish.
WORKER_SHUTDOWN_GRACE_MS = 30000
_MAPPER: Optional["MapperDialog"] = None
_LIVE_MAPPER: Optional["LiveMapperDialog"] = None
_LANG: Optional[LanguageManager] = None
_BRIDGE: Optional["_UIBridge"] = None


def _(text: str) -> str:
    """Translate via LanguageManager; falls back to identity."""
    if _LANG is None:
        return text
    return _LANG._(text)


# Preserve original cwd state for file dialogs.
_RECENT_SOURCE_DIR: Optional[str] = None
_RECENT_TARGET_DIR: Optional[str] = None
_RECENT_OUTPUT_DIR: Optional[str] = None

# QFileDialog filter strings, built from the canonical extension sets in
# globals so every dialog stays in sync (no hand-copied lists to drift).
_IMAGE_FILE_FILTER = "Images (" + " ".join(
    f"*{ext}" for ext in modules.globals.IMAGE_EXTENSIONS
) + ")"
_MEDIA_FILE_FILTER = "Media (" + " ".join(
    f"*{ext}" for ext in (*modules.globals.IMAGE_EXTENSIONS, *modules.globals.VIDEO_EXTENSIONS)
) + ")"
_VIDEO_FILE_FILTER = "Videos (" + " ".join(
    f"*{ext}" for ext in modules.globals.VIDEO_EXTENSIONS
) + ")"


# --- image utilities -----------------------------------------------------


def fit_image_to_size(image, width: int, height: int):
    """BGR ndarray -> BGR ndarray scaled to fit within (width, height)."""
    if width is None and height is None or width <= 0 or height <= 0:
        return image
    h, w = image.shape[:2]
    ratio_w = width / w
    ratio_h = height / h
    ratio = min(ratio_w, ratio_h)
    new_size = (max(1, int(w * ratio)), max(1, int(h * ratio)))
    return gpu_resize(image, dsize=new_size)


def _bgr_to_qpixmap(bgr: np.ndarray) -> QPixmap:
    """Zero-copy BGR ndarray -> QPixmap."""
    h, w = bgr.shape[:2]
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    qimg = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888).copy()
    return QPixmap.fromImage(qimg)


def _pil_to_qpixmap(image: Image.Image) -> QPixmap:
    """PIL.Image -> QPixmap."""
    image = image.convert("RGBA")
    data = image.tobytes("raw", "RGBA")
    qimg = QImage(data, image.width, image.height, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qimg.copy())


def render_image_preview(image_path: str, size: Tuple[int, int]) -> QPixmap:
    image = Image.open(image_path)
    if size:
        image = ImageOps.fit(image, size, Image.LANCZOS)
    return _pil_to_qpixmap(image)


def render_video_preview(
    video_path: str, size: Tuple[int, int], frame_number: int = 0
) -> Optional[QPixmap]:
    capture = cv2.VideoCapture(video_path)
    try:
        if frame_number:
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        has_frame, frame = capture.read()
        if not has_frame:
            return None
        image = Image.fromarray(gpu_cvt_color(frame, cv2.COLOR_BGR2RGB))
        if size:
            image = ImageOps.fit(image, size, Image.LANCZOS)
        return _pil_to_qpixmap(image)
    finally:
        capture.release()


# --- persistence ---------------------------------------------------------


def save_switch_states():
    state = {
        "keep_fps": modules.globals.keep_fps,
        "keep_audio": modules.globals.keep_audio,
        "keep_frames": modules.globals.keep_frames,
        "many_faces": modules.globals.many_faces,
        "map_faces": modules.globals.map_faces,
        "poisson_blend": modules.globals.poisson_blend,
        "color_correction": modules.globals.color_correction,
        "nsfw_filter": modules.globals.nsfw_filter,
        "live_mirror": modules.globals.live_mirror,
        "live_resizable": modules.globals.live_resizable,
        "fp_ui": modules.globals.fp_ui,
        "show_fps": modules.globals.show_fps,
        "mouth_mask": modules.globals.mouth_mask,
        "show_mouth_mask_box": modules.globals.show_mouth_mask_box,
        "mouth_mask_size": modules.globals.mouth_mask_size,
        "capture_resolution": list(modules.globals.capture_resolution),
        "live_fps_limit": modules.globals.live_fps_limit,
        "det_size": modules.globals.det_size,
    }
    try:
        with open("switch_states.json", "w") as f:
            json.dump(state, f)
    except OSError:
        pass


def load_switch_states():
    try:
        with open("switch_states.json", "r") as f:
            state = json.load(f)
        modules.globals.keep_fps = state.get("keep_fps", True)
        modules.globals.keep_audio = state.get("keep_audio", True)
        modules.globals.keep_frames = state.get("keep_frames", False)
        modules.globals.many_faces = state.get("many_faces", False)
        modules.globals.map_faces = state.get("map_faces", False)
        modules.globals.poisson_blend = state.get("poisson_blend", False)
        modules.globals.color_correction = state.get("color_correction", False)
        modules.globals.nsfw_filter = state.get("nsfw_filter", False)
        modules.globals.live_mirror = state.get("live_mirror", False)
        modules.globals.live_resizable = state.get("live_resizable", False)
        modules.globals.fp_ui = state.get("fp_ui", {"face_enhancer": False})
        modules.globals.show_fps = state.get("show_fps", False)
        # Mouth mask always starts disabled (slider at 0) on launch,
        # regardless of the persisted value - enable it explicitly each session.
        modules.globals.mouth_mask_size = 0.0
        modules.globals.mouth_mask = False
        modules.globals.show_mouth_mask_box = False
        # Validate persisted camera settings before trusting them - a hand-
        # edited/corrupt file shouldn't push a bad size into cv2/insightface.
        res = state.get("capture_resolution")
        if isinstance(res, (list, tuple)) and len(res) == 2:
            try:
                w, h = int(res[0]), int(res[1])
                if w > 0 and h > 0:
                    modules.globals.capture_resolution = (w, h)
            except (TypeError, ValueError):
                pass
        if state.get("det_size") in (160, 320, 640):
            modules.globals.det_size = int(state["det_size"])
        if state.get("live_fps_limit") in (15, 24, 30):
            modules.globals.live_fps_limit = int(state["live_fps_limit"])
    except FileNotFoundError:
        pass
    except (OSError, json.JSONDecodeError):
        pass


# --- thread-safe status bridge -------------------------------------------


class _UIBridge(QObject):
    """Single QObject that owns cross-thread signals."""

    statusChanged = Signal(str)


def _emit_status(text: str) -> None:
    if _BRIDGE is None:
        print(text)
        return
    _BRIDGE.statusChanged.emit(text)


# --- public API ----------------------------------------------------------


def update_status(text: str) -> None:
    """Thread-safe status update - uses signal if called off-UI thread."""
    _emit_status(_(text))
    if _APP is not None and QThread.currentThread() is _APP.thread():
        # On UI thread - flush events so the user sees the update during
        # long synchronous start() runs.
        _APP.processEvents()


def check_and_ignore_nsfw(target, destroy: Optional[Callable] = None) -> bool:
    from numpy import ndarray
    from modules.predicter import predict_frame, predict_image, predict_video

    check_nsfw = None
    if isinstance(target, str):
        check_nsfw = predict_image if has_image_extension(target) else predict_video
    elif isinstance(target, ndarray):
        check_nsfw = predict_frame

    if check_nsfw and check_nsfw(target):
        if destroy:
            destroy(to_quit=False)
        update_status("Processing ignored!")
        return True
    return False


# --- camera enumeration (unchanged from tk version) ----------------------


def _collect_host_info() -> str:
    import platform as _platform
    import subprocess
    lines = []
    lines.append(f"OS: {_platform.system()} {_platform.release()} ({_platform.machine()})")
    lines.append(f"CPU: {_platform.processor() or 'Unknown'}")
    lines.append(f"Python: {_platform.python_version()}")
    try:
        import os as _os
        ram = "Unknown"
        if _platform.system() == "Windows":
            out = subprocess.check_output(
                ["wmic", "computersystem", "get", "TotalPhysicalMemory"],
                text=True, stderr=subprocess.DEVNULL,
            ).split()
            if len(out) >= 2:
                ram = f"{int(out[1]) // (1024**3)} GB"
        lines.append(f"RAM: {ram}")
    except Exception:
        pass
    try:
        if _platform.system() == "Windows":
            out = subprocess.check_output(
                ["wmic", "path", "win32_VideoController", "get", "name"],
                text=True, stderr=subprocess.DEVNULL,
            )
            gpus = [x.strip() for x in out.splitlines() if x.strip() and x.strip().lower() != "name"]
            if gpus:
                lines.append("GPU: " + "; ".join(gpus))
    except Exception:
        pass
    try:
        out = subprocess.check_output(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                                     text=True, stderr=subprocess.DEVNULL)
        smi = [x.strip() for x in out.splitlines() if x.strip()]
        if smi:
            lines.append("NVIDIA: " + "; ".join(smi))
    except Exception:
        pass
    return "\n".join(lines)


def get_available_cameras() -> Tuple[List[int], List[str]]:
    if platform.system() == "Windows":
        try:
            graph = FilterGraph()
            devices = graph.get_input_devices()
            if devices:
                return list(range(len(devices))), devices
            return [], ["No cameras found"]
        except Exception as exc:
            print(f"Error detecting cameras: {exc}")
            return [], ["No cameras found"]

    if platform.system() == "Darwin":
        return [0, 1], ["Camera 0", "Camera 1"]

    # Linux probe
    indices: List[int] = []
    names: List[str] = []
    for i in range(10):
        cap = cv2.VideoCapture(f"/dev/video{i}")
        if cap.isOpened():
            indices.append(i)
            names.append(f"Camera {i}")
            cap.release()
    return (indices, names) if names else ([], ["No cameras found"])


# --- main window ---------------------------------------------------------


def _make_image_drop(text: str, size: Tuple[int, int]) -> QLabel:
    label = QLabel(text)
    label.setObjectName("imageDrop")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setFixedSize(size[0], size[1])
    label.setText(text)
    return label


class _Switch(QWidget):
    """Compact toggle switch with label + optional tooltip."""

    toggled = Signal(bool)

    def __init__(self, text: str, initial: bool, tooltip: str = ""):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._checkbox = QCheckBox(text)
        self._checkbox.setChecked(initial)
        self._checkbox.toggled.connect(self.toggled.emit)
        if tooltip:
            self._checkbox.setToolTip(tooltip)
        layout.addWidget(self._checkbox)
        layout.addStretch(1)

    def isChecked(self) -> bool:
        return self._checkbox.isChecked()

    def setChecked(self, value: bool) -> None:
        self._checkbox.setChecked(value)


class ActivationDialog(QDialog):
    """Mandatory first-run activation shown before the product UI."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("HBM-LIVECAM - Kích hoạt thiết bị")
        self.setModal(True)
        self.setMinimumSize(720, 520)
        self.resize(760, 560)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 28, 30, 28)
        layout.setSpacing(18)

        eyebrow = QLabel("HBM  /  COMMERCIAL EDITION")
        eyebrow.setObjectName("sectionEyebrow")
        title = QLabel("Kích hoạt HBM-LIVECAM")
        title.setObjectName("heroTitle")
        intro = QLabel("Liên kết bản quyền thương mại với thiết bị này để bắt đầu sử dụng.")
        intro.setObjectName("heroSubtitle")
        layout.addWidget(eyebrow)
        layout.addWidget(title)
        layout.addWidget(intro)

        card = QFrame()
        card.setObjectName("activationCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 22, 24, 22)
        card_layout.setSpacing(14)

        device_caption = QLabel("MÃ THIẾT BỊ")
        device_caption.setObjectName("sectionEyebrow")
        card_layout.addWidget(device_caption)

        device_row = QHBoxLayout()
        self.device_id = QLineEdit(modules.device_identity.get_device_id())
        self.device_id.setReadOnly(True)
        self.device_id.setObjectName("deviceValue")
        self.device_id.setMinimumHeight(48)
        copy_button = QPushButton("Sao chép mã")
        copy_button.setObjectName("secondary")
        copy_button.setMinimumHeight(48)
        copy_button.clicked.connect(
            lambda: QApplication.clipboard().setText(self.device_id.text())
        )
        device_row.addWidget(self.device_id, 1)
        device_row.addWidget(copy_button)
        card_layout.addLayout(device_row)

        hint = QLabel("Gửi mã thiết bị này cho quản trị viên để nhận key riêng. Mỗi key chỉ dùng cho đúng một thiết bị.")
        hint.setObjectName("activationHint")
        hint.setWordWrap(True)
        card_layout.addWidget(hint)

        key_caption = QLabel("KEY KÍCH HOẠT")
        key_caption.setObjectName("sectionEyebrow")
        card_layout.addWidget(key_caption)

        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("Dán key đã được cấp vào đây")
        self.key_input.setMinimumHeight(48)
        self.key_input.returnPressed.connect(self._activate)
        card_layout.addWidget(self.key_input)

        actions = QHBoxLayout()
        secure = QLabel("●  Xác thực chữ ký số • Hoạt động ngoại tuyến")
        secure.setObjectName("successText")
        actions.addWidget(secure)
        actions.addStretch(1)
        activate_button = QPushButton("KÍCH HOẠT")
        activate_button.setMinimumSize(150, 48)
        activate_button.clicked.connect(self._activate)
        actions.addWidget(activate_button)
        card_layout.addLayout(actions)
        layout.addWidget(card)
        layout.addStretch(1)

        footer = QLabel("HBM-LIVECAM  •  GPU-FIRST PORTRAIT STUDIO")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setObjectName("heroSubtitle")
        layout.addWidget(footer)

    def _activate(self) -> None:
        if modules.licensing.activate(self.key_input.text()):
            QMessageBox.information(self, "HBM-LIVECAM", "Kích hoạt thành công.")
            self.accept()
            return
        QMessageBox.critical(
            self,
            "HBM-LIVECAM",
            "Key không hợp lệ hoặc không thuộc thiết bị này.",
        )


class MainWindow(QMainWindow):
    def __init__(self, start_cb: Callable, destroy_cb: Callable):
        super().__init__()
        load_switch_states()
        self._start_cb = start_cb
        self._destroy_cb = destroy_cb

        self.setWindowTitle(
            f"{modules.metadata.name} {modules.metadata.version} {modules.metadata.edition}"
        )
        self.setMinimumSize(560, 560)
        self.resize(ROOT_WIDTH, ROOT_HEIGHT)

        root = QWidget()
        root.setObjectName("appRoot")
        root.setMinimumWidth(540)
        scroll = QScrollArea()
        scroll.setObjectName("appScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setWidget(root)
        self.setCentralWidget(scroll)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(8, 7, 8, 8)
        layout.setSpacing(5)

        # Commercial product header
        hero = QFrame()
        hero.setObjectName("heroCard")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(10, 6, 10, 6)
        brand = QVBoxLayout()
        hero_title = QLabel("HBM  LIVECAM")
        hero_title.setObjectName("heroTitle")
        hero_subtitle = QLabel("GPU PORTRAIT STUDIO")
        hero_subtitle.setObjectName("heroSubtitle")
        brand.addWidget(hero_title)
        brand.addWidget(hero_subtitle)
        hero_layout.addLayout(brand)
        hero_layout.addStretch(1)
        gpu_badge = QLabel("● GPU")
        gpu_badge.setObjectName("badgeSuccess")
        output_badge = QLabel("9:16  /  720×1280")
        output_badge.setObjectName("badgePrimary")
        hero_layout.addWidget(gpu_badge)
        hero_layout.addWidget(output_badge)
        layout.addWidget(hero)

        # Source/Target row
        layout.addLayout(self._build_image_row())

        controls = QHBoxLayout()
        controls.setSpacing(8)
        controls.addWidget(self._build_options_card(), 3)
        controls.addWidget(self._build_sliders_card(), 2)
        layout.addLayout(controls)

        # Action buttons
        layout.addLayout(self._build_action_row())

        # Camera selection
        layout.addWidget(self._build_camera_card())

        # Status & footer
        self._status_label = QLabel("")
        self._status_label.setObjectName("statusLabel")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._status_label)


    # -- image row --------------------------------------------------------

    def _build_image_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        # Source column
        src_col = QVBoxLayout()
        self.source_label = _make_image_drop(_("Source face"), (SOURCE_TARGET_PREVIEW_SIZE, SOURCE_TARGET_PREVIEW_SIZE))
        src_col.addWidget(self.source_label, alignment=Qt.AlignmentFlag.AlignCenter)
        src_row = QHBoxLayout()
        self.btn_select_source = QPushButton(_("Select a face"))
        self.btn_select_source.setToolTip(
            _("Choose the source face image to swap onto the target")
        )
        self.btn_select_source.clicked.connect(self._on_select_source)
        src_row.addWidget(self.btn_select_source)
        src_col.addLayout(src_row)

        # Swap button column
        swap_col = QVBoxLayout()
        swap_col.addStretch(1)
        self.btn_swap = QPushButton("↔")
        self.btn_swap.setObjectName("secondary")
        self.btn_swap.setFixedSize(34, 34)
        self.btn_swap.setToolTip(_("Swap source and target images"))
        self.btn_swap.clicked.connect(self._on_swap_paths)
        swap_col.addWidget(self.btn_swap, alignment=Qt.AlignmentFlag.AlignCenter)
        swap_col.addStretch(1)

        # Target column
        tgt_col = QVBoxLayout()
        self.target_label = _make_image_drop(_("Target"), (SOURCE_TARGET_PREVIEW_SIZE, SOURCE_TARGET_PREVIEW_SIZE))
        tgt_col.addWidget(self.target_label, alignment=Qt.AlignmentFlag.AlignCenter)
        self.btn_select_target = QPushButton(_("Select a target"))
        self.btn_select_target.setToolTip(
            _("Choose the target image or video to apply face swap to")
        )
        self.btn_select_target.clicked.connect(self._on_select_target)
        tgt_col.addWidget(self.btn_select_target)

        row.addLayout(src_col)
        row.addLayout(swap_col)
        row.addLayout(tgt_col)
        return row

    # -- options card -----------------------------------------------------

    def _build_options_card(self) -> QGroupBox:
        card = QGroupBox(_("Options"))
        grid = QGridLayout(card)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(4)

        def make(field, label, tip):
            sw = _Switch(_(label), getattr(modules.globals, field), _(tip))
            sw.toggled.connect(
                lambda v, f=field: (
                    setattr(modules.globals, f, v),
                    save_switch_states(),
                )
            )
            return sw

        self.sw_keep_fps = make("keep_fps", "Keep fps",
                                "Output video keeps the original frame rate")
        self.sw_keep_audio = make("keep_audio", "Keep audio",
                                  "Copy audio track from the source video to output")
        self.sw_keep_frames = make("keep_frames", "Keep frames",
                                   "Keep extracted frames on disk after processing")
        self.sw_many_faces = make("many_faces", "Many faces",
                                  "Swap every detected face, not just the primary one")
        self.sw_poisson = make("poisson_blend", "Poisson Blend",
                               "Blend face edges smoothly using Poisson blending")
        self.sw_color_fix = make("color_correction", "Fix Blueish Cam",
                                 "Fix blue/green color cast from some webcams")
        self.sw_show_fps = make("show_fps", "Show FPS",
                                "Display frames-per-second counter on the live preview")

        # Map faces is special - closes mapper when toggled off.
        self.sw_map_faces = _Switch(_("Map faces"), modules.globals.map_faces,
                                    _("Manually assign which source face maps to which target face"))
        self.sw_map_faces.toggled.connect(self._on_map_faces_toggled)

        # Two-column control matrix inside the left dashboard pane.
        items = [
            self.sw_keep_fps, self.sw_keep_audio,
            self.sw_keep_frames, self.sw_many_faces,
            self.sw_map_faces, self.sw_show_fps,
            self.sw_poisson, self.sw_color_fix,
        ]
        for i, w in enumerate(items):
            grid.addWidget(w, i // 2, i % 2)

        # Face enhancer dropdown
        enhancer_label = QLabel(_("Face Enhancer:"))
        grid.addWidget(enhancer_label, 4, 0)

        self.cb_enhancer = QComboBox()
        self.cb_enhancer.addItems(["None", "GFPGAN", "GPEN-512", "GPEN-256"])
        initial = "None"
        if modules.globals.fp_ui.get("face_enhancer", False):
            initial = "GFPGAN"
        elif modules.globals.fp_ui.get("face_enhancer_gpen512", False):
            initial = "GPEN-512"
        elif modules.globals.fp_ui.get("face_enhancer_gpen256", False):
            initial = "GPEN-256"
        self.cb_enhancer.setCurrentText(initial)
        self.cb_enhancer.currentTextChanged.connect(self._on_enhancer_change)
        self.cb_enhancer.setToolTip(_("Select a face enhancement model (None = no enhancement)"))
        grid.addWidget(self.cb_enhancer, 4, 1)

        return card

    # -- sliders card -----------------------------------------------------

    def _build_sliders_card(self) -> QGroupBox:
        card = QGroupBox(_("Refinement"))
        grid = QGridLayout(card)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)

        def slider(min_v, max_v, default, denom, on_change):
            s = QSlider(Qt.Orientation.Horizontal)
            s.setRange(int(min_v * denom), int(max_v * denom))
            s.setValue(int(default * denom))
            s.valueChanged.connect(lambda iv: on_change(iv / denom))
            return s

        # Transparency
        grid.addWidget(QLabel(_("Transparency")), 0, 0)
        self.s_transparency = slider(0.0, 1.0, 1.0, 100, self._on_transparency_change)
        self.s_transparency.setToolTip(
            _("Blend between original and swapped face (0% = original, 100% = fully swapped)")
        )
        grid.addWidget(self.s_transparency, 0, 1)

        # Sharpness
        grid.addWidget(QLabel(_("Sharpness")), 1, 0)
        self.s_sharpness = slider(0.0, 5.0, 0.0, 10, self._on_sharpness_change)
        self.s_sharpness.setToolTip(_("Sharpen the enhanced face output"))
        grid.addWidget(self.s_sharpness, 1, 1)

        # Mouth mask - always starts at 0 (disabled) on launch
        grid.addWidget(QLabel(_("Mouth Mask")), 2, 0)
        self.s_mouth = slider(0.0, 100.0, 0.0, 1,
                              self._on_mouth_mask_change)
        self.s_mouth.sliderPressed.connect(self._on_mouth_mask_pressed)
        self.s_mouth.sliderReleased.connect(self._on_mouth_mask_released)
        self.s_mouth.setToolTip(
            _("0 = use swapped mouth, 100 = expose original mouth to chin area")
        )
        grid.addWidget(self.s_mouth, 2, 1)
        return card

    # -- action row -------------------------------------------------------

    def _build_action_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self.btn_start = QPushButton(_("Start"))
        self.btn_start.setToolTip(_("Begin processing the target image/video with selected face"))
        self.btn_start.clicked.connect(self._on_start)

        self.btn_destroy = QPushButton(_("Exit"))
        self.btn_destroy.setObjectName("danger")
        self.btn_destroy.setToolTip(_("Stop processing and close the application"))
        self.btn_destroy.clicked.connect(lambda: self._destroy_cb())

        self.btn_preview = QPushButton(_("Preview"))
        self.btn_preview.setObjectName("secondary")
        self.btn_preview.setToolTip(_("Show/hide a preview of the processed output"))
        self.btn_preview.clicked.connect(self._on_toggle_preview)

        self.btn_update = QPushButton(_("Check Update"))
        self.btn_update.setObjectName("secondary")
        self.btn_update.setToolTip(_("Check GitHub for a newer release"))
        self.btn_update.clicked.connect(self._on_check_update)

        row.addWidget(self.btn_start, 2)
        row.addWidget(self.btn_preview)
        row.addWidget(self.btn_update)
        row.addWidget(self.btn_destroy)
        return row

    # -- camera card ------------------------------------------------------

    def _build_camera_card(self) -> QGroupBox:
        card = QGroupBox(_("Camera"))
        grid = QGridLayout(card)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)

        # Row 0: camera selector + Live button
        grid.addWidget(QLabel(_("Select Camera:")), 0, 0)
        self._camera_indices, self._camera_names = get_available_cameras()

        self.cb_camera = QComboBox()
        if not self._camera_names or self._camera_names[0] == "No cameras found":
            self.cb_camera.addItem("No cameras found")
            self.cb_camera.setEnabled(False)
            cam_ok = False
        else:
            self.cb_camera.addItems(self._camera_names)
            cam_ok = True
        self.cb_camera.setToolTip(_("Select which camera to use for live mode"))
        grid.addWidget(self.cb_camera, 0, 1)

        self.btn_live = QPushButton(_("Live"))
        self.btn_live.setEnabled(cam_ok)
        self.btn_live.setToolTip(_("Start real-time face swap using webcam"))
        self.btn_live.clicked.connect(self._on_live)
        grid.addWidget(self.btn_live, 0, 2)

        self.btn_refresh_cameras = QPushButton(_("Refresh"))
        self.btn_refresh_cameras.setObjectName("secondary")
        self.btn_refresh_cameras.setToolTip(_("Rescan available cameras"))
        self.btn_refresh_cameras.clicked.connect(self._on_refresh_cameras)
        grid.addWidget(self.btn_refresh_cameras, 0, 3)

        grid.setColumnStretch(1, 1)
        return card

    def _on_resolution_change(self, idx: int) -> None:
        if 0 <= idx < len(self._resolution_options):
            _label, wh = self._resolution_options[idx]
            modules.globals.capture_resolution = wh
            save_switch_states()
            # Pre-translate the static template; append the dynamic size after
            # so the message still participates in localization (update_status
            # only translates whole-string keys).
            update_status(
                _("Capture resolution set (applies on next Live start):")
                + f" {wh[0]}x{wh[1]}"
            )

    def _on_det_size_change(self, idx: int) -> None:
        if 0 <= idx < len(self._det_size_options):
            v = self._det_size_options[idx]
            modules.globals.det_size = v
            reset_face_analyser()
            save_switch_states()
            update_status(
                _("Face detection size set (analyser re-inits on next call):")
                + f" {v}x{v}"
            )

    def _on_live_fps_change(self, idx: int) -> None:
        value = self.cb_live_fps.itemData(idx)
        if value in (15, 24, 30):
            modules.globals.live_fps_limit = int(value)
            save_switch_states()
            update_status(
                _("Live FPS limit set (applies on next Live start):")
                + f" {value}"
            )

    # -- slot handlers ----------------------------------------------------

    def set_status(self, text: str) -> None:
        self._status_label.setText(text)

    def _on_select_source(self) -> None:
        global _RECENT_SOURCE_DIR
        if _PREVIEW is not None:
            _PREVIEW.hide()
        path, _filter = QFileDialog.getOpenFileName(
            self, _("select an source image"),
            _RECENT_SOURCE_DIR or "",
            _IMAGE_FILE_FILTER,
        )
        if path and is_image(path):
            modules.globals.source_path = path
            _RECENT_SOURCE_DIR = os.path.dirname(path)
            self.source_label.setPixmap(render_image_preview(path, (SOURCE_TARGET_PREVIEW_SIZE, SOURCE_TARGET_PREVIEW_SIZE)))
            self.source_label.setText("")
        elif not path:
            return
        else:
            modules.globals.source_path = None
            self.source_label.clear()
            self.source_label.setText(_("Source face"))

    def _on_select_target(self) -> None:
        global _RECENT_TARGET_DIR
        if _PREVIEW is not None:
            _PREVIEW.hide()
        path, _filter = QFileDialog.getOpenFileName(
            self, _("select an target image or video"),
            _RECENT_TARGET_DIR or "",
            _MEDIA_FILE_FILTER,
        )
        if not path:
            return
        if is_image(path):
            modules.globals.target_path = path
            _RECENT_TARGET_DIR = os.path.dirname(path)
            self.target_label.setPixmap(render_image_preview(path, (SOURCE_TARGET_PREVIEW_SIZE, SOURCE_TARGET_PREVIEW_SIZE)))
            self.target_label.setText("")
        elif is_video(path):
            modules.globals.target_path = path
            _RECENT_TARGET_DIR = os.path.dirname(path)
            pm = render_video_preview(path, (SOURCE_TARGET_PREVIEW_SIZE, SOURCE_TARGET_PREVIEW_SIZE))
            if pm:
                self.target_label.setPixmap(pm)
                self.target_label.setText("")
        else:
            modules.globals.target_path = None
            self.target_label.clear()
            self.target_label.setText(_("Target"))

    def _on_random_face(self) -> None:
        if _PREVIEW is not None:
            _PREVIEW.hide()
        try:
            response = requests.get(
                "https://thispersondoesnotexist.com/random-person.jpeg",
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10,
            )
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if not content_type.startswith("image/"):
                raise ValueError(f"expected an image, got {content_type!r}")
            temp_path = os.path.join(tempfile.gettempdir(), "deep_live_cam_random_face.jpg")
            staging_path = f"{temp_path}.part"
            # Download into a staging file and validate there. Writing straight
            # to temp_path would destroy the image currently in use whenever a
            # later fetch comes back bad, and content-type alone does not prove
            # the bytes decode.
            try:
                with open(staging_path, "wb") as f:
                    f.write(response.content)
                pixmap = render_image_preview(staging_path, (SOURCE_TARGET_PREVIEW_SIZE, SOURCE_TARGET_PREVIEW_SIZE))
                if imread_unicode(staging_path) is None:
                    raise ValueError("downloaded image could not be decoded")
                os.replace(staging_path, temp_path)
            except Exception:
                try:
                    os.remove(staging_path)
                except OSError:
                    pass
                raise
            modules.globals.source_path = temp_path
            self.source_label.setPixmap(pixmap)
            self.source_label.setText("")
        except Exception as exc:
            print(f"Failed to fetch random face: {exc}")

    def _on_swap_paths(self) -> None:
        global _RECENT_SOURCE_DIR, _RECENT_TARGET_DIR
        sp = modules.globals.source_path
        tp = modules.globals.target_path
        if not (sp and tp and is_image(sp) and is_image(tp)):
            return
        modules.globals.source_path, modules.globals.target_path = tp, sp
        _RECENT_SOURCE_DIR = os.path.dirname(tp)
        _RECENT_TARGET_DIR = os.path.dirname(sp)
        if _PREVIEW is not None:
            _PREVIEW.hide()
        self.source_label.setPixmap(render_image_preview(tp, (SOURCE_TARGET_PREVIEW_SIZE, SOURCE_TARGET_PREVIEW_SIZE)))
        self.target_label.setPixmap(render_image_preview(sp, (SOURCE_TARGET_PREVIEW_SIZE, SOURCE_TARGET_PREVIEW_SIZE)))
        self.source_label.setText("")
        self.target_label.setText("")

    def _on_map_faces_toggled(self, value: bool) -> None:
        modules.globals.map_faces = value
        save_switch_states()
        if not value:
            close_mapper_window()

    def _on_enhancer_change(self, choice: str) -> None:
        key_map = {
            "None": None,
            "GFPGAN": "face_enhancer",
            "GPEN-512": "face_enhancer_gpen512",
            "GPEN-256": "face_enhancer_gpen256",
        }
        for key in ("face_enhancer", "face_enhancer_gpen256", "face_enhancer_gpen512"):
            _update_tumbler(key, False)
        selected = key_map.get(choice)
        if selected:
            _update_tumbler(selected, True)
        save_switch_states()

    def _on_transparency_change(self, value: float) -> None:
        modules.globals.opacity = value
        pct = int(value * 100)
        if pct == 0:
            modules.globals.fp_ui["face_enhancer"] = False
            update_status("Transparency set to 0% - Face swapping disabled.")
        elif pct == 100:
            modules.globals.face_swapper_enabled = True
            update_status("Transparency set to 100%.")
        else:
            modules.globals.face_swapper_enabled = True
            update_status(f"Transparency set to {pct}%")

    def _on_sharpness_change(self, value: float) -> None:
        modules.globals.sharpness = value
        update_status(f"Sharpness set to {value:.1f}")

    def _on_mouth_mask_change(self, value: float) -> None:
        modules.globals.mouth_mask_size = value
        modules.globals.mouth_mask = value > 0
        if value <= 0:
            modules.globals.show_mouth_mask_box = False

    def _on_mouth_mask_pressed(self) -> None:
        if modules.globals.mouth_mask_size > 0:
            modules.globals.show_mouth_mask_box = True

    def _on_mouth_mask_released(self) -> None:
        modules.globals.show_mouth_mask_box = False

    def _on_start(self) -> None:
        if _MAPPER is not None and _MAPPER.isVisible():
            update_status("Please complete pop-up or close it.")
            return
        if modules.globals.map_faces:
            modules.globals.source_target_map = []
            if is_image(modules.globals.target_path):
                update_status("Getting unique faces")
                get_unique_faces_from_target_image()
            elif is_video(modules.globals.target_path):
                update_status("Getting unique faces")
                get_unique_faces_from_target_video()
            if modules.globals.source_target_map:
                _open_mapper_dialog(self._start_cb, modules.globals.source_target_map)
            else:
                update_status("No faces found in target")
        else:
            self._select_output_and_start()

    def _select_output_and_start(self) -> None:
        global _RECENT_OUTPUT_DIR
        if is_image(modules.globals.target_path):
            path, _f = QFileDialog.getSaveFileName(
                self, _("save image output file"),
                os.path.join(_RECENT_OUTPUT_DIR or "", "output.png"),
                _IMAGE_FILE_FILTER,
            )
        elif is_video(modules.globals.target_path):
            path, _f = QFileDialog.getSaveFileName(
                self, _("save video output file"),
                os.path.join(_RECENT_OUTPUT_DIR or "", "output.mp4"),
                _VIDEO_FILE_FILTER,
            )
        else:
            return
        if path:
            modules.globals.output_path = path
            _RECENT_OUTPUT_DIR = os.path.dirname(path)
            self._start_cb()

    def _on_toggle_preview(self) -> None:
        if _PREVIEW is None:
            return
        if _PREVIEW.isVisible():
            _PREVIEW.hide()
        elif modules.globals.source_path and modules.globals.target_path:
            _PREVIEW.init_for_target()
            _PREVIEW.refresh_frame(0)
            _PREVIEW.show()

    def _on_live(self) -> None:
        idx = self.cb_camera.currentIndex()
        if idx < 0 or idx >= len(self._camera_indices):
            update_status("No camera available")
            return
        camera_index = self._camera_indices[idx]
        if _LIVE_MAPPER is not None and _LIVE_MAPPER.isVisible():
            update_status("Source x Target Mapper is already open.")
            _LIVE_MAPPER.raise_()
            return
        if not modules.globals.map_faces:
            if modules.globals.source_path is None:
                update_status("Please select a source image first")
                return
            from modules.face_analyser import get_face_analyser
            from modules.processors.frame.face_swapper import get_face_swapper
            get_face_analyser()
            get_face_swapper()
            _open_webcam_preview(camera_index)
        else:
            modules.globals.source_target_map = []
            _open_live_mapper_dialog(camera_index, modules.globals.source_target_map)

    def _on_refresh_cameras(self) -> None:
        self._camera_indices, self._camera_names = get_available_cameras()
        self.cb_camera.clear()
        if not self._camera_names or self._camera_names[0] == "No cameras found":
            self.cb_camera.addItem("No cameras found")
            self.cb_camera.setEnabled(False)
            self.btn_live.setEnabled(False)
        else:
            self.cb_camera.addItems(self._camera_names)
            self.cb_camera.setEnabled(True)
            self.btn_live.setEnabled(True)
        update_status("Cameras refreshed")

    def _build_activation_card(self) -> QGroupBox:
        card = QGroupBox(_("Bản quyền thiết bị"))
        grid = QGridLayout(card)
        grid.setContentsMargins(14, 12, 14, 10)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)

        device_caption = QLabel(_("Thiết bị"))
        device_caption.setObjectName("heroSubtitle")
        grid.addWidget(device_caption, 0, 0)
        self._device_id_label = QLabel(modules.device_identity.get_device_id())
        self._device_id_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        grid.addWidget(self._device_id_label, 0, 1)
        btn_copy = QPushButton(_("Sao chép"))
        btn_copy.setObjectName("secondary")
        btn_copy.clicked.connect(lambda: QApplication.clipboard().setText(modules.device_identity.get_device_id()))
        grid.addWidget(btn_copy, 0, 2)

        self._host_info = QLabel("● GPU ưu tiên  •  CPU chỉ cho node không hỗ trợ")
        self._host_info.setObjectName("successText")
        grid.addWidget(self._host_info, 1, 0, 1, 2)

        self._activation_status = QLabel(modules.licensing.current_status())
        self._activation_status.setObjectName("successText")
        grid.addWidget(self._activation_status, 1, 2, alignment=Qt.AlignmentFlag.AlignRight)

        notice = QLabel(_("HBM khuyến cáo không sử dụng vào những việc phi pháp, miễn trừ trách nhiệm."))
        notice.setObjectName("statusLabel")
        notice.setWordWrap(True)
        grid.addWidget(notice, 2, 0, 1, 3)
        grid.setColumnStretch(1, 1)
        return card

    def _on_scan_device(self) -> None:
        self._host_info.setText("Đã quét thiết bị  •  GPU ưu tiên")
        update_status("Đã quét lại thiết bị")

    def _on_activate(self) -> None:
        self._activation_status.setText(modules.licensing.current_status())

    def _on_check_update(self) -> None:
        try:
            import modules.updater as updater
            has_update, tag, url = updater.check_for_updates(modules.metadata.version)
            if has_update:
                update_status(f"Update available: {tag} - {url}")
                import webbrowser
                if url:
                    webbrowser.open(url)
            else:
                update_status("No updates available")
        except Exception as exc:
            update_status(f"Update check failed: {exc}")

    def closeEvent(self, event):
        # Treat OS-level close as Destroy click
        self._destroy_cb()
        event.accept()


def _update_tumbler(var: str, value: bool) -> None:
    modules.globals.fp_ui[var] = value
    save_switch_states()
    # If we're currently in a live preview, refresh frame processors so
    # toggling enhancers takes effect immediately.
    if _WEBCAM_PREVIEW is not None and _WEBCAM_PREVIEW.isVisible():
        get_frame_processors_modules(modules.globals.frame_processors)


# --- preview window (still-image / video scrub) --------------------------


class PreviewWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(_("Preview"))
        self.resize(PREVIEW_DEFAULT_WIDTH, PREVIEW_DEFAULT_HEIGHT)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self._image_label, 1)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 0)
        self._slider.valueChanged.connect(self.refresh_frame)
        layout.addWidget(self._slider)

    def init_for_target(self) -> None:
        if is_image(modules.globals.target_path):
            self._slider.hide()
        elif is_video(modules.globals.target_path):
            total = get_video_frame_total(modules.globals.target_path)
            self._slider.setRange(0, max(0, total - 1))
            self._slider.setValue(0)
            self._slider.show()

    def refresh_frame(self, frame_number: int = 0) -> None:
        if not (modules.globals.source_path and modules.globals.target_path):
            return
        update_status("Processing...")
        temp_frame = get_video_frame(modules.globals.target_path, frame_number)
        if modules.globals.nsfw_filter and check_and_ignore_nsfw(temp_frame):
            return
        source_frame = imread_unicode(modules.globals.source_path)
        if source_frame is None:
            update_status(
                f"Could not read source image: {modules.globals.source_path}"
            )
            return
        from modules.processors.frame.core import get_frame_processors_modules as _gfpm
        for fp in _gfpm(modules.globals.frame_processors):
            temp_frame = fp.process_frame(get_one_face(source_frame), temp_frame)
        temp_frame = compose_portrait(temp_frame)
        # Fit to current widget size while preserving aspect ratio.
        h, w = temp_frame.shape[:2]
        bound_w = min(PREVIEW_MAX_WIDTH, max(self.width(), PREVIEW_DEFAULT_WIDTH))
        bound_h = min(PREVIEW_MAX_HEIGHT, max(self.height(), PREVIEW_DEFAULT_HEIGHT))
        ratio = min(bound_w / w, bound_h / h)
        new_size = (max(1, int(w * ratio)), max(1, int(h * ratio)))
        temp_frame = cv2.resize(temp_frame, new_size, interpolation=cv2.INTER_LANCZOS4)
        self._image_label.setPixmap(_bgr_to_qpixmap(temp_frame))
        update_status("Processing succeed!")


# --- webcam preview window -----------------------------------------------


class _CaptureWorker(QThread):
    """Reads frames from the camera into a bounded queue. Drops on overflow."""

    def __init__(self, cap, capture_queue: queue.Queue, stop_event: threading.Event):
        super().__init__()
        self._cap = cap
        self._queue = capture_queue
        self._stop = stop_event

    def run(self) -> None:
        while not self._stop.is_set():
            ret, frame = self._cap.read()
            if not ret:
                self._stop.set()
                break
            try:
                self._queue.put_nowait(frame)
            except queue.Full:
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    pass
                try:
                    self._queue.put_nowait(frame)
                except queue.Full:
                    pass


class _ProcessingWorker(QThread):
    """Pulls raw frames, runs detect/swap/enhance, pushes processed frames."""

    def __init__(self, capture_queue, processed_queue, stop_event, camera_fps: float):
        super().__init__()
        self._cq = capture_queue
        self._pq = processed_queue
        self._stop = stop_event
        self._fps = max(1.0, float(camera_fps))
        self._frame_interval = 1.0 / self._fps

    def run(self) -> None:
        frame_processors = get_frame_processors_modules(modules.globals.frame_processors)
        source_image = None
        last_source_path = None
        reported_source_error = None
        prev_time = time.time()
        fps_update_interval = 0.5
        frame_count = 0
        fps = 0.0
        last_process_time = 0.0
        det_count = 0
        cached_target_face = None
        cached_many_faces = None
        det_interval = max(1, round(self._fps * 0.08))

        while not self._stop.is_set():
            try:
                frame = self._cq.get(timeout=0.05)
            except queue.Empty:
                continue

            now = time.perf_counter()
            if last_process_time and now - last_process_time < self._frame_interval:
                continue
            last_process_time = now

            temp_frame = frame
            if modules.globals.live_mirror:
                temp_frame = gpu_flip(temp_frame, 1)

            if not modules.globals.map_faces:
                if (
                    modules.globals.source_path
                    and modules.globals.source_path != last_source_path
                ):
                    source_frame = imread_unicode(modules.globals.source_path)
                    if source_frame is None:
                        # Clear the cached path along with the image. It keeps
                        # a source that is only transiently unreadable (still
                        # being written, on a volume that just went away) from
                        # being given up on, and it keeps a bad pick from
                        # sticking: with the path cached, A -> unreadable B -> A
                        # never reloaded A, so swapping stayed off. Retrying
                        # every frame is cheap; the message is reported once per
                        # path so it cannot flood the status line.
                        source_image = None
                        last_source_path = None
                        if reported_source_error != modules.globals.source_path:
                            reported_source_error = modules.globals.source_path
                            update_status(
                                f"Could not read source image: {modules.globals.source_path}"
                            )
                    else:
                        last_source_path = modules.globals.source_path
                        reported_source_error = None
                        source_image = get_one_face(source_frame)

                det_count += 1
                if det_count % det_interval == 0:
                    if modules.globals.many_faces:
                        cached_target_face = None
                        cached_many_faces = detect_many_faces_fast(temp_frame)
                    else:
                        cached_target_face = detect_one_face_fast(temp_frame)
                        cached_many_faces = None

                cached_faces = None
                if cached_many_faces:
                    cached_faces = cached_many_faces
                elif cached_target_face is not None:
                    cached_faces = [cached_target_face]

                # Fast detection skips the 2d106 landmark model, but the mouth
                # mask needs it. Attach landmarks on demand (computed once per
                # detection cycle - the helper no-ops if already present).
                if modules.globals.mouth_mask and cached_faces:
                    ensure_landmarks(temp_frame, cached_faces)

                for fp in frame_processors:
                    if fp.NAME == "DLC.FACE-ENHANCER":
                        if modules.globals.fp_ui["face_enhancer"]:
                            temp_frame = fp.process_frame(
                                None, temp_frame, detected_faces=cached_faces
                            )
                    elif fp.NAME == "DLC.FACE-ENHANCER-GPEN256":
                        if modules.globals.fp_ui.get("face_enhancer_gpen256", False):
                            temp_frame = fp.process_frame(
                                None, temp_frame, detected_faces=cached_faces
                            )
                    elif fp.NAME == "DLC.FACE-ENHANCER-GPEN512":
                        if modules.globals.fp_ui.get("face_enhancer_gpen512", False):
                            temp_frame = fp.process_frame(
                                None, temp_frame, detected_faces=cached_faces
                            )
                    elif fp.NAME == "DLC.FACE-SWAPPER":
                        swapped_bboxes = []
                        if modules.globals.many_faces and cached_many_faces:
                            result = temp_frame.copy()
                            for t_face in cached_many_faces:
                                result = fp.swap_face(source_image, t_face, result)
                                if hasattr(t_face, "bbox") and t_face.bbox is not None:
                                    swapped_bboxes.append(t_face.bbox.astype(int))
                            temp_frame = result
                        elif cached_target_face is not None:
                            temp_frame = fp.swap_face(
                                source_image, cached_target_face, temp_frame
                            )
                            if (
                                hasattr(cached_target_face, "bbox")
                                and cached_target_face.bbox is not None
                            ):
                                swapped_bboxes.append(cached_target_face.bbox.astype(int))
                        temp_frame = fp.apply_post_processing(temp_frame, swapped_bboxes)
                    else:
                        temp_frame = fp.process_frame(source_image, temp_frame)
            else:
                modules.globals.target_path = None
                for fp in frame_processors:
                    if fp.NAME == "DLC.FACE-ENHANCER":
                        if modules.globals.fp_ui["face_enhancer"]:
                            temp_frame = fp.process_frame_v2(temp_frame)
                    elif fp.NAME in ("DLC.FACE-ENHANCER-GPEN256", "DLC.FACE-ENHANCER-GPEN512"):
                        fp_key = fp.NAME.split(".")[-1].lower().replace("-", "_")
                        if modules.globals.fp_ui.get(fp_key, False):
                            temp_frame = fp.process_frame_v2(temp_frame)
                    else:
                        temp_frame = fp.process_frame_v2(temp_frame)

            current_time = time.time()
            frame_count += 1
            if current_time - prev_time >= fps_update_interval:
                fps = frame_count / (current_time - prev_time)
                frame_count = 0
                prev_time = current_time

            if modules.globals.show_fps:
                cv2.putText(
                    temp_frame, f"FPS: {fps:.1f}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2,
                )

            temp_frame = compose_portrait(
                temp_frame,
                focus_bbox=getattr(
                    cached_target_face if not modules.globals.map_faces else None,
                    "bbox",
                    None,
                ),
            )
            try:
                self._pq.put_nowait(temp_frame)
            except queue.Full:
                try:
                    self._pq.get_nowait()
                except queue.Empty:
                    pass
                try:
                    self._pq.put_nowait(temp_frame)
                except queue.Full:
                    pass


class WebcamPreviewWindow(QWidget):
    def __init__(self, camera_index: int):
        super().__init__()
        self.setWindowTitle("Live Preview")
        self.resize(450, 800)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self._image_label, 1)

        self._cap = VideoCapturer(camera_index)
        req_w, req_h = modules.globals.capture_resolution
        target_fps = int(modules.globals.live_fps_limit)
        if not self._cap.start(req_w, req_h, target_fps):
            update_status("Failed to start camera")
            QTimer.singleShot(0, self.close)
            return

        camera_fps = self._cap.actual_fps
        print(
            f"[webcam] Camera running at {self._cap.actual_width}x"
            f"{self._cap.actual_height}@{camera_fps:.0f}fps; "
            f"processing capped at {target_fps}fps"
        )

        self._capture_queue: queue.Queue = queue.Queue(maxsize=2)
        self._processed_queue: queue.Queue = queue.Queue(maxsize=2)
        self._stop_event = threading.Event()

        self._capture_worker = _CaptureWorker(
            self._cap, self._capture_queue, self._stop_event
        )
        self._processing_worker = _ProcessingWorker(
            self._capture_queue,
            self._processed_queue,
            self._stop_event,
            min(camera_fps, target_fps),
        )
        self._capture_worker.start()
        self._processing_worker.start()

        # Refresh the UI at a bounded rate; camera/inference have their own
        # workers and frame queues.
        poll_ms = max(16, int(1000 / max(target_fps, 1)))
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(poll_ms)

    def _tick(self) -> None:
        if self._stop_event.is_set():
            self.close()
            return
        try:
            bgr_frame = self._processed_queue.get_nowait()
        except queue.Empty:
            return
        bgr_frame = fit_image_to_size(bgr_frame, self.width(), self.height())
        self._image_label.setPixmap(_bgr_to_qpixmap(bgr_frame))

    def closeEvent(self, event) -> None:
        # __init__ can bail out before these exist (e.g. the camera fails to open),
        # and closeEvent still runs.
        stop_event = getattr(self, "_stop_event", None)
        if stop_event is not None:
            stop_event.set()
        timer = getattr(self, "_timer", None)
        if timer is not None:
            try:
                timer.stop()
            except Exception:
                pass
        # Shutdown has to actually complete. Qt aborts the process when a
        # running QThread is destroyed, and holding a straggler in a module
        # global only moves that abort to interpreter exit. Both loops re-check
        # the stop flag between bounded operations (a camera read, a 50ms queue
        # get, one inference), so waiting terminates; a first-time model load
        # is simply slow, which is what the grace period absorbs quietly.
        for name in ("_capture_worker", "_processing_worker"):
            worker = getattr(self, name, None)
            if worker is None:
                continue
            if not worker.wait(WORKER_SHUTDOWN_GRACE_MS):
                print(
                    f"[webcam] still waiting for {name[1:]} to stop...",
                    flush=True,
                )
                worker.wait()
        # Only now: releasing the capture while the capture thread could still
        # be inside cap.read() is not safe.
        cap = getattr(self, "_cap", None)
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass
        global _WEBCAM_PREVIEW
        if _WEBCAM_PREVIEW is self:
            _WEBCAM_PREVIEW = None
        event.accept()


def _open_webcam_preview(camera_index: int) -> None:
    global _WEBCAM_PREVIEW
    if _WEBCAM_PREVIEW is not None:
        _WEBCAM_PREVIEW.close()
    _WEBCAM_PREVIEW = WebcamPreviewWindow(camera_index)
    _WEBCAM_PREVIEW.show()


# --- mapper dialogs (image/video + live) --------------------------------


def _make_thumb(cv2_img: np.ndarray) -> QPixmap:
    rgb = gpu_cvt_color(cv2_img, cv2.COLOR_BGR2RGB)
    image = Image.fromarray(rgb).resize(
        (MAPPER_PREVIEW_SIZE, MAPPER_PREVIEW_SIZE), Image.LANCZOS
    )
    return _pil_to_qpixmap(image)


class MapperDialog(QDialog):
    """Source x Target mapper for image / video processing."""

    def __init__(self, start_cb: Callable, mapping: list):
        super().__init__(_MAIN)
        self._start_cb = start_cb
        self._map = mapping
        self.setWindowTitle(_("Source x Target Mapper"))
        self.resize(POPUP_WIDTH, POPUP_HEIGHT)
        layout = QVBoxLayout(self)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        layout.addWidget(self._scroll, 1)

        self._status = QLabel("")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._status)

        btn_submit = QPushButton(_("Submit"))
        btn_submit.clicked.connect(self._on_submit)
        layout.addWidget(btn_submit, alignment=Qt.AlignmentFlag.AlignCenter)

        self._rebuild()

    def set_status(self, text: str) -> None:
        self._status.setText(_(text))

    def _rebuild(self) -> None:
        body = QWidget()
        grid = QGridLayout(body)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        for item in self._map:
            row = item["id"]
            btn = QPushButton(_("Select source image"))
            btn.setFixedWidth(200)
            btn.clicked.connect(lambda _c, n=row: self._select_source(n))
            grid.addWidget(btn, row, 0)

            src_label = QLabel(f"S-{row}")
            src_label.setFixedSize(MAPPER_PREVIEW_SIZE, MAPPER_PREVIEW_SIZE)
            src_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            src_label.setStyleSheet("border: 1px dashed #555;")
            grid.addWidget(src_label, row, 1)
            if "source" in item:
                src_label.setPixmap(_make_thumb(item["source"]["cv2"]))
                src_label.setText("")

            x_label = QLabel("x")
            x_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(x_label, row, 2)

            tgt_label = QLabel(f"T-{row}")
            tgt_label.setFixedSize(MAPPER_PREVIEW_SIZE, MAPPER_PREVIEW_SIZE)
            tgt_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tgt_label.setStyleSheet("border: 1px solid #555;")
            grid.addWidget(tgt_label, row, 3)
            if "target" in item:
                tgt_label.setPixmap(_make_thumb(item["target"]["cv2"]))
                tgt_label.setText("")

        grid.setRowStretch(grid.rowCount(), 1)
        self._scroll.setWidget(body)

    def _select_source(self, row: int) -> None:
        path, _f = QFileDialog.getOpenFileName(
            self, _("select an source image"),
            _RECENT_SOURCE_DIR or "",
            _IMAGE_FILE_FILTER,
        )
        if not path:
            return
        cv2_img = imread_unicode(path)
        face = get_one_face(cv2_img)
        if face is None:
            self.set_status("Face could not be detected in last upload!")
            return
        x_min, y_min, x_max, y_max = face["bbox"]
        self._map[row]["source"] = {
            "cv2": cv2_img[int(y_min):int(y_max), int(x_min):int(x_max)],
            "face": face,
        }
        self._rebuild()

    def _on_submit(self) -> None:
        if has_valid_map():
            self.accept()
            _MAIN._select_output_and_start()
        else:
            self.set_status("Atleast 1 source with target is required!")


class LiveMapperDialog(QDialog):
    """Source x Target mapper for live webcam mode."""

    def __init__(self, camera_index: int, mapping: list):
        super().__init__(_MAIN)
        self._camera_index = camera_index
        self._map = mapping
        self.setWindowTitle(_("Source x Target Mapper"))
        self.resize(POPUP_LIVE_WIDTH, POPUP_LIVE_HEIGHT)
        layout = QVBoxLayout(self)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        layout.addWidget(self._scroll, 1)

        self._status = QLabel("")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._status)

        btn_row = QHBoxLayout()
        for text, slot in (
            (_("Add"), self._on_add),
            (_("Clear"), self._on_clear),
            (_("Submit"), self._on_submit),
        ):
            b = QPushButton(text)
            b.clicked.connect(slot)
            btn_row.addWidget(b)
        layout.addLayout(btn_row)

        self._rebuild()

    def set_status(self, text: str) -> None:
        self._status.setText(_(text))

    def _rebuild(self) -> None:
        body = QWidget()
        grid = QGridLayout(body)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        for item in self._map:
            row = item["id"]
            btn_s = QPushButton(_("Select source image"))
            btn_s.setFixedWidth(200)
            btn_s.clicked.connect(lambda _c, n=row: self._select_face(n, "source"))
            grid.addWidget(btn_s, row, 0)

            src_label = QLabel(f"S-{row}")
            src_label.setFixedSize(MAPPER_PREVIEW_SIZE, MAPPER_PREVIEW_SIZE)
            src_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            src_label.setStyleSheet("border: 1px dashed #555;")
            grid.addWidget(src_label, row, 1)
            if "source" in item:
                src_label.setPixmap(_make_thumb(item["source"]["cv2"]))
                src_label.setText("")

            x_label = QLabel("x")
            x_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(x_label, row, 2)

            btn_t = QPushButton(_("Select target image"))
            btn_t.setFixedWidth(200)
            btn_t.clicked.connect(lambda _c, n=row: self._select_face(n, "target"))
            grid.addWidget(btn_t, row, 3)

            tgt_label = QLabel(f"T-{row}")
            tgt_label.setFixedSize(MAPPER_PREVIEW_SIZE, MAPPER_PREVIEW_SIZE)
            tgt_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tgt_label.setStyleSheet("border: 1px dashed #555;")
            grid.addWidget(tgt_label, row, 4)
            if "target" in item:
                tgt_label.setPixmap(_make_thumb(item["target"]["cv2"]))
                tgt_label.setText("")

        grid.setRowStretch(grid.rowCount(), 1)
        self._scroll.setWidget(body)

    def _select_face(self, row: int, kind: str) -> None:
        path, _f = QFileDialog.getOpenFileName(
            self, _("select an source image"),
            _RECENT_SOURCE_DIR or "",
            _IMAGE_FILE_FILTER,
        )
        if not path:
            return
        cv2_img = imread_unicode(path)
        face = get_one_face(cv2_img)
        if face is None:
            self.set_status("Face could not be detected in last upload!")
            return
        x_min, y_min, x_max, y_max = face["bbox"]
        self._map[row][kind] = {
            "cv2": cv2_img[int(y_min):int(y_max), int(x_min):int(x_max)],
            "face": face,
        }
        self._rebuild()

    def _on_add(self) -> None:
        add_blank_map()
        self._rebuild()
        self.set_status("Please provide mapping!")

    def _on_clear(self) -> None:
        for item in self._map:
            item.pop("source", None)
            item.pop("target", None)
        self._rebuild()
        self.set_status("All mappings cleared!")

    def _on_submit(self) -> None:
        if has_valid_map():
            simplify_maps()
            self.set_status("Mappings successfully submitted!")
            self.accept()
            _open_webcam_preview(self._camera_index)
        else:
            self.set_status("At least 1 source with target is required!")


def _open_mapper_dialog(start_cb: Callable, mapping: list) -> None:
    global _MAPPER
    close_mapper_window()
    _MAPPER = MapperDialog(start_cb, mapping)
    _MAPPER.show()


def _open_live_mapper_dialog(camera_index: int, mapping: list) -> None:
    global _LIVE_MAPPER
    close_mapper_window()
    _LIVE_MAPPER = LiveMapperDialog(camera_index, mapping)
    _LIVE_MAPPER.show()


def close_mapper_window() -> None:
    global _MAPPER, _LIVE_MAPPER
    if _MAPPER is not None:
        _MAPPER.close()
        _MAPPER = None
    if _LIVE_MAPPER is not None:
        _LIVE_MAPPER.close()
        _LIVE_MAPPER = None


# --- entry point ---------------------------------------------------------


def _close_live_windows() -> None:
    """Close every window that owns worker threads, so the threads stop."""
    for win in (_WEBCAM_PREVIEW, _LIVE_MAPPER):
        if win is None:
            continue
        try:
            win.close()
        except Exception:
            pass


class _Window:
    """Thin wrapper exposing .mainloop() for core.py compatibility."""

    def __init__(self, app: QApplication, main_window: MainWindow):
        self._app = app
        self._main = main_window

    def mainloop(self) -> None:
        self._main.show()
        self._app.exec()


def init(
    start: Callable[[], None], destroy: Callable[[], None], lang: str
) -> _Window:
    global _APP, _MAIN, _PREVIEW, _LANG, _BRIDGE

    _LANG = LanguageManager(lang)
    if QApplication.instance() is None:
        _APP = QApplication(sys.argv)
    else:
        _APP = QApplication.instance()
    _APP.setStyleSheet(QSS)

    if not modules.licensing.is_activated():
        activation = ActivationDialog()
        if activation.exec() != QDialog.DialogCode.Accepted:
            raise SystemExit(2)

    _BRIDGE = _UIBridge()
    def _destroy_with_cleanup(*args, **kwargs):
        # core.destroy() ends in a bare quit(), which raises SystemExit and tears
        # the interpreter down without unwinding Qt. Destroying a running QThread
        # is fatal in Qt, so stop the live-preview workers before that happens.
        _close_live_windows()
        return destroy(*args, **kwargs)

    _MAIN = MainWindow(start, _destroy_with_cleanup)
    _PREVIEW = PreviewWindow()

    # Route status updates onto the UI thread regardless of caller.
    _BRIDGE.statusChanged.connect(_MAIN.set_status)

    return _Window(_APP, _MAIN)

