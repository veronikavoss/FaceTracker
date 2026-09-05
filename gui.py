import os
import sys
from PySide6.QtCore import Qt, QPoint, Signal, Slot, QSize
from PySide6.QtGui import QImage, QPixmap, QColor, QFont, QIcon, QPainter, QBrush, QPen
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QComboBox, QCheckBox, QFrame, QStackedWidget,
    QGraphicsDropShadowEffect, QSizePolicy, QSpacerItem, QScrollArea, QGridLayout,
    QDialog, QLineEdit, QMessageBox
)
from PySide6.QtMultimedia import QMediaDevices
import cv2
import numpy as np
import config
from pynput import keyboard

class DarkInputDialog(QDialog):
    """글자와 버튼이 선명하고 아름답게 보이는 다크 테마 입력 대화상자"""
    def __init__(self, parent, title, prompt):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(360, 160)
        self.setStyleSheet("""
            QDialog {
                background-color: #182234;
                border: 1px solid #33435C;
                border-radius: 10px;
                font-family: 'Pretendard', 'Malgun Gothic', '맑은 고딕', 'Segoe UI', sans-serif;
            }
            QLabel {
                color: #FFFFFF;
                font-size: 14px;
                font-weight: 700;
            }
            QLineEdit {
                background-color: #0D1420;
                color: #FFFFFF;
                border: 1.5px solid #38BDF8;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 14px;
                font-weight: 500;
            }
            QLineEdit:focus {
                border: 1.5px solid #7DD3FC;
                background-color: #111A29;
            }
            QPushButton#ConfirmBtn {
                background-color: #0284C7;
                color: #FFFFFF;
                font-size: 13px;
                font-weight: bold;
                border: none;
                border-radius: 6px;
                padding: 9px 18px;
            }
            QPushButton#ConfirmBtn:hover {
                background-color: #0369A1;
            }
            QPushButton#CancelBtn {
                background-color: #334155;
                color: #F8FAFC;
                font-size: 13px;
                font-weight: 600;
                border: none;
                border-radius: 6px;
                padding: 9px 18px;
            }
            QPushButton#CancelBtn:hover {
                background-color: #475569;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        
        self.prompt_lbl = QLabel(prompt)
        layout.addWidget(self.prompt_lbl)
        
        self.input_edit = QLineEdit()
        self.input_edit.setMaxLength(25)
        layout.addWidget(self.input_edit)
        
        btn_box = QHBoxLayout()
        btn_box.addStretch()
        
        self.cancel_btn = QPushButton("취소")
        self.cancel_btn.setObjectName("CancelBtn")
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.clicked.connect(self.reject)
        
        self.confirm_btn = QPushButton("확인")
        self.confirm_btn.setObjectName("ConfirmBtn")
        self.confirm_btn.setCursor(Qt.PointingHandCursor)
        self.confirm_btn.clicked.connect(self.accept)
        
        btn_box.addWidget(self.cancel_btn)
        btn_box.addWidget(self.confirm_btn)
        layout.addLayout(btn_box)
        
        self.input_edit.setFocus()

    def get_text(self):
        return self.input_edit.text()

# ========================================================
# QSS 프리미엄 다크 테마 스타일시트
# ========================================================
STYLE_SHEET = """
QWidget {
    font-family: 'Pretendard', 'Malgun Gothic', '맑은 고딕', 'Segoe UI', -apple-system, sans-serif;
    color: #F8FAFC;
    font-size: 13px;
}

/* 메인 윈도우 배경 및 테두리 (깊고 정돈된 딥 네이비 블랙) */
#MainContainer {
    background-color: #0A0F1A;
    border: 1.5px solid #2B3B56;
    border-radius: 12px;
}

/* 좌측 사이드바 (메인 배경과 확실한 경계 구분) */
#Sidebar {
    background-color: #0E1524;
    border-right: 1.5px solid #24324A;
    border-top-left-radius: 12px;
    border-bottom-left-radius: 12px;
}

/* 사이드바 탭 버튼 (선명하고 큼직한 가독성) */
QPushButton.NavButton {
    background-color: transparent;
    color: #CBD5E1;
    text-align: left;
    font-size: 14px;
    font-weight: 600;
    padding: 13px 18px;
    border: none;
    border-radius: 8px;
}

QPushButton.NavButton:hover {
    background-color: #1A263A;
    color: #FFFFFF;
}

QPushButton.NavButton:checked {
    background-color: #1E293B;
    color: #38BDF8;
    border-left: 4px solid #10B981;
    font-weight: bold;
}

/* 글래스모피즘 대시보드 카드 (메인 배경에서 확연히 떠오르는 고대비 밝은 톤) */
QFrame.DashboardCard {
    background-color: #182234;
    border: 1.5px solid #2D3E5B;
    border-radius: 10px;
}

QFrame.DashboardCard:hover {
    border-color: #3B4F73;
}

/* 대형 시작 버튼 (기본: 에메랄드 네온 글로우) */
QPushButton#StartButton {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10B981, stop:1 #059669);
    color: #FFFFFF;
    font-size: 16px;
    font-weight: 800;
    border-radius: 25px;
    border: 1.5px solid #34D399;
    padding: 14px 28px;
    letter-spacing: 0.5px;
}

QPushButton#StartButton:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #34D399, stop:1 #10B981);
}

QPushButton#StartButton:checked {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #EF4444, stop:1 #DC2626);
    border: 1.5px solid #F87171;
}

QPushButton#StartButton:checked:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #F87171, stop:1 #EF4444);
}

/* 슬라이더 스타일링 (카드 내부 깊은 음각 효과 & 선명한 핸들) */
QSlider::groove:horizontal {
    border: 1px solid #2A3B54;
    height: 7px;
    background: #0D1420;
    border-radius: 3px;
}

QSlider::sub-page:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284C7, stop:1 #38BDF8);
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: #38BDF8;
    border: 2px solid #FFFFFF;
    width: 18px;
    height: 18px;
    margin: -6px 0;
    border-radius: 9px;
}

QSlider::handle:horizontal:hover {
    background: #7DD3FC;
    width: 20px;
    height: 20px;
    margin: -7px 0;
    border-radius: 10px;
}

/* 콤보박스 (카드 대비 뚜렷한 음각 디자인과 고대비 텍스트) */
QComboBox {
    background-color: #0D1420;
    border: 1.5px solid #2D3E5B;
    border-radius: 6px;
    padding: 6px 12px;
    color: #FFFFFF;
    font-size: 13px;
    font-weight: 500;
}

QComboBox:hover {
    border-color: #38BDF8;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox QAbstractItemView {
    background-color: #182234;
    border: 1.5px solid #38BDF8;
    color: #FFFFFF;
    font-size: 13px;
    selection-background-color: #0284C7;
    selection-color: #FFFFFF;
    padding: 4px;
}

