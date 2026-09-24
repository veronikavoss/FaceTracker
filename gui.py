import os
import sys
import subprocess
from PySide6.QtCore import Qt, QPoint, Signal, Slot, QSize, QTimer, QEvent
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
from pynput import keyboard  # type: ignore

REG_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
REG_APP_NAME = "FaceTracker"
OLD_REG_APP_NAME = "EnableViaCam_FaceTracker"

def is_standalone_exe() -> bool:
    """현재 프로세스가 Nuitka/PyInstaller 등으로 컴파일된 독립 실행 파일인지 여부"""
    if getattr(sys, 'frozen', False) or hasattr(sys, '__compiled__') or '__compiled__' in globals():
        return True
    exe_name = os.path.basename(sys.executable).lower()
    return not exe_name.startswith("python")

def get_expected_auto_start_cmd() -> str:
    """현재 실행 파일 기준 등록되어야 할 올바른 명령줄 반환"""
    base_dir = config.get_base_dir()
    if is_standalone_exe():
        exe_file = os.path.join(base_dir, "FaceTracker.exe")
        target_exe = exe_file if os.path.exists(exe_file) else os.path.abspath(sys.executable)
        return f'"{target_exe}"'
    else:
        main_py = os.path.abspath(os.path.join(base_dir, "main.py"))
        py_dir = os.path.dirname(sys.executable)
        pyw = os.path.join(py_dir, "pythonw.exe")
        exe_to_use = pyw if os.path.exists(pyw) else sys.executable
        return f'"{exe_to_use}" "{main_py}"'

def is_auto_start_windows_registered() -> bool:
    """Windows 시작 프로그램 레지스트리에 등록되어 있는지 검사"""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_READ) as key:
            for name in (REG_APP_NAME, OLD_REG_APP_NAME):
                try:
                    val, _ = winreg.QueryValueEx(key, name)
                    if val:
                        return True
                except FileNotFoundError:
                    pass
        return False
    except Exception:
        return False

def set_auto_start_windows(enable: bool) -> bool:
    """Windows 시작 프로그램 레지스트리(HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run) 등록 또는 삭제"""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enable:
                cmd = get_expected_auto_start_cmd()
                winreg.SetValueEx(key, REG_APP_NAME, 0, winreg.REG_SZ, cmd)
                # 이전 등록 키가 남아있으면 정리
                try:
                    winreg.DeleteValue(key, OLD_REG_APP_NAME)
                except FileNotFoundError:
                    pass
                print(f"[FaceTracker] 윈도우 시작 프로그램 레지스트리 등록 완료: {cmd}")
            else:
                for name in (REG_APP_NAME, OLD_REG_APP_NAME):
                    try:
                        winreg.DeleteValue(key, name)
                    except FileNotFoundError:
                        pass
                print("[FaceTracker] 윈도우 시작 프로그램 레지스트리 삭제 완료")
        return True
    except Exception as e:
        print(f"[시작프로그램 레지스트리 오류]: {e}")
        return False

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
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.clicked.connect(self.reject)
        
        self.confirm_btn = QPushButton("확인")
        self.confirm_btn.setObjectName("ConfirmBtn")
        self.confirm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
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

