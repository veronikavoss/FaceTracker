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
        threading.Thread(target=winsound.Beep, args=(freq, duration), daemon=True).start()
    except Exception:
        pass

from PySide6.QtCore import Qt, QPoint, QRect, QTimer, QSize
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPainterPath
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
        
        self.setFixedSize(56, 56)
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
        radius = 20.0
        rect = QRect(int(center_x - radius), int(center_y - radius), int(radius * 2), int(radius * 2))

        # 1. 배경 가이드 링 (은은한 반투명 다크 링)
        bg_pen = QPen(QColor(15, 23, 42, 160), 4)
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
    사용자가 제공한 원본 이미지와 완벽하게 일치하는 벡터 아이콘 & 라벨 렌더링 버튼.
    """
    def __init__(self, key, label, parent=None):
        super().__init__(parent)
        self.key = key
        self.label_text = label
        self.is_active_mode = False
        self.is_power_on = True
        self.is_dragging_state = False
        self.setFixedSize(54, 52)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect()
        w = rect.width()
        h = rect.height()

        # 1. 버튼 배경 및 테두리 결정
        if self.is_active_mode:
            # 선택된 모드: 선명한 스카이블루 배경 (사용자 이미지의 LEFT 활성 스타일)
            bg_color = QColor(138, 226, 244)
            border_color = QColor(3, 105, 161)
            text_color = QColor(15, 23, 42)
        elif self.underMouse():
            bg_color = QColor(241, 245, 249)
            border_color = QColor(148, 163, 184)
            text_color = QColor(30, 41, 59)
        else:
            bg_color = QColor(248, 250, 252)
            border_color = QColor(203, 213, 225)
            text_color = QColor(51, 65, 85)

        # 특수 상태 배경
        if self.key == "DRAG" and self.is_dragging_state:
            bg_color = QColor(254, 215, 170)  # 드래그 중 앰버 하이라이트
            border_color = QColor(234, 88, 12)

        # 라운드 박스 렌더링
        painter.setPen(QPen(border_color, 1.5))
        painter.setBrush(QBrush(bg_color))
        painter.drawRoundedRect(2, 2, w - 4, h - 4, 4, 4)

        # 2. 아이콘 렌더링 (상단 32px 영역 중심)
        cx = w / 2.0
        cy = 18.0

        if self.key == "ON/OFF":
            # 전원 아이콘 (ON: 그린, OFF: 그레이)
            icon_color = QColor(34, 197, 94) if self.is_power_on else QColor(148, 163, 184)
            pen = QPen(icon_color, 2.5)
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            
            # 열린 원
            arc_r = 8.0
            painter.drawArc(QRect(int(cx - arc_r), int(cy - arc_r), int(arc_r * 2), int(arc_r * 2)), 30 * 16, 300 * 16)
            # 상단 수직선
            painter.drawLine(QPoint(int(cx), int(cy - 10)), QPoint(int(cx), int(cy - 2)))

        elif self.key == "LEFT":
            # 좌측 삼각형 화살표 ◀
            path = QPainterPath()
            path.moveTo(cx - 8, cy)
            path.lineTo(cx + 6, cy - 8)
            path.lineTo(cx + 6, cy + 8)
            path.closeSubpath()
            painter.setPen(QPen(QColor(15, 23, 42), 1.8))
            painter.setBrush(QBrush(QColor(226, 232, 240) if not self.is_active_mode else QColor(255, 255, 255)))
            painter.drawPath(path)

        elif self.key == "DOUBLE":
            # 이중 좌측 삼각형 ◀◀
            for offset in [-4, 5]:
                path = QPainterPath()
                path.moveTo(cx + offset - 7, cy)
                path.lineTo(cx + offset + 3, cy - 7)
                path.lineTo(cx + offset + 3, cy + 7)
                path.closeSubpath()
                painter.setPen(QPen(QColor(15, 23, 42), 1.6))
                painter.setBrush(QBrush(QColor(226, 232, 240) if not self.is_active_mode else QColor(255, 255, 255)))
                painter.drawPath(path)

        elif self.key == "DRAG":
            # 사용자 원본 이미지: 좌측 점선 + 우측으로 벌어지는 삼각형 (···◁)
            # 점선 3개 점
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor(15, 23, 42)))
            for dot_x in [cx - 11, cx - 7, cx - 3]:
                painter.drawEllipse(QPoint(int(dot_x), int(cy)), 1.5, 1.5)
            
            # 좌측을 향하는 삼각형 (꼭짓점이 좌측 점선을 향하고 우측이 세로 밑변)
            path = QPainterPath()
            path.moveTo(cx + 1, cy)
            path.lineTo(cx + 9, cy - 8)
            path.lineTo(cx + 9, cy + 8)
            path.closeSubpath()
            painter.setPen(QPen(QColor(15, 23, 42), 1.6))
            painter.setBrush(QBrush(QColor(226, 232, 240) if not self.is_active_mode else QColor(255, 255, 255)))
            painter.drawPath(path)

        elif self.key == "RIGHT":
            # 우측 삼각형 화살표 ▶
            path = QPainterPath()
            path.moveTo(cx + 8, cy)
            path.lineTo(cx - 6, cy - 8)
            path.lineTo(cx - 6, cy + 8)
            path.closeSubpath()
            painter.setPen(QPen(QColor(15, 23, 42), 1.8))
            painter.setBrush(QBrush(QColor(226, 232, 240) if not self.is_active_mode else QColor(255, 255, 255)))
            painter.drawPath(path)

        elif self.key == "SETUP":
            # 실제 스패너/렌치 모양 🔧 (45도 기울어진 오픈 엔드 렌치)
            painter.save()
            painter.translate(cx, cy)
            painter.rotate(-45)
            
            pen = QPen(QColor(51, 65, 85), 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(QBrush(QColor(226, 232, 240)))
            
            wrench = QPainterPath()
            # 렌치 자루
            wrench.moveTo(-2, 9)
            wrench.lineTo(2, 9)
            wrench.lineTo(2, -1)
            # 우측 턱
            wrench.lineTo(6, -2)
            wrench.lineTo(7, -6)
            wrench.lineTo(4, -8)
            # 렌치 입 (안쪽 홈)
            wrench.lineTo(1, -5)
            wrench.lineTo(-1, -5)
            # 좌측 턱
            wrench.lineTo(-4, -8)
            wrench.lineTo(-7, -6)
            wrench.lineTo(-6, -2)
            wrench.lineTo(-2, -1)
            wrench.closeSubpath()
            
            painter.drawPath(wrench)
            painter.restore()

        elif self.key == "EXIT":
            # 빨간 사각 테두리 안의 X ❎
            box_r = 7.0
            painter.setPen(QPen(QColor(185, 28, 28), 1.5))
            painter.setBrush(QBrush(QColor(254, 226, 226)))
            painter.drawRoundedRect(QRect(int(cx - box_r), int(cy - box_r), int(box_r * 2), int(box_r * 2)), 2, 2)
            
            painter.setPen(QPen(QColor(185, 28, 28), 2.0, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(QPoint(int(cx - 4), int(cy - 4)), QPoint(int(cx + 4), int(cy + 4)))
            painter.drawLine(QPoint(int(cx + 4), int(cy - 4)), QPoint(int(cx - 4), int(cy + 4)))

        elif self.key == "MOVE":
            # 4방향 독립 삼각형 화살표 ✥
            pen = QPen(QColor(51, 65, 85), 1.4)
            brush = QBrush(QColor(226, 232, 240))
            painter.setPen(pen)
            painter.setBrush(brush)
            
            # 상 (▲)
            up = QPainterPath()
            up.moveTo(cx, cy - 9)
            up.lineTo(cx - 5, cy - 3)
            up.lineTo(cx + 5, cy - 3)
            up.closeSubpath()
            painter.drawPath(up)
            
            # 하 (▼)
            dn = QPainterPath()
            dn.moveTo(cx, cy + 9)
            dn.lineTo(cx - 5, cy + 3)
            dn.lineTo(cx + 5, cy + 3)
            dn.closeSubpath()
            painter.drawPath(dn)
            
            # 좌 (◀)
            lf = QPainterPath()
            lf.moveTo(cx - 9, cy)
            lf.lineTo(cx - 3, cy - 5)
            lf.lineTo(cx - 3, cy + 5)
            lf.closeSubpath()
            painter.drawPath(lf)
            
            # 우 (▶)
            rt = QPainterPath()
            rt.moveTo(cx + 9, cy)
            rt.lineTo(cx + 3, cy - 5)
            rt.lineTo(cx + 3, cy + 5)
            rt.closeSubpath()
            painter.drawPath(rt)

        # 3. 하단 텍스트 라벨 렌더링
        font = QFont("Segoe UI", 8, QFont.Bold)
        font.setLetterSpacing(QFont.AbsoluteSpacing, 0.5)
        painter.setFont(font)
        painter.setPen(text_color)
        
        text_rect = QRect(0, h - 18, w, 14)
        painter.drawText(text_rect, Qt.AlignCenter, self.label_text)

# ========================================================
# 3. 설정 대화상자 (Setup Dialog)
# ========================================================
class ClickBarSetupDialog(QDialog):
    """
    머무름 클릭 바 세부 설정 (대기 시간, 반경, 사운드, 자동 복귀 등)
    """
    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.setWindowTitle("Click Bar 설정")
        self.setFixedSize(400, 420)
        self.setWindowFlags(Qt.Dialog | Qt.WindowStaysOnTopHint)
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

        # 1. 머무름 시간 슬라이더 (0.3초 ~ 2.5초)
        time_box = QVBoxLayout()
        t_header = QHBoxLayout()
        t_lbl = QLabel("머무름 대기 시간 (Dwell Time):")
        self.t_val_lbl = QLabel(f"{self.cfg['dwell_time']:.1f}초")
        self.t_val_lbl.setStyleSheet("color: #38BDF8; font-weight: bold;")
        t_header.addWidget(t_lbl)
        t_header.addStretch()
        t_header.addWidget(self.t_val_lbl)
        time_box.addLayout(t_header)

        self.time_slider = QSlider(Qt.Horizontal)
        self.time_slider.setRange(3, 25)  # 0.3 ~ 2.5s
        self.time_slider.setValue(int(self.cfg['dwell_time'] * 10))
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
        cancel_btn.clicked.connect(self.reject)
        
        save_btn = QPushButton("저장")
        save_btn.setObjectName("SaveBtn")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.clicked.connect(self._on_save)
        
        btn_box.addWidget(cancel_btn)
        btn_box.addWidget(save_btn)
        layout.addLayout(btn_box)

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
        self.accept()

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

        self.buttons = {}
        self.is_dragging_mouse = False  # DRAG 모드 동작 중 여부
        self.drag_start_pos = None     # 툴바 윈도우 자체 이동용

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

        self.dwell_timer = QTimer(self)
        self.dwell_timer.timeout.connect(self._check_dwell_tick)
        self.dwell_timer.start(25)

        # 초기 모드 적용 및 저장된 위치로 이동
        self.set_mode(self.cfg.get("current_mode", "LEFT"))
        pos_x = self.cfg.get("pos_x", 400)
        pos_y = self.cfg.get("pos_y", 30)
        self.move(pos_x, pos_y)

    def showEvent(self, event):
        super().showEvent(event)
        # Windows API를 호출하여 이 창이 클릭되어도 포커스를 뺏지 않도록(WS_EX_NOACTIVATE) 설정
        hwnd = int(self.winId())
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE | WS_EX_TOPMOST)

    def _init_ui(self):
        # 외곽 프레임 (사용자 이미지처럼 밝고 깔끔한 테두리 및 둥근 모서리)
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(0)

        self.frame = QFrame()
        self.frame.setStyleSheet("""
            QFrame {
                background-color: #E2E8F0;
                border: 1.5px solid #94A3B8;
                border-radius: 6px;
            }
        """)
        f_layout = QHBoxLayout(self.frame)
        f_layout.setContentsMargins(5, 5, 5, 5)
        f_layout.setSpacing(4)

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

        # 전원 상태 동기화
        self.buttons["ON/OFF"].is_power_on = self.cfg.get("active", True)

    def set_mode(self, mode):
        """클릭 모드(LEFT, DOUBLE, DRAG, RIGHT) 변경 및 버튼 하이라이트 동기화"""
        self.cfg["current_mode"] = mode
        save_config(self.cfg)

        for k in ["LEFT", "DOUBLE", "DRAG", "RIGHT"]:
            if k in self.buttons:
                self.buttons[k].is_active_mode = (k == mode)
                self.buttons[k].update()

    def _on_button_clicked(self, key):
        """버튼 클릭 처리"""
        if key == "ON/OFF":
            self.cfg["active"] = not self.cfg.get("active", True)
            self.buttons["ON/OFF"].is_power_on = self.cfg["active"]
            self.buttons["ON/OFF"].update()
            save_config(self.cfg)
            if self.cfg.get("sound_enabled", True):
                play_sound(900 if self.cfg["active"] else 600, 40)

        elif key in ["LEFT", "DOUBLE", "DRAG", "RIGHT"]:
            # 만약 드래그 중이었는데 다른 모드로 바꾸면 드래그 자동 해제
            if self.is_dragging_mouse and key != "DRAG":
                self._release_drag()
            self.set_mode(key)
            if self.cfg.get("sound_enabled", True):
                play_sound(1200, 30)

        elif key == "SETUP":
            dlg = ClickBarSetupDialog(self.cfg, self)
            dlg.exec()

        elif key == "EXIT":
            self.close()

        elif key == "MOVE":
            # MOVE 버튼 클릭 시 화면 상단/하단 중앙으로 빠른 스냅 이동 지원
            screen = QApplication.primaryScreen().geometry()
            cur_y = self.y()
            if cur_y < screen.height() / 2:
                new_y = screen.height() - self.height() - 60
            else:
                new_y = 30
            new_x = int((screen.width() - self.width()) / 2)
            self.move(new_x, new_y)
            self.cfg["pos_x"] = new_x
            self.cfg["pos_y"] = new_y
            save_config(self.cfg)

    def _release_drag(self):
        """드래그 상태 마우스 버튼 업 해제"""
        if self.is_dragging_mouse:
            user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            self.is_dragging_mouse = False
            if "DRAG" in self.buttons:
                self.buttons["DRAG"].is_dragging_state = False
                self.buttons["DRAG"].update()

    # ========================================================
    # 마우스 드래그를 통한 툴바 자유 위치 이동
    # ========================================================
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.drag_start_pos is not None:
            new_pos = event.globalPosition().toPoint() - self.drag_start_pos
            self.move(new_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.drag_start_pos = None
        self.cfg["pos_x"] = self.x()
        self.cfg["pos_y"] = self.y()
        save_config(self.cfg)
        event.accept()

    # ========================================================
    # Dwell Click 감지 핵심 엔진 루프
    # ========================================================
    def _check_dwell_tick(self):
        pt = POINT()
        if not user32.GetCursorPos(ctypes.byref(pt)):
            return

        cur_x = pt.x
        cur_y = pt.y
        now = time.time()

        # 1. 커서가 이전에 클릭했던 앵커 반경을 벗어났는지 확인 (쿨다운 해제)
        if self.is_cooling_down:
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

        # 3. 커서가 멈춰 있는 시간 계산
        elapsed = now - self.dwell_start_time
        dwell_time = max(0.2, self.cfg.get("dwell_time", 0.8))
        progress = min(1.0, elapsed / dwell_time)

        # 4. 커서 위치가 툴바 창 위인지 확인
        bar_rect = self.geometry()
        is_on_bar = bar_rect.contains(cur_x, cur_y)

        # 시각적 인디케이터 표시 (비활성 상태에서 바탕화면 머무름 시에는 숨김)
        should_show_overlay = self.cfg.get("visual_indicator", True) and (elapsed > 0.08)
        if not is_on_bar and not self.cfg.get("active", True):
            should_show_overlay = False

        if should_show_overlay:
            self.overlay.set_progress(progress, cur_x, cur_y, self.cfg.get("current_mode", "LEFT"))
        else:
            self.overlay.hide()

        # 5. 머무름 시간 도달 시 클릭 트리거!
        if elapsed >= dwell_time:
            self.overlay.hide()
            self.is_cooling_down = True  # 연속 클릭 방지 쿨다운 진입

            if is_on_bar:
                # 툴바 위에서의 머무름 처리
                if self.cfg.get("dwell_on_bar", True):
                    self._trigger_bar_dwell(cur_x, cur_y)
            else:
                # 일반 화면 위에서의 머무름 클릭 처리 (ON 상태일 때만)
                if self.cfg.get("active", True):
                    self._trigger_mouse_action(cur_x, cur_y)

    def _trigger_bar_dwell(self, gx, gy):
        """클릭바 버튼 위에서 머물렀을 때 해당 버튼 활성화 (손을 전혀 쓰지 않는 사용자 지원)"""
        local_pos = self.mapFromGlobal(QPoint(gx, gy))
        for key, btn in self.buttons.items():
            btn_rect = btn.geometry()
            # 프레임 안의 버튼 좌표 매핑
            frame_top_left = self.frame.pos()
            mapped_rect = QRect(
                frame_top_left.x() + btn_rect.x(),
                frame_top_left.y() + btn_rect.y(),
                btn_rect.width(),
                btn_rect.height()
            )
            if mapped_rect.contains(local_pos):
                self._on_button_clicked(key)
                break

    def _trigger_mouse_action(self, gx, gy):
        """선택된 모드에 따른 실제 윈도우 마우스 이벤트 발생"""
        mode = self.cfg.get("current_mode", "LEFT")

        if mode == "LEFT":
            user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

        elif mode == "DOUBLE":
            user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            time.sleep(0.04)
            user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

        elif mode == "DRAG":
            if not self.is_dragging_mouse:
                # 1단계: 마우스 좌클릭 누른 상태 시작
                user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                self.is_dragging_mouse = True
                if "DRAG" in self.buttons:
                    self.buttons["DRAG"].is_dragging_state = True
                    self.buttons["DRAG"].update()
            else:
                # 2단계: 마우스 좌클릭 해제 (드롭 완료)
                user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                self.is_dragging_mouse = False
                if "DRAG" in self.buttons:
                    self.buttons["DRAG"].is_dragging_state = False
                    self.buttons["DRAG"].update()

        elif mode == "RIGHT":
            user32.mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
            user32.mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)

        # 클릭 사운드 피드백
        if self.cfg.get("sound_enabled", True):
            play_sound(1400, 35)

        # 자동 LEFT 모드 복귀 (더블클릭, 우클릭, 드래그 완료 후)
        if self.cfg.get("auto_revert", True):
            if mode in ["DOUBLE", "RIGHT"] or (mode == "DRAG" and not self.is_dragging_mouse):
                self.set_mode("LEFT")

    def closeEvent(self, event):
        # 종료 시 오버레이 및 타이머 해제
        self._release_drag()
        self.dwell_timer.stop()
        if self.overlay:
            self.overlay.close()
        event.accept()

# ========================================================
# 5. 진입점
# ========================================================
def main():
    app = QApplication(sys.argv)
    window = ClickBarWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
