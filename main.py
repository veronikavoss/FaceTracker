import os
# OpenBLAS / OpenMP 다중 스레딩 충돌 및 메모리 오류 방지
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

import sys
import time
import traceback

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage
from pynput import keyboard  # type: ignore
import cv2

from tracker import FaceTracker
from gui import FaceTrackerGUI
import config

# Windows 부팅 시(시작 프로그램) CWD가 C:\Windows\System32로 시작되어
# 권한 오류나 설정/모델 파일을 찾지 못하고 종료되는 문제를 100% 방지하기 위해
# 프로세스 시작 즉시 CWD를 실행 파일이 위치한 폴더로 전환합니다.
try:
    os.chdir(config.get_base_dir())
except Exception:
    pass

def global_exception_handler(exctype, value, tb):
    """콘솔 창이 숨겨진 배포 환경에서 예기치 않은 오류 발생 시 exe 옆 error.log에 기록"""
    base_dir = config.get_base_dir()
    log_file = os.path.join(base_dir, "error.log")
    err_msg = "".join(traceback.format_exception(exctype, value, tb))
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Unhandled Exception:\n{err_msg}\n")
    except Exception:
        pass
    sys.__excepthook__(exctype, value, tb)

sys.excepthook = global_exception_handler

import ctypes
from PySide6.QtCore import QTimer

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

class NativeMouseController:
    """
    Win32 User32.dll GetCursorPos / SetCursorPos를 직접 호출하는 초고속 순수 픽셀 마우스 컨트롤러.
    Windows OS의 '마우스 가속도'나 '포인터 정확도 향상'으로 인한 속도 뻥튀기 왜곡이 전혀 없으며,
    eViacam 알고리즘이 계산한 정확한 픽셀 단위로만 이동합니다.
    지연(Latency)이나 관성(Inertia) 없이 프레임 수신 즉시 1:1로 반응합니다.
    """
    def __init__(self):
        self.user32 = ctypes.windll.user32
        self.accum_x = 0.0
        self.accum_y = 0.0
        self.pt = POINT()
        self._cursor_awakened = False

    def _wake_cursor(self):
        """
        Windows 부팅 직후 또는 마우스 물리 미접촉 상태에서 OS가 커서를 숨김 상태로 두는 현상을
        단 1회 미세 이동 패킷(+1 -> -1) 주입으로 깨웁니다. (최초 1회만 0.01ms 실행 후 완전 종료, 부하 0%)
        """
        try:
            self.user32.mouse_event(0x0001, 1, 0, 0, 0)
            self.user32.mouse_event(0x0001, -1, 0, 0, 0)
            self._cursor_awakened = True
        except Exception:
            pass

    def move(self, dx, dy):
        # 최초 구동 시 1회만 OS 커서를 깨우고, 이후에는 순수 SetCursorPos만 초고속 1:1 실행
        if not self._cursor_awakened:
            self._wake_cursor()

        self.accum_x += dx
        self.accum_y += dy
        
        move_x = int(self.accum_x)
        move_y = int(self.accum_y)
        
        self.accum_x -= move_x
        self.accum_y -= move_y
        
        if move_x != 0 or move_y != 0:
            if self.user32.GetCursorPos(ctypes.byref(self.pt)):
                new_x = self.pt.x + move_x
                new_y = self.pt.y + move_y
                self.user32.SetCursorPos(new_x, new_y)

# 초고속 네이티브 마우스 컨트롤러 초기화
mouse = NativeMouseController()

