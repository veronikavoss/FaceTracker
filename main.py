import os
# OpenBLAS / OpenMP 다중 스레딩 충돌 및 메모리 오류 방지
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage
from pynput.mouse import Controller
from pynput import keyboard
import cv2

from tracker import FaceTracker
from gui import FaceTrackerGUI
import config

class FractionalMouseController:
    """
    1픽셀 미만의 미세 소수점 이동량을 누적하여, 
    정밀한 조준과 극도의 부드러운 하드웨어 마우스 이동을 지원하는 컨트롤러
    """
    def __init__(self, mouse_controller):
        self.mouse = mouse_controller
        self.accum_x = 0.0
        self.accum_y = 0.0

    def move(self, dx, dy):
        self.accum_x += dx
        self.accum_y += dy
        
        move_x = int(self.accum_x)
        move_y = int(self.accum_y)
        
        self.accum_x -= move_x
        self.accum_y -= move_y
        
        if move_x != 0 or move_y != 0:
            self.mouse.move(move_x, move_y)

# 마우스 컨트롤러 초기화 (소수점 정밀 누적기 결합)
mouse = FractionalMouseController(Controller())

def main():
    app = QApplication(sys.argv)
    
    # 1. 설정 로드
    app_config = config.load_config()
    
    # 2. GUI 인스턴스 생성을 위해 먼저 트래커 변수 선언
    tracker = None
    gui = None

    # 3. 콜백 함수 정의 (스레드 안전한 Qt Signal 전송)
    def on_frame_callback(frame, tracking_enabled, nose_x, nose_y, fps, w, h):
        if gui is None:
            return
        try:
            # OpenCV BGR -> RGB QImage 변환 (무복사 최적화)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h_f, w_f, ch = rgb_frame.shape
            bytes_per_line = ch * w_f
            q_img = QImage(rgb_frame.data, w_f, h_f, bytes_per_line, QImage.Format_RGB888).copy()
            
            # Qt 시그널을 통해 메인 UI 스레드로 안전하게 프레임 전달
            gui.frame_received_signal.emit(q_img, tracking_enabled, nose_x or 0, nose_y or 0, fps, w, h)
        except Exception:
            pass

    def on_move_callback(dx, dy):
        try:
            mouse.move(dx, dy)
        except Exception as e:
            print(f"마우스 제어 에러: {e}")

    # 4. 트래커 초기화
    tracker = FaceTracker(
        config=app_config,
        on_frame_callback=on_frame_callback,
        on_move_callback=on_move_callback
    )
    
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
                
            if key_name == toggle_key_str:
                new_state = not tracker.tracking_enabled
                tracker.set_tracking(new_state)
                # GUI의 버튼 및 상태 뱃지를 즉시 동기화
                gui.tracking_toggled_signal.emit(new_state)
        except Exception:
            pass

    listener = keyboard.Listener(on_press=on_key_press)
    listener.daemon = True
    listener.start()
    
    # 7. 애플리케이션 종료 시 하드웨어 자원 완전 해제 훅 등록
    def clean_up():
        try:
            if listener and listener.is_alive():
                listener.stop()
            if tracker:
                tracker.stop_tracker()
                if tracker.cap and tracker.cap.isOpened():
                    tracker.cap.release()
        except Exception:
            pass

    app.aboutToQuit.connect(clean_up)
    
    # 트래커 백그라운드 스레드 시작
    tracker.start_tracker()
    
    # Qt 메인 이벤트 루프 시작
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