/* 체크박스 (또렷한 글씨와 선명한 체크 박스) */
QCheckBox {
    color: #F1F5F9;
    font-size: 13px;
    font-weight: 500;
    spacing: 9px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1.5px solid #3D5174;
    background-color: #0D1420;
}

QCheckBox::indicator:hover {
    border-color: #38BDF8;
}

QCheckBox::indicator:checked {
    background-color: #10B981;
    border-color: #34D399;
}

/* 보조 버튼 */
QPushButton.SecondaryButton {
    background-color: #243247;
    color: #F8FAFC;
    font-size: 12px;
    font-weight: 600;
    border: 1px solid #3D5174;
    border-radius: 6px;
    padding: 7px 14px;
}

QPushButton.SecondaryButton:hover {
    background-color: #33435C;
    color: #FFFFFF;
    border-color: #38BDF8;
}

/* 강조 보조 버튼 */
QPushButton.PrimaryActionBtn {
    background-color: #0284C7;
    color: #FFFFFF;
    font-size: 12px;
    font-weight: bold;
    border: 1px solid #38BDF8;
    border-radius: 6px;
    padding: 7px 14px;
}

QPushButton.PrimaryActionBtn:hover {
    background-color: #0369A1;
}

/* 위험/삭제 버튼 */
QPushButton.DangerBtn {
    background-color: #4A1A1A;
    color: #FCA5A5;
    font-size: 12px;
    font-weight: bold;
    border: 1px solid #991B1B;
    border-radius: 6px;
    padding: 7px 14px;
}

QPushButton.DangerBtn:hover {
    background-color: #5C1D1D;
    color: #EF4444;
    border-color: #DC2626;
}

