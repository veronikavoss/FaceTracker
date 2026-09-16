import cv2
import numpy as np
import threading
import time
import os
import urllib.request
from filters import EMASmoothingFilter
from config import get_base_dir

class FaceTracker(threading.Thread):
    def __init__(self, config, on_frame_callback=None, on_move_callback=None):
        super().__init__()
        self.daemon = True
        self.config = config
        self.on_frame_callback = on_frame_callback
        self.on_move_callback = on_move_callback
        
        self.running = False
        self.tracking_enabled = False
        
        self.cap = None
        self.actual_fps = 0.0
        
        # Lucas-Kanade Optical Flow 파라미터 (고속 서브픽셀 정밀도)
        self.lk_params = dict(
            winSize=(21, 21),
            maxLevel=3,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 20, 0.03)
        )
        
        # 추적 상태 변수
        self.prev_gray = None
        self.track_point = None
        self.face_rect = None
        self.face_rect_smooth = None
        self.prev_brightness = None
        self.frame_counter = 0
        
        # 24/7 무중단 감시용 하트비트 및 프레임 드롭 카운터
        self.last_heartbeat = time.time()
        self.consecutive_fails = 0
        
        # YuNet 필터 (eViacam C++ 호환 필터)
        self.yunet_filter = EMASmoothingFilter(self.config)
        
        # YuNet 모델 로드
        self.yunet_detector = None
        self._init_yunet()
        
        # 스레드 안전 카메라 동기화 락 및 안전한 재시작 플래그
        self.camera_lock = threading.Lock()
        self._restart_requested = False

    def _compute_file_sha256(self, filepath):
        """파일의 SHA-256 체크섬을 계산하여 반환합니다."""
        import hashlib
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest().lower()

    def _init_yunet(self):
        """OpenCV YuNet 얼굴 검출기 모델 초기화 (SHA-256 무결성 검증 및 안전한 원자적 다운로드)"""
        import hashlib
        model_path = os.path.join(get_base_dir(), "face_detection_yunet_2023mar.onnx")
        expected_sha256 = "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"
        
        # 1. 파일이 이미 존재하면 SHA-256 무결성 검증
        if os.path.exists(model_path):
            try:
                current_sha256 = self._compute_file_sha256(model_path)
                if current_sha256 != expected_sha256:
                    print(f"[보안 경고] YuNet 모델 파일의 무결성 검증 실패(변조 또는 손상 의심). 안전을 위해 재다운로드합니다.")
                    os.remove(model_path)
                else:
                    print("[YuNet] 모델 파일 무결성 검증 완료 (SHA-256 일치).")
            except Exception as e:
                print(f"[보안 경고] 기존 모델 검증 중 오류: {e}. 재다운로드를 진행합니다.")
                try:
                    os.remove(model_path)
                except Exception:
                    pass

        # 2. 파일이 없으면 안전하게 다운로드 (임시 파일 -> 해시 검증 -> 원자적 교체)
        if not os.path.exists(model_path):
            print(f"[YuNet] 모델 파일({model_path})이 없어 안전한 공식 저장소에서 다운로드를 시작합니다...")
            url = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
            temp_path = model_path + ".tmp"
            try:
                # 타임아웃 15초 및 원자적 다운로드
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=15) as response, open(temp_path, 'wb') as out_file:
                    out_file.write(response.read())
                
                # 다운로드된 임시 파일의 SHA-256 해시 검증
                temp_sha256 = self._compute_file_sha256(temp_path)
                if temp_sha256 != expected_sha256:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    print(f"[보안 차단] 다운로드된 파일의 SHA-256 해시가 일치하지 않아 차단되었습니다!")
                    return
                
                # 검증 통과 시 원자적 파일 교체 (Atomic replace)
                os.replace(temp_path, model_path)
                print("[YuNet] 모델 무결성 검증 통과 및 안전 다운로드 완료.")
            except Exception as e:
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass
                print(f"[YuNet] 모델 다운로드 실패: {e}")
                return

        try:
            self.yunet_detector = cv2.FaceDetectorYN.create(
                model=model_path,
                config="",
                input_size=(320, 240),
                score_threshold=0.5,
                nms_threshold=0.3,
                top_k=5000
            )
            print("[YuNet] FaceDetectorYN 모델 초기화 완료.")
        except Exception as e:
            print(f"[YuNet] 모델 로드 중 오류 발생: {e}")
            self.yunet_detector = None

    def start_tracker(self):
        self.running = True
        self.start()

    def stop_tracker(self):
        self.running = False
        self.tracking_enabled = False
        with self.camera_lock:
            if self.cap and self.cap.isOpened():
                try:
                    self.cap.release()
                except Exception:
                    pass
                self.cap = None

    def restart_camera(self):
        """GUI 또는 외부 스레드에서 안전하게 카메라 재설정을 요청 (스레드 간 충돌 100% 방지)"""
        self._restart_requested = True
        self.last_heartbeat = time.time()

    def set_tracking(self, enabled):
        self.tracking_enabled = enabled
        if not enabled:
            self.reset_tracking_state()

    def reset_tracking_state(self):
        self.track_point = None
        self.prev_gray = None
        self.face_rect = None
        self.face_rect_smooth = None
        self.prev_brightness = None
        self.yunet_filter.reset()

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

    def open_camera_settings_dialog(self):
        """DirectShow 카메라 고급 설정(노출, 밝기, 화이트밸런스 등) 대화상자 호출"""
        if self.cap and self.cap.isOpened():
            try:
                print("[카메라] DirectShow 고급 설정 대화상자를 엽니다.")
                self.cap.set(cv2.CAP_PROP_SETTINGS, 1)
            except Exception as e:
                print(f"카메라 설정 대화상자 호출 에러: {e}")

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

    def _open_camera(self):
        """설정에 따라 최적 백엔드 및 포맷으로 카메라를 초기화합니다."""
        if self.cap is not None:
            try:
                if self.cap.isOpened():
                    self.cap.release()
            except Exception:
                pass
            self.cap = None

        try:
            cam_id = int(self.config.get("camera_id", 0))
            target_w = int(self.config.get("camera_width", 640))
            target_h = int(self.config.get("camera_height", 480))
            target_fps = int(self.config.get("target_fps", 30))
            backend_str = str(self.config.get("camera_backend", "DSHOW")).upper()
            
            backend = cv2.CAP_DSHOW if backend_str == "DSHOW" else cv2.CAP_ANY
            print(f"[카메라 백엔드] {backend_str} 모드로 카메라 {cam_id} 초기화 가동합니다.")
            
            self.cap = cv2.VideoCapture(cam_id, backend)
            
            if not self.cap.isOpened() and backend_str == "DSHOW":
                print("[카메라 경고] DSHOW 실패. 기본 백엔드로 재시도합니다.")
                self.cap = cv2.VideoCapture(cam_id, cv2.CAP_ANY)
                
            if self.cap.isOpened():
                # 60 FPS 이상이거나 고주사율 모드일 때는 대역폭이 넓은 MJPG 우선 적용
                # 30 FPS 이하일 때는 압축 딜레이가 없는 무압축 YUY2 우선 적용
                preferred_codecs = ['MJPG', 'YUY2'] if target_fps > 30 else ['YUY2', 'MJPG']
                
                applied_fps = 0
                for codec in preferred_codecs:
                    fourcc = cv2.VideoWriter_fourcc(*codec)
                    self.cap.set(cv2.CAP_PROP_FOURCC, fourcc)
                    self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, target_w)
                    self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, target_h)
                    self.cap.set(cv2.CAP_PROP_FPS, target_fps)
                    self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    
                    w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    applied_fps = int(self.cap.get(cv2.CAP_PROP_FPS))
                    if applied_fps >= target_fps - 5:
                        print(f"[카메라 설정] 코덱: {codec} | 해상도: {w}x{h} | FPS: {applied_fps}")
                        break
                else:
                    w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    print(f"[카메라 설정] 해상도: {w}x{h} | FPS: {applied_fps}")
                
                auto_exp = self.config.get("auto_exposure", True)
                lock_fps = self.config.get("lock_fps_low_light", False)
                self.set_auto_exposure(auto_exp and not lock_fps)
                self.last_heartbeat = time.time()
                return True
        except Exception as e:
            print(f"[카메라 에러] 카메라 초기화 중 예외: {e}")
            
        print("[카메라 에러] 웹캠을 열 수 없습니다.")
        return False

    def run(self):
        with self.camera_lock:
            if not self._open_camera():
                self.running = False
                return

        prev_time = time.time()
        fps_smoothing = 0.9
        self.last_heartbeat = time.time()
        self.consecutive_fails = 0

        while self.running:
            try:
                # 0. 외부에서 카메라 재시작/설정 변경이 요청된 경우 스레드 루프 내에서 안전하게 재오픈
                if self._restart_requested:
                    self._restart_requested = False
                    self.last_heartbeat = time.time()
                    print("[트래커] 카메라 설정 변경 요청 수신 -> 스레드 안전 재연결 시작...")
                    
                    # 새 카메라의 프레임 해상도 및 영상에 맞춰 얼굴을 즉시 새로 잡도록 트래킹 좌표 상태 리셋
                    # (self.tracking_enabled 플래그는 그대로 유지되므로 추적 켜짐 상태가 끊기지 않고 연속 유지!)
                    self.reset_tracking_state()

                    with self.camera_lock:
                        if self.cap is not None:
                            try:
                                if self.cap.isOpened():
                                    self.cap.release()
                            except Exception as e:
                                print(f"[트래커] 이전 카메라 릴리즈 예외: {e}")
                            self.cap = None
                        time.sleep(0.2)  # DirectShow OS 드라이버 및 필터 그래프 완전 해제 대기
                        self._open_camera()
                    continue

                # 1. 카메라 장치 열림 확인 및 복구
                if self.cap is None or not self.cap.isOpened():
                    print("[트래커 복구] 카메라가 닫혀 있어 재연결을 시도합니다...")
                    with self.camera_lock:
                        self._open_camera()
                    if self.cap is None or not self.cap.isOpened():
                        time.sleep(0.3)
                        continue

                # 2. 프레임 캡처 및 연속 실패 감시
                with self.camera_lock:
                    ret, frame = self.cap.read() if self.cap else (False, None)
                    
                if not ret or frame is None:
                    self.consecutive_fails += 1
                    # 약 1초(30프레임) 연속 캡처 실패 시 USB/드라이버 자동 재연결
                    if self.consecutive_fails >= 30:
                        print(f"[트래커 경고] 카메라 프레임 {self.consecutive_fails}회 연속 수신 실패 -> 카메라 자동 재연결 시도...")
                        with self.camera_lock:
                            try:
                                if self.cap:
                                    self.cap.release()
                            except Exception:
                                pass
                            self.cap = None
                            time.sleep(0.3)
                            self._open_camera()
                        self.consecutive_fails = 0
                    time.sleep(0.01)
                    continue

                # 정상 프레임 수신: 실패 카운터 리셋 및 하트비트 갱신
                self.consecutive_fails = 0
                self.last_heartbeat = time.time()

                # 3. 프레임 처리 및 마우스 추적 (개별 예외 완벽 격리)
                try:
                    current_time = time.time()
                    dt = current_time - prev_time
                    prev_time = current_time
                    
                    if dt > 0:
                        inst_fps = 1.0 / dt
                        self.actual_fps = fps_smoothing * self.actual_fps + (1.0 - fps_smoothing) * inst_fps

                    # 좌우 반전 (거울 모드)
                    frame = cv2.flip(frame, 1)
                    h, w = frame.shape[:2]

                    self.frame_counter += 1
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    
                    # 조도(광량) 계산
                    avg_brightness = float(np.mean(gray))
                    is_low_light = avg_brightness < 60.0
                    
                    illumination_shock = False
                    if self.prev_brightness is not None:
                        diff_b = abs(avg_brightness - self.prev_brightness)
                        il_th = float(self.config.get("illumination_threshold", 10.0))
                        if diff_b > il_th:
                            illumination_shock = True
                    self.prev_brightness = avg_brightness

                    spike_th = float(self.config.get("spike_threshold", 15.0))
                    
                    # CLAHE 조명 보정
                    if is_low_light:
                        clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))
                        gray_enhanced = clahe.apply(gray)
                        gray = cv2.GaussianBlur(gray_enhanced, (3, 3), 0)
                    else:
                        gray = cv2.GaussianBlur(gray, (3, 3), 0)
                    
                    dx, dy = 0.0, 0.0
                    nose_x, nose_y = None, None

                    # ==========================================
                    # OpenCV YuNet + Lucas-Kanade Optical Flow
                    # (순수 이동량 계산 + 5프레임 코끝 앵커 보정으로 튐 0% & 코끝 완벽 고정)
                    # ==========================================
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
                                
                                # 1. 순수한 광학 흐름(Optical Flow) 이동량 계산
                                raw_dx = cur_x - prev_pt_x
                                raw_dy = cur_y - prev_pt_y
                                
                                if illumination_shock or abs(raw_dx) > spike_th or abs(raw_dy) > spike_th:
                                    raw_dx = 0.0
                                    raw_dy = 0.0
                                    self.yunet_filter.reset()
                                
                                # 2. 마우스 스무딩 필터 적용 및 디스패치
                                cur_fps = self.actual_fps if self.actual_fps > 0 else 30.0
                                dx, dy = self.yunet_filter.filter(raw_dx, raw_dy, actual_fps=cur_fps)

                                if self.on_move_callback and (dx != 0.0 or dy != 0.0):
                                    self.on_move_callback(dx, dy)
                                
                                # 3. 마우스 계산 완료 후, 다음 프레임을 위한 코끝 앵커 보정 (마우스 움직임에 전혀 간섭 없음!)
                                corr_interval = max(1, int(self.config.get("correction_interval", 5)))
                                if self.frame_counter % corr_interval == 0:
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
                                        
                                        if dist_to_nose > 6.0:
                                            cur_x = nx
                                            cur_y = ny
                                        elif dist_to_nose > 1.5:
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
                        rect_color = (59, 130, 246) if self.tracking_enabled else (148, 163, 184)
                        cv2.rectangle(frame, (x, y), (x + fw, y + fh), rect_color, 2)
                    
                    if nose_x is not None and nose_y is not None:
                        point_color = (0, 255, 0) if self.tracking_enabled else (0, 0, 255)
                        cv2.circle(frame, (nose_x, nose_y), 6, point_color, -1)
                        cv2.circle(frame, (nose_x, nose_y), 2, (255, 255, 255), -1)

                    if self.on_frame_callback:
                        self.on_frame_callback(
                            frame, 
                            self.tracking_enabled, 
                            nose_x, 
                            nose_y, 
                            int(self.actual_fps + 0.5), 
                            w, 
                            h
                        )
                except Exception as frame_e:
                    print(f"[트래커 프레임 처리 예외]: {frame_e}")
                    self.reset_tracking_state()

            except Exception as outer_e:
                print(f"[트래커 루프 심각 오류 격리]: {outer_e}")
                self.reset_tracking_state()
                time.sleep(0.1)

        if self.cap and self.cap.isOpened():
            self.cap.release()
            print("[카메라] 비디오 캡처 자원이 성공적으로 해제되었습니다.")
