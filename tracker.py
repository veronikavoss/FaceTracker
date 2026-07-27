import cv2
import numpy as np
import threading
import time
from filters import EMASmoothingFilter

class FaceTracker(threading.Thread):
    def __init__(self, config, on_frame_callback=None, on_move_callback=None):
        super().__init__()
        self.daemon = True # 메인 스레드 종료 시 서브 스레드가 즉시 자동 종료되도록 설정
        self.config = config
        self.on_frame_callback = on_frame_callback  # GUI 프레임 전달 콜백
        self.on_move_callback = on_move_callback    # 마우스 이동 전달 콜백
        
        self.running = False
        self.tracking_enabled = False
        
        # 1. OpenCV 내장 얼굴 검출기(Haar Cascade) 초기화
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        self.face_cascade = cv2.CascadeClassifier(cascade_path)
        
        # 2. Optical Flow(Lucas-Kanade) 매개변수 설정
        self.lk_params = dict(
            winSize=(21, 21),
            maxLevel=2,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03)
        )
        
        # 스무딩 필터 초기화
        self.filter = EMASmoothingFilter(self.config)
        
        # 트래킹 관련 상태 변수
        self.prev_gray = None
        self.track_point = None  # 추적 중인 코 끝 특징점
        self.face_rect = None    # 시각화용 얼굴 영역
        self.face_rect_smooth = None  # 얼굴 바운딩 박스 흔들림 보정용 스무더
        self.frame_counter = 0   # 프레임 수 세는 카운터
        
        self.cap = None

    def start_tracker(self):
        self.running = True
        self.start()

    def stop_tracker(self):
        self.running = False
        self.tracking_enabled = False

    def set_tracking(self, enabled):
        self.tracking_enabled = enabled
        if not enabled:
            self.reset_tracking_state()

    def reset_tracking_state(self):
        self.track_point = None
        self.prev_gray = None
        self.face_rect = None
        self.filter.reset()

    def update_filter_alpha(self, alpha):
        self.filter.update_alpha(alpha)

    def update_deadzone(self, deadzone):
        self.filter.update_deadzone(deadzone)

    def set_auto_exposure(self, auto):
        if self.cap and self.cap.isOpened():
            try:
                backend_str = self.config.get("camera_backend", "DSHOW").upper()
                if auto:
                    print("[카메라 노출 설정] 자동 노출(Auto Exposure)을 켭니다.")
                    if backend_str == "DSHOW":
                        # DirectShow 백엔드: 0.75가 Auto Exposure 표준입니다.
                        r = self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.75)
                        if not r:
                            self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
                    else:
                        r = self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 3)
                        if not r:
                            self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.75)
                else:
                    print("[카메라 노출 설정] 수동 노출(Manual Exposure)로 고정합니다.")
                    if backend_str == "DSHOW":
                        self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
                    else:
                        self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
                    self.cap.set(cv2.CAP_PROP_EXPOSURE, -7.0)   # 고속 노출 고정
            except Exception as e:
                print(f"노출 제어 설정 중 에러: {e}")

    def _detect_face(self, gray, w):
        scale = 320.0 / w if w > 320 else 1.0
        h_small = int(gray.shape[0] * scale)
        w_small = int(gray.shape[1] * scale)
        gray_small = cv2.resize(gray, (w_small, h_small))
        
        min_size = int(w_small * 0.12)
        faces = self.face_cascade.detectMultiScale(gray_small, scaleFactor=1.1, minNeighbors=4, minSize=(min_size, min_size))
        
        if len(faces) > 0:
            x_s, y_s, fw_s, fh_s = max(faces, key=lambda f: f[2] * f[3])
            return (int(x_s / scale), int(y_s / scale), int(fw_s / scale), int(fh_s / scale))
        return None

    def open_camera_settings(self):
        if self.cap and self.cap.isOpened():
            try:
                self.cap.set(cv2.CAP_PROP_SETTINGS, 1) # DirectShow 드라이버 설정 창 호출
            except Exception as e:
                print(f"카메라 설정 창 호출 중 에러: {e}")

    def run(self):
        camera_id = self.config["camera_id"]
        
        # 설정 파일로부터 카메라 백엔드 로드 (DSHOW, MSMF, AUTO)
        backend_str = self.config.get("camera_backend", "DSHOW").upper()
        if backend_str == "MSMF":
            backend = cv2.CAP_MSMF
            print("[카메라 백엔드] MSMF(Media Foundation) 모드로 가동합니다.")
        elif backend_str == "AUTO":
            backend = cv2.CAP_ANY
            print("[카메라 백엔드] AUTO(기본 자동 선택) 모드로 가동합니다.")
        else:
            backend = cv2.CAP_DSHOW
            print("[카메라 백엔드] DSHOW(DirectShow) 모드로 가동합니다.")
            
        self.cap = cv2.VideoCapture(camera_id, backend)
        
        def apply_settings(cap, target_fps, target_w, target_h):
            try:
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                r1 = cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
                r2 = cap.set(cv2.CAP_PROP_FRAME_WIDTH, target_w)
                r3 = cap.set(cv2.CAP_PROP_FRAME_HEIGHT, target_h)
                r4 = cap.set(cv2.CAP_PROP_FPS, target_fps)
                
                w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                fps = cap.get(cv2.CAP_PROP_FPS)
                fourcc_val = int(cap.get(cv2.CAP_PROP_FOURCC))
                fourcc_str = "".join([chr((fourcc_val >> 8 * i) & 0xFF) for i in range(4)]) if fourcc_val > 0 else "NONE"
                return w, h, fps, fourcc_str, (r1, r2, r3, r4)
            except Exception as e:
                print(f"설정 적용 중 에러: {e}")
                return 0, 0, 0, "ERROR", (False, False, False, False)

        target_fps = self.config.get("target_fps", 90)
        target_w = self.config.get("camera_width", 640)
        target_h = self.config.get("camera_height", 360)
        
        w, h, fps, codec, results = apply_settings(self.cap, target_fps, target_w, target_h)
        print(f"[카메라 설정 디버그] FOURCC(MJPG) 설정 결과: {results[0]} | 가로: {results[1]} | 세로: {results[2]} | FPS: {results[3]}")
        print(f"[카메라 최종 연결 완료] 해상도: {int(w)}x{int(h)} | FPS: {int(fps)} | 최종 코덱: {codec}")

        # 초기 설정값 기반 노출 모드 적용 (auto_exposure 기본값 True)
        auto_exp = self.config.get("auto_exposure", not self.config.get("lock_fps_low_light", False))
        self.set_auto_exposure(auto_exp)

        current_camera_id = camera_id
        fps_start_time = time.time()
        fps_counter = 0
        current_fps = 0
        while self.running:
            try:
                # 실시간 카메라 ID 변경 감지 시 동적 재연결
                if self.config.get("camera_id", 0) != current_camera_id:
                    new_camera_id = self.config.get("camera_id", 0)
                    print(f"[카메라 변경 감지] ID: {current_camera_id} -> {new_camera_id}")
                    self.reset_tracking_state()
                    if self.cap:
                        self.cap.release()
                    
                    current_camera_id = new_camera_id
                    self.cap = cv2.VideoCapture(current_camera_id, backend)
                    w, h, fps, codec, results = apply_settings(self.cap, target_fps, target_w, target_h)
                    
                    # 노출 모드 재적용
                    auto_exp = self.config.get("auto_exposure", not self.config.get("lock_fps_low_light", False))
                    self.set_auto_exposure(auto_exp)
                    
                    fps_start_time = time.time()
                    fps_counter = 0
                    current_fps = 0
                    continue

                if not self.cap or not self.cap.isOpened():
                    time.sleep(0.1)
                    continue
                    
                ret, frame = self.cap.read()
                if not ret or frame is None:
                    time.sleep(0.005)
                    continue
                    
                self.frame_counter += 1
                fps_counter += 1
                if fps_counter >= 30:
                    elapsed = time.time() - fps_start_time
                    current_fps = int(fps_counter / elapsed) if elapsed > 0 else 0
                    fps_start_time = time.time()
                    fps_counter = 0

                # 거울 모드 좌우 반전
                frame = cv2.flip(frame, 1)
                h, w, _ = frame.shape
                
                # 그레이스케일 변환
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                
                # 저조도 전처리
                mean_brightness = np.mean(gray)
                if mean_brightness < 60:
                    clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))
                    gray_enhanced = clahe.apply(gray)
                    gray = cv2.GaussianBlur(gray_enhanced, (5, 5), 0)
                else:
                    gray = cv2.GaussianBlur(gray, (3, 3), 0)
                
                dx, dy = 0.0, 0.0
                nose_x, nose_y = None, None

                # 3. 실시간 트래킹 알고리즘
                if self.tracking_enabled:
                    if self.track_point is None or self.prev_gray is None:
                        face = self._detect_face(gray, w)
                        
                        if face is not None:
                            x, y, fw, fh = face
                            self.face_rect_smooth = [float(x), float(y), float(fw), float(fh)]
                            self.face_rect = (x, y, fw, fh)
                            
                            mask = np.zeros_like(gray)
                            cx = x + fw // 2
                            cy = y + int(fh * 0.55)
                            r = int(min(fw, fh) * 0.15)
                            cv2.circle(mask, (cx, cy), r, 255, -1)
                            
                            corners = cv2.goodFeaturesToTrack(gray, maxCorners=1, qualityLevel=0.01, minDistance=10, mask=mask)
                            
                            if corners is not None:
                                self.track_point = corners
                                self.prev_gray = gray.copy()
                    
                    elif self.track_point is not None and self.prev_gray is not None:
                        current_point = self.track_point
                        current_gray = self.prev_gray
                        
                        if current_point is None or current_gray is None:
                            continue
                            
                        next_point, status, err = cv2.calcOpticalFlowPyrLK(
                            current_gray, gray, current_point, None, **self.lk_params
                        )
                        
                        realigned = False
                        if status is not None and status[0][0] == 1:
                            if self.frame_counter % 20 == 0:
                                face = self._detect_face(gray, w)
                                if face is not None:
                                    x, y, fw, fh = face
                                    if self.face_rect_smooth is None:
                                        self.face_rect_smooth = [float(x), float(y), float(fw), float(fh)]
                                    else:
                                        self.face_rect_smooth[0] = 0.85 * self.face_rect_smooth[0] + 0.15 * x
                                        self.face_rect_smooth[1] = 0.85 * self.face_rect_smooth[1] + 0.15 * y
                                        self.face_rect_smooth[2] = 0.85 * self.face_rect_smooth[2] + 0.15 * fw
                                        self.face_rect_smooth[3] = 0.85 * self.face_rect_smooth[3] + 0.15 * fh
                                    
                                    x_sm = int(self.face_rect_smooth[0])
                                    y_sm = int(self.face_rect_smooth[1])
                                    fw_sm = int(self.face_rect_smooth[2])
                                    fh_sm = int(self.face_rect_smooth[3])
                                    self.face_rect = (x_sm, y_sm, fw_sm, fh_sm)
                                    
                                    cx = x_sm + fw_sm // 2
                                    cy = y_sm + int(fh_sm * 0.55)
                                    r = int(min(fw_sm, fh_sm) * 0.12)
                                    
                                    tx = next_point[0][0][0]
                                    ty = next_point[0][0][1]
                                    dist = np.sqrt((tx - cx)**2 + (ty - cy)**2)
                                    
                                    if dist > r:
                                        mask = np.zeros_like(gray)
                                        cv2.circle(mask, (cx, cy), int(r * 0.8), 255, -1)
                                        corners = cv2.goodFeaturesToTrack(gray, maxCorners=1, qualityLevel=0.01, minDistance=10, mask=mask)
                                        if corners is not None:
                                            next_point = corners
                                            realigned = True
                                            
                            if realigned:
                                raw_dx = 0.0
                                raw_dy = 0.0
                                self.filter.reset()
                            else:
                                raw_dx = next_point[0][0][0] - current_point[0][0][0]
                                raw_dy = next_point[0][0][1] - current_point[0][0][1]
                            
                            dx, dy = self.filter.filter(raw_dx, raw_dy)
                            
                            if self.on_move_callback and (dx != 0.0 or dy != 0.0):
                                self.on_move_callback(dx, dy)
                                
                            nose_x = int(next_point[0][0][0])
                            nose_y = int(next_point[0][0][1])
                            
                            self.track_point = next_point
                            self.prev_gray = gray.copy()
                        else:
                            self.reset_tracking_state()
                else:
                    face = self._detect_face(gray, w)
                    if face is not None:
                        x, y, fw, fh = face
                        self.face_rect = (x, y, fw, fh)
                        nose_x = x + fw // 2
                        nose_y = y + int(fh * 0.55)
                    else:
                        self.face_rect = None

                # 4. 시각적 오버레이 그리기
                if self.face_rect is not None:
                    x, y, fw, fh = self.face_rect
                    rect_color = (59, 130, 246) if self.tracking_enabled else (148, 163, 184)
                    cv2.rectangle(frame, (x, y), (x + fw, y + fh), rect_color, 2)
                
                if nose_x is not None and nose_y is not None:
                    point_color = (0, 255, 0) if self.tracking_enabled else (0, 0, 255)
                    cv2.circle(frame, (nose_x, nose_y), 6, point_color, -1)
                    cv2.circle(frame, (nose_x, nose_y), 2, (255, 255, 255), -1)

                if self.on_frame_callback:
                    self.on_frame_callback(frame, self.tracking_enabled, nose_x, nose_y, current_fps, w, h)

            except Exception as e:
                print(f"트래커 루프 내 예외 발생: {e}")
                self.reset_tracking_state()
                time.sleep(0.1)

            time.sleep(0.002)

        if self.cap:
            try:
                self.cap.release()
            except Exception as e:
                print(f"카메라 리소스 해제 중 에러: {e}")
