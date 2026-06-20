import os
# MSMF 카메라 초기화 속도 대폭 단축을 위한 하드웨어 트랜스폼 비활성화
os.environ["OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS"] = "0"

import tkinter as tk
from pynput import keyboard
from pynput.mouse import Controller
import config
from tracker import FaceTracker
from gui import PyViacamGUI

class FractionalMouseController:
    """
    마우스 이동 시 정수형 픽셀 변환으로 소실되는 소수점(fractional) 좌표 변화량을
    누적했다가 1픽셀 이상 도달 시 반영하여, 초미세 머리 움직임도 부드럽고 정확하게 제어합니다.
    """
    def __init__(self, mouse_backend):
        self.mouse = mouse_backend
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

# 마우스 및 키보드 컨트롤러 초기화 (소수점 정밀 누적기 결합)
mouse = FractionalMouseController(Controller())

def main():
    # 1. 설정 로드
    app_config = config.load_config()
    
    # Tkinter 루트 윈도우 생성
    root = tk.Tk()
    
    # 2. 콜백 함수 정의 (스레드 세이프 보장)
    def on_frame_callback(frame, tracking_enabled, nose_x, nose_y, fps, w, h):
        # 트래커(서브 스레드)에서 GUI(메인 스레드)로 안전하게 그래픽 업데이트 전달
        try:
            # GUI 스레드 과부하로 인한 대기열 누적(TclError/MemoryError) 방지를 위한 프레임 드롭
            if root.winfo_exists() and not gui.update_pending:
                gui.update_pending = True
                root.after_idle(gui.update_frame, frame, tracking_enabled, nose_x, nose_y, fps, w, h)
        except Exception:
            pass

    def on_move_callback(dx, dy):
        # pynput을 사용해 딜레이 없이 하드웨어 레벨로 마우스 이동 제어
        try:
            mouse.move(dx, dy)
        except Exception as e:
            print(f"마우스 제어 에러: {e}")
            
    # 3. 트래커 초기화 및 시작
    tracker = FaceTracker(
        config=app_config,
        on_frame_callback=on_frame_callback,
        on_move_callback=on_move_callback
    )
    
    # 4. GUI 초기화
    gui = PyViacamGUI(root, app_config, tracker)
    
    # 5. 전역 핫키 감지 리스너 등록
    def on_key_press(key):
        try:
            # 설정 파일에서 실시간으로 핫키 매개변수를 읽어와 비교 (기본값: f12)
            target_key_str = app_config.get("tracking_toggle_key", "f12").lower()
            
            is_matched = False
            # 1) 특수 키 (f1~f12, insert, home, backspace 등) 매칭
            if hasattr(key, 'name') and key.name:
                is_matched = (key.name.lower() == target_key_str)
            # 2) 일반 문자 및 기호 문자 매칭
            elif hasattr(key, 'char') and key.char:
                is_matched = (key.char.lower() == target_key_str)
                
            if is_matched:
                new_state = not tracker.tracking_enabled
                tracker.set_tracking(new_state)
        except Exception:
            pass

    # 백그라운드 키보드 리스너 시작
    listener = keyboard.Listener(on_press=on_key_press)
    listener.daemon = True
    listener.start()
    
    # 트래커 카메라 스레드 시작
    tracker.start_tracker()
    
    # GUI 메인 루프 실행
    root.mainloop()

if __name__ == "__main__":
    main()