/* 스크롤 영역 */
QScrollArea {
    border: none;
    background: transparent;
}
"""

class CustomTitleBar(QWidget):
    """모던 다크 커스텀 타이틀바 (창 드래그 및 최소화/닫기 버튼 내장)"""
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.drag_position = QPoint()
        self.setFixedHeight(38)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 10, 0)
        
        # 타이틀바 텍스트
        self.title_lbl = QLabel("Face Tracker")
        self.title_lbl.setStyleSheet("color: #E2E8F0; font-size: 13px; font-weight: 700; letter-spacing: 0.3px;")
        layout.addWidget(self.title_lbl)
        
        version_lbl = QLabel("v2.2")
        version_lbl.setStyleSheet("color: #64748B; font-size: 11px; font-weight: bold; margin-left: 6px;")
        layout.addWidget(version_lbl)
        
        layout.addStretch()
        
        # 최소화 버튼
        self.min_btn = QPushButton("─")
        self.min_btn.setFixedSize(28, 28)
        self.min_btn.setStyleSheet("""
            QPushButton { background: transparent; color: #CBD5E1; border: none; font-size: 11px; border-radius: 4px; }
            QPushButton:hover { background: #1E293B; color: #FFFFFF; }
        """)
        self.min_btn.clicked.connect(self.parent.showMinimized)
        layout.addWidget(self.min_btn)
        
        # 닫기 버튼
        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(28, 28)
        self.close_btn.setStyleSheet("""
            QPushButton { background: transparent; color: #CBD5E1; border: none; font-size: 13px; border-radius: 4px; }
            QPushButton:hover { background: #DC2626; color: #FFFFFF; }
        """)
        self.close_btn.clicked.connect(self.parent.close)
        layout.addWidget(self.close_btn)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.parent.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and not self.drag_position.isNull():
            self.parent.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()


class FaceTrackerGUI(QWidget):
    # 백엔드 스레드로부터 비디오 프레임 전달받는 Qt 시그널
    frame_received_signal = Signal(QImage, bool, int, int, int, int, int)
    tracking_toggled_signal = Signal(bool)

    def __init__(self, app_config, tracker):
        super().__init__()
        self.config = app_config
        self.tracker = tracker
        
        # 윈도우 기본 설정 (프레임리스 + 둥근 모서리)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.resize(880, 750)
        self.setMinimumSize(820, 700)
        
        self.setStyleSheet(STYLE_SHEET)
        
        # 카메라 하드웨어 이름 매핑 리스트: [(id, name), ...]
        self.camera_device_list = self._detect_camera_names()
        
        # 메인 컨테이너
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.container = QWidget()
        self.container.setObjectName("MainContainer")
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        
        # 1. 커스텀 타이틀바
        self.title_bar = CustomTitleBar(self)
        container_layout.addWidget(self.title_bar)
        
        # 2. 본문 (사이드바 + 스택 위젯 콘텐츠)
        content_box = QHBoxLayout()
        content_box.setContentsMargins(0, 0, 0, 0)
        content_box.setSpacing(0)
        
        # 좌측 사이드바
        self.sidebar = self._build_sidebar()
        content_box.addWidget(self.sidebar)
        
        # 우측 페이지 스택
        self.page_stack = QStackedWidget()
        self.page_stack.setStyleSheet("background-color: transparent;")
        
        self.home_page = self._build_home_page()
        self.settings_page = self._build_settings_page()
        self.help_page = self._build_help_page()
        
        self.page_stack.addWidget(self.home_page)
        self.page_stack.addWidget(self.settings_page)
        self.page_stack.addWidget(self.help_page)
        
        content_box.addWidget(self.page_stack)
        container_layout.addLayout(content_box)
        main_layout.addWidget(self.container)
        
        # 시그널 연결
        self.frame_received_signal.connect(self.update_video_frame)
        self.tracking_toggled_signal.connect(self.sync_tracking_ui)
        
        self.is_recording_hotkey = False
        self.key_listener = None
        self._is_frame_busy = False

    def _detect_camera_names(self):
        """QMediaDevices를 사용하여 시스템에 연결된 실제 카메라 원래 이름을 검출"""
        devs = QMediaDevices.videoInputs()
        result = []
        for i, d in enumerate(devs):
            name = d.description()
            if not name:
                name = f"카메라 {i}"
            result.append((i, name))
            
        if not result:
            result = [(0, "기본 카메라 (카메라 0)"), (1, "카메라 1")]
        return result

    def _get_current_cam_name(self):
        cur_id = self.config.get("camera_id", 0)
        for cid, cname in self.camera_device_list:
            if cid == cur_id:
                return cname
        return f"카메라 {cur_id}"

    def _build_sidebar(self):
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(160)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 16, 12, 16)
        layout.setSpacing(8)
        
        # 네비게이션 버튼들 (Home, Settings, Help 만 깔끔하게 배치)
        self.nav_home = QPushButton("  🏠  Home")
        self.nav_home.setProperty("class", "NavButton")
        self.nav_home.setCheckable(True)
        self.nav_home.setChecked(True)
        self.nav_home.clicked.connect(lambda: self._switch_page(0))
        layout.addWidget(self.nav_home)
        
        self.nav_settings = QPushButton("  ⚙️  Settings")
        self.nav_settings.setProperty("class", "NavButton")
        self.nav_settings.setCheckable(True)
        self.nav_settings.clicked.connect(lambda: self._switch_page(1))
        layout.addWidget(self.nav_settings)
        
        self.nav_help = QPushButton("  ❓  Help")
        self.nav_help.setProperty("class", "NavButton")
        self.nav_help.setCheckable(True)
        self.nav_help.clicked.connect(lambda: self._switch_page(2))
        layout.addWidget(self.nav_help)
        
        layout.addStretch()
        
        # 하단 단축키 힌트
        shortcut_box = QFrame()
        shortcut_box.setStyleSheet("background-color: #131B2A; border: 1px solid #28374E; border-radius: 8px; padding: 8px;")
        sc_layout = QVBoxLayout(shortcut_box)
        sc_layout.setContentsMargins(6, 6, 6, 6)
        sc_lbl = QLabel("Toggle Hotkey")
        sc_lbl.setStyleSheet("color: #94A3B8; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        self.sc_key_lbl = QLabel(f"[{self.config.get('tracking_toggle_key', 'F12').upper()}]")
        self.sc_key_lbl.setStyleSheet("color: #38BDF8; font-size: 13px; font-weight: 800;")
        sc_layout.addWidget(sc_lbl)
        sc_layout.addWidget(self.sc_key_lbl)
        layout.addWidget(shortcut_box)
        
        return sidebar

    def _switch_page(self, index):
        self.page_stack.setCurrentIndex(index)
        self.nav_home.setChecked(index == 0)
        self.nav_settings.setChecked(index == 1)
        self.nav_help.setChecked(index == 2)

    # ========================================================
    # 1. Home Page: 대형 카메라 화면 + 카메라 퀵 제어 + START 버튼
    # ========================================================
    def _build_home_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 14, 20, 16)
        layout.setSpacing(10)
        
        # 1-1. 대형 라이브 카메라 프리뷰 카드
        video_card = QFrame()
        video_card.setProperty("class", "DashboardCard")
        vc_layout = QVBoxLayout(video_card)
        vc_layout.setContentsMargins(14, 10, 14, 10)
        vc_layout.setSpacing(6)
        
        # 카드 상단 헤더
        vc_header = QHBoxLayout()
        vc_title = QLabel("LIVE VIDEO FEED")
        vc_title.setStyleSheet("font-size: 14px; font-weight: 800; color: #38BDF8; letter-spacing: 0.8px;")
        
        self.badge_detected = QLabel("추적 대기 중...")
        self.badge_detected.setStyleSheet("""
            background-color: #381A1A; color: #FCA5A5;
            font-size: 11px; font-weight: bold; padding: 3px 10px; border-radius: 5px;
            border: 1px solid #7F1D1D;
        """)
        vc_header.addWidget(vc_title)
        vc_header.addStretch()
        vc_header.addWidget(self.badge_detected)
        vc_layout.addLayout(vc_header)
        
        # 비디오 캔버스 라벨 (가로 540px, 세로 360px)
        self.video_canvas = QLabel()
        self.video_canvas.setFixedSize(540, 360)
        self.video_canvas.setStyleSheet("background-color: #000000; border: 1.5px solid #2B3A54; border-radius: 8px;")
        self.video_canvas.setAlignment(Qt.AlignCenter)
        vc_layout.addWidget(self.video_canvas, 0, Qt.AlignCenter)
        
        # 하단 카메라 메타정보 바
        vc_footer = QHBoxLayout()
        self.cam_name_lbl = QLabel(f"Device: {self._get_current_cam_name()}")
        self.cam_name_lbl.setStyleSheet("color: #E2E8F0; font-size: 12px; font-weight: 600;")
        
        self.cam_fps_lbl = QLabel("FPS: 0 | 640x480")
        self.cam_fps_lbl.setStyleSheet("color: #38BDF8; font-size: 12px; font-weight: 800;")
        vc_footer.addWidget(self.cam_name_lbl)
        vc_footer.addStretch()
        vc_footer.addWidget(self.cam_fps_lbl)
        vc_layout.addLayout(vc_footer)
        
        layout.addWidget(video_card)
        
        # 1-2. 카메라 퀵 컨트롤 카드 (실제 카메라 이름 반영!)
        cam_ctrl_card = QFrame()
        cam_ctrl_card.setProperty("class", "DashboardCard")
        cc_layout = QVBoxLayout(cam_ctrl_card)
        cc_layout.setContentsMargins(14, 12, 14, 12)
        cc_layout.setSpacing(10)
        
        # 1행: 카메라 선택 (실제 하드웨어 명칭 노출), 해상도, FPS 드롭다운
        row1 = QHBoxLayout()
        cam_lbl = QLabel("카메라 선택:")
        cam_lbl.setStyleSheet("color: #F1F5F9; font-size: 13px; font-weight: 600;")
        
        self.cam_combo = QComboBox()
        cur_cam_id = self.config.get("camera_id", 0)
        cur_idx = 0
        for idx, (cid, cname) in enumerate(self.camera_device_list):
            self.cam_combo.addItem(cname, cid)
            if cid == cur_cam_id:
                cur_idx = idx
        self.cam_combo.setCurrentIndex(cur_idx)
        self.cam_combo.currentIndexChanged.connect(self._on_camera_changed)
        
        res_lbl = QLabel("해상도:")
        res_lbl.setStyleSheet("color: #F1F5F9; font-size: 13px; font-weight: 600; margin-left: 12px;")
        self.res_combo = QComboBox()
        self.res_combo.addItems(["640x480", "1280x720", "320x240"])
        cur_res = f"{self.config.get('camera_width', 640)}x{self.config.get('camera_height', 480)}"
        self.res_combo.setCurrentText(cur_res)
        self.res_combo.currentIndexChanged.connect(self._on_resolution_changed)
        
        fps_lbl = QLabel("FPS:")
        fps_lbl.setStyleSheet("color: #F1F5F9; font-size: 13px; font-weight: 600; margin-left: 12px;")
        self.fps_combo = QComboBox()
        self.fps_combo.addItems(["30", "60"])
        self.fps_combo.setCurrentText(str(self.config.get("target_fps", 30)))
        self.fps_combo.currentIndexChanged.connect(self._on_fps_changed)
        
        row1.addWidget(cam_lbl)
        row1.addWidget(self.cam_combo, 1)
        row1.addWidget(res_lbl)
        row1.addWidget(self.res_combo)
        row1.addWidget(fps_lbl)
        row1.addWidget(self.fps_combo)
        cc_layout.addLayout(row1)
        
        # 2행: 자동 노출 및 저조도 고정 체크박스
        row2 = QHBoxLayout()
        self.auto_exp_chk = QCheckBox("카메라 자동 노출 켜기 (Auto Exposure)")
        self.auto_exp_chk.setChecked(self.config.get("auto_exposure", True))
        self.auto_exp_chk.toggled.connect(self._on_auto_exp_toggled)
        
        self.lock_fps_chk = QCheckBox("저조도 30FPS 수동 고정")
        self.lock_fps_chk.setChecked(self.config.get("lock_fps_low_light", False))
        self.lock_fps_chk.toggled.connect(self._on_lock_fps_toggled)
        
        row2.addWidget(self.auto_exp_chk)
        row2.addSpacing(24)
        row2.addWidget(self.lock_fps_chk)
        row2.addStretch()
        cc_layout.addLayout(row2)
        
        # 3행: 카메라 고급 설정 창 열기 버튼
        adv_cam_btn = QPushButton("📷  카메라 고급 설정 창 열기 (DirectShow Property Page)")
        adv_cam_btn.setProperty("class", "SecondaryButton")
        adv_cam_btn.setCursor(Qt.PointingHandCursor)
        adv_cam_btn.clicked.connect(self._open_cam_adv_settings)
        cc_layout.addWidget(adv_cam_btn)
        
        layout.addWidget(cam_ctrl_card)
        
        # 1-3. 하단 대형 START / STOP 토글 버튼 영역
        btn_card = QFrame()
        btn_card.setStyleSheet("background-color: transparent;")
        bc_layout = QVBoxLayout(btn_card)
        bc_layout.setContentsMargins(0, 2, 0, 0)
        bc_layout.setAlignment(Qt.AlignCenter)
        
        self.start_btn = QPushButton("▶   START TRACKING (F12)")
        self.start_btn.setObjectName("StartButton")
        self.start_btn.setCheckable(True)
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.setFixedSize(480, 52)
        
        # 에메랄드 글로우 드롭 섀도우 효과
        self.btn_glow = QGraphicsDropShadowEffect(self)
        self.btn_glow.setBlurRadius(24)
        self.btn_glow.setColor(QColor(16, 185, 129, 140))
        self.btn_glow.setOffset(0, 2)
        self.start_btn.setGraphicsEffect(self.btn_glow)
        
        self.start_btn.clicked.connect(self._toggle_tracking_clicked)
        bc_layout.addWidget(self.start_btn)
        
        # 하단 상태 텍스트
        self.status_text = QLabel("상태: 비활성 (F12를 누르거나 위 버튼을 클릭하여 추적 시작)")
        self.status_text.setStyleSheet("color: #94A3B8; font-size: 12px; font-weight: 600; margin-top: 6px;")
        self.status_text.setAlignment(Qt.AlignCenter)
        bc_layout.addWidget(self.status_text)
        
        layout.addWidget(btn_card)
        return page

    # ========================================================
    # 2. Settings Page: 모션 감도 슬라이더 + 단축키 + 프로필 관리
    # ========================================================
    def _build_settings_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)
        
        # 상단 타이틀 & 초기화 버튼
        title_box = QHBoxLayout()
        st_lbl = QLabel("⚙️ Tracking & Motion Settings")
        st_lbl.setStyleSheet("font-size: 17px; font-weight: 800; color: #FFFFFF;")
        
        reset_btn = QPushButton("↺  기본값 복원")
        reset_btn.setProperty("class", "SecondaryButton")
        reset_btn.setCursor(Qt.PointingHandCursor)
        reset_btn.clicked.connect(self._on_reset_defaults)
        
        title_box.addWidget(st_lbl)
        title_box.addStretch()
        title_box.addWidget(reset_btn)
        layout.addLayout(title_box)
        
        # 스크롤 영역
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        
        content = QWidget()
        c_layout = QVBoxLayout(content)
        c_layout.setContentsMargins(0, 0, 8, 0)
        c_layout.setSpacing(14)
        c_layout.setAlignment(Qt.AlignTop)  # 위에서부터 자연스럽게 정렬 (아래 여백 허용)
        
        # 2-1. 모션 및 감도 컨트롤 카드
        motion_card = QFrame()
        motion_card.setProperty("class", "DashboardCard")
        motion_card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        mc_layout = QVBoxLayout(motion_card)
        mc_layout.setContentsMargins(18, 16, 18, 16)
        mc_layout.setSpacing(14)
        
        mc_title = QLabel("모션 및 감도 컨트롤")
        mc_title.setStyleSheet("font-size: 14px; font-weight: 800; color: #38BDF8; letter-spacing: 0.5px;")
        mc_layout.addWidget(mc_title)
        
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(14)
        
        def make_field_lbl(text):
            lbl = QLabel(text)
            lbl.setStyleSheet("color: #F1F5F9; font-size: 13px; font-weight: 600;")
            return lbl

        # 민감도 X
        grid.addWidget(make_field_lbl("민감도 X:"), 0, 0)
        self.sx_badge = QLabel(f"{self.config.get('sensitivity_x', 27)}")
        self.sx_badge.setStyleSheet("color: #38BDF8; font-size: 14px; font-weight: 800; min-width: 32px;")
        grid.addWidget(self.sx_badge, 0, 1)
        self.sx_slider = QSlider(Qt.Horizontal)
        self.sx_slider.setRange(0, 50)
        self.sx_slider.setValue(int(self.config.get("sensitivity_x", 27)))
        self.sx_slider.valueChanged.connect(self._on_sx_changed)
        grid.addWidget(self.sx_slider, 0, 2)
        
        # 민감도 Y
        grid.addWidget(make_field_lbl("민감도 Y:"), 0, 3)
        self.sy_badge = QLabel(f"{self.config.get('sensitivity_y', 27)}")
        self.sy_badge.setStyleSheet("color: #38BDF8; font-size: 14px; font-weight: 800; min-width: 32px;")
        grid.addWidget(self.sy_badge, 0, 4)
        self.sy_slider = QSlider(Qt.Horizontal)
        self.sy_slider.setRange(0, 50)
        self.sy_slider.setValue(int(self.config.get("sensitivity_y", 27)))
        self.sy_slider.valueChanged.connect(self._on_sy_changed)
        grid.addWidget(self.sy_slider, 0, 5)
        
        # 임계값 (Deadzone)
        grid.addWidget(make_field_lbl("임계값:"), 1, 0)
        self.th_badge = QLabel(f"{self.config.get('motion_threshold', 2)}")
        self.th_badge.setStyleSheet("color: #F1F5F9; font-size: 14px; font-weight: 800; min-width: 32px;")
        grid.addWidget(self.th_badge, 1, 1)
        self.th_slider = QSlider(Qt.Horizontal)
        self.th_slider.setRange(0, 4)
        self.th_slider.setValue(int(self.config.get("motion_threshold", 2)))
        self.th_slider.valueChanged.connect(self._on_th_changed)
        grid.addWidget(self.th_slider, 1, 2)
        
        # 스무딩
        grid.addWidget(make_field_lbl("스무딩:"), 1, 3)
        self.sm_badge = QLabel(f"{self.config.get('smoothing', 3)}")
        self.sm_badge.setStyleSheet("color: #34D399; font-size: 14px; font-weight: 800; min-width: 32px;")
        grid.addWidget(self.sm_badge, 1, 4)
        self.sm_slider = QSlider(Qt.Horizontal)
        self.sm_slider.setRange(0, 6)
        self.sm_slider.setValue(int(self.config.get("smoothing", 3)))
        self.sm_slider.valueChanged.connect(self._on_sm_changed)
        grid.addWidget(self.sm_slider, 1, 5)
        
        # 가속도 (좌측: 0, 1, 2열)
        grid.addWidget(make_field_lbl("가속도:"), 2, 0)
        self.acc_badge = QLabel(f"{self.config.get('acceleration', 5)}")
        self.acc_badge.setStyleSheet("color: #FBBF24; font-size: 14px; font-weight: 800; min-width: 32px;")
        grid.addWidget(self.acc_badge, 2, 1)
        self.acc_slider = QSlider(Qt.Horizontal)
        self.acc_slider.setRange(0, 10)
        self.acc_slider.setValue(int(self.config.get("acceleration", 5)))
        self.acc_slider.valueChanged.connect(self._on_accel_changed)
        grid.addWidget(self.acc_slider, 2, 2)
        
        # 보정 주기 (우측: 3, 4, 5열)
        grid.addWidget(make_field_lbl("보정 주기:"), 2, 3)
        self.ci_badge = QLabel(f"{self.config.get('correction_interval', 5)}")
        self.ci_badge.setStyleSheet("color: #A78BFA; font-size: 14px; font-weight: 800; min-width: 32px;")
        grid.addWidget(self.ci_badge, 2, 4)
        self.ci_slider = QSlider(Qt.Horizontal)
        self.ci_slider.setRange(1, 20)
        self.ci_slider.setValue(int(self.config.get("correction_interval", 5)))
        self.ci_slider.valueChanged.connect(self._on_ci_changed)
        grid.addWidget(self.ci_slider, 2, 5)
        
        # 광량 감지 & 튐 억제
        grid.addWidget(make_field_lbl("광량 감지:"), 3, 0)
        self.il_badge = QLabel(f"{float(self.config.get('illumination_threshold', 10.0)):.1f}")
        self.il_badge.setStyleSheet("color: #F1F5F9; font-size: 14px; font-weight: 800; min-width: 42px;")
        grid.addWidget(self.il_badge, 3, 1)
        self.il_slider = QSlider(Qt.Horizontal)
        self.il_slider.setRange(10, 300)
        self.il_slider.setValue(int(float(self.config.get("illumination_threshold", 10.0)) * 10))
        self.il_slider.valueChanged.connect(self._on_il_changed)
        grid.addWidget(self.il_slider, 3, 2)
        
        grid.addWidget(make_field_lbl("튐 억제:"), 3, 3)
        self.sp_badge = QLabel(f"{float(self.config.get('spike_threshold', 15.0)):.1f}px")
        self.sp_badge.setStyleSheet("color: #F1F5F9; font-size: 14px; font-weight: 800; min-width: 48px;")
        grid.addWidget(self.sp_badge, 3, 4)
        self.sp_slider = QSlider(Qt.Horizontal)
        self.sp_slider.setRange(50, 500)
        self.sp_slider.setValue(int(float(self.config.get("spike_threshold", 15.0)) * 10))
        self.sp_slider.valueChanged.connect(self._on_sp_changed)
        grid.addWidget(self.sp_slider, 3, 5)
        
        mc_layout.addLayout(grid)
        c_layout.addWidget(motion_card)
        
        # 2-2. 단축키 설정 카드
        hk_card = QFrame()
        hk_card.setProperty("class", "DashboardCard")
        hk_card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        hc_layout = QVBoxLayout(hk_card)
        hc_layout.setContentsMargins(18, 14, 18, 14)
        hc_layout.setSpacing(10)
        
        hc_title = QLabel("단축키 설정")
        hc_title.setStyleSheet("font-size: 14px; font-weight: 800; color: #38BDF8; letter-spacing: 0.5px;")
        hc_layout.addWidget(hc_title)
        
        hk_row = QHBoxLayout()
        self.hk_info_lbl = QLabel(f"단축키: {self.config.get('tracking_toggle_key', 'F12').upper()}")
        self.hk_info_lbl.setStyleSheet("color: #FFFFFF; font-weight: 700; font-size: 13px;")
        
        self.hotkey_btn = QPushButton("단축키 변경")
        self.hotkey_btn.setProperty("class", "SecondaryButton")
        self.hotkey_btn.setCursor(Qt.PointingHandCursor)
        self.hotkey_btn.clicked.connect(self._start_hotkey_recording)
        
        hk_row.addWidget(self.hk_info_lbl)
        hk_row.addStretch()
        hk_row.addWidget(self.hotkey_btn)
        hc_layout.addLayout(hk_row)
        c_layout.addWidget(hk_card)
        
        # 2-3. 프로필 저장 및 관리 카드 (단축키 아래 신규 추가!)
        prof_card = QFrame()
        prof_card.setProperty("class", "DashboardCard")
        prof_card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        pc_layout = QVBoxLayout(prof_card)
        pc_layout.setContentsMargins(18, 16, 18, 16)
        pc_layout.setSpacing(12)
        
        pc_title = QLabel("💾 설정 프로필 관리 (Profiles)")
        pc_title.setStyleSheet("font-size: 14px; font-weight: 800; color: #38BDF8; letter-spacing: 0.5px;")
        pc_layout.addWidget(pc_title)
        
        # 1행: 프로필 선택 콤보박스
        p_row1 = QHBoxLayout()
        p_lbl = QLabel("현재 프로필:")
        p_lbl.setStyleSheet("color: #F1F5F9; font-size: 13px; font-weight: 600;")
        
        self.profile_combo = QComboBox()
        self._refresh_profile_combo()
        self.profile_combo.currentTextChanged.connect(self._on_profile_selected)
        
        p_row1.addWidget(p_lbl)
        p_row1.addWidget(self.profile_combo, 1)
        pc_layout.addLayout(p_row1)
        
        # 2행: 프로필 조작 버튼들 (새 프로필 추가, 현재 프로필 덮어쓰기, 삭제)
        p_row2 = QHBoxLayout()
        
        save_new_btn = QPushButton("➕ 새 프로필 저장")
        save_new_btn.setProperty("class", "PrimaryActionBtn")
        save_new_btn.setCursor(Qt.PointingHandCursor)
        save_new_btn.clicked.connect(self._on_save_new_profile)
        
        overwrite_btn = QPushButton("💾 현재 프로필 덮어쓰기")
        overwrite_btn.setProperty("class", "SecondaryButton")
        overwrite_btn.setCursor(Qt.PointingHandCursor)
        overwrite_btn.clicked.connect(self._on_overwrite_profile)
        
        delete_btn = QPushButton("🗑️ 삭제")
        delete_btn.setProperty("class", "DangerBtn")
        delete_btn.setCursor(Qt.PointingHandCursor)
        delete_btn.clicked.connect(self._on_delete_profile)
        
        p_row2.addWidget(save_new_btn)
        p_row2.addWidget(overwrite_btn)
        p_row2.addWidget(delete_btn)
        pc_layout.addLayout(p_row2)
        
        c_layout.addWidget(prof_card)
        c_layout.addStretch()  # 아래 여백을 자연스럽게 남김!
        
        scroll.setWidget(content)
        layout.addWidget(scroll)
        return page

    # ========================================================
    # 3. Help Page
    # ========================================================
    def _build_help_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)
        
        title = QLabel("Face Tracker 사용 안내")
        title.setStyleSheet("font-size: 17px; font-weight: 800; color: #FFFFFF;")
        layout.addWidget(title)
        
        card = QFrame()
        card.setProperty("class", "DashboardCard")
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(20, 18, 20, 18)
        c_layout.setSpacing(12)
        
        tips = [
            "🎯 <b>마우스 추적 시작/일시정지</b>: Home 탭의 <code>START TRACKING</code> 버튼을 클릭하거나 <code>F12</code> 단축키를 누르세요.",
            "📷 <b>카메라 퀵 제어</b>: Home 탭에서 웹캠 이름(로지텍 등)을 확인하고, 해상도(640x480/1280x720)와 노출을 바로 조작할 수 있습니다.",
            "💾 <b>프로필 관리</b>: Settings 탭에서 '게임용', '작업용', '정밀조준' 등 사용자만의 설정값을 프로필로 저장하고 언제든 불러올 수 있습니다."
        ]
        
        for t in tips:
            lbl = QLabel(t)
            lbl.setStyleSheet("color: #F1F5F9; font-size: 14px; line-height: 1.6; padding: 4px 0;")
            lbl.setWordWrap(True)
            c_layout.addWidget(lbl)
            
        layout.addWidget(card)
        layout.addStretch()
        return page

    # ========================================================
    # 프로필 관리 로직
    # ========================================================
    def _refresh_profile_combo(self):
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        profiles = self.config.get("profiles", {})
        cur = self.config.get("current_profile", "기본")
        for pname in profiles.keys():
            self.profile_combo.addItem(pname)
        self.profile_combo.setCurrentText(cur)
        self.profile_combo.blockSignals(False)

    def _on_profile_selected(self, pname):
        if not pname:
            return
        profiles = self.config.get("profiles", {})
        if pname in profiles:
            p_data = profiles[pname]
            self.config["current_profile"] = pname
            
            # 현재 슬라이더 및 config에 프로필 데이터 적용
            for k, v in p_data.items():
                self.config[k] = v
            config.save_config(self.config)
            
            # UI 슬라이더 업데이트 (블록 시그널 방지하면서 반영)
            self.sx_slider.setValue(int(p_data.get("sensitivity_x", 27)))
            self.sy_slider.setValue(int(p_data.get("sensitivity_y", 27)))
            self.th_slider.setValue(int(p_data.get("motion_threshold", 2)))
            self.sm_slider.setValue(int(p_data.get("smoothing", 3)))
            self.acc_slider.setValue(int(p_data.get("acceleration", 5)))
            self.il_slider.setValue(int(float(p_data.get("illumination_threshold", 10.0)) * 10))
            self.sp_slider.setValue(int(float(p_data.get("spike_threshold", 15.0)) * 10))
            
            self.sx_badge.setText(str(p_data.get("sensitivity_x", 27)))
            self.sy_badge.setText(str(p_data.get("sensitivity_y", 27)))
            self.th_badge.setText(str(p_data.get("motion_threshold", 2)))
            self.sm_badge.setText(str(p_data.get("smoothing", 3)))
            self.acc_badge.setText(str(p_data.get("acceleration", 5)))
            self.il_badge.setText(f"{float(p_data.get('illumination_threshold', 10.0)):.1f}")
            self.sp_badge.setText(f"{float(p_data.get('spike_threshold', 15.0)):.1f}px")
            
            if hasattr(self.tracker, "yunet_filter"):
                self.tracker.yunet_filter.config = self.config
                self.tracker.yunet_filter.reset()
                self.tracker.yunet_filter._build_accel_array()
                
            print(f"[프로필] '{pname}' 프로필이 적용되었습니다.")

    def _show_dark_info(self, title, text):
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setText(text)
        box.setStyleSheet("""
            QMessageBox { background-color: #182234; border: 1.5px solid #2D3E5B; border-radius: 10px; font-family: 'Pretendard', 'Malgun Gothic', '맑은 고딕', 'Segoe UI', sans-serif; }
            QLabel { color: #FFFFFF; font-size: 14px; font-weight: 600; }
            QPushButton { background-color: #0284C7; color: #FFFFFF; font-size: 13px; font-weight: bold; border-radius: 6px; padding: 7px 20px; min-width: 68px; }
            QPushButton:hover { background-color: #0369A1; }
        """)
        box.exec()

    def _show_dark_warning(self, title, text):
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setText(text)
        box.setIcon(QMessageBox.Warning)
        box.setStyleSheet("""
            QMessageBox { background-color: #182234; border: 1.5px solid #2D3E5B; border-radius: 10px; font-family: 'Pretendard', 'Malgun Gothic', '맑은 고딕', 'Segoe UI', sans-serif; }
            QLabel { color: #FFFFFF; font-size: 14px; font-weight: 600; }
            QPushButton { background-color: #D97706; color: #FFFFFF; font-size: 13px; font-weight: bold; border-radius: 6px; padding: 7px 20px; min-width: 68px; }
            QPushButton:hover { background-color: #B45309; }
        """)
        box.exec()

    def _show_dark_confirm(self, title, text):
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setText(text)
        box.setIcon(QMessageBox.Question)
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        yes_btn = box.button(QMessageBox.Yes)
        no_btn = box.button(QMessageBox.No)
        if yes_btn:
            yes_btn.setText("예")
        if no_btn:
            no_btn.setText("아니오")
        box.setStyleSheet("""
            QMessageBox { background-color: #182234; border: 1.5px solid #2D3E5B; border-radius: 10px; font-family: 'Pretendard', 'Malgun Gothic', '맑은 고딕', 'Segoe UI', sans-serif; }
            QLabel { color: #FFFFFF; font-size: 14px; font-weight: 600; }
            QPushButton { background-color: #243247; color: #F8FAFC; font-size: 13px; font-weight: 600; border: 1px solid #3D5174; border-radius: 6px; padding: 7px 20px; min-width: 68px; }
            QPushButton:hover { background-color: #33435C; color: #FFFFFF; border-color: #38BDF8; }
        """)
        return box.exec() == QMessageBox.Yes

    def _on_save_new_profile(self):
        dlg = DarkInputDialog(self, "새 프로필 저장", "저장할 프로필 이름을 입력하세요 (최대 25자):")
        if dlg.exec() == QDialog.Accepted:
            pname = dlg.get_text().strip()
            # 입력값 검증: 빈 값 및 제어문자 방어
            pname = "".join(c for c in pname if c.isprintable()).strip()
            if not pname:
                self._show_dark_warning("경고", "유효한 프로필 이름을 입력해주세요.")
                return
            
            profiles = self.config.setdefault("profiles", {})
            if pname in profiles:
                if not self._show_dark_confirm("확인", f"'{pname}' 프로필이 이미 존재합니다.\n덮어쓰시겠습니까?"):
                    return

            profiles[pname] = config.get_current_profile_data(self.config)
            self.config["current_profile"] = pname
            config.save_config(self.config)
            self._refresh_profile_combo()
            self._show_dark_info("성공", f"'{pname}' 프로필이 안전하게 저장되었습니다!")

    def _on_overwrite_profile(self):
        cur_name = self.profile_combo.currentText()
        if not cur_name:
            return
        profiles = self.config.setdefault("profiles", {})
        profiles[cur_name] = config.get_current_profile_data(self.config)
        config.save_config(self.config)
        self._show_dark_info("성공", f"'{cur_name}' 프로필에 현재 설정값이 저장되었습니다!")

    def _on_delete_profile(self):
        cur_name = self.profile_combo.currentText()
        if cur_name == "기본":
            self._show_dark_warning("경고", "'기본' 프로필은 삭제할 수 없습니다.")
            return
        
        if self._show_dark_confirm("확인", f"'{cur_name}' 프로필을 정말 삭제하시겠습니까?"):
            profiles = self.config.get("profiles", {})
            if cur_name in profiles:
                del profiles[cur_name]
                self.config["current_profile"] = "기본"
                config.save_config(self.config)
                self._refresh_profile_combo()
                self._on_profile_selected("기본")

    # ========================================================
    # 이벤트 핸들러 및 슬롯
    # ========================================================
    def _toggle_tracking_clicked(self):
        new_state = self.start_btn.isChecked()
        self.tracker.set_tracking(new_state)
        self.sync_tracking_ui(new_state)

    @Slot(bool)
    def sync_tracking_ui(self, enabled):
        """전역 핫키(F12) 또는 버튼 클릭 시 UI 상태 100% 동기화"""
        self.start_btn.blockSignals(True)
        self.start_btn.setChecked(enabled)
        self.start_btn.blockSignals(False)
        
        if enabled:
            self.start_btn.setText(f"⏸   추적 일시정지 ({self.config.get('tracking_toggle_key', 'F12').upper()})")
            self.btn_glow.setColor(QColor(239, 68, 68, 160))
            self.status_text.setText("상태: ● 추적 활성화 중 (코끝 추적 동작 중)")
            self.status_text.setStyleSheet("color: #34D399; font-size: 11px; font-weight: bold; margin-top: 4px;")
            self.badge_detected.setText("추적 활성화 중...")
            self.badge_detected.setStyleSheet("""
                background-color: #064E3B; color: #34D399;
                font-size: 10px; font-weight: bold; padding: 2px 8px; border-radius: 4px;
            """)
        else:
            self.start_btn.setText(f"▶   START TRACKING ({self.config.get('tracking_toggle_key', 'F12').upper()})")
            self.btn_glow.setColor(QColor(16, 185, 129, 140))
            self.status_text.setText("상태: 비활성 (F12를 누르거나 위 버튼을 클릭하여 추적 시작)")
            self.status_text.setStyleSheet("color: #64748B; font-size: 11px; font-weight: 500; margin-top: 4px;")
            self.badge_detected.setText("추적 대기 중...")
            self.badge_detected.setStyleSheet("""
                background-color: #2A1414; color: #EF4444;
                font-size: 10px; font-weight: bold; padding: 3px 10px; border-radius: 4px;
            """)

    @Slot(QImage, bool, int, int, int, int, int)
    def update_video_frame(self, q_img, tracking_enabled, nose_x, nose_y, fps, w, h):
        # 1. 창이 최소화되었거나 화면에 보이지 않을 때는 무거운 비디오 렌더링을 완전히 스킵 (CPU/GPU 절전)
        if self.isMinimized() or not self.isVisible():
            return

        # 2. Home 탭(인덱스 0)이 아닐 때는 비디오 렌더링을 완전히 스킵 (CPU/GPU 부하 0)
        if self.page_stack.currentIndex() != 0:
            return
            
        # 3. 메인 스레드가 이전 프레임 처리 중이면 신규 프레임을 드롭하여 Qt 큐 메모리 누적/프리징 방지
        if self._is_frame_busy:
            return
            
        self._is_frame_busy = True
        try:
            pixmap = QPixmap.fromImage(q_img)
            scaled_pix = pixmap.scaled(self.video_canvas.size(), Qt.KeepAspectRatio, Qt.FastTransformation)
            self.video_canvas.setPixmap(scaled_pix)
            
            self.cam_fps_lbl.setText(f"FPS: {fps} | {w}x{h}")
            self.cam_name_lbl.setText(f"Device: {self._get_current_cam_name()}")
        except Exception:
            pass
        finally:
            self._is_frame_busy = False

    # 슬라이더 변경 핸들러들
    def _on_sx_changed(self, val):
        self.config["sensitivity_x"] = val
        self.sx_badge.setText(str(val))
        config.save_config(self.config)

    def _on_sy_changed(self, val):
        self.config["sensitivity_y"] = val
        self.sy_badge.setText(str(val))
        config.save_config(self.config)

    def _on_th_changed(self, val):
        self.config["motion_threshold"] = val
        self.th_badge.setText(str(val))
        config.save_config(self.config)

    def _on_sm_changed(self, val):
        self.config["smoothing"] = val
        self.sm_badge.setText(str(val))
        config.save_config(self.config)

    def _on_accel_changed(self, val):
        self.config["acceleration"] = val
        self.acc_badge.setText(str(val))
        if hasattr(self.tracker, "yunet_filter"):
            self.tracker.yunet_filter._build_accel_array()
        config.save_config(self.config)

    def _on_ci_changed(self, val):
        self.config["correction_interval"] = val
        self.ci_badge.setText(str(val))
        config.save_config(self.config)

    def _on_il_changed(self, val):
        real_val = round(val / 10.0, 1)
        self.config["illumination_threshold"] = real_val
        self.il_badge.setText(f"{real_val:.1f}")
        config.save_config(self.config)

    def _on_sp_changed(self, val):
        real_val = round(val / 10.0, 1)
        self.config["spike_threshold"] = real_val
        self.sp_badge.setText(f"{real_val:.1f}px")
        config.save_config(self.config)

    def _on_camera_changed(self, combo_idx):
        if combo_idx < 0 or combo_idx >= len(self.camera_device_list):
            return
        cid, cname = self.camera_device_list[combo_idx]
        if cid != self.config.get("camera_id", 0):
            print(f"[카메라 전환] 장치 선택: {cname} (ID: {cid})")
            self.config["camera_id"] = cid
            config.save_config(self.config)
            self.cam_name_lbl.setText(f"Device: {cname}")
            self._restart_camera()

    def _on_resolution_changed(self, txt):
        try:
            w, h = map(int, txt.split('x'))
            if w != self.config.get("camera_width", 640) or h != self.config.get("camera_height", 480):
                self.config["camera_width"] = w
                self.config["camera_height"] = h
                config.save_config(self.config)
                self._restart_camera()
        except Exception as e:
            print(f"해상도 파싱 에러: {e}")

    def _on_fps_changed(self, txt):
        fps_val = int(txt)
        if fps_val != self.config.get("target_fps", 30):
            self.config["target_fps"] = fps_val
            config.save_config(self.config)
            self._restart_camera()

    def _on_auto_exp_toggled(self, checked):
        self.config["auto_exposure"] = checked
        config.save_config(self.config)
        if self.tracker:
            self.tracker.set_auto_exposure(checked)

    def _on_lock_fps_toggled(self, checked):
        self.config["lock_fps_low_light"] = checked
        config.save_config(self.config)
        if self.tracker:
            self.tracker.set_auto_exposure(self.config.get("auto_exposure", True) and not checked)

    def _open_cam_adv_settings(self):
        if self.tracker:
            self.tracker.open_camera_settings_dialog()

    def _on_reset_defaults(self):
        defaults = config.DEFAULT_CONFIG.copy()
        for k, v in config.DEFAULT_PROFILE_DATA.items():
            self.config[k] = v
        config.save_config(self.config)
        
        self.sx_slider.setValue(defaults["sensitivity_x"])
        self.sy_slider.setValue(defaults["sensitivity_y"])
        self.th_slider.setValue(defaults["motion_threshold"])
        self.sm_slider.setValue(defaults["smoothing"])
        self.acc_slider.setValue(defaults["acceleration"])
        self.ci_slider.setValue(defaults["correction_interval"])
        self.il_slider.setValue(int(defaults["illumination_threshold"] * 10))
        self.sp_slider.setValue(int(defaults["spike_threshold"] * 10))
        
        self.sx_badge.setText(str(defaults["sensitivity_x"]))
        self.sy_badge.setText(str(defaults["sensitivity_y"]))
        self.th_badge.setText(str(defaults["motion_threshold"]))
        self.sm_badge.setText(str(defaults["smoothing"]))
        self.acc_badge.setText(str(defaults["acceleration"]))
        self.ci_badge.setText(str(defaults["correction_interval"]))
        self.il_badge.setText(f"{defaults['illumination_threshold']:.1f}")
        self.sp_badge.setText(f"{defaults['spike_threshold']:.1f}px")
        
        if hasattr(self.tracker, "yunet_filter"):
            self.tracker.yunet_filter.config = self.config
            self.tracker.yunet_filter.reset()
            self.tracker.yunet_filter._build_accel_array()

    def _restart_camera(self):
        if self.tracker:
            if self.tracker.cap and self.tracker.cap.isOpened():
                self.tracker.cap.release()
            self.tracker._open_camera()

    def _start_hotkey_recording(self):
        if self.is_recording_hotkey:
            return
        self.is_recording_hotkey = True
        self.hotkey_btn.setText("키 누르는 중...")
        self.hotkey_btn.setStyleSheet("background-color: #D97706; color: #FFFFFF;")
        
        def on_press_temp(key):
            k_name = ""
            if hasattr(key, 'name') and key.name:
                k_name = key.name.lower()
            elif hasattr(key, 'char') and key.char:
                k_name = key.char.lower()
            
            if k_name:
                self.config["tracking_toggle_key"] = k_name
                config.save_config(self.config)
                self.hotkey_btn.setText("단축키 변경")
                self.hotkey_btn.setStyleSheet("")
                self.hk_info_lbl.setText(f"단축키: {k_name.upper()}")
                self.sc_key_lbl.setText(f"[{k_name.upper()}]")
                if not self.start_btn.isChecked():
                    self.start_btn.setText(f"▶   START TRACKING ({k_name.upper()})")
                else:
                    self.start_btn.setText(f"⏸   추적 일시정지 ({k_name.upper()})")
                self.is_recording_hotkey = False
                return False
                
        self.key_listener = keyboard.Listener(on_press=on_press_temp)
        self.key_listener.start()

    def closeEvent(self, event):
        """창 종료 시 웹캠 장치 점유를 완전히 해제하고 백그라운드 스레드를 안전하게 종료합니다."""
        print("[FaceTracker] 애플리케이션 종료 절차 시작...")
        # 1. 단축키 녹음 리스너 정리
        if hasattr(self, 'key_listener') and self.key_listener and self.key_listener.is_alive():
            try:
                self.key_listener.stop()
            except Exception:
                pass

        # 2. 트래커 스레드 및 웹캠 하드웨어 락 해제
        if self.tracker:
            try:
                self.tracker.stop_tracker()
                if self.tracker.cap and self.tracker.cap.isOpened():
                    self.tracker.cap.release()
                    print("[카메라] 웹캠 장치 점유가 안전하게 해제되었습니다.")
            except Exception as e:
                print(f"[카메라] 장치 해제 중 오류: {e}")
                
        event.accept()
