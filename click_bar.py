import os
import sys
import json
import time
import ctypes
from ctypes import wintypes
import threading

def play_sound(freq, duration):
    """GUI 스레드 지연을 방지하는 백그라운드 비동기 비프음 재생"""
    try:
        import winsound
        threading.Thread(target=winsound.Beep, args=(freq, duration), daemon=True).start()
    except Exception:
        pass

def play_click_sound():
    """사용자 지정 마우스 클릭 효과음(click.wav)을 비동기(0ms 지연)로 재생"""
    try:
        import winsound
        wav_path = os.path.join(get_base_dir(), "click.wav")
        if os.path.exists(wav_path):
            winsound.PlaySound(wav_path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        else:
            threading.Thread(target=winsound.Beep, args=(1400, 30), daemon=True).start()
    except Exception:
        pass

from PySide6.QtCore import Qt, QPoint, QRect, QTimer, QSize
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPainterPath, QCursor, QIcon
from PySide6.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QLabel, QDialog, QSlider, QCheckBox, QFrame, QMessageBox, QSpacerItem, QSizePolicy
)

# ========================================================
# Win32 API 상수 및 함수 선언
# ========================================================
user32 = ctypes.windll.user32

GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOPMOST = 0x00000008
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000
WS_EX_TOOLWINDOW = 0x00000080

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

CONFIG_PATH = os.path.join(get_base_dir(), "clickbar_config.json")

DEFAULT_CONFIG = {
    "active": True,
    "current_mode": "LEFT",
    "dwell_time": 0.8,
    "dwell_radius": 10,
    "auto_revert": True,
    "sound_enabled": True,
    "visual_indicator": True,
    "dwell_on_bar": True,
    "pos_x": 400,
    "pos_y": 30
}

def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                cfg = DEFAULT_CONFIG.copy()
                cfg.update(data)
                return cfg
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()

def save_config(cfg):
    try:
        temp_file = CONFIG_PATH + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_file, CONFIG_PATH)
    except Exception as e:
        print(f"[설정 저장 오류]: {e}")

# ========================================================
# 1. 시각적 카운트다운 게이지 오버레이 (Dwell Indicator)
# ========================================================
class DwellIndicatorOverlay(QWidget):
    """
    커서 위치에 도넛형 원형 카운트다운 게이지를 표시하는 투명 오버레이 윈도우.
    마우스 입력을 전혀 가로채지 않는(Click-through) 속성을 지닙니다.
    """
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool |
            Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_QuitOnClose, False)
        
        self.setFixedSize(40, 40)
        self.progress = 0.0  # 0.0 ~ 1.0
        self.mode = "LEFT"
        self.hide()

    def showEvent(self, event):
        super().showEvent(event)
        # Windows API로 마우스 클릭 완전 투과 설정
        hwnd = int(self.winId())
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_NOACTIVATE | WS_EX_TOPMOST)

    def set_progress(self, progress, x, y, mode="LEFT"):
        self.progress = min(1.0, max(0.0, progress))
        self.mode = mode
        # 커서 중앙에 위치하도록 조정
        self.move(int(x - self.width() / 2), int(y - self.height() / 2))
        self.update()
        if not self.isVisible():
            self.show()

    def paintEvent(self, event):
        if self.progress <= 0.0:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        center_x = self.width() / 2.0
        center_y = self.height() / 2.0
        radius = 14.0
        rect = QRect(int(center_x - radius), int(center_y - radius), int(radius * 2), int(radius * 2))

        # 1. 배경 가이드 링 (은은한 반투명 다크 링)
        bg_pen = QPen(QColor(15, 23, 42, 160), 3)
        bg_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(bg_pen)
        painter.drawEllipse(rect)

        # 2. 모드별 진행 색상 결정
        if self.mode == "LEFT":
            arc_color = QColor(14, 165, 233, 230)   # 스카이블루
        elif self.mode == "DOUBLE":
            arc_color = QColor(16, 185, 129, 230)  # 에메랄드 그린
        elif self.mode == "DRAG":
            arc_color = QColor(245, 158, 11, 230)  # 앰버 오렌지
        elif self.mode == "RIGHT":
            arc_color = QColor(168, 85, 247, 230)  # 퍼플
        else:
            arc_color = QColor(56, 189, 248, 230)

        # 3. 진행도 게이지 아크 (12시 방향부터 시계방향 회전)
        arc_pen = QPen(arc_color, 4)
        arc_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(arc_pen)
        
        start_angle = 90 * 16
        span_angle = -int(self.progress * 360 * 16)
        painter.drawArc(rect, start_angle, span_angle)

        # 4. 중심 앵커 점
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(arc_color))
        painter.drawEllipse(QPoint(int(center_x), int(center_y)), 3, 3)