/* 툴팁 스타일 (다크 네이비 고대비 + 스카이블루 테두리) */
QToolTip {
    background-color: #0F172A;
    color: #F8FAFC;
    border: 1.5px solid #38BDF8;
    border-radius: 6px;
    padding: 7px 11px;
    font-size: 12px;
    font-weight: 500;
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
        self.win = parent
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
        self.min_btn.clicked.connect(self.win.showMinimized)
        layout.addWidget(self.min_btn)
        
        # 닫기 버튼
        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(28, 28)
        self.close_btn.setStyleSheet("""
            QPushButton { background: transparent; color: #CBD5E1; border: none; font-size: 13px; border-radius: 4px; }
            QPushButton:hover { background: #DC2626; color: #FFFFFF; }
        """)
        self.close_btn.clicked.connect(self.win.close)
        layout.addWidget(self.close_btn)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.win.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and not self.drag_position.isNull():
            self.win.move(event.globalPosition().toPoint() - self.drag_position)
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
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(880, 750)
        self.setMinimumSize(820, 700)
        
        self.setStyleSheet(STYLE_SHEET)
        
        ico_path = os.path.join(config.get_base_dir(), "facetracker.ico")
        if os.path.exists(ico_path):
            self.setWindowIcon(QIcon(ico_path))
        self.setWindowTitle("Face Tracker")
        
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

        # 머무름 클릭 바(Click Bar) 서브프로세스 관리
        self.click_bar_process = None
        self.click_bar_timer = QTimer(self)
        self.click_bar_timer.timeout.connect(self._check_click_bar_status)
        self.click_bar_timer.start(200)

        # 설정에 따라 시작 시 홈 화면 토글을 켜서 클릭바 자동 실행 (다음에 FaceTracker 열었을 때 적용)
        if self.config.get("enable_click_bar", False):
            QTimer.singleShot(400, lambda: self.click_bar_chk.setChecked(True))

        # 설정에 따라 앱 실행 시 추적기 자동 시작 (추적 시작 버튼 누르지 않아도 바로 추적)
        if self.config.get("auto_start_tracking", False):
            def _auto_start_tracking():
                if self.tracker:
                    self.tracker.set_tracking(True)
                    self.sync_tracking_ui(True)
                    print("[FaceTracker] '앱 실행 시 추적기 실행' 설정에 따라 코끝 추적이 자동 시작되었습니다.")
            QTimer.singleShot(600, _auto_start_tracking)

        # 설정에 'auto_start_windows'가 켜져 있으면 시작 프로그램 레지스트리 경로가 항상 최신 exe 위치와 일치하도록 보장 동기화
        if self.config.get("auto_start_windows", False):
            set_auto_start_windows(True)

    def _detect_camera_names(self):
        """QMediaDevices 및 Windows PnP 쿼리로 실제 카메라 하드웨어 이름과 DirectShow 인덱스를 100% 매핑"""
        # 1. DirectShow 백엔드로 실제 캡처 가능한 유효 인덱스 수집 (0~3 범위)
        valid_dshow_ids = []
        try:
            import cv2
            for i in range(4):
                cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                if cap.isOpened():
                    valid_dshow_ids.append(i)
                    cap.release()
        except Exception as e:
            print(f"[카메라 감지] DirectShow 스캔 예외: {e}")

        # 2. 실제 연결된 카메라 장치 명칭 수집
        device_names = []
        # 2-1. 1차 시도: QMediaDevices
        try:
            devs = QMediaDevices.videoInputs()
            for d in devs:
                dname = d.description().strip()
                if dname and dname not in device_names:
                    device_names.append(dname)
        except Exception as e:
            print(f"[카메라 감지] QMediaDevices 예외: {e}")

        # 2-2. 2차 시도: device_names가 비어있거나 부족할 때 PowerShell PnP 쿼리로 100% 보완
        if not device_names or (valid_dshow_ids and len(device_names) < len(valid_dshow_ids)):
            try:
                import subprocess
                flags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                cmd = 'powershell -NoProfile -Command "Get-PnpDevice -Class Camera,Image -Status OK | Select-Object -ExpandProperty FriendlyName"'
                out = subprocess.check_output(cmd, shell=True, timeout=2.5, creationflags=flags).decode('utf-8', errors='ignore')
                pnp_names = [line.strip() for line in out.splitlines() if line.strip()]
                for pname in pnp_names:
                    if pname not in device_names:
                        device_names.append(pname)
            except Exception as pe:
                print(f"[카메라 감지] PnP 쿼리 예외: {pe}")

        # 3. 유효 DirectShow 인덱스와 실제 하드웨어 이름 매핑
        result = []
        if valid_dshow_ids:
            for idx, dshow_id in enumerate(valid_dshow_ids):
                if idx < len(device_names):
                    name = device_names[idx]
                else:
                    name = f"카메라 {dshow_id}"
                result.append((dshow_id, name))
        elif device_names:
            for idx, name in enumerate(device_names):
                result.append((idx, name))
        else:
            result = [(0, "기본 카메라 (카메라 0)"), (1, "카메라 1")]

        print(f"[카메라 감지 완료] 검출된 카메라 목록: {result}")
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
        config.trim_process_memory()

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
        
        # 비디오 캔버스 라벨 (가로 480px, 세로 330px - 4:3 비율 최적화)
        self.video_canvas = QLabel()
        self.video_canvas.setFixedSize(480, 330)
        self.video_canvas.setStyleSheet("background-color: #000000; border: 1.5px solid #2B3A54; border-radius: 8px;")
        self.video_canvas.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vc_layout.addWidget(self.video_canvas, 0, Qt.AlignmentFlag.AlignCenter)
        
        # 하단 카메라 메타정보 바 (비디오 화면과 완전히 분리된 전용 독립 정보 바)
        vc_footer_frame = QFrame()
        vc_footer_frame.setStyleSheet("""
            QFrame {
                background-color: #0B111E;
                border: 1px solid #1E293B;
                border-radius: 6px;
            }
        """)
        vc_footer = QHBoxLayout(vc_footer_frame)
        vc_footer.setContentsMargins(12, 6, 12, 6)
        
        self.cam_name_lbl = QLabel(f"Device: {self._get_current_cam_name()}")
        self.cam_name_lbl.setStyleSheet("color: #CBD5E1; font-size: 12px; font-weight: 600; border: none; background: transparent;")
        
        self.cam_fps_lbl = QLabel("FPS: 0 | 640x480")
        self.cam_fps_lbl.setStyleSheet("color: #38BDF8; font-size: 12px; font-weight: 800; border: none; background: transparent;")
        vc_footer.addWidget(self.cam_name_lbl)
        vc_footer.addStretch()
        vc_footer.addWidget(self.cam_fps_lbl)
        
        vc_layout.addSpacing(4)
        vc_layout.addWidget(vc_footer_frame)
        
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
        
        row1.addWidget(cam_lbl)
        row1.addWidget(self.cam_combo, 1)
        
        opt_badge = QLabel("⚡ 640×480 @ 30 FPS (추적 최적화)")
        opt_badge.setStyleSheet("""
            QLabel {
                color: #38BDF8;
                background-color: #0F172A;
                border: 1px solid rgba(56, 189, 248, 0.35);
                border-radius: 6px;
                padding: 5px 12px;
                font-size: 12px;
                font-weight: 600;
                margin-left: 12px;
            }
        """)
        opt_badge.setToolTip("인풋렉 0과 저조도 노이즈 억제를 위해 얼굴 마우스 표준인 640×480 @ 30 FPS 최적 모드로 고정되어 있습니다.")
        row1.addWidget(opt_badge)
        cc_layout.addLayout(row1)
        
        # 2행: 카메라 고급 설정 창 열기 버튼 (홈 화면을 심플하게 정돈)
        adv_cam_btn = QPushButton("📷  카메라 고급 설정 창 열기 (DirectShow Property Page)")
        adv_cam_btn.setProperty("class", "SecondaryButton")
        adv_cam_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        adv_cam_btn.clicked.connect(self._open_cam_adv_settings)
        cc_layout.addWidget(adv_cam_btn)
        
        layout.addWidget(cam_ctrl_card)
        
        # 1-3. 하단 대형 START / STOP 토글 버튼 영역
        btn_card = QFrame()
        btn_card.setStyleSheet("background-color: transparent;")
        bc_layout = QVBoxLayout(btn_card)
        bc_layout.setContentsMargins(0, 2, 0, 0)
        bc_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 보조 기능: 머무름 클릭 바 토글 체크박스
        aux_box = QHBoxLayout()
        aux_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.click_bar_chk = QCheckBox("🖱️  머무름 클릭 바 (Click Bar) 함께 실행")
        self.click_bar_chk.setCursor(Qt.CursorShape.PointingHandCursor)
        self.click_bar_chk.setStyleSheet("""
            QCheckBox {
                color: #38BDF8;
                font-size: 13px;
                font-weight: 700;
                padding: 6px 14px;
                background-color: #111A29;
                border: 1.5px solid #233044;
                border-radius: 6px;
            }
            QCheckBox:hover {
                border-color: #38BDF8;
                background-color: #162235;
            }
        """)
        self.click_bar_chk.setChecked(False)
        self.click_bar_chk.toggled.connect(self._on_click_bar_toggled)
        aux_box.addWidget(self.click_bar_chk)
        bc_layout.addLayout(aux_box)
        bc_layout.addSpacing(6)

        self.start_btn = QPushButton("▶   START TRACKING (F12)")
        self.start_btn.setObjectName("StartButton")
        self.start_btn.setCheckable(True)
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
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
        self.status_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
        reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
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
        c_layout.setAlignment(Qt.AlignmentFlag.AlignTop)  # 위에서부터 자연스럽게 정렬 (아래 여백 허용)
        
        # 2-1. 시작 및 시스템 자동 실행 설정 카드 (최상단 배치!)
        startup_card = QFrame()
        startup_card.setProperty("class", "DashboardCard")
        startup_card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        sc_layout = QVBoxLayout(startup_card)
        sc_layout.setContentsMargins(18, 16, 18, 16)
        sc_layout.setSpacing(14)

        sc_title = QLabel("시작 및 자동 실행 설정")
        sc_title.setStyleSheet("font-size: 14px; font-weight: 800; color: #38BDF8; letter-spacing: 0.5px;")
        sc_layout.addWidget(sc_title)

        chk_grid = QGridLayout()
        chk_grid.setHorizontalSpacing(24)
        chk_grid.setVerticalSpacing(12)

        chk_style = """
            QCheckBox {
                color: #F1F5F9;
                font-size: 13px;
                font-weight: 700;
                spacing: 8px;
            }
            QCheckBox:hover {
                color: #38BDF8;
            }
        """

        # 1) 윈도우 시작 시 실행하기 (아이콘 제거, 순수 텍스트)
        self.auto_start_win_chk = QCheckBox("윈도우 시작 시 실행하기")
        self.auto_start_win_chk.setCursor(Qt.CursorShape.PointingHandCursor)
        self.auto_start_win_chk.setStyleSheet(chk_style)
        reg_active = is_auto_start_windows_registered()
        cfg_active = self.config.get("auto_start_windows", False)
        self.auto_start_win_chk.setChecked(reg_active or cfg_active)
        self.auto_start_win_chk.toggled.connect(self._on_auto_start_win_toggled)
        chk_grid.addWidget(self.auto_start_win_chk, 0, 0)

        # 2) 앱 실행 시 클릭바 실행 (아이콘 제거, 순수 텍스트)
        self.settings_click_bar_chk = QCheckBox("앱 실행 시 클릭바 실행")
        self.settings_click_bar_chk.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_click_bar_chk.setStyleSheet(chk_style)
        self.settings_click_bar_chk.setChecked(self.config.get("enable_click_bar", False))
        self.settings_click_bar_chk.toggled.connect(self._on_settings_click_bar_toggled)
        chk_grid.addWidget(self.settings_click_bar_chk, 0, 1)

        # 3) 앱 실행 시 추적기 실행 (오른쪽 가로 나란히 배치)
        self.auto_start_tracking_chk = QCheckBox("앱 실행 시 추적기 실행")
        self.auto_start_tracking_chk.setCursor(Qt.CursorShape.PointingHandCursor)
        self.auto_start_tracking_chk.setStyleSheet(chk_style)
        self.auto_start_tracking_chk.setChecked(self.config.get("auto_start_tracking", False))
        self.auto_start_tracking_chk.toggled.connect(self._on_auto_start_tracking_toggled)
        chk_grid.addWidget(self.auto_start_tracking_chk, 1, 0)

        # 4) 페이스 트래커 닫을 때 클릭바도 같이 닫기
        self.close_clickbar_on_exit_chk = QCheckBox("페이스 트래커 닫을 때 클릭바도 같이 닫기")
        self.close_clickbar_on_exit_chk.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_clickbar_on_exit_chk.setStyleSheet(chk_style)
        self.close_clickbar_on_exit_chk.setChecked(self.config.get("close_clickbar_on_exit", True))
        self.close_clickbar_on_exit_chk.toggled.connect(self._on_close_clickbar_on_exit_toggled)
        chk_grid.addWidget(self.close_clickbar_on_exit_chk, 1, 1)

        sc_layout.addLayout(chk_grid)

        c_layout.addWidget(startup_card)

        # 2-2. 모션 및 감도 컨트롤 카드
        motion_card = QFrame()
        motion_card.setProperty("class", "DashboardCard")
        motion_card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        mc_layout = QVBoxLayout(motion_card)
        mc_layout.setContentsMargins(18, 16, 18, 16)
        mc_layout.setSpacing(14)
        
        mc_title = QLabel("모션 및 감도 컨트롤")
        mc_title.setStyleSheet("font-size: 14px; font-weight: 800; color: #38BDF8; letter-spacing: 0.5px;")
        mc_layout.addWidget(mc_title)
        
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(14)
        
        def make_field_lbl(text, tooltip=None):
            lbl = QLabel(text)
            lbl.setStyleSheet("color: #F1F5F9; font-size: 13px; font-weight: 600;")
            if tooltip:
                lbl.setToolTip(tooltip)
                lbl.setCursor(Qt.CursorShape.PointingHandCursor)
            return lbl

        tip_sx = "가로(좌/우) 머리 움직임에 대한 마우스 포인터 이동 속도와 민감도를 조절합니다.\n값이 클수록 적은 움직임으로도 커서가 더 멀리 이동합니다."
        tip_sy = "세로(상/하) 머리 움직임에 대한 마우스 포인터 이동 속도와 민감도를 조절합니다.\n값이 클수록 적은 고개 움직임으로도 화면 위아래를 빠르게 이동합니다."
        tip_th = "미세한 머리 떨림이나 호흡으로 인한 불필요한 커서 흔들림을 방지하는 최소 움직임 임계값(Deadzone)입니다.\n이 값 이하의 미세한 움직임은 무시하여 정지 상태를 안정적으로 유지합니다."
        tip_sm = "마우스 포인터의 이동 궤적을 부드럽게 다듬는 평활화 강도입니다.\n값이 클수록 커서 떨림이 줄어들고 움직임이 부드러워지며, 값이 작을수록 즉각적이고 민첩하게 반응합니다."
        tip_acc = "머리를 빠르게 움직일 때 마우스 포인터 이동 거리를 추가 증폭하는 가속 기능입니다.\n고개를 크게 돌리지 않아도 화면 구석까지 손쉽게 이동할 수 있습니다."
        tip_ci = "장시간 사용 시 얼굴 인식 위치의 미세 누적 오차(Drift)를 재정렬하고 보정하는 주기(초 단위)입니다.\n기본값 5초가 가장 안정적입니다."
        tip_il = "주변 조명 변화, 모니터 화면 빛 반사, 그림자 등으로 인한 급격한 프레임 밝기 왜곡을 감지하여\n오작동을 방지하는 광량 임계값입니다."
        tip_sp = "재채기나 카메라 순간 노이즈 등으로 인해 마우스 포인터가 갑자기 엉뚱한 위치로\n순간 이동(튐 현상)하는 것을 감지하여 차단하는 최대 이동 제한 픽셀입니다."

        # 민감도 X
        grid.addWidget(make_field_lbl("민감도 X:", tip_sx), 0, 0)
        self.sx_badge = QLabel(f"{self.config.get('sensitivity_x', 27)}")
        self.sx_badge.setStyleSheet("color: #38BDF8; font-size: 14px; font-weight: 800; min-width: 32px;")
        self.sx_badge.setToolTip(tip_sx)
        grid.addWidget(self.sx_badge, 0, 1)
        self.sx_slider = QSlider(Qt.Orientation.Horizontal)
        self.sx_slider.setRange(0, 50)
        self.sx_slider.setValue(int(self.config.get("sensitivity_x", 27)))
        self.sx_slider.setToolTip(tip_sx)
        self.sx_slider.valueChanged.connect(self._on_sx_changed)
        grid.addWidget(self.sx_slider, 0, 2)
        
        # 민감도 Y
        grid.addWidget(make_field_lbl("민감도 Y:", tip_sy), 0, 3)
        self.sy_badge = QLabel(f"{self.config.get('sensitivity_y', 27)}")
        self.sy_badge.setStyleSheet("color: #38BDF8; font-size: 14px; font-weight: 800; min-width: 32px;")
        self.sy_badge.setToolTip(tip_sy)
        grid.addWidget(self.sy_badge, 0, 4)
        self.sy_slider = QSlider(Qt.Orientation.Horizontal)
        self.sy_slider.setRange(0, 50)
        self.sy_slider.setValue(int(self.config.get("sensitivity_y", 27)))
        self.sy_slider.setToolTip(tip_sy)
        self.sy_slider.valueChanged.connect(self._on_sy_changed)
        grid.addWidget(self.sy_slider, 0, 5)
        
        # 임계값 (Deadzone)
        grid.addWidget(make_field_lbl("임계값:", tip_th), 1, 0)
        self.th_badge = QLabel(f"{self.config.get('motion_threshold', 2)}")
        self.th_badge.setStyleSheet("color: #F1F5F9; font-size: 14px; font-weight: 800; min-width: 32px;")
        self.th_badge.setToolTip(tip_th)
        grid.addWidget(self.th_badge, 1, 1)
        self.th_slider = QSlider(Qt.Orientation.Horizontal)
        self.th_slider.setRange(0, 4)
        self.th_slider.setValue(int(self.config.get("motion_threshold", 2)))
        self.th_slider.setToolTip(tip_th)
        self.th_slider.valueChanged.connect(self._on_th_changed)
        grid.addWidget(self.th_slider, 1, 2)
        
        # 스무딩
        grid.addWidget(make_field_lbl("스무딩:", tip_sm), 1, 3)
        self.sm_badge = QLabel(f"{self.config.get('smoothing', 3)}")
        self.sm_badge.setStyleSheet("color: #34D399; font-size: 14px; font-weight: 800; min-width: 32px;")
        self.sm_badge.setToolTip(tip_sm)
        grid.addWidget(self.sm_badge, 1, 4)
        self.sm_slider = QSlider(Qt.Orientation.Horizontal)
        self.sm_slider.setRange(0, 6)
        self.sm_slider.setValue(int(self.config.get("smoothing", 3)))
        self.sm_slider.setToolTip(tip_sm)
        self.sm_slider.valueChanged.connect(self._on_sm_changed)
        grid.addWidget(self.sm_slider, 1, 5)
        
        # 가속도 (좌측: 0, 1, 2열)
        grid.addWidget(make_field_lbl("가속도:", tip_acc), 2, 0)
        self.acc_badge = QLabel(f"{self.config.get('acceleration', 5)}")
        self.acc_badge.setStyleSheet("color: #FBBF24; font-size: 14px; font-weight: 800; min-width: 32px;")
        self.acc_badge.setToolTip(tip_acc)
        grid.addWidget(self.acc_badge, 2, 1)
        self.acc_slider = QSlider(Qt.Orientation.Horizontal)
        self.acc_slider.setRange(0, 10)
        self.acc_slider.setValue(int(self.config.get("acceleration", 5)))
        self.acc_slider.setToolTip(tip_acc)
        self.acc_slider.valueChanged.connect(self._on_accel_changed)
        grid.addWidget(self.acc_slider, 2, 2)
        
        # 보정 주기 (우측: 3, 4, 5열)
        grid.addWidget(make_field_lbl("보정 주기:", tip_ci), 2, 3)
        self.ci_badge = QLabel(f"{self.config.get('correction_interval', 5)}")
        self.ci_badge.setStyleSheet("color: #A78BFA; font-size: 14px; font-weight: 800; min-width: 32px;")
        self.ci_badge.setToolTip(tip_ci)
        grid.addWidget(self.ci_badge, 2, 4)
        self.ci_slider = QSlider(Qt.Orientation.Horizontal)
        self.ci_slider.setRange(1, 20)
        self.ci_slider.setValue(int(self.config.get("correction_interval", 5)))
        self.ci_slider.setToolTip(tip_ci)
        self.ci_slider.valueChanged.connect(self._on_ci_changed)
        grid.addWidget(self.ci_slider, 2, 5)
        
        # 광량 감지 & 튐 억제
        grid.addWidget(make_field_lbl("광량 감지:", tip_il), 3, 0)
        self.il_badge = QLabel(f"{float(self.config.get('illumination_threshold', 10.0)):.1f}")
        self.il_badge.setStyleSheet("color: #F1F5F9; font-size: 14px; font-weight: 800; min-width: 42px;")
        self.il_badge.setToolTip(tip_il)
        grid.addWidget(self.il_badge, 3, 1)
        self.il_slider = QSlider(Qt.Orientation.Horizontal)
        self.il_slider.setRange(10, 300)
        self.il_slider.setValue(int(float(self.config.get("illumination_threshold", 10.0)) * 10))
        self.il_slider.setToolTip(tip_il)
        self.il_slider.valueChanged.connect(self._on_il_changed)
        grid.addWidget(self.il_slider, 3, 2)
        
        grid.addWidget(make_field_lbl("튐 억제:", tip_sp), 3, 3)
        self.sp_badge = QLabel(f"{float(self.config.get('spike_threshold', 15.0)):.1f}px")
        self.sp_badge.setStyleSheet("color: #F1F5F9; font-size: 14px; font-weight: 800; min-width: 48px;")
        self.sp_badge.setToolTip(tip_sp)
        grid.addWidget(self.sp_badge, 3, 4)
        self.sp_slider = QSlider(Qt.Orientation.Horizontal)
        self.sp_slider.setRange(50, 500)
        self.sp_slider.setValue(int(float(self.config.get("spike_threshold", 15.0)) * 10))
        self.sp_slider.setToolTip(tip_sp)
        self.sp_slider.valueChanged.connect(self._on_sp_changed)
        grid.addWidget(self.sp_slider, 3, 5)
        
        mc_layout.addLayout(grid)
        c_layout.addWidget(motion_card)
        
        # 2-3. 단축키 설정 카드
        hk_card = QFrame()
        hk_card.setProperty("class", "DashboardCard")
        hk_card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
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
        self.hotkey_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hotkey_btn.clicked.connect(self._start_hotkey_recording)
        
        hk_row.addWidget(self.hk_info_lbl)
        hk_row.addStretch()
        hk_row.addWidget(self.hotkey_btn)
        hc_layout.addLayout(hk_row)
        c_layout.addWidget(hk_card)
        
        # 2-4. 프로필 저장 및 관리 카드
        prof_card = QFrame()
        prof_card.setProperty("class", "DashboardCard")
        prof_card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
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
        save_new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_new_btn.clicked.connect(self._on_save_new_profile)
        
        overwrite_btn = QPushButton("💾 현재 프로필 덮어쓰기")
        overwrite_btn.setProperty("class", "SecondaryButton")
        overwrite_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        overwrite_btn.clicked.connect(self._on_overwrite_profile)
        
        delete_btn = QPushButton("🗑️ 삭제")
        delete_btn.setProperty("class", "DangerBtn")
        delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
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
        box.setIcon(QMessageBox.Icon.Warning)
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
        box.setIcon(QMessageBox.Icon.Question)
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        yes_btn = box.button(QMessageBox.StandardButton.Yes)
        no_btn = box.button(QMessageBox.StandardButton.No)
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
        return box.exec() == QMessageBox.StandardButton.Yes

    def _on_save_new_profile(self):
        dlg = DarkInputDialog(self, "새 프로필 저장", "저장할 프로필 이름을 입력하세요 (최대 25자):")
        if dlg.exec() == QDialog.DialogCode.Accepted:
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
            config.trim_process_memory()

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
            scaled_pix = pixmap.scaled(self.video_canvas.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
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
            print(f"[카메라 전환] 장치 선택: {cname} (DSHOW ID: {cid})")
            self.config["camera_id"] = cid
            config.save_config(self.config)
            self.cam_name_lbl.setText(f"Device: {cname}")
            
            # 추적 기능이 켜진 상태(START TRACKING)에서 카메라를 변경하더라도
            # 추적 플래그(is_tracking)는 끄지 않고 그대로 유지!
            # 새 카메라 영상에서 얼굴을 즉시 새로 잡도록 트래킹 내부 좌표만 안전하게 리셋.
            if self.tracker:
                self.tracker.reset_tracking_state()
            self._restart_camera()



    def _open_cam_adv_settings(self):
        if self.tracker:
            self.tracker.open_camera_settings_dialog()

    def _on_reset_defaults(self):
        defaults = config.DEFAULT_PROFILE_DATA.copy()
        for k, v in defaults.items():
            self.config[k] = v
        config.save_config(self.config)
        
        self.sx_slider.setValue(int(defaults.get("sensitivity_x", 25)))
        self.sy_slider.setValue(int(defaults.get("sensitivity_y", 25)))
        self.th_slider.setValue(int(defaults.get("motion_threshold", 2)))
        self.sm_slider.setValue(int(defaults.get("smoothing", 3)))
        self.acc_slider.setValue(int(defaults.get("acceleration", 5)))
        self.ci_slider.setValue(int(defaults.get("correction_interval", 5)))
        self.il_slider.setValue(int(float(defaults.get("illumination_threshold", 10.0)) * 10))
        self.sp_slider.setValue(int(float(defaults.get("spike_threshold", 15.0)) * 10))
        
        self.sx_badge.setText(str(defaults.get("sensitivity_x", 25)))
        self.sy_badge.setText(str(defaults.get("sensitivity_y", 25)))
        self.th_badge.setText(str(defaults.get("motion_threshold", 2)))
        self.sm_badge.setText(str(defaults.get("smoothing", 3)))
        self.acc_badge.setText(str(defaults.get("acceleration", 5)))
        self.ci_badge.setText(str(defaults.get("correction_interval", 5)))
        self.il_badge.setText(f"{float(defaults.get('illumination_threshold', 10.0)):.1f}")
        self.sp_badge.setText(f"{float(defaults.get('spike_threshold', 15.0)):.1f}px")
        
        if hasattr(self.tracker, "yunet_filter"):
            self.tracker.yunet_filter.config = self.config
            self.tracker.yunet_filter.reset()
            self.tracker.yunet_filter._build_accel_array()

    def _on_auto_start_win_toggled(self, checked):
        """윈도우 시작 시 자동 실행 토글 및 레지스트리 동기화"""
        self.config["auto_start_windows"] = checked
        config.save_config(self.config)
        success = set_auto_start_windows(checked)
        if success:
            print(f"[FaceTracker] 윈도우 시작 시 실행 설정이 {'등록' if checked else '해제'}되었습니다.")
        else:
            print(f"[FaceTracker] 윈도우 시작 시 실행 설정 변경 실패")

    def _restart_camera(self):
        if self.tracker:
            self.tracker.restart_camera()

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

    # ========================================================
    # 머무름 클릭 바(Click Bar) 수명주기 관리
    # ========================================================
    def _launch_click_bar(self):
        # 이미 클릭바 창이 떠 있거나 프로세스가 살아있으면 중복 실행 방지
        import ctypes
        user32 = ctypes.windll.user32
        existing_hwnd = user32.FindWindowW(None, "ClickBar")
        if not existing_hwnd:
            existing_hwnd = user32.FindWindowW(None, "Enable Viacam - ClickBar")
        if existing_hwnd:
            user32.ShowWindow(existing_hwnd, 9)  # SW_RESTORE
            user32.SetForegroundWindow(existing_hwnd)
            return

        if self.click_bar_process is not None and self.click_bar_process.poll() is None:
            return  # 이미 프로세스 실행 중
        
        base_dir = config.get_base_dir()
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0

        try:
            # 1. 배포 환경 최우선: FaceTracker.exe 자체 인자 호출 (--click-bar)
            #    중계 런처를 거치지 않고 직접 직속 자식 프로세스로 띄워 1:1 프로세스 라이프사이클 제어
            ft_exe = os.path.join(base_dir, "FaceTracker.exe")
            if os.path.exists(ft_exe):
                self.click_bar_process = subprocess.Popen(
                    [ft_exe, "--click-bar"],
                    cwd=base_dir,
                    creationflags=flags
                )
                print(f"[FaceTracker] FaceTracker.exe --click-bar 직속 구동 완료: {ft_exe}")
                return

            # 2. ClickBar.exe 단독 바이너리가 있는 경우
            cb_exe = os.path.join(base_dir, "ClickBar.exe")
            if os.path.exists(cb_exe):
                self.click_bar_process = subprocess.Popen(
                    [cb_exe],
                    cwd=base_dir,
                    creationflags=flags
                )
                print(f"[FaceTracker] ClickBar.exe 구동 완료: {cb_exe}")
                return

            # 3. 개발 환경 Fallback: Python 인터프리터로 click_bar.py 직접 실행
            py_path = os.path.join(base_dir, "click_bar.py")
            if not os.path.exists(py_path):
                parent_dir = os.path.dirname(base_dir)
                alt_py = os.path.join(parent_dir, "click_bar.py")
                if os.path.exists(alt_py):
                    py_path = alt_py
                    base_dir = parent_dir

            import shutil
            python_candidates = [
                r"D:\Program Files\Python\pythonw.exe",
                r"D:\Program Files\Python\python.exe",
                shutil.which("pythonw"),
                shutil.which("python"),
            ]
            if "python" in os.path.basename(sys.executable).lower():
                pyw_near = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
                if os.path.exists(pyw_near):
                    python_candidates.insert(0, pyw_near)
                python_candidates.insert(0, sys.executable)

            found_py = None
            for cand in python_candidates:
                if cand and os.path.exists(cand):
                    found_py = cand
                    break

            if found_py and os.path.exists(py_path):
                self.click_bar_process = subprocess.Popen(
                    [found_py, py_path],
                    cwd=base_dir,
                    creationflags=flags
                )
                print(f"[FaceTracker] 머무름 클릭 바(Click Bar) 개발 스크립트 구동 완료! ({found_py})")
            else:
                self.click_bar_process = subprocess.Popen(["pythonw", "click_bar.py"], cwd=base_dir, shell=True)
        except Exception as e:
            print(f"[FaceTracker] 클릭바 실행 실패: {e}")

    def _terminate_click_bar(self):
        """체크 해제 시 실행 중인 클릭바 프로세스 및 창을 즉시 완벽하게 종료"""
        import ctypes
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        WM_CLOSE = 0x0010
        PROCESS_TERMINATE = 0x0001

        # 1. 실행 중인 클릭바 창에 Win32 WM_CLOSE 메시지 전송 (정상적이고 안전한 종료 유도)
        try:
            for title in ["ClickBar", "Enable Viacam - ClickBar"]:
                hwnd = user32.FindWindowW(None, title)
                if hwnd:
                    user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
        except Exception:
            pass

        # 2. 관리 중인 서브프로세스 핸들이 있는 경우 대기 후 종료 (외부 taskkill.exe 호출 배제)
        #    * 중요: Windows 시스템 종료(Shutdown) 시 외부 프로세스(taskkill.exe)를 실행하면
        #      세션 종료 상태로 인해 DLL 초기화 실패(0xc0000142) 오류창이 발생하므로
        #      외부 바이너리 호출을 일절 배제하고 순수 커널 API(TerminateProcess)만을 사용하여 0.001초 만에 안전 종료합니다.
        if self.click_bar_process is not None:
            try:
                self.click_bar_process.wait(timeout=0.2)
            except Exception:
                try:
                    self.click_bar_process.kill()
                except Exception:
                    pass
            self.click_bar_process = None

        # 3. 만약 외부에서 단독 실행된 잔여 창이 여전히 남아있다면 강제 정리
        try:
            for title in ["ClickBar", "Enable Viacam - ClickBar"]:
                hwnd = user32.FindWindowW(None, title)
                if hwnd:
                    pid = ctypes.c_ulong()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    if pid.value > 0:
                        h_proc = kernel32.OpenProcess(PROCESS_TERMINATE, False, pid.value)
                        if h_proc:
                            kernel32.TerminateProcess(h_proc, 0)
                            kernel32.CloseHandle(h_proc)
        except Exception:
            pass

        print("[FaceTracker] 머무름 클릭 바(Click Bar)가 완벽하게 종료되었습니다.")

    def _on_settings_click_bar_toggled(self, checked):
        """Settings 페이지의 '앱 실행 시 클릭바 실행' 설정 핸들러 (다음 시작 시 적용, 현재 프로세스는 건드리지 않음)"""
        self.config["enable_click_bar"] = checked
        config.save_config(self.config)
        print(f"[FaceTracker] 시작 시 클릭바 자동 실행 설정 저장됨: {checked} (현재 실행 상태는 변경되지 않음)")

    def _on_auto_start_tracking_toggled(self, checked):
        """Settings 페이지의 '앱 실행 시 추적기 실행' 설정 핸들러 (다음 시작 시 적용)"""
        self.config["auto_start_tracking"] = checked
        config.save_config(self.config)
        print(f"[FaceTracker] 시작 시 추적기 자동 실행 설정 저장됨: {checked}")

    def _on_close_clickbar_on_exit_toggled(self, checked):
        """Settings 페이지의 '페이스 트래커 닫을 때 클릭바도 같이 닫기' 설정 핸들러"""
        self.config["close_clickbar_on_exit"] = checked
        config.save_config(self.config)
        print(f"[FaceTracker] 페이스 트래커 종료 시 클릭바 함께 닫기 설정 저장됨: {checked}")

    def _on_click_bar_toggled(self, checked):
        """Home 페이지의 머무름 클릭 바 토글: 현재 클릭바 즉시 켜기/끄기 실시간 제어"""
        if checked:
            self._launch_click_bar()
        else:
            self._terminate_click_bar()

    def _check_click_bar_status(self):
        """외부에서 클릭바 창이 닫혔을 때 Home 토글만 해제 (Settings 영구 설정값은 보존)"""
        import ctypes
        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW(None, "ClickBar")
        if not hwnd:
            hwnd = user32.FindWindowW(None, "Enable Viacam - ClickBar")

        # 프로세스가 종료되었거나 창이 사라진 경우
        is_running = False
        if self.click_bar_process is not None and self.click_bar_process.poll() is None:
            is_running = True
        elif hwnd:
            is_running = True

        if not is_running:
            self.click_bar_process = None
            if hasattr(self, 'click_bar_chk') and self.click_bar_chk.isChecked():
                self.click_bar_chk.blockSignals(True)
                self.click_bar_chk.setChecked(False)
                self.click_bar_chk.blockSignals(False)

    def changeEvent(self, event):
        """창이 최소화될 때 UI 렌더링 캐시 및 비디오 버퍼를 즉시 OS에 반환하여 백그라운드 메모리 극소화"""
        if event.type() == QEvent.Type.WindowStateChange:
            if self.isMinimized():
                config.trim_process_memory()
        super().changeEvent(event)

    def closeEvent(self, event):
        """창 종료 시 웹캠 장치 점유를 완전히 해제하고 백그라운드 스레드를 안전하게 종료합니다."""
        print("[FaceTracker] 애플리케이션 종료 절차 시작...")
        # 1. 클릭바 서브프로세스 안전 종료 (설정 활성화 시에만 종료)
        if self.config.get("close_clickbar_on_exit", True):
            self._terminate_click_bar()
        else:
            print("[FaceTracker] '페이스 트래커 닫을 때 클릭바도 같이 닫기' 설정이 꺼져 있어 클릭바를 유지합니다.")

        # 2. 단축키 녹음 리스너 정리
        if hasattr(self, 'key_listener') and self.key_listener and self.key_listener.is_alive():
            try:
                self.key_listener.stop()
            except Exception:
                pass

        # 3. 트래커 스레드 및 웹캠 하드웨어 락 해제
        if self.tracker:
            try:
                self.tracker.stop_tracker()
                if self.tracker.cap and self.tracker.cap.isOpened():
                    self.tracker.cap.release()
                    print("[카메라] 웹캠 장치 점유가 안전하게 해제되었습니다.")
            except Exception as e:
                print(f"[카메라] 장치 해제 중 오류: {e}")
                
        config.trim_process_memory()
        event.accept()
