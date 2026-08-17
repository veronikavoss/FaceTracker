import cv2
import numpy as np
import threading
import time
import os
import sys
import urllib.request
import ssl
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
        
        # 1. OpenCV 5 초경량 딥러닝 얼굴 검출기(YuNet FaceDetectorYN) 초기화
        self.face_detector = None
        self._init_face_detector()
        
        # 2. Optical Flow(Lucas-Kanade) 매개변수 설정
        self.lk_params = dict(
            winSize=(21, 21),
            maxLevel=2,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03)
        )
        
        # 3. 스무딩 필터 초기화
        self.filter = EMASmoothingFilter(self.config)
        
        # 트래킹 관련 상태 변수
        self.prev_gray = None
        self.track_point = None  # 추적 중인 코 끝 특징점
        self.face_rect = None    # 시각화용 얼굴 영역 (x, y, w, h)
        self.face_rect_smooth = None  # 얼굴 바운딩 박스 흔들림 보정용 스무더
        self.prev_brightness = None   # 조명/모니터 빛 급변 감지용 밝기 기록
        self.illumination_threshold = float(self.config.get("illumination_threshold", 10.0))
        self.spike_threshold = float(self.config.get("spike_threshold", 15.0))
        self.frame_counter = 0   # 프레임 수 세는 카운터
        
        self.cap = None

    def _init_face_detector(self):
        """OpenCV 5의 YuNet (FaceDetectorYN) ONNX 모델을 로드합니다."""
        model_filename = "face_detection_yunet_2023mar.onnx"
        base_dir = os.path.dirname(os.path.abspath(__file__))
        possible_paths = [
            os.path.join(base_dir, model_filename),
            os.path.join(getattr(sys, "_MEIPASS", os.getcwd()), model_filename),
            os.path.join(os.getcwd(), model_filename)
        ]
        
        model_path = None
        for path in possible_paths:
            if os.path.exists(path) and os.path.getsize(path) > 50000:
                model_path = path
                break
                
        if model_path is None:
            # 모델 파일이 없는 경우 자동 다운로드 시도
            target_path = os.path.join(base_dir, model_filename)
            urls = [
                "https://raw.githubusercontent.com/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
                "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
                "https://huggingface.co/opencv/face_detection_yunet/resolve/main/face_detection_yunet_2023mar.onnx"
            ]
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            for url in urls:
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req, context=ctx, timeout=10) as resp, open(target_path, "wb") as f:
                        data = resp.read()
                        if len(data) > 50000:
                            f.write(data)
                            model_path = target_path
                            print(f"[YuNet] 모델 다운로드 완료: {target_path}")
                            break
                except Exception as e:
                    print(f"[YuNet] 다운로드 실패 ({url}): {e}")
        
        if model_path and os.path.exists(model_path):
            try:
                self.face_detector = cv2.FaceDetectorYN.create(
                    model=model_path,
                    config="",
                    input_size=(320, 240),
                    score_threshold=0.5,
                    nms_threshold=0.3,
                    top_k=5
                )
            except Exception as e:
                print(f"[YuNet] 모델 초기화 에러: {e}")
        else:
            print("[YuNet] 경고: YuNet 모델 파일을 찾을 수 없습니다.")

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
        self.prev_brightness = None
        self.filter.reset()

    def update_illumination_threshold(self, val):
        self.illumination_threshold = float(val)

    def update_spike_threshold(self, val):
        self.spike_threshold = float(val)

    def set_auto_exposure(self, auto):
        if self.cap and self.cap.isOpened():
            try:
                backend_str = self.config.get("camera_backend", "DSHOW").upper()
                if auto:
                    print("[카메라 노출 설정] 자동 노출(Auto Exposure)을 켭니다.")
                    if backend_str == "DSHOW":
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
                    self.cap.set(cv2.CAP_PROP_EXPOSURE, -7.0)
            except Exception as e:
                print(f"노출 제어 설정 중 에러: {e}")

    def _detect_face(self, frame_bgr, w, h, is_low_light=False):
        """
        OpenCV 5 YuNet을 사용하여 얼굴 영역 및 코 끝 랜드마크를 검출합니다.
        반환값: ((x, y, w, h), (nose_x, nose_y)) 또는 None
        """
        if self.face_detector is None:
            return None
            
        try:
            self.face_detector.setInputSize((w, h))
            score_th = 0.4 if is_low_light else 0.5
            self.face_detector.setScoreThreshold(score_th)
            
            _, faces = self.face_detector.detect(frame_bgr)
            
            if faces is not None and len(faces) > 0:
                best_face = max(faces, key=lambda f: f[2] * f[3])
                
                fx, fy, fw, fh = int(best_face[0]), int(best_face[1]), int(best_face[2]), int(best_face[3])
                fx = max(0, fx)
                fy = max(0, fy)
                fw = min(w - fx, fw)
                fh = min(h - fy, fh)
                
                # YuNet 랜드마크 8, 9번 인덱스: 코 끝(nose tip)
                nose_x = float(best_face[8])
                nose_y = float(best_face[9])
                
                if not (fx <= nose_x <= fx + fw and fy <= nose_y <= fy + fh):
                    nose_x = fx + fw / 2.0
                    nose_y = fy + fh * 0.55
                
                return ((fx, fy, fw, fh), (nose_x, nose_y))
        except Exception as e:
            print(f"[YuNet] 얼굴 검출 중 예외: {e}")
            
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
                
                # 모니터 화면 빛/조명 급변(Illumination Shock) 감지 및 튐 억제
                mean_brightness = np.mean(gray)
                is_low_light = mean_brightness < 60
                
                illumination_shock = False
                if self.prev_brightness is not None:
                    brightness_diff = abs(mean_brightness - self.prev_brightness)
                    if brightness_diff > self.illumination_threshold:
                        illumination_shock = True
                self.prev_brightness = mean_brightness
                
                if is_low_light:
                    clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))
                    gray_enhanced = clahe.apply(gray)
                    gray = cv2.GaussianBlur(gray_enhanced, (3, 3), 0)
                else:
                    gray = cv2.GaussianBlur(gray, (3, 3), 0)
                
                dx, dy = 0.0, 0.0
                nose_x, nose_y = None, None

                # 3. 실시간 트래킹 알고리즘
                if self.tracking_enabled:
                    if self.track_point is None or self.prev_gray is None:
                        # YuNet 딥러닝으로 얼굴 및 코 끝 랜드마크 검출
                        detection = self._detect_face(frame, w, h, is_low_light)
                        
                        if detection is not None:
                            (x, y, fw, fh), (nx, ny) = detection
                            self.face_rect_smooth = [float(x), float(y), float(fw), float(fh)]
                            self.face_rect = (x, y, fw, fh)
                            
                            # YuNet 코 끝 위치를 Optical Flow 추적점으로 등록
                            self.track_point = np.array([[[nx, ny]]], dtype=np.float32)
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
                            # 20프레임마다 YuNet으로 얼굴 위치 동기화 및 이탈 방지
                            if self.frame_counter % 20 == 0:
                                detection = self._detect_face(frame, w, h, is_low_light)
                                if detection is not None:
                                    (x, y, fw, fh), (nx, ny) = detection
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
                                    
                                    tx = next_point[0][0][0]
                                    ty = next_point[0][0][1]
                                    dist = np.sqrt((tx - nx)**2 + (ty - ny)**2)
                                    
                                    max_allowed_dist = min(fw_sm, fh_sm) * 0.2
                                    if dist > max_allowed_dist:
                                        next_point = np.array([[[nx, ny]]], dtype=np.float32)
                                        realigned = True
                                            
                            if realigned or illumination_shock:
                                raw_dx = 0.0
                                raw_dy = 0.0
                                self.filter.reset()
                            else:
                                raw_dx = next_point[0][0][0] - current_point[0][0][0]
                                raw_dy = next_point[0][0][1] - current_point[0][0][1]
                                
                                if abs(raw_dx) > self.spike_threshold or abs(raw_dy) > self.spike_threshold:
                                    raw_dx = 0.0
                                    raw_dy = 0.0
                                    self.filter.reset()
                            
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
                    detection = self._detect_face(frame, w, h, is_low_light)
                    if detection is not None:
                        (x, y, fw, fh), (nx, ny) = detection
                        self.face_rect = (x, y, fw, fh)
                        nose_x = int(nx)
                        nose_y = int(ny)
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