# ========================================================
# 2. 툴바 전용 커스텀 스타일 버튼
# ========================================================
class ClickBarButton(QPushButton):
    """
    사용자가 제공한 원본 이미지와 완벽하게 일치하는 벡터 아이콘 & 라벨 렌더링 버튼 (30% 콤팩트 축소).
    """
    def __init__(self, key, label, parent=None):
        super().__init__(parent)
        self.key = key
        self.label_text = label
        self.is_active_mode = False
        self.is_continuous = False
        self.is_power_on = True
        self.is_dragging_state = False
        self.is_drag_active = False
        self.drag_start_mouse_pos = QPoint()
        self.setFixedSize(38, 38)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)

    def mousePressEvent(self, event):
        win = self.window()
        if hasattr(win, 'is_follow_moving') and win.is_follow_moving:
            win._stop_follow_moving()
            event.accept()
            return

        if self.key == "MOVE" and event.button() == Qt.LeftButton:
            start_pt = event.globalPosition().toPoint()
            if hasattr(win, '_start_native_drag'):
                win._start_native_drag()
            # 네이티브 드래그 종료 후, 마우스 이동이 거의 없는 단순 클릭이었으면 토글 클릭 시그널 방출
            end_pt = QCursor.pos()
            if (end_pt - start_pt).manhattanLength() <= 4:
                self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)

    def enterEvent(self, event):
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect()
        w = rect.width()
        h = rect.height()

        # 1. 버튼 배경 및 테두리 결정
        border_style = Qt.SolidLine
        border_width = 1.2
        border_color = QColor(203, 213, 225)
        bg_color = QColor(248, 250, 252)
        text_color = QColor(51, 65, 85)

        if self.key == "ON/OFF" and not self.is_power_on:
            # OFF 상태: 은은한 레드 틴트 배경 & 레드 테두리 & 레드 텍스트
            if self.underMouse():
                bg_color = QColor(254, 226, 226)
                border_color = QColor(239, 68, 68)
            else:
                bg_color = QColor(254, 242, 242)
                border_color = QColor(248, 113, 113)
            text_color = QColor(220, 38, 38)
        elif self.is_active_mode:
            if self.is_continuous:
                # [연속 사용 모드 (고정)]: 선명한 스카이블루 배경 + 짙은 블루 실선 테두리 (꽉 찬 색상)
                bg_color = QColor(138, 226, 244)
                border_color = QColor(3, 105, 161)
                border_width = 1.6
                border_style = Qt.SolidLine
                text_color = QColor(15, 23, 42)
            else:
                # [1회 사용 모드]: 외곽선에 점선(Dashed) 표시! + 연한 파스텔 스카이블루 틴트 배경
                bg_color = QColor(224, 242, 254)
                border_color = QColor(2, 132, 199)
                border_width = 2.0
                border_style = Qt.DashLine
                text_color = QColor(3, 105, 161)
        elif self.underMouse():
            bg_color = QColor(241, 245, 249)
            border_color = QColor(148, 163, 184)
            text_color = QColor(30, 41, 59)

        # 특수 상태 배경
        if self.key == "DRAG" and self.is_dragging_state:
            bg_color = QColor(254, 215, 170)  # 드래그 중 앰버 하이라이트
            border_color = QColor(234, 88, 12)
            border_style = Qt.SolidLine
            border_width = 1.6

        # 라운드 박스 렌더링 (1회 사용 시 또렷한 점선 테두리)
        if border_style == Qt.DashLine:
            pen = QPen(border_color, border_width, Qt.CustomDashLine)
            pen.setDashPattern([3, 2])
        else:
            pen = QPen(border_color, border_width, Qt.SolidLine)
        painter.setPen(pen)
        painter.setBrush(QBrush(bg_color))
        painter.drawRoundedRect(1, 1, w - 2, h - 2, 3, 3)

        # 2. 아이콘 렌더링 (중심 기준 축소 렌더링)
        cx = w / 2.0
        cy = 13.5

        if self.key == "ON/OFF":
            # 전원 아이콘 (ON: 그린, OFF: 레드/그레이)
            icon_color = QColor(34, 197, 94) if self.is_power_on else QColor(239, 68, 68)
            pen = QPen(icon_color, 2.0)
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            
            # 열린 원
            arc_r = 5.5
            painter.drawArc(QRect(int(cx - arc_r), int(cy - arc_r), int(arc_r * 2), int(arc_r * 2)), 30 * 16, 300 * 16)
            # 상단 수직선
            painter.drawLine(QPoint(int(cx), int(cy - 7)), QPoint(int(cx), int(cy - 1)))

        elif self.key == "LEFT":
            # 좌측 삼각형 화살표 ◀
            path = QPainterPath()
            path.moveTo(cx - 5.5, cy)
            path.lineTo(cx + 4.5, cy - 5.5)
            path.lineTo(cx + 4.5, cy + 5.5)
            path.closeSubpath()
            painter.setPen(QPen(QColor(15, 23, 42), 1.4))
            painter.setBrush(QBrush(QColor(226, 232, 240) if not self.is_active_mode else QColor(255, 255, 255)))
            painter.drawPath(path)

        elif self.key == "DOUBLE":
            # 이중 좌측 삼각형 ◀◀
            for offset in [-3.0, 3.5]:
                path = QPainterPath()
                path.moveTo(cx + offset - 5.0, cy)
                path.lineTo(cx + offset + 2.0, cy - 5.0)
                path.lineTo(cx + offset + 2.0, cy + 5.0)
                path.closeSubpath()
                painter.setPen(QPen(QColor(15, 23, 42), 1.2))
                painter.setBrush(QBrush(QColor(226, 232, 240) if not self.is_active_mode else QColor(255, 255, 255)))
                painter.drawPath(path)

        elif self.key == "DRAG":
            # 사용자 원본 이미지: 좌측 점선 + 우측으로 벌어지는 삼각형 (···◁)
            # 점선 3개 점
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor(15, 23, 42)))
            for dot_x in [cx - 7.5, cx - 4.5, cx - 1.5]:
                painter.drawEllipse(QPoint(int(dot_x), int(cy)), 1.2, 1.2)
            
            # 좌측을 향하는 삼각형
            path = QPainterPath()
            path.moveTo(cx + 1.0, cy)
            path.lineTo(cx + 6.5, cy - 5.5)
            path.lineTo(cx + 6.5, cy + 5.5)
            path.closeSubpath()
            painter.setPen(QPen(QColor(15, 23, 42), 1.3))
            painter.setBrush(QBrush(QColor(226, 232, 240) if not self.is_active_mode else QColor(255, 255, 255)))
            painter.drawPath(path)

        elif self.key == "RIGHT":
            # 우측 삼각형 화살표 ▶
            path = QPainterPath()
            path.moveTo(cx + 5.5, cy)
            path.lineTo(cx - 4.5, cy - 5.5)
            path.lineTo(cx - 4.5, cy + 5.5)
            path.closeSubpath()
            painter.setPen(QPen(QColor(15, 23, 42), 1.4))
            painter.setBrush(QBrush(QColor(226, 232, 240) if not self.is_active_mode else QColor(255, 255, 255)))
            painter.drawPath(path)

        elif self.key == "SETUP":
            # 렌치 모양 🔧 (스케일 0.7배 축소)
            painter.save()
            painter.translate(cx, cy)
            painter.scale(0.7, 0.7)
            painter.rotate(-45)
            
            pen = QPen(QColor(51, 65, 85), 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(QBrush(QColor(226, 232, 240)))
            
            wrench = QPainterPath()
            wrench.moveTo(-2, 9)
            wrench.lineTo(2, 9)
            wrench.lineTo(2, -1)
            wrench.lineTo(6, -2)
            wrench.lineTo(7, -6)
            wrench.lineTo(4, -8)
            wrench.lineTo(1, -5)
            wrench.lineTo(-1, -5)
            wrench.lineTo(-4, -8)
            wrench.lineTo(-7, -6)
            wrench.lineTo(-6, -2)
            wrench.lineTo(-2, -1)
            wrench.closeSubpath()
            
            painter.drawPath(wrench)
            painter.restore()

        elif self.key == "EXIT":
            # 빨간 사각 테두리 안의 X ❎
            box_r = 5.0
            painter.setPen(QPen(QColor(185, 28, 28), 1.2))
            painter.setBrush(QBrush(QColor(254, 226, 226)))
            painter.drawRoundedRect(QRect(int(cx - box_r), int(cy - box_r), int(box_r * 2), int(box_r * 2)), 1, 1)
            
            painter.setPen(QPen(QColor(185, 28, 28), 1.5, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(QPoint(int(cx - 3), int(cy - 3)), QPoint(int(cx + 3), int(cy + 3)))
            painter.drawLine(QPoint(int(cx + 3), int(cy - 3)), QPoint(int(cx - 3), int(cy + 3)))

        elif self.key == "MOVE":
            # 4방향 독립 삼각형 화살표 ✥
            pen = QPen(QColor(51, 65, 85), 1.2)
            brush = QBrush(QColor(226, 232, 240))
            painter.setPen(pen)
            painter.setBrush(brush)
            
            # 상 (▲)
            up = QPainterPath()
            up.moveTo(cx, cy - 6.5)
            up.lineTo(cx - 3.5, cy - 1.5)
            up.lineTo(cx + 3.5, cy - 1.5)
            up.closeSubpath()
            painter.drawPath(up)
            
            # 하 (▼)
            dn = QPainterPath()
            dn.moveTo(cx, cy + 6.5)
            dn.lineTo(cx - 3.5, cy + 1.5)
            dn.lineTo(cx + 3.5, cy + 1.5)
            dn.closeSubpath()
            painter.drawPath(dn)
            
            # 좌 (◀)
            lf = QPainterPath()
            lf.moveTo(cx - 6.5, cy)
            lf.lineTo(cx - 1.5, cy - 3.5)
            lf.lineTo(cx - 1.5, cy + 3.5)
            lf.closeSubpath()
            painter.drawPath(lf)
            
            # 우 (▶)
            rt = QPainterPath()
            rt.moveTo(cx + 6.5, cy)
            rt.lineTo(cx + 1.5, cy - 3.5)
            rt.lineTo(cx + 1.5, cy + 3.5)
            rt.closeSubpath()
            painter.drawPath(rt)

        # 3. 하단 텍스트 라벨 렌더링
        font = QFont("Segoe UI", 6, QFont.Bold)
        font.setLetterSpacing(QFont.AbsoluteSpacing, 0.2)
        painter.setFont(font)
        painter.setPen(text_color)
        
        text_rect = QRect(0, h - 12, w, 10)
        label = self.label_text
        if self.key == "ON/OFF":
            label = "ON" if self.is_power_on else "OFF"
        painter.drawText(text_rect, Qt.AlignCenter, label)

# ========================================================
# 3. 설정 대화상자 (Setup Dialog)
# ========================================================
class ClickBarSetupDialog(QDialog):
    """
    머무름 클릭 바 세부 설정 (대기 시간, 반경, 사운드, 자동 복귀 등)
    """
    def __init__(self, cfg, on_save_callback=None, parent_window=None):
        super().__init__(None)  # 독립 윈도우로 생성하여 부모 종속 및 Z-order 충돌 방지
        self.cfg = cfg
        self.on_save_callback = on_save_callback
        self.parent_window = parent_window
        self.setWindowTitle("Click Bar 설정")
        self.setFixedSize(400, 420)
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating, False)
        self.setAttribute(Qt.WA_QuitOnClose, False)  # 설정창이 닫혀도 클릭바 앱이 절대 종료되지 않도록 보장
        ico_path = os.path.join(get_base_dir(), "clickbar.ico")
        if os.path.exists(ico_path):
            self.setWindowIcon(QIcon(ico_path))
        self.setStyleSheet("""
            QDialog {
                background-color: #182234;
                border: 1.5px solid #2D3E5B;
                border-radius: 12px;
                font-family: 'Pretendard', 'Malgun Gothic', '맑은 고딕', 'Segoe UI', sans-serif;
            }
            QLabel {
                color: #FFFFFF;
                font-size: 13px;
                font-weight: 600;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #2D3E5B;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #38BDF8;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #FFFFFF;
                border: 2px solid #38BDF8;
                width: 16px;
                margin-top: -5px;
                margin-bottom: -5px;
                border-radius: 8px;
            }
            QCheckBox {
                color: #F1F5F9;
                font-size: 13px;
                font-weight: 500;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1.5px solid #475569;
                background: #0F172A;
            }
            QCheckBox::indicator:checked {
                background: #0284C7;
                border-color: #38BDF8;
            }
            QPushButton#SaveBtn {
                background-color: #0284C7;
                color: #FFFFFF;
                font-size: 13px;
                font-weight: bold;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
            }
            QPushButton#SaveBtn:hover { background-color: #0369A1; }
            QPushButton#CancelBtn {
                background-color: #334155;
                color: #F8FAFC;
                font-size: 13px;
                font-weight: 600;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
            }
            QPushButton#CancelBtn:hover { background-color: #475569; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        title = QLabel("⚙️  머무름 클릭 바(Click Bar) 설정")
        title.setStyleSheet("font-size: 16px; font-weight: 800; color: #38BDF8; margin-bottom: 4px;")
        layout.addWidget(title)

        # 1. 머무름 시간 슬라이더 (0.1초 ~ 2.5초)
        time_box = QVBoxLayout()
        t_header = QHBoxLayout()
        t_lbl = QLabel("머무름 대기 시간 (Dwell Time):")
        cur_dwell = self.cfg.get('dwell_time', 0.8)
        self.t_val_lbl = QLabel(f"{cur_dwell:.1f}초")
        self.t_val_lbl.setStyleSheet("color: #38BDF8; font-weight: bold;")
        t_header.addWidget(t_lbl)
        t_header.addStretch()
        t_header.addWidget(self.t_val_lbl)
        time_box.addLayout(t_header)

        self.time_slider = QSlider(Qt.Horizontal)
        self.time_slider.setRange(1, 25)  # 0.1 ~ 2.5s (최소 0.1초)
        self.time_slider.setValue(max(1, int(round(cur_dwell * 10))))
        self.time_slider.valueChanged.connect(self._on_time_changed)
        time_box.addWidget(self.time_slider)
        layout.addLayout(time_box)

        # 2. 떨림 방지 반경 슬라이더 (5px ~ 30px)
        rad_box = QVBoxLayout()
        r_header = QHBoxLayout()
        r_lbl = QLabel("떨림 방지 허용 반경 (Deadzone Radius):")
        self.r_val_lbl = QLabel(f"{self.cfg['dwell_radius']}px")
        self.r_val_lbl.setStyleSheet("color: #38BDF8; font-weight: bold;")
        r_header.addWidget(r_lbl)
        r_header.addStretch()
        r_header.addWidget(self.r_val_lbl)
        rad_box.addLayout(r_header)

        self.rad_slider = QSlider(Qt.Horizontal)
        self.rad_slider.setRange(5, 30)
        self.rad_slider.setValue(int(self.cfg['dwell_radius']))
        self.rad_slider.valueChanged.connect(self._on_rad_changed)
        rad_box.addWidget(self.rad_slider)
        layout.addLayout(rad_box)

        # 3. 체크박스 옵션들
        self.chk_revert = QCheckBox("클릭 후 일반 좌클릭(LEFT)으로 자동 복귀")
        self.chk_revert.setChecked(self.cfg.get("auto_revert", True))
        layout.addWidget(self.chk_revert)

        self.chk_sound = QCheckBox("클릭 실행 시 효과음 재생")
        self.chk_sound.setChecked(self.cfg.get("sound_enabled", True))
        layout.addWidget(self.chk_sound)

        self.chk_visual = QCheckBox("커서 주변 원형 카운트다운 게이지 표시")
        self.chk_visual.setChecked(self.cfg.get("visual_indicator", True))
        layout.addWidget(self.chk_visual)

        self.chk_dwell_bar = QCheckBox("클릭바 버튼 위에서도 머무름으로 선택 허용")
        self.chk_dwell_bar.setChecked(self.cfg.get("dwell_on_bar", True))
        layout.addWidget(self.chk_dwell_bar)

        layout.addStretch()

        # 하단 버튼 박스
        btn_box = QHBoxLayout()
        btn_box.addStretch()
        
        cancel_btn = QPushButton("취소")
        cancel_btn.setObjectName("CancelBtn")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.clicked.connect(self.close)
        
        save_btn = QPushButton("저장")
        save_btn.setObjectName("SaveBtn")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.clicked.connect(self._on_save)
        
        btn_box.addWidget(cancel_btn)
        btn_box.addWidget(save_btn)
        layout.addLayout(btn_box)

    def showEvent(self, event):
        super().showEvent(event)
        hwnd = int(self.winId())
        user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002)
        # 설정창 표시 후에도 클릭바가 항상 더 최우선 최상단이 되도록 보장
        if self.parent_window and hasattr(self.parent_window, '_ensure_topmost'):
            self.parent_window._ensure_topmost()

    def _on_time_changed(self, val):
        sec = val / 10.0
        self.t_val_lbl.setText(f"{sec:.1f}초")

    def _on_rad_changed(self, val):
        self.r_val_lbl.setText(f"{val}px")

    def _on_save(self):
        self.cfg["dwell_time"] = self.time_slider.value() / 10.0
        self.cfg["dwell_radius"] = self.rad_slider.value()
        self.cfg["auto_revert"] = self.chk_revert.isChecked()
        self.cfg["sound_enabled"] = self.chk_sound.isChecked()
        self.cfg["visual_indicator"] = self.chk_visual.isChecked()
        self.cfg["dwell_on_bar"] = self.chk_dwell_bar.isChecked()
        save_config(self.cfg)
        if self.on_save_callback:
            self.on_save_callback(self.cfg)
        self.close()

    def closeEvent(self, event):
        # 설정창이 닫힐 때 클릭바 쿨다운을 부여하여 의도치 않은 잔여 클릭 방지 및 클릭바 최우선순위 복구
        if self.parent_window and hasattr(self.parent_window, '_ensure_topmost'):
            self.parent_window.is_cooling_down = True
            self.parent_window.cooldown_end_time = time.time() + 0.5
            self.parent_window._ensure_topmost()
        event.accept()

# ========================================================
# 4. 메인 머무름 클릭 바 윈도우 (ClickBarWindow)
# ========================================================
class ClickBarWindow(QWidget):
    """
    화면 최상단에 항상 떠 있는 8버튼 머무름 클릭 툴바.
    """
    def __init__(self):
        super().__init__()
        self.cfg = load_config()

        # 윈도우 속성 설정 (항상 위, 프레임리스, 툴 윈도우, 포커스 비활성화)
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_QuitOnClose, False)

        self.buttons = {}
        self.is_dragging_mouse = False  # DRAG 모드 동작 중 여부
        self.drag_start_pos = None     # 툴바 윈도우 자체 이동용
        self.is_follow_moving = False  # MOVE 버튼 클릭 토글 이동 모드
        self.follow_offset_x = 0
        self.follow_offset_y = 0
        self.follow_move_start_time = 0.0
        self.on_off_hover_ready = True  # ON/OFF 버튼 마우스 오버 토글 준비 플래그
        self.setup_dialog = None       # 설정창 인스턴스 (비모달 관리)
        self.last_topmost_check = 0.0  # 최상위 Z-order 보장 주기 관리

        # 1. UI 툴바 레이아웃 구성
        self._init_ui()

        # 2. 카운트다운 오버레이 생성
        self.overlay = DwellIndicatorOverlay()

        # 3. Dwell 감지 타이머 초기화 (25ms 주기 고속 감지)
        self.last_cursor_x = -1
        self.last_cursor_y = -1
        self.dwell_anchor_x = -1
        self.dwell_anchor_y = -1
        self.dwell_start_time = 0.0
        self.is_cooling_down = False
        self.cooldown_end_time = 0.0
        self.drag_mouse_start_time = 0.0

        self.dwell_timer = QTimer(self)
        self.dwell_timer.timeout.connect(self._check_dwell_tick)
        self.dwell_timer.start(25)

        # 초기 모드 적용 (기본 LEFT는 연속 모드로 시작)
        cur_m = self.cfg.get("current_mode", "LEFT")
        self.is_continuous = (cur_m == "LEFT")
        self.set_mode(cur_m, is_continuous=self.is_continuous)
        pos_x = self.cfg.get("pos_x", 400)
        pos_y = self.cfg.get("pos_y", 30)
        self.move(pos_x, pos_y)
        ico_path = os.path.join(get_base_dir(), "clickbar.ico")
        if os.path.exists(ico_path):
            self.setWindowIcon(QIcon(ico_path))

    def showEvent(self, event):
        super().showEvent(event)
        # Windows API를 호출하여 이 창이 클릭되어도 포커스를 뺏지 않도록(WS_EX_NOACTIVATE) 및 최상위(TOPMOST) 설정
        hwnd = int(self.winId())
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE | WS_EX_TOPMOST)
        self._ensure_topmost()

    def _ensure_topmost(self):
        """클릭바 및 오버레이가 어떤 창(설정창, 브라우저 등)보다도 항상 화면 최상단 최우선순위에 위치하도록 보장"""
        hwnd = int(self.winId())
        user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)
        if hasattr(self, 'overlay') and self.overlay and self.overlay.isVisible():
            ov_hwnd = int(self.overlay.winId())
            user32.SetWindowPos(ov_hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)

    def _apply_config_update(self, new_cfg):
        """설정창에서 변경된 설정을 즉시 실시간 동기화"""
        self.cfg = new_cfg
        self.set_mode(self.cfg.get("current_mode", "LEFT"))
        self._update_power_ui()

    def _init_ui(self):
        # 외곽 프레임 (30% 콤팩트 축소 마진)
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(3, 3, 3, 3)
        main_layout.setSpacing(0)

        self.frame = QFrame()
        self.frame.setStyleSheet("""
            QFrame {
                background-color: #E2E8F0;
                border: 1.5px solid #94A3B8;
                border-radius: 5px;
            }
        """)
        f_layout = QHBoxLayout(self.frame)
        f_layout.setContentsMargins(3, 3, 3, 3)
        f_layout.setSpacing(3)

        # 8개 버튼 정의 (키, 라벨)
        btn_defs = [
            ("ON/OFF", "ON/OFF"),
            ("LEFT",   "LEFT"),
            ("DOUBLE", "DOUBLE"),
            ("DRAG",   "DRAG"),
            ("RIGHT",  "RIGHT"),
            ("SETUP",  "SETUP"),
            ("EXIT",   "EXIT"),
            ("MOVE",   "MOVE")
        ]

        for key, label in btn_defs:
            btn = ClickBarButton(key, label, self)
            btn.clicked.connect(lambda checked=False, k=key: self._on_button_clicked(k))
            self.buttons[key] = btn
            f_layout.addWidget(btn)

        main_layout.addWidget(self.frame)
        self.frame.mousePressEvent = self.mousePressEvent

        # 전원 상태에 따른 초기 버튼 표시/숨김 동기화
        self._update_power_ui()

    def _update_power_ui(self):
        """전원(ON/OFF) 상태에 따라 버튼을 표시하거나 숨겨 툴바를 접고 펼침"""
        is_on = self.cfg.get("active", True)
        if "ON/OFF" in self.buttons:
            self.buttons["ON/OFF"].is_power_on = is_on
            self.buttons["ON/OFF"].update()

        other_keys = ["LEFT", "DOUBLE", "DRAG", "RIGHT", "SETUP", "EXIT", "MOVE"]
        if is_on:
            for k in other_keys:
                if k in self.buttons:
                    self.buttons[k].show()
        else:
            for k in other_keys:
                if k in self.buttons:
                    self.buttons[k].hide()

        self.frame.adjustSize()
        self.adjustSize()

        # 화면 우측이나 하단으로 잘려나가지 않도록 화면 경계 보정
        screen = QApplication.primaryScreen().availableGeometry()
        cur_x = self.x()
        cur_y = self.y()
        new_x = max(screen.left(), min(cur_x, screen.right() - self.width() - 5))
        new_y = max(screen.top(), min(cur_y, screen.bottom() - self.height() - 5))
        if new_x != cur_x or new_y != cur_y:
            self.move(new_x, new_y)

    def _toggle_power_by_hover(self):
        """마우스를 갖다 대면 ON ↔ OFF 자동 전환 (호버 토글)"""
        if self.on_off_hover_ready:
            self.on_off_hover_ready = False
            new_active = not self.cfg.get("active", True)
            self.cfg["active"] = new_active
            save_config(self.cfg)
            self._update_power_ui()
            if self.cfg.get("sound_enabled", True):
                play_sound(900 if new_active else 600, 40)

    def _on_off_hover_leave(self):
        """마우스가 ON/OFF 버튼을 벗어났을 때, 다음 호버 토글 준비 완료"""
        self.on_off_hover_ready = True

    def _get_button_under_cursor(self, cur_pos):
        """현재 마우스 커서 위치(QPoint 논리 좌표)에 위치한 버튼(key, btn)을 반환"""
        if not self.isVisible():
            return None, None
        for key, btn in self.buttons.items():
            if not btn.isVisible():
                continue
            btn_pos = btn.mapToGlobal(QPoint(0, 0))
            btn_rect = QRect(btn_pos, btn.size())
            if btn_rect.contains(cur_pos):
                return key, btn
        return None, None

    def _start_follow_moving(self):
        """마우스 커서를 따라 툴바를 이동시키는 모드 시작"""
        cur_pos = QCursor.pos()
        now = time.time()
        self.is_follow_moving = True
        self.follow_move_start_time = now
        self.dwell_start_time = now
        self.dwell_anchor_x = cur_pos.x()
        self.dwell_anchor_y = cur_pos.y()
        self.follow_offset_x = self.x() - cur_pos.x()
        self.follow_offset_y = self.y() - cur_pos.y()
        self.is_cooling_down = False
        if hasattr(self, 'overlay') and self.overlay:
            self.overlay.hide()
        if "MOVE" in self.buttons:
            self.buttons["MOVE"].is_active_mode = True
            self.buttons["MOVE"].update()
        if self.cfg.get("sound_enabled", True):
            play_sound(1500, 35)

    def _stop_follow_moving(self):
        """마우스 따라오기 이동 모드 종료 및 현재 위치 고정"""
        if not self.is_follow_moving:
            return
        self.is_follow_moving = False
        if "MOVE" in self.buttons:
            self.buttons["MOVE"].is_active_mode = False
            self.buttons["MOVE"].update()
        self.cfg["pos_x"] = self.x()
        self.cfg["pos_y"] = self.y()
        save_config(self.cfg)
        self.is_cooling_down = True
        self.dwell_start_time = time.time()
        if self.cfg.get("sound_enabled", True):
            play_sound(1000, 35)

    def set_mode(self, mode, is_continuous=None):
        """클릭 모드(LEFT, DOUBLE, DRAG, RIGHT) 변경 및 1회/연속 모드 동기화"""
        self.cfg["current_mode"] = mode
        if is_continuous is not None:
            self.is_continuous = is_continuous
        elif mode == "LEFT":
            self.is_continuous = True
        save_config(self.cfg)

        for k in ["LEFT", "DOUBLE", "DRAG", "RIGHT"]:
            if k in self.buttons:
                is_active = (k == mode)
                self.buttons[k].is_active_mode = is_active
                self.buttons[k].is_continuous = (self.is_continuous if is_active else False)
                self.buttons[k].update()

    def _on_button_clicked(self, key):
        """버튼 클릭 처리 (1회 클릭: 점선 1회 사용 / 2회 클릭: 꽉 찬 색상 연속 고정 사용)"""
        # 이동 모드 중일 때 어떤 버튼이든 클릭되면 이동을 멈춤
        if self.is_follow_moving:
            self._stop_follow_moving()
            return

        if key == "ON/OFF":
            new_active = not self.cfg.get("active", True)
            self.cfg["active"] = new_active
            save_config(self.cfg)
            self._update_power_ui()
            if self.cfg.get("sound_enabled", True):
                play_sound(900 if new_active else 600, 40)

        elif key in ["LEFT", "DOUBLE", "DRAG", "RIGHT"]:
            cur_mode = self.cfg.get("current_mode", "LEFT")

            # 만약 드래그 중이었는데 다른 모드로 바꾸면 드래그 자동 해제
            if self.is_dragging_mouse and key != "DRAG":
                self._release_drag()

            if key != cur_mode:
                # 1) 다른 버튼을 처음 선택한 경우:
                # LEFT는 항상 기본 연속(고정) 모드, 다른 버튼(DOUBLE, DRAG, RIGHT)은 1회용(점선) 모드로 시작!
                if key == "LEFT":
                    self.set_mode("LEFT", is_continuous=True)
                    if self.cfg.get("sound_enabled", True):
                        play_sound(1200, 30)
                else:
                    self.set_mode(key, is_continuous=False)
                    if self.cfg.get("sound_enabled", True):
                        play_sound(1200, 30)
            else:
                # 2) 이미 선택되어 있는 버튼을 다시 누른 경우:
                if key != "LEFT":
                    if not self.is_continuous:
                        # 1회(점선) 모드 -> 연속(꽉 찬 색상) 모드로 승격!
                        self.set_mode(key, is_continuous=True)
                        if self.cfg.get("sound_enabled", True):
                            play_sound(1600, 45)  # 연속 사용 고정 알림 고음 피드백
                    else:
                        # 이미 연속 모드 상태에서 다시 누르면 -> 기본 LEFT(연속)으로 복귀!
                        self.set_mode("LEFT", is_continuous=True)
                        if self.cfg.get("sound_enabled", True):
                            play_sound(1000, 30)
                else:
                    # LEFT 버튼을 다시 누른 경우 항상 연속 모드 유지
                    self.set_mode("LEFT", is_continuous=True)
                    if self.cfg.get("sound_enabled", True):
                        play_sound(1200, 30)

        elif key == "SETUP":
            if self.is_dragging_mouse:
                self._release_drag()
            if self.setup_dialog is None or not self.setup_dialog.isVisible():
                self.setup_dialog = ClickBarSetupDialog(self.cfg, on_save_callback=self._apply_config_update, parent_window=self)
                self.setup_dialog.show()
            else:
                self.setup_dialog.raise_()
                self.setup_dialog.activateWindow()
            # 클릭바가 설정창보다 더 최우선 최상위에 있도록 Z-order 갱신
            self._ensure_topmost()
            self.is_cooling_down = True
            self.cooldown_end_time = time.time() + 0.4

        elif key == "EXIT":
            self._sync_facetracker_config_off()
            self.close()
            app = QApplication.instance()
            if app:
                app.quit()
            sys.exit(0)

        elif key == "MOVE":
            # 헤드 마우스 및 클릭 이동 토글 (한 번 누르면 이동, 한 번 더 누르면 멈춤)
            if self.is_follow_moving:
                self._stop_follow_moving()
            else:
                self._start_follow_moving()

    def _release_drag(self):
        """드래그 상태 마우스 버튼 업 해제"""
        if self.is_dragging_mouse:
            user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            self.is_dragging_mouse = False
            self.cooldown_end_time = time.time() + 0.6
            if "DRAG" in self.buttons:
                self.buttons["DRAG"].is_dragging_state = False
                self.buttons["DRAG"].update()

    # ========================================================
    # 마우스 드래그를 통한 툴바 자유 위치 이동 헬퍼
    # ========================================================
    def _start_window_drag(self, global_pt):
        self.drag_start_pos = global_pt - self.frameGeometry().topLeft()

    def _perform_window_drag(self, global_pt):
        if self.drag_start_pos is not None:
            new_pos = global_pt - self.drag_start_pos
            screen = QApplication.primaryScreen().availableGeometry()
            nx = max(screen.left(), min(new_pos.x(), screen.right() - self.width()))
            ny = max(screen.top(), min(new_pos.y(), screen.bottom() - self.height()))
            self.move(nx, ny)

    # ========================================================
    # 마우스 드래그를 통한 툴바 자유 위치 이동 헬퍼
    # ========================================================
    def _start_native_drag(self):
        """Windows OS 네이티브 창 이동을 시작하여 끊김 없이 100% 부드럽게 마우스 드래그 수행"""
        self.is_cooling_down = True
        self.cooldown_end_time = time.time() + 0.6
        if hasattr(self, 'overlay') and self.overlay:
            self.overlay.hide()

        hwnd = int(self.winId())
        user32.ReleaseCapture()
        user32.SendMessageW(hwnd, 0x00A1, 2, 0)

        # 드래그 완료 후 최종 위치 저장 및 앵커 갱신
        self.cfg["pos_x"] = self.x()
        self.cfg["pos_y"] = self.y()
        save_config(self.cfg)

        cur_pos = QCursor.pos()
        self.dwell_anchor_x = cur_pos.x()
        self.dwell_anchor_y = cur_pos.y()
        self.dwell_start_time = time.time()
        self.cooldown_end_time = time.time() + 0.4

    def _start_window_drag(self, global_pt):
        self._start_native_drag()

    def _perform_window_drag(self, global_pt):
        pass

    def _end_window_drag(self):
        self.cfg["pos_x"] = self.x()
        self.cfg["pos_y"] = self.y()
        save_config(self.cfg)

    def mousePressEvent(self, event):
        if self.is_follow_moving:
            # 따라오기 모드 중 창 클릭 시 현재 위치 고정
            self._stop_follow_moving()
            event.accept()
            return
        if event.button() == Qt.LeftButton:
            self._start_native_drag()
            event.accept()

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)

    # ========================================================
    # Dwell Click 감지 핵심 엔진 루프
    # ========================================================
    def _check_dwell_tick(self):
        # 1. Qt의 전역 논리 좌표계(QPoint)로 커서 위치 획득 (High-DPI 배율 자동 보정)
        cur_pos = QCursor.pos()
        cur_x = cur_pos.x()
        cur_y = cur_pos.y()
        now = time.time()

        # [최우선순위 보장] 매 0.5초마다 어떤 창이 새로 뜨거나 활성화되더라도 클릭바를 화면 맨 위 최상위(HWND_TOPMOST)로 유지
        if now - self.last_topmost_check > 0.5:
            self.last_topmost_check = now
            self._ensure_topmost()

        # 0. MOVE 버튼 따라오기(Follow Moving) 모드 동작 중일 때
        if self.is_follow_moving:
            # 1) 사용자가 이동 중 물리 마우스 클릭을 누르면 즉시 멈춤 (시작 0.4초 이후 감지)
            if (now - self.follow_move_start_time > 0.4) and (user32.GetAsyncKeyState(0x01) & 0x8000):
                self._stop_follow_moving()
                return

            new_x = cur_x + self.follow_offset_x
            new_y = cur_y + self.follow_offset_y
            screen = QApplication.primaryScreen().availableGeometry()
            nx = max(screen.left(), min(new_x, screen.right() - self.width()))
            ny = max(screen.top(), min(new_y, screen.bottom() - self.height()))
            self.move(nx, ny)

            # 2) 시작 직후 0.6초간은 원하는 새 위치로 이동할 수 있도록 Dwell 자동 고정 유예
            if now - self.follow_move_start_time < 0.6:
                self.dwell_anchor_x = cur_x
                self.dwell_anchor_y = cur_y
                self.dwell_start_time = now
                self.overlay.hide()
                return

            # 3) 헤드 마우스 사용자가 원하는 위치에 마우스를 잠깐 멈추면(Dwell) 자동 고정
            dist_from_anchor = ((cur_x - self.dwell_anchor_x)**2 + (cur_y - self.dwell_anchor_y)**2)**0.5
            if dist_from_anchor > self.cfg.get("dwell_radius", 10):
                self.dwell_anchor_x = cur_x
                self.dwell_anchor_y = cur_y
                self.dwell_start_time = now
                self.overlay.hide()
            else:
                elapsed = now - self.dwell_start_time
                dwell_time = max(0.3, self.cfg.get("dwell_time", 0.8))
                if elapsed > 0.05 and self.cfg.get("visual_indicator", True):
                    self.overlay.set_progress(min(1.0, elapsed / dwell_time), cur_x, cur_y, "MOVE")
                if elapsed >= dwell_time:
                    self.overlay.hide()
                    self._stop_follow_moving()
            return

        # 1. 커서가 이전에 클릭했던 앵커 반경을 벗어났는지 확인 (쿨다운 해제)
        if self.is_cooling_down:
            if now < self.cooldown_end_time:
                self.overlay.hide()
                return
            dist = ((cur_x - self.dwell_anchor_x)**2 + (cur_y - self.dwell_anchor_y)**2)**0.5
            if dist > self.cfg.get("dwell_radius", 10):
                self.is_cooling_down = False
                self.dwell_anchor_x = cur_x
                self.dwell_anchor_y = cur_y
                self.dwell_start_time = now
            else:
                self.overlay.hide()
                return

        # 2. 커서 이동량 검사 (떨림 방지 반경)
        dist_from_anchor = ((cur_x - self.dwell_anchor_x)**2 + (cur_y - self.dwell_anchor_y)**2)**0.5
        if dist_from_anchor > self.cfg.get("dwell_radius", 10):
            # 사용자가 새 위치로 이동 중
            self.dwell_anchor_x = cur_x
            self.dwell_anchor_y = cur_y
            self.dwell_start_time = now
            self.overlay.hide()
            return

        # 3. 커서 위치 판별 (Qt 논리 좌표계 기준)
        # 3-1. 클릭바 프레임 영역 내부인지 확인
        frame_pos = self.frame.mapToGlobal(QPoint(0, 0))
        frame_rect = QRect(frame_pos, self.frame.size())
        is_on_bar = frame_rect.contains(cur_pos) or self.frameGeometry().contains(cur_pos)

        # 3-2. 정확히 어떤 버튼 위에 커서가 있는지 확인
        target_btn_key, target_btn = self._get_button_under_cursor(cur_pos)

        # 3-3. 설정창 위인지 확인
        is_on_setup = False
        if self.setup_dialog and self.setup_dialog.isVisible():
            is_on_setup = self.setup_dialog.geometry().contains(cur_pos)

        # 4. 커서가 멈춰 있는 시간 계산 (최소 0.1초 Dwell 완벽 수용: max 0.05s)
        elapsed = now - self.dwell_start_time
        base_dwell = max(0.05, self.cfg.get("dwell_time", 0.8))

        # 툴바 버튼을 바꿀 때는 오작동을 방지하기 위해 최소 0.25초 보장, 일반 영역은 사용자 지정값(최소 0.1초) 적용
        target_dwell = max(0.25, base_dwell * 1.3) if is_on_bar else base_dwell
        progress = min(1.0, elapsed / target_dwell)

        # 시각적 인디케이터 표시
        # 툴바 위에서는 정확히 버튼 위에 있을 때만 표시 (버튼 사이 여백 등에서는 표시하지 않음)
        should_show_overlay = self.cfg.get("visual_indicator", True) and (elapsed > 0.05)
        if is_on_bar:
            if not target_btn_key or not self.cfg.get("dwell_on_bar", True):
                should_show_overlay = False
        elif not is_on_setup and not self.cfg.get("active", True):
            should_show_overlay = False

        if should_show_overlay:
            if target_btn_key:
                overlay_mode = target_btn_key
            elif self.is_dragging_mouse:
                overlay_mode = "DRAG"
            else:
                overlay_mode = self.cfg.get("current_mode", "LEFT")
            self.overlay.set_progress(progress, cur_x, cur_y, overlay_mode)
        else:
            self.overlay.hide()

        # 5. 머무름 시간 도달 시 클릭 트리거!
        if elapsed >= target_dwell:
            self.overlay.hide()
            self.is_cooling_down = True
            self.cooldown_end_time = now + 0.35  # 안전 쿨다운

            # 핵심 보호 1: 마우스 드래그 중인 경우
            # 커서가 어디에 있든 '드롭 완료(LEFTUP)'만 안전하게 수행
            if self.is_dragging_mouse:
                if now - self.drag_mouse_start_time >= 0.35:
                    self._trigger_mouse_action(cur_x, cur_y)
                return

            # [최우선 판별]
            # 1순위: 클릭바 툴바 위에서의 머무름 처리
            # 툴바 영역 내에서는 절대 OS 마우스 클릭(mouse_event)이 호출되지 않도록 완전 차단!
            if is_on_bar:
                if self.cfg.get("dwell_on_bar", True) and target_btn_key:
                    self._on_button_clicked(target_btn_key)
            # 2순위: 설정창 위에서의 머무름 처리 (헤드마우스 사용자를 위한 위젯 직접 조작)
            elif is_on_setup:
                self._trigger_dialog_dwell(cur_x, cur_y)
            # 3순위: 일반 화면 및 다른 윈도우 창 위에서의 머무름 클릭 처리 (ON 상태일 때)
            else:
                if self.cfg.get("active", True):
                    self._trigger_mouse_action(cur_x, cur_y)

    def _trigger_dialog_dwell(self, gx, gy):
        """설정창 위에서 머물렀을 때 내부 위젯(저장/취소 버튼, 체크박스, 슬라이더)을 100% 확실하게 조작"""
        if not self.setup_dialog or not self.setup_dialog.isVisible():
            return
        dlg = self.setup_dialog
        local_pos = dlg.mapFromGlobal(QPoint(gx, gy))
        widget = dlg.childAt(local_pos)

        target = widget
        while target and target != dlg:
            if isinstance(target, (QPushButton, QCheckBox, QSlider)):
                break
            target = target.parentWidget()

        handled = False
        if target:
            if isinstance(target, QPushButton):
                target.click()
                handled = True
            elif isinstance(target, QCheckBox):
                target.click()
                handled = True
            elif isinstance(target, QSlider):
                w_pt = target.mapFromGlobal(QPoint(gx, gy))
                ratio = max(0.0, min(1.0, w_pt.x() / max(1, target.width())))
                val = int(target.minimum() + ratio * (target.maximum() - target.minimum()))
                target.setValue(val)
                handled = True

        if not handled:
            # 특정 위젯이 잡히지 않은 경우에만 OS 레벨 마우스 클릭 발생
            user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

        if self.cfg.get("sound_enabled", True):
            play_click_sound()

        self.is_cooling_down = True
        self.cooldown_end_time = time.time() + 0.5
        self.dwell_anchor_x = gx
        self.dwell_anchor_y = gy

    def _trigger_bar_dwell(self, gx, gy):
        """클릭바 버튼 위에서 머물렀을 때 해당 버튼 활성화 (손을 전혀 쓰지 않는 사용자 지원)"""
        # 드래그 중일 때는 툴바 버튼 Dwell 엄격히 차단
        if self.is_dragging_mouse:
            return

        target_btn_key, _ = self._get_button_under_cursor(QPoint(gx, gy))
        if target_btn_key:
            self._on_button_clicked(target_btn_key)

    def _trigger_mouse_action(self, gx, gy):
        """선택된 모드에 따른 실제 윈도우 마우스 이벤트 발생"""
        mode = self.cfg.get("current_mode", "LEFT")
        now = time.time()

        if mode == "LEFT":
            user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

        elif mode == "DOUBLE":
            user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            time.sleep(0.04)
            user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            self.cooldown_end_time = now + 0.5

        elif mode == "DRAG":
            if not self.is_dragging_mouse:
                # 1단계: 마우스 좌클릭 누른 상태 시작
                user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                self.is_dragging_mouse = True
                self.drag_mouse_start_time = now
                self.cooldown_end_time = now + 0.4  # 시작 직후 0.4초간 즉시 드롭 방지
                if "DRAG" in self.buttons:
                    self.buttons["DRAG"].is_dragging_state = True
                    self.buttons["DRAG"].update()
            else:
                # 2단계: 마우스 좌클릭 해제 (드롭 완료)
                user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                self.is_dragging_mouse = False
                self.cooldown_end_time = now + 0.6  # 드롭 후 0.6초간 안전 쿨다운
                if "DRAG" in self.buttons:
                    self.buttons["DRAG"].is_dragging_state = False
                    self.buttons["DRAG"].update()

        elif mode == "RIGHT":
            user32.mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
            user32.mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
            self.cooldown_end_time = now + 0.5

        # 클릭 사운드 피드백 (click.wav 재생)
        if self.cfg.get("sound_enabled", True):
            play_click_sound()

        # [1회 사용 / 연속 사용 복귀 로직]
        # 1회 사용 모드(not self.is_continuous)인 경우, 마우스 액션 1회 완료 후 즉시 기본 LEFT(연속) 모드로 자동 복귀!
        # (드래그 모드의 경우 1단계(Down)가 아닌 2단계(Drop 완료) 시 복귀)
        if not self.is_continuous and mode != "LEFT":
            if mode in ["DOUBLE", "RIGHT"] or (mode == "DRAG" and not self.is_dragging_mouse):
                self.set_mode("LEFT", is_continuous=True)

        # 동작 실행 후 쿨다운 상태 진입 및 앵커 갱신
        self.is_cooling_down = True
        self.dwell_anchor_x = gx
        self.dwell_anchor_y = gy

    def _sync_facetracker_config_off(self):
        """클릭바가 종료될 때 FaceTracker 설정 파일의 enable_click_bar도 False로 안전하게 동기화"""
        try:
            cfg_path = os.path.join(get_base_dir(), "facetracker_config.json")
            if os.path.exists(cfg_path):
                with open(cfg_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["enable_click_bar"] = False
                with open(cfg_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception:
            pass

    def closeEvent(self, event):
        # 종료 시 오버레이 및 타이머 해제
        self._release_drag()
        self.dwell_timer.stop()
        if self.overlay:
            self.overlay.close()
        self._sync_facetracker_config_off()
        event.accept()
        app = QApplication.instance()
        if app:
            app.quit()

# ========================================================
# 5. 진입점
# ========================================================
def main():
    app = QApplication(sys.argv)
    # 설정창 등 어떤 보조 창이 닫혀도 클릭바 프로세스가 종료되지 않도록 보장
    app.setQuitOnLastWindowClosed(False)
    window = ClickBarWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
