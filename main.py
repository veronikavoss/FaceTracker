import os
# MSMF 카메라 초기화 속도 대폭 단축을 위한 하드웨어 트랜스폼 비활성화
os.environ["OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS"] = "0"

import queue
import tkinter as tk
from pynput import keyboard
from pynput.mouse import Controller
import config
from tracker import FaceTracker
from gui import FaceTrackerGUI

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
    
    # 스레드 간 비디오 프레임 전달을 위한 스레드 안전한 큐 생성 (오버플로우 방지를 위해 크기 2로 제한)
    frame_queue = queue.Queue(maxsize=2)
    
    # 2. 콜백 함수 정의 (스레드 세이프 보장)
    def on_frame_callback(frame, tracking_enabled, nose_x, nose_y, fps, w, h):
        # 서브 스레드에서 직접 GUI(메인 스레드)에 접근하지 않고 큐에 데이터 전달
        try:
            if frame_queue.full():
                try:
                    frame_queue.get_nowait()
                except queue.Empty:
                    pass
            frame_queue.put_nowait((frame, tracking_enabled, nose_x, nose_y, fps, w, h))
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
    gui = FaceTrackerGUI(root, app_config, tracker, frame_queue)
    
    # GUI 측 프레임 큐 폴링 루프 개시
    gui.start_poll_loop()
    
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
