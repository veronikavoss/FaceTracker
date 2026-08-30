import cv2
import numpy as np
import threading
import time
import os
import sys
import urllib.request
import ssl
from filters import EMASmoothingFilter, MediaPipeHeadPosePipeline

# MediaPipe 관련 모듈 임포트
try:
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision as mp_vision
    MEDIAPIPE_AVAILABLE = True
except ImportError:
    MEDIAPIPE_AVAILABLE = False
    mp = None
    mp_python = None
    mp_vision = None

class FaceTracker(threading.Thread):
    def __init__(self, config, on_frame_callback=None, on_move_callback=None):
        super().__init__()
        self.daemon = True  # 메인 스레드 종료 시 서브 스레드가 즉시 자동 종료되도록 설정
        self.config = config
        self.on_frame_callback = on_frame_callback  # GUI 프레임 전달 콜백
        self.on_move_callback = on_move_callback    # 마우스 이동 전달 콜백
        
        self.running = False
        self.tracking_enabled = False
        
        # 트래킹 엔진 설정 ("mediapipe" 또는 "yunet")
        self.tracking_engine = self.config.get("tracking_engine", "mediapipe").lower()
        
        # 1. OpenCV YuNet 얼굴 검출기 초기화
        self.yunet_detector = None
        self._init_yunet_detector()
        
        # 2. MediaPipe FaceLandmarker 초기화
        self.mp_landmarker = None
        self._init_mediapipe_landmarker()
        
        # 3. Optical Flow(Lucas-Kanade) 매개변수 설정 (YuNet 모드용)
        self.lk_params = dict(
            winSize=(21, 21),
            maxLevel=2,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03)
        )
        
        # 4. 모션 필터 인스턴스 초기화 (각각의 독립 설정 적용)
        self.yunet_filter = EMASmoothingFilter(self.config.get("yunet", {}))
        self.mp_pipeline = MediaPipeHeadPosePipeline(self.config.get("mediapipe", {}))

        
        # 트래킹 관련 상태 변수 (YuNet 모드)
        self.prev_gray = None
        self.track_point = None  # 추적 중인 코 끝 특징점
        
        # 공통 상태 변수
        self.face_rect = None    # 시각화용 얼굴 영역 (x, y, w, h)
        self.face_rect_smooth = None  # 얼굴 바운딩 박스 흔들림 보정용 스무더
        self.prev_brightness = None   # 조명/모니터 빛 급변 감지용 밝기 기록
        self.frame_counter = 0   # 프레임 수 세는 카운터
        
        self.cap = None

    def _get_model_path(self, filename, default_url):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        possible_paths = [
            os.path.join(base_dir, filename),
            os.path.join(getattr(sys, "_MEIPASS", os.getcwd()), filename),
            os.path.join(os.getcwd(), filename)
        ]
        
        for path in possible_paths:
            if os.path.exists(path) and os.path.getsize(path) > 50000:
                return path
                
        # 모델 파일 다운로드 시도
        target_path = os.path.join(base_dir, filename)
        print(f"[{filename}] 모델 다운로드 시작: {default_url}")
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(default_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, context=ctx, timeout=15) as resp, open(target_path, "wb") as f:
                data = resp.read()
                if len(data) > 50000:
                    f.write(data)
                    print(f"[{filename}] 모델 다운로드 성공: {target_path}")
                    return target_path
        except Exception as e:
            print(f"[{filename}] 모델 다운로드 실패: {e}")
            
        return None

    def _init_yunet_detector(self):
        """OpenCV의 YuNet (FaceDetectorYN) ONNX 모델을 로드합니다."""
        model_url = "https://raw.githubusercontent.com/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
        model_path = self._get_model_path("face_detection_yunet_2023mar.onnx", model_url)
        
        if model_path and os.path.exists(model_path):
            try:
                self.yunet_detector = cv2.FaceDetectorYN.create(
                    model=model_path,
                    config="",
                    input_size=(320, 240),
                    score_threshold=0.5,
                    nms_threshold=0.3,
                    top_k=5
                )
                print("[YuNet] FaceDetectorYN 모델 초기화 완료.")
            except Exception as e:
                print(f"[YuNet] 모델 초기화 에러: {e}")
        else:
            print("[YuNet] 경고: YuNet 모델 파일을 찾을 수 없습니다.")

    def _init_mediapipe_landmarker(self):
        """MediaPipe Face Landmarker 모델을 로드합니다 (Facial Transformation Matrix 포함)."""
        if not MEDIAPIPE_AVAILABLE:
            print("[MediaPipe] 경고: mediapipe 패키지가 설치되어 있지 않습니다.")
            return
            
        model_url = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
        model_path = self._get_model_path("face_landmarker.task", model_url)
        
        if model_path and os.path.exists(model_path):
            try:
                base_options = mp_python.BaseOptions(model_asset_path=model_path)
                options = mp_vision.FaceLandmarkerOptions(
                    base_options=base_options,
                    running_mode=mp_vision.RunningMode.IMAGE,
                    num_faces=1,
                    min_face_detection_confidence=0.5,
                    min_face_presence_confidence=0.5,
                    min_tracking_confidence=0.5,
                    output_face_blendshapes=False,
                    output_facial_transformation_matrixes=True
                )
                self.mp_landmarker = mp_vision.FaceLandmarker.create_from_options(options)
                print("[MediaPipe] Face Landmarker (Head Pose Matrix 지원) 모델 초기화 완료.")
            except Exception as e:
                print(f"[MediaPipe] 모델 초기화 에러: {e}")
        else:
            print("[MediaPipe] 경고: face_landmarker.task 모델 파일을 찾을 수 없습니다.")

    def set_tracking_engine(self, engine_name):
        """트래킹 엔진을 동적으로 전환합니다 ('mediapipe' 또는 'yunet')"""
        engine_name = str(engine_name).lower()
        if engine_name in ["mediapipe", "yunet"]:
            if self.tracking_engine != engine_name:
                print(f"[엔진 전환] 트래킹 엔진 변경: {self.tracking_engine} -> {engine_name}")
                self.tracking_engine = engine_name
                self.config["tracking_engine"] = engine_name
                self.reset_tracking_state()

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
        self.yunet_filter.reset()
        self.mp_pipeline.reset()

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

    def _detect_yunet_face(self, frame_bgr, w, h, is_low_light=False):
        """
        YuNet을 사용하여 얼굴 영역 및 코 끝 랜드마크를 검출합니다.
        반환값: ((x, y, w, h), (nose_x, nose_y)) 또는 None
        """
        if self.yunet_detector is None:
            return None
            
        try:
            self.yunet_detector.setInputSize((w, h))
            score_th = 0.4 if is_low_light else 0.5
            self.yunet_detector.setScoreThreshold(score_th)
            
            _, faces = self.yunet_detector.detect(frame_bgr)
            
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

    def _process_mediapipe_frame(self, frame_bgr, w, h):
        """
        MediaPipe Face Landmarker를 사용하여 478개 3D 랜드마크 및 4x4 Facial Transformation Matrix(Head Pose)를 추출합니다.
        반환값: ((x, y, w, h), (nose_x, nose_y), matrix_4x4) 또는 None
        """
        if self.mp_landmarker is None:
            return None
            
        try:
            rgb_frame = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            detection_result = self.mp_landmarker.detect(mp_image)
            
            if detection_result and detection_result.face_landmarks and len(detection_result.face_landmarks) > 0:
                landmarks = detection_result.face_landmarks[0]
                
                # 인덱스 1번: 코 끝 (Nose Tip)
                nose_lm = landmarks[1]
                nose_x = float(nose_lm.x * w)
                nose_y = float(nose_lm.y * h)
                
                # 랜드마크 전체로 얼굴 바운딩 박스 산출
                xs = [lm.x * w for lm in landmarks]
                ys = [lm.y * h for lm in landmarks]
                min_x, max_x = max(0, min(xs)), min(w, max(xs))
                min_y, max_y = max(0, min(ys)), min(h, max(ys))
                
                fx = int(min_x)
                fy = int(min_y)
                fw = int(max_x - min_x)
                fh = int(max_y - min_y)
                
                matrix_4x4 = None
                if detection_result.facial_transformation_matrixes and len(detection_result.facial_transformation_matrixes) > 0:
                    matrix_4x4 = np.array(detection_result.facial_transformation_matrixes[0])
                
                return ((fx, fy, fw, fh), (nose_x, nose_y), matrix_4x4)
        except Exception as e:
            print(f"[MediaPipe] 처리 중 예외: {e}")
            
        return None

    def open_camera_settings(self):
        if self.cap and self.cap.isOpened():
            try:
                self.cap.set(cv2.CAP_PROP_SETTINGS, 1) # DirectShow 드라이버 설정 창 호출
            except Exception as e:
                print(f"카메라 설정 창 호출 중 에러: {e}")

    def run(self):
        camera_id = self.config.get("camera_id", 0)
        
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

        target_fps = self.config.get("target_fps", 30)
        target_w = self.config.get("camera_width", 640)
        target_h = self.config.get("camera_height", 480)
        
        w, h, fps, codec, results = apply_settings(self.cap, target_fps, target_w, target_h)
        print(f"[카메라 설정] 해상도: {int(w)}x{int(h)} | FPS: {int(fps)} | 코덱: {codec}")

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
                
                # 그레이스케일 변환 및 밝기 분석
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                mean_brightness = np.mean(gray)
                is_low_light = mean_brightness < 60
                
                # 조명 급변(Illumination Shock) 감지
                yunet_cfg = self.config.get("yunet", {})
                illum_th = float(yunet_cfg.get("illumination_threshold", 10.0))
                spike_th = float(yunet_cfg.get("spike_threshold", 15.0))
                
                illumination_shock = False
                if self.prev_brightness is not None:
                    brightness_diff = abs(mean_brightness - self.prev_brightness)
                    if brightness_diff > illum_th:
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

                # ==========================================
                # 엔진 1: MediaPipe Head Pose (Transformation Matrix) 모드
                # (오일러 각 추출 -> 2D 칼만 -> 속도 적응 스무딩 -> 데드존 -> 비선형 커브 & 가속도)
                # ==========================================
                if self.tracking_engine == "mediapipe" and self.mp_landmarker is not None:
                    mp_detection = self._process_mediapipe_frame(frame, w, h)
                    
                    if mp_detection is not None:
                        (x, y, fw, fh), (nx, ny), matrix_4x4 = mp_detection
                        
                        # 얼굴 사각형 스무딩
                        if self.face_rect_smooth is None:
                            self.face_rect_smooth = [float(x), float(y), float(fw), float(fh)]
                        else:
                            self.face_rect_smooth[0] = 0.8 * self.face_rect_smooth[0] + 0.2 * x
                            self.face_rect_smooth[1] = 0.8 * self.face_rect_smooth[1] + 0.2 * y
                            self.face_rect_smooth[2] = 0.8 * self.face_rect_smooth[2] + 0.2 * fw
                            self.face_rect_smooth[3] = 0.8 * self.face_rect_smooth[3] + 0.2 * fh
                            
                        self.face_rect = (
                            int(self.face_rect_smooth[0]),
                            int(self.face_rect_smooth[1]),
                            int(self.face_rect_smooth[2]),
                            int(self.face_rect_smooth[3])
                        )
                        
                        nose_x = int(nx)
                        nose_y = int(ny)
                        
                        if self.tracking_enabled:
                            # 4x4 Transformation Matrix 기반 머리 자세(Head Pose) 5단계 파이프라인 처리
                            if matrix_4x4 is not None:
                                dx, dy = self.mp_pipeline.process_matrix(matrix_4x4)
                            else:
                                dx, dy = self.mp_pipeline.process_pose(nx, ny)
                                
                            if self.on_move_callback and (dx != 0.0 or dy != 0.0):
                                self.on_move_callback(dx, dy)
                        else:
                            self.mp_pipeline.reset()
                    else:
                        self.face_rect = None
                        self.mp_pipeline.reset()

                # ==========================================
                # 엔진 2: OpenCV YuNet + Optical Flow 모드
                # (순수 광학 흐름 이동량 계산 + 마우스 계산 후 코끝 앵커 보정으로 튐 완전 해결)
                # ==========================================
                else:
                    if self.tracking_enabled:
                        if self.track_point is None or self.prev_gray is None:
                            detection = self._detect_yunet_face(frame, w, h, is_low_light)
                            if detection is not None:
                                (x, y, fw, fh), (nx, ny) = detection
                                self.face_rect_smooth = [float(x), float(y), float(fw), float(fh)]
                                self.face_rect = (x, y, fw, fh)
                                self.track_point = np.array([[[nx, ny]]], dtype=np.float32)
                                self.prev_gray = gray.copy()
                        
                        elif self.track_point is not None and self.prev_gray is not None:
                            current_point = self.track_point
                            current_gray = self.prev_gray
                            
                            next_point, status, err = cv2.calcOpticalFlowPyrLK(
                                current_gray, gray, current_point, None, **self.lk_params
                            )
                            
                            if status is not None and status[0][0] == 1:
                                cur_x = float(next_point[0][0][0])
                                cur_y = float(next_point[0][0][1])
                                prev_pt_x = float(current_point[0][0][0])
                                prev_pt_y = float(current_point[0][0][1])
                                
                                # 1. 오직 순수한 Optical Flow 프레임 간 변위로만 마우스 이동량 계산 (인위적 튐 100% 방지)
                                raw_dx = cur_x - prev_pt_x
                                raw_dy = cur_y - prev_pt_y
                                
                                if illumination_shock or abs(raw_dx) > spike_th or abs(raw_dy) > spike_th:
                                    raw_dx = 0.0
                                    raw_dy = 0.0
                                    self.yunet_filter.reset()
                                
                                # 2. 마우스 스무딩 필터 적용 및 디스패치
                                dx, dy = self.yunet_filter.filter(raw_dx, raw_dy)
                                if self.on_move_callback and (dx != 0.0 or dy != 0.0):
                                    self.on_move_callback(dx, dy)
                                
                                # 3. 마우스 계산 완료 후, 다음 프레임을 위한 코끝 앵커 보정 (마우스 움직임에 전혀 간섭 없음!)
                                if self.frame_counter % 8 == 0:
                                    detection = self._detect_yunet_face(frame, w, h, is_low_light)
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
                                        
                                        dist_to_nose = np.sqrt((cur_x - nx)**2 + (cur_y - ny)**2)
                                        
                                        # 코끝에서 8픽셀 이상 벗어나면 다음 프레임 기준점을 코끝으로 스냅
                                        if dist_to_nose > 8.0:
                                            cur_x = nx
                                            cur_y = ny
                                        elif dist_to_nose > 2.0:
                                            # 미세 드리프트는 코끝 방향으로 부드럽게 30% 견인
                                            cur_x = 0.70 * cur_x + 0.30 * nx
                                            cur_y = 0.70 * cur_y + 0.30 * ny
                                
                                nose_x = int(cur_x)
                                nose_y = int(cur_y)
                                self.track_point = np.array([[[cur_x, cur_y]]], dtype=np.float32)
                                self.prev_gray = gray.copy()
                            else:
                                self.reset_tracking_state()
                    else:
                        detection = self._detect_yunet_face(frame, w, h, is_low_light)
                        if detection is not None:
                            (x, y, fw, fh), (nx, ny) = detection
                            self.face_rect = (x, y, fw, fh)
                            nose_x = int(nx)
                            nose_y = int(ny)
                        else:
                            self.face_rect = None

                # ==========================================
                # 시각적 오버레이 그리기
                # ==========================================
                if self.face_rect is not None:
                    x, y, fw, fh = self.face_rect
                    # MediaPipe는 아쿠아(0, 200, 255), YuNet은 블루(59, 130, 246)
                    if self.tracking_engine == "mediapipe":
                        rect_color = (0, 200, 255) if self.tracking_enabled else (148, 163, 184)
                    else:
                        rect_color = (59, 130, 246) if self.tracking_enabled else (148, 163, 184)
                    cv2.rectangle(frame, (x, y), (x + fw, y + fh), rect_color, 2)
                
                if nose_x is not None and nose_y is not None:
                    point_color = (0, 255, 0) if self.tracking_enabled else (0, 0, 255)
                    cv2.circle(frame, (nose_x, nose_y), 6, point_color, -1)
                    cv2.circle(frame, (nose_x, nose_y), 2, (255, 255, 255), -1)

                if self.on_frame_callback:
                    engine_display_name = "MediaPipe" if self.tracking_engine == "mediapipe" else "YuNet"
                    self.on_frame_callback(frame, self.tracking_enabled, nose_x, nose_y, current_fps, w, h, engine_display_name)

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