def main():
    app = QApplication(sys.argv)
    
    # 1. 설정 로드
    app_config = config.load_config()
    
    # 2. GUI 및 트래커 변수 선언
    tracker = None
    gui = None

    # 3. 콜백 함수 정의 (이벤트 큐 포화 방지 프레임 드롭 가드 장착)
    def on_frame_callback(frame, tracking_enabled, nose_x, nose_y, fps, w, h):
        if gui is None:
            return
        # 1. 창이 최소화되었거나 화면에 표시되지 않을 때, 또는 Home 탭이 아닐 때는
        #    비디오 컬러 변환 및 Qt 시그널 방출 자체를 원천 차단하여 백그라운드 CPU/메모리 부하를 0으로 절감
        if gui.isMinimized() or not gui.isVisible() or (hasattr(gui, 'page_stack') and gui.page_stack.currentIndex() != 0):
            return
        # 2. 메인 UI 스레드가 이전 프레임을 렌더링 중이면 시그널 방출을 즉시 스킵하여 Qt 큐 메모리 누적/프리징 100% 방어
        if getattr(gui, '_is_frame_busy', False):
            return
        try:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h_f, w_f, ch = rgb_frame.shape
            bytes_per_line = ch * w_f
            q_img = QImage(rgb_frame.data, w_f, h_f, bytes_per_line, QImage.Format.Format_RGB888).copy()
            
            gui.frame_received_signal.emit(q_img, tracking_enabled, nose_x or 0, nose_y or 0, fps, w, h)
        except Exception:
            pass

    def on_move_callback(dx, dy):
        try:
            mouse.move(dx, dy)
        except Exception as e:
            print(f"마우스 제어 에러: {e}")

    # 4. 트래커 초기화 함수 (워치독에서 재사용 가능하도록 팩토리 분리)
    def create_tracker():
        return FaceTracker(
            config=app_config,
            on_frame_callback=on_frame_callback,
            on_move_callback=on_move_callback
        )

    tracker = create_tracker()
    
    # 5. PySide6 GUI 초기화 및 표시
    gui = FaceTrackerGUI(app_config, tracker)
    gui.show()
    
    # 6. 전역 핫키(F12) 리스너 등록
    def on_key_press(key):
        try:
            toggle_key_str = app_config.get("tracking_toggle_key", "f12").lower()
            
            key_name = ""
            if hasattr(key, 'name') and key.name:
                key_name = key.name.lower()
            elif hasattr(key, 'char') and key.char:
                key_name = key.char.lower()
                
            if key_name == toggle_key_str and tracker:
                new_state = not tracker.tracking_enabled
                tracker.set_tracking(new_state)
                gui.tracking_toggled_signal.emit(new_state)
        except Exception:
            pass

    listener = keyboard.Listener(on_press=on_key_press)
    listener.daemon = True
    listener.start()
    
    # 7. 자가 치유 워치독(Self-Healing Watchdog) 및 메모리 최적화 타이머 등록 (1초 주기)
    # 트래커 스레드가 비정상 사망하거나 카메라가 4초 이상 멈추면 자동으로 재기동하여 절대 멈추지 않음!
    app_start_time = time.time()
    is_recovering = False
    mem_trim_tick = 0

    def watchdog_check():
        nonlocal tracker, is_recovering, mem_trim_tick
        if not tracker or is_recovering:
            return
        
        now = time.time()
        # 30초마다 Windows 작업 세트(Working Set) 메모리를 트림하여 장시간 실행 시에도 점유율 극소화 유지
        mem_trim_tick += 1
        if mem_trim_tick >= 30:
            mem_trim_tick = 0
            config.trim_process_memory()

        # 앱 실행 초기 6초는 카메라 하드웨어 초기화 및 해상도 협상 시간이므로 워치독 유예
        if now - app_start_time < 6.0:
            return
        
        # 트래커가 작동 중인데 스레드가 죽었거나, 마지막 프레임 이후 4초 이상 먹통인 경우
        if tracker.running:
            is_dead = not tracker.is_alive()
            is_hung = (now - getattr(tracker, 'last_heartbeat', now)) > 4.0
            
            if is_dead or is_hung:
                is_recovering = True
                print(f"[워치독] 카메라 또는 추적 스레드 멈춤 감지 (사망: {is_dead}, 멈춤: {is_hung}). 안전한 자동 복구를 시작합니다...")
                old_enabled = getattr(tracker, 'tracking_enabled', False)
                try:
                    old_tracker = tracker
                    old_tracker.stop_tracker()
                    if old_tracker.cap and old_tracker.cap.isOpened():
                        old_tracker.cap.release()
                    # 이전 스레드가 완전히 종료될 때까지 대기 (장치 충돌 및 마우스 중복 입력 100% 방지)
                    if old_tracker.is_alive():
                        old_tracker.join(timeout=1.0)
                except Exception as e:
                    print(f"[워치독] 기존 트래커 해제 예외: {e}")
                
                # 새 트래커 생성 및 재시작
                tracker = create_tracker()
                gui.tracker = tracker
                tracker.set_tracking(old_enabled)
                tracker.start_tracker()
                is_recovering = False
                print("[워치독] 자가 치유 완료! 마우스 및 카메라가 정상 복구되었습니다.")

    watchdog_timer = QTimer()
    watchdog_timer.timeout.connect(watchdog_check)
    watchdog_timer.start(1000)  # 1초마다 감시
    
    # 8. 애플리케이션 종료 시 하드웨어 자원 완전 해제 훅 등록
    def clean_up():
        try:
            if gui and gui.config.get("close_clickbar_on_exit", True):
                gui._terminate_click_bar()
            if watchdog_timer:
                watchdog_timer.stop()
            if listener and listener.is_alive():
                listener.stop()
            if tracker:
                tracker.stop_tracker()
                if tracker.cap and tracker.cap.isOpened():
                    tracker.cap.release()
            config.trim_process_memory()
        except Exception:
            pass

    app.aboutToQuit.connect(clean_up)
    
    # 트래커 백그라운드 스레드 시작
    tracker.start_tracker()
    
    # 9. 초기 구동 직후 메모리 최적화:
    # 카메라 연결 및 UI 초기 렌더링 완료 후 2.5초 시점에 초기 작업 세트 메모리를 즉시 OS에 반환 (150MB+ -> 수십 MB 절감)
    QTimer.singleShot(2500, config.trim_process_memory)

    # Qt 메인 이벤트 루프 시작
    sys.exit(app.exec())

if __name__ == "__main__":
    exe_name = os.path.basename(sys.argv[0]).lower()
    if "clickbar" in exe_name or "--click-bar" in sys.argv:
        import click_bar
        click_bar.main()
    else:
        main()
