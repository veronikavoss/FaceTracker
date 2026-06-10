import cv2
import numpy as np
import threading
import time
from filters import EMASmoothingFilter

class FaceTracker(threading.Thread):
    def __init__(self, config, on_frame_callback=None, on_move_callback=None):
        super().__init__()
        self.config = config
        self.on_frame_callback = on_frame_callback  # GUI 프레임 전달 콜백
        self.on_move_callback = on_move_callback    # 마우스 이동 전달 콜백
        
        self.running = False
        self.tracking_enabled = False
        
        # 1. OpenCV 내장 얼굴 검출기(Haar Cascade) 초기화 (의존성 최소화 및 오프라인 작동)
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        self.face_cascade = cv2.CascadeClassifier(cascade_path)
        
        # 2. Optical Flow(Lucas-Kanade) 매개변수 설정
        self.lk_params = dict(
            winSize=(15, 15),
            maxLevel=2,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03)
        )
        
        # 스무딩 필터 초기화 (설정값 내 모션 임계값 deadzone 연동)
        self.filter = EMASmoothingFilter(alpha=self.config["smoothing"], deadzone=self.config["motion_threshold"])
        
        # 트래킹 관련 상태 변수
        self.prev_gray = None
        self.track_point = None  # 추적 중인 코 끝 특징점
        self.face_rect = None    # 시각화용 얼굴 영역
        self.frame_counter = 0   # 프레임 수 세는 카운터
        
        self.cap = None

    def start_tracker(self):
        self.running = True
        self.start()

    def stop_tracker(self):
        self.running = False
        self.tracking_enabled = False
        if self.cap and self.cap.isOpened():
            self.cap.release()

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
                if auto:
                    self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 3) # 3: Auto
                else:
                    self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1) # 1: Manual
                    self.cap.set(cv2.CAP_PROP_EXPOSURE, -7.0)   # 90FPS 잠금 해제를 위한 고속 노출 고정 (-7.0 = 1/125초)
            except Exception as e:
                print(f"노출 제어 설정 중 에러: {e}")

    def open_camera_settings(self):
        if self.cap and self.cap.isOpened():
            try:
                self.cap.set(cv2.CAP_PROP_SETTINGS, 1) # DirectShow 드라이버 설정 창 호출
            except Exception as e:
                print(f"카메라 설정 창 호출 중 에러: {e}")

    def run(self):
        self.cap = cv2.VideoCapture(self.config["camera_id"], cv2.CAP_DSHOW)
        
        # MJPG 포맷 및 고성능 프레임 설정 적용 (호환성 보장을 위한 순서 지정: 해상도 -> 코덱 -> FPS)
        try:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            target_fps = self.config.get("target_fps", 90)
            self.cap.set(cv2.CAP_PROP_FPS, target_fps)
            
            # 실제 설정된 스펙 출력 (드라이버가 거부했는지 확인용)
            actual_w = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            actual_h = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
            print(f"[카메라 실시간 하드웨어 연결 상태] 해상도: {int(actual_w)}x{int(actual_h)} | FPS: {int(actual_fps)}")
        except Exception as e:
            print(f"카메라 해상도/FPS 설정 중 오류 발생: {e}")

        # 초기 설정값 기반 노출 모드 적용
        lock_fps = self.config.get("lock_fps_low_light", False)
        try:
            if lock_fps:
                self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1) # Manual
                self.cap.set(cv2.CAP_PROP_EXPOSURE, -7.0)   # 90FPS 잠금 해제를 위한 고속 노출 고정 (-7.0 = 1/125초)
            else:
                self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 3) # Auto
        except Exception as e:
            print(f"초기 노출 설정 중 에러: {e}")

        fps_start_time = time.time()
        fps_counter = 0
        current_fps = 0

        while self.running:
            if not self.cap or not self.cap.isOpened():
                time.sleep(0.1)
                continue
                
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.01)
                continue
                
            # 연산 속도 향상을 위해 해상도는 1280x720 네이티브로 직접 처리합니다.
                
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
            
            # 연산 속도 향상을 위한 그레이스케일 변환
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # 저조도(어두운 환경) 극복을 위한 어댑티브 전처리 (CLAHE + Gaussian Blur)
            mean_brightness = np.mean(gray)
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            gray_enhanced = clahe.apply(gray)
            
            # 조도가 매우 낮은 경우(60 미만) 노이즈 감쇄 필터링 강화 및 데드존 보정 계수 할당
            if mean_brightness < 60:
                gray = cv2.GaussianBlur(gray_enhanced, (5, 5), 0)
                temp_deadzone_mult = 1.3
            else:
                gray = cv2.GaussianBlur(gray_enhanced, (3, 3), 0)
                temp_deadzone_mult = 1.0
            
            dx, dy = 0.0, 0.0
            nose_x, nose_y = None, None

            # 3. 실시간 트래킹 알고리즘 (얼굴 검출 + Optical Flow 기반 특징점 추적)
            if self.tracking_enabled:
                # 3-1. 이전 프레임 정보나 추적점이 없다면 새로 얼굴을 인식하여 특징점 지정
                if self.track_point is None or self.prev_gray is None:
                    # 얼굴 영역 검출
                    faces = self.face_cascade.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5, minSize=(int(w * 0.15), int(w * 0.15)))
                    
                    if len(faces) > 0:
                        # 가장 큰 얼굴 선택
                        x, y, fw, fh = max(faces, key=lambda f: f[2] * f[3])
                        self.face_rect = (x, y, fw, fh)
                        
                        # 코가 위치할 것으로 추정되는 얼굴 중심 영역에 ROI 마스크 적용
                        mask = np.zeros_like(gray)
                        cx = x + fw // 2
                        cy = y + int(fh * 0.55) # 미간보다 약간 아래인 코 위치
                        r = int(min(fw, fh) * 0.15) # 코 반경 제한
                        cv2.circle(mask, (cx, cy), r, 255, -1)
                        
                        # 해당 영역에서 가장 강력한 특징점(코너) 검출
                        corners = cv2.goodFeaturesToTrack(gray, maxCorners=1, qualityLevel=0.01, minDistance=10, mask=mask)
                        
                        if corners is not None:
                            self.track_point = corners
                            self.prev_gray = gray.copy()
                
                # 3-2. 추적점이 존재한다면 다음 프레임에서의 위치를 Optical Flow로 빠르게 추적
                elif self.track_point is not None and self.prev_gray is not None:
                    # 스레드 경합(Race Condition) 방지: 리셋 시 외부 스레드가 self.track_point를 None으로 날리는 것에 대비
                    current_point = self.track_point
                    current_gray = self.prev_gray
                    
                    if current_point is None or current_gray is None:
                        continue
                        
                    next_point, status, err = cv2.calcOpticalFlowPyrLK(
                        current_gray, gray, current_point, None, **self.lk_params
                    )
                    
                    realigned = False
                    if status is not None and status[0][0] == 1:
                        # 주기적인 코 끝 고정 보정 (20프레임마다 작동, 약 0.33초 주기)
                        if self.frame_counter % 20 == 0:
                            faces = self.face_cascade.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5, minSize=(int(w * 0.15), int(w * 0.15)))
                            if len(faces) > 0:
                                x, y, fw, fh = max(faces, key=lambda f: f[2] * f[3])
                                self.face_rect = (x, y, fw, fh) # GUI상의 얼굴 박스를 실시간 업데이트
                                
                                cx = x + fw // 2
                                cy = y + int(fh * 0.55) # 추정된 코 중심
                                r = int(min(fw, fh) * 0.12) # 코 반경
                                
                                tx = next_point[0][0][0]
                                ty = next_point[0][0][1]
                                dist = np.sqrt((tx - cx)**2 + (ty - cy)**2)
                                
                                # 코 끝을 이탈(Drift)한 경우 코 영역에서 가장 강력한 특징점 재배치
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
                            # 델타(이동 변화량) 계산 시 안전한 로컬 캐시 변수 사용
                            raw_dx = next_point[0][0][0] - current_point[0][0][0]
                            raw_dy = next_point[0][0][1] - current_point[0][0][1]
                        
                        # 1) 원본 픽셀 변화량(raw_dx, raw_dy)을 먼저 스무딩 및 데드존 필터링!
                        # 어두운 곳에서는 감지 감쇄용 임계값(deadzone)을 동적으로 올려 미세 노이즈 요동을 완벽 제어
                        active_deadzone = self.config["motion_threshold"] * temp_deadzone_mult
                        self.filter.update_deadzone(active_deadzone)
                        fdx, fdy = self.filter.filter(raw_dx, raw_dy)
                        
                        # 2) 순수 원본 필터링된 델타(fdx, fdy) 기준으로 가속 계수(accel_factor)를 정밀하게 계산
                        # 속도 임계값(0.3 픽셀) 이상의 움직임에만 유선형의 부드러운 점진 가속 적용
                        raw_speed = np.sqrt(fdx**2 + fdy**2)
                        accel_factor = 1.0
                        if self.config["acceleration"] > 1.0 and raw_speed > 0.3:
                            accel_factor = min(
                                self.config["acceleration"], 
                                1.0 + (raw_speed - 0.3) * (self.config["acceleration"] - 1.0) * 0.8
                            )
                            
                        # 3) 가속도가 점진적으로 반영된 모션 델타 생성
                        fdx *= accel_factor
                        fdy *= accel_factor
                        
                        # 4) 가속이 끝난 최종 델타에 민감도 배율(40배)을 곱해 최종 화면 마우스 속도로 변환
                        dx = fdx * self.config["sensitivity_x"] * 40
                        dy = fdy * self.config["sensitivity_y"] * 40
                        
                        # 마우스 제어 콜백 호출
                        if self.on_move_callback and (dx != 0.0 or dy != 0.0):
                            self.on_move_callback(dx, dy)
                            
                        # 현재 픽셀 좌표 업데이트
                        nose_x = int(next_point[0][0][0])
                        nose_y = int(next_point[0][0][1])
                        
                        # 상태 갱신
                        self.track_point = next_point
                        self.prev_gray = gray.copy()
                    else:
                        # 추적 실패 시 트래킹 상태 리셋 (다음 프레임에서 재검출)
                        self.reset_tracking_state()
            else:
                # 활성화되지 않았을 때는 그냥 얼굴 영역만 시각화용으로 가볍게 찾아줌
                faces = self.face_cascade.detectMultiScale(gray, scaleFactor=1.3, minNeighbors=5, minSize=(int(w * 0.15), int(w * 0.15)))
                if len(faces) > 0:
                    x, y, fw, fh = max(faces, key=lambda f: f[2] * f[3])
                    self.face_rect = (x, y, fw, fh)
                    nose_x = x + fw // 2
                    nose_y = y + int(fh * 0.55)
                else:
                    self.face_rect = None

            # 4. 카메라 화면에 시각적 오버레이 그리기
            # 얼굴 바운딩 박스 시각화
            if self.face_rect is not None:
                x, y, fw, fh = self.face_rect
                rect_color = (59, 130, 246) if self.tracking_enabled else (148, 163, 184) # 활성 시 블루, 비활성 시 슬레이트 그레이
                cv2.rectangle(frame, (x, y), (x + fw, y + fh), rect_color, 2)
            
            # 트래킹 중심점(코 끝) 표시
            if nose_x is not None and nose_y is not None:
                point_color = (0, 255, 0) if self.tracking_enabled else (0, 0, 255)
                cv2.circle(frame, (nose_x, nose_y), 6, point_color, -1)
                cv2.circle(frame, (nose_x, nose_y), 2, (255, 255, 255), -1)

            # GUI에 프레임 전달 (FPS, 해상도 포함)
            if self.on_frame_callback:
                self.on_frame_callback(frame, self.tracking_enabled, nose_x, nose_y, current_fps, w, h)

            # 지연 시간(Latency) 최소화를 위해 수면 시간을 15ms에서 2ms로 대폭 단축
            time.sleep(0.002)

        if self.cap:
            self.cap.release()
