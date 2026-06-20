import cv2
import numpy as np
import threading
import time
from filters import EMASmoothingFilter

# winrt API 관련 라이브러리 안전 임포트
WINRT_AVAILABLE = False
try:
    import winrt.windows.media.capture as wmc
    import winrt.windows.media.capture.frames as wmcf
    import winrt.windows.graphics.imaging as wgi
    import winrt.windows.foundation as wf
    import winrt.windows.foundation.collections as wfc
    import queue
    import asyncio
    WINRT_AVAILABLE = True
except ImportError:
    pass

class WinRTIRCamera:
    """
    Windows 10/11의 WinRT API를 이용해 로지텍 브리오 등
    시스템에 숨겨진 적외선(IR) 카메라 장치를 비동기로 액세스하고 캡처합니다.
    """
    def __init__(self):
        self.frame_queue = queue.Queue(maxsize=2)
        self.running = False
        self.loop = None
        self.thread = None
        self.width = 640
        self.height = 480
        self.is_opened = False

    def isOpened(self):
        return self.is_opened

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        # 카메라 디바이스가 완전히 오픈되어 스트림을 시작할 때까지 안전 대기
        start_t = time.time()
        while not self.is_opened and time.time() - start_t < 3.0:
            if not self.running:
                break
            time.sleep(0.1)

    def _run_loop(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._capture_loop())
        except Exception as e:
            print(f"[WinRT IR] 백그라운드 캡처 루프 크래시: {e}")
            self.is_opened = False
            self.running = False

    async def _capture_loop(self):
        # 1. 시스템의 모든 프레임 소스에서 Infrared 소스를 지원하는 기기 검색
        groups = await wmcf.MediaFrameSourceGroup.find_all_async()
        selected_group = None
        selected_source_info = None
        
        for group in groups:
            for source_info in group.source_infos:
                if source_info.source_kind == wmcf.MediaFrameSourceKind.INFRARED:
                    selected_group = group
                    selected_source_info = source_info
                    break
            if selected_group:
                break
                
        if not selected_group:
            print("[WinRT IR] 적외선(IR) 카메라 장치를 감지하지 못했습니다.")
            self.running = False
            return
            
        print(f"[WinRT IR] 적외선 장치 바인딩 완료: {selected_group.display_name}")
        
        # 2. 미디어 캡처 객체 초기화
        media_capture = wmc.MediaCapture()
        settings = wmc.MediaCaptureInitializationSettings()
        settings.source_group = selected_group
        settings.streaming_capture_mode = wmc.StreamingCaptureMode.VIDEO
        settings.memory_preference = wmc.MediaCaptureMemoryPreference.CPU
        
        try:
            await media_capture.initialize_with_settings_async(settings)
        except Exception as e:
            print(f"[WinRT IR] 미디어 캡처 초기화 실패: {e}")
            self.running = False
            return
            
        # 3. 프레임 리더 생성 및 구독 시작
        source = media_capture.frame_sources[selected_source_info.id]
        fmt = source.current_format
        print(f"[WinRT IR] 소스 포맷: {fmt.major_type}/{fmt.subtype}, {fmt.video_format.width}x{fmt.video_format.height}")
        
        try:
            frame_reader = await media_capture.create_frame_reader_async(source)
        except Exception as e:
            print(f"[WinRT IR] 프레임 리더 생성 실패: {e}")
            self.running = False
            return
        
        start_status = await frame_reader.start_async()
        print(f"[WinRT IR] 프레임 리더 시작 상태: {start_status}")
        
        self.is_opened = True
        
        try:
            while self.running:
                frame_reference = frame_reader.try_acquire_latest_frame()
                if frame_reference:
                    video_frame = frame_reference.video_media_frame
                    if video_frame:
                        software_bitmap = video_frame.software_bitmap
                        if software_bitmap:
                            w = software_bitmap.pixel_width
                            h = software_bitmap.pixel_height
                            self.width = w
                            self.height = h
                            
                            buffer = None
                            reference = None
                            try:
                                buffer = software_bitmap.lock_buffer(wgi.BitmapBufferAccessMode.READ)
                                reference = buffer.create_reference()
                                
                                # reference 객체가 버퍼 프로토콜을 만족하므로 np.frombuffer로 변환 시도
                                try:
                                    raw_data = np.frombuffer(reference, dtype=np.uint8)
                                except TypeError:
                                    raw_data = np.frombuffer(bytes(reference), dtype=np.uint8)
                                px_len = len(raw_data)
                                
                                frame_data = None
                                # 비디오 카드 포맷별 적응형 그레이스케일 추출
                                if px_len == w * h:
                                    frame_data = raw_data.reshape((h, w)).copy()
                                elif px_len == w * h * 2:
                                    data16 = raw_data.view(np.uint16).reshape((h, w))
                                    frame_data = (data16 >> 8).astype(np.uint8).copy()
                                elif px_len == w * h * 4:
                                    bgra = raw_data.reshape((h, w, 4))
                                    frame_data = cv2.cvtColor(bgra, cv2.COLOR_BGRA2GRAY).copy()
                                elif px_len >= w * h:
                                    # stride 패딩이 있는 경우 행별로 추출
                                    stride = px_len // h
                                    frame_data = raw_data.reshape((h, stride))[:, :w].copy()
                                    
                                if frame_data is not None:
                                    # [Windows Hello IR 스트로빙 방지 및 FPS 유지]
                                    current_mean = np.mean(frame_data)
                                    
                                    # 최근 밝기 최대치를 추적 (기준점)
                                    if not hasattr(self, 'max_mean_brightness'):
                                        self.max_mean_brightness = current_mean
                                        self.last_good_frame = frame_data.copy()
                                        
                                    # 환경 밝기 변화에 적응하기 위해 기준점 서서히 감소
                                    self.max_mean_brightness = max(1.0, self.max_mean_brightness * 0.995)
                                    
                                    if current_mean > self.max_mean_brightness:
                                        self.max_mean_brightness = current_mean
                                        
                                    # 기준점의 절반 미만으로 급격히 어두워진 프레임(LED Off)은 이전 프레임으로 대체하여 깜빡임 제거
                                    if current_mean < self.max_mean_brightness * 0.5:
                                        frame_data = self.last_good_frame.copy()
                                    else:
                                        self.last_good_frame = frame_data.copy()

                                    if self.frame_queue.full():
                                        try:
                                            self.frame_queue.get_nowait()
                                        except queue.Empty:
                                            pass
                                    self.frame_queue.put(frame_data)
                            except Exception as e:
                                print(f"[WinRT IR] 프레임 변환 오류: {e}")
                            finally:
                                if reference:
                                    try:
                                        reference.close()
                                    except:
                                        pass
                                if buffer:
                                    try:
                                        buffer.close()
                                    except:
                                        pass
                    frame_reference.close()
                await asyncio.sleep(0.002)
        finally:
            self.is_opened = False
            try:
                await frame_reader.stop_async()
            except Exception:
                pass
            try:
                media_capture.close()
            except Exception:
                pass

    def read(self):
        if not self.running or not self.is_opened:
            return False, None
        try:
            gray_frame = self.frame_queue.get(timeout=0.05)
            # 기존 트래커 및 얼굴 검출 파이프라인(BGR 3채널 기준)과의 완벽 호환을 위한 BGR 복제 변환
            bgr_frame = cv2.cvtColor(gray_frame, cv2.COLOR_GRAY2BGR)
            return True, bgr_frame
        except queue.Empty:
            return False, None

    def get(self, propId):
        if propId == cv2.CAP_PROP_FRAME_WIDTH:
            return self.width
        elif propId == cv2.CAP_PROP_FRAME_HEIGHT:
            return self.height
        elif propId == cv2.CAP_PROP_FPS:
            return 30.0
        elif propId == cv2.CAP_PROP_FOURCC:
            return 0
        return 0.0

    def set(self, propId, value):
        return False

    def release(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.5)
            self.thread = None
        self.is_opened = False

class FaceTracker(threading.Thread):
    def __init__(self, config, on_frame_callback=None, on_move_callback=None):
        super().__init__()
        self.daemon = True # 메인 스레드 종료 시 서브 스레드가 즉시 자동 종료되도록 설정
        self.config = config
        self.on_frame_callback = on_frame_callback  # GUI 프레임 전달 콜백
        self.on_move_callback = on_move_callback    # 마우스 이동 전달 콜백
        
        self.running = False
        self.tracking_enabled = False
        
        # 1. OpenCV 내장 얼굴 검출기(Haar Cascade) 초기화 (의존성 최소화 및 오프라인 작동)
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        self.face_cascade = cv2.CascadeClassifier(cascade_path)
        
        # 2. Optical Flow(Lucas-Kanade) 매개변수 설정 (21x21 크기로 확장하여 반응 안정성 및 코너 이탈 억제)
        self.lk_params = dict(
            winSize=(21, 21),
            maxLevel=2,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03)
        )
        
        # 스무딩 필터 초기화 (오리지널 eViacam 설정 수학 공식 기반 필터)
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
        # 메인 스레드에서 cap.release()를 직접 호출하면 OpenCV 멀티스레드 데드락이 발생할 수 있습니다.
        # 루프 탈출 후 서브 스레드 내부에서 스스로 해제하도록 일임하고, 데몬 설정을 통해 안전한 탈출을 보장합니다.

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

    def _detect_face(self, gray, w, use_ir=False):
        # 가로 해상도가 320px가 되도록 동적으로 축소 비율 계산 (가벼운 연산량과 높은 검출 정확도 동시 만족)
        scale = 320.0 / w if w > 320 else 1.0
        h_small = int(gray.shape[0] * scale)
        w_small = int(gray.shape[1] * scale)
        gray_small = cv2.resize(gray, (w_small, h_small))
        
        min_size = int(w_small * 0.12)
        # IR 카메라 영상에서는 대비가 부족하므로 minNeighbors를 낮춰 얼굴 검출률을 높입니다.
        min_neighbors = 2 if use_ir else 4
        faces = self.face_cascade.detectMultiScale(gray_small, scaleFactor=1.1, minNeighbors=min_neighbors, minSize=(min_size, min_size))
        
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
        use_ir = self.config.get("use_ir_camera", False)
        
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
            
        if use_ir and WINRT_AVAILABLE:
            print("[카메라] WinRT 기반 적외선(IR) 카메라 모드를 시작합니다.")
            self.cap = WinRTIRCamera()
            self.cap.start()
        else:
            if use_ir and not WINRT_AVAILABLE:
                print("[카메라 경고] IR 모드가 설정되었으나 winrt 라이브러리를 로드할 수 없어 일반 카메라 모드로 전환합니다.")
            self.cap = cv2.VideoCapture(camera_id, backend)
        
        def apply_settings(cap, target_fps, target_w, target_h):
            try:
                # 버퍼 크기를 1로 제한하여 프레임 지연 및 큐 누적 방지 (실시간성 확보 및 MSMF 오버플로우 크래시 예방)
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
        
        if use_ir and WINRT_AVAILABLE:
            w = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            h = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            fps = self.cap.get(cv2.CAP_PROP_FPS)
            codec = "RAW"
            results = (False, False, False, False)
        else:
            w, h, fps, codec, results = apply_settings(self.cap, target_fps, target_w, target_h)
            print(f"[카메라 설정 디버그] FOURCC(MJPG) 설정 결과: {results[0]} | 가로: {results[1]} | 세로: {results[2]} | FPS: {results[3]}")
            
        print(f"[카메라 최종 연결 완료] 해상도: {int(w)}x{int(h)} | FPS: {int(fps)} | 최종 코덱: {codec}")

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

        current_camera_id = camera_id
        fps_start_time = time.time()
        fps_counter = 0
        current_fps = 0
        while self.running:
            # 실시간 카메라 ID 또는 적외선 모드 변경 감지 시 동적 재연결
            if self.config.get("camera_id", 0) != current_camera_id or self.config.get("use_ir_camera", False) != use_ir:
                new_camera_id = self.config.get("camera_id", 0)
                new_use_ir = self.config.get("use_ir_camera", False)
                print(f"[카메라 변경 감지] IR: {use_ir} -> {new_use_ir} | ID: {current_camera_id} -> {new_camera_id}")
                self.reset_tracking_state()
                if self.cap:
                    self.cap.release()
                
                current_camera_id = new_camera_id
                use_ir = new_use_ir
                
                if use_ir and WINRT_AVAILABLE:
                    print("[카메라] WinRT 기반 적외선(IR) 카메라 모드를 재시작합니다.")
                    self.cap = WinRTIRCamera()
                    self.cap.start()
                    w = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                    h = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                    fps = self.cap.get(cv2.CAP_PROP_FPS)
                    codec = "RAW"
                    results = (False, False, False, False)
                else:
                    if use_ir and not WINRT_AVAILABLE:
                        print("[카메라 경고] IR 모드가 설정되었으나 winrt 라이브러리를 로드할 수 없어 일반 카메라 모드로 전환합니다.")
                    self.cap = cv2.VideoCapture(current_camera_id, backend)
                    w, h, fps, codec, results = apply_settings(self.cap, target_fps, target_w, target_h)
                    
                    # 노출 모드 재적용
                    lock_fps = self.config.get("lock_fps_low_light", False)
                    try:
                        if lock_fps:
                            self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
                            self.cap.set(cv2.CAP_PROP_EXPOSURE, -7.0)
                        else:
                            self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 3)
                    except Exception as e:
                        print(f"노출 설정 재적용 중 에러: {e}")
                
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
            
            # 저조도(어두운 환경) 극복을 위한 어댑티브 전처리 (어두울 때만 대비 증폭)
            mean_brightness = np.mean(gray)
            
            if use_ir:
                # IR(적외선) 모드에서는 명암비가 부족해 얼굴 검출이 매우 어렵습니다.
                # 스트로빙 검은 프레임이 제거된 상태이므로 항상 강력한 대비 증폭(CLAHE)을 적용하여 이목구비를 뚜렷하게 만듭니다.
                clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
                gray_enhanced = clahe.apply(gray)
                gray = cv2.GaussianBlur(gray_enhanced, (5, 5), 0)
                temp_deadzone_mult = 1.0
            elif mean_brightness < 60:
                # 조도가 낮을 때만 대비를 소프트하게 향상 (clipLimit을 1.5로 완화하여 노이즈 증폭 억제)
                clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))
                gray_enhanced = clahe.apply(gray)
                gray = cv2.GaussianBlur(gray_enhanced, (5, 5), 0)
                temp_deadzone_mult = 1.5
            else:
                # 일반 조도에서는 대비 보정을 생략해 센서 노이즈 추가 증폭 및 플리커링 차단
                gray = cv2.GaussianBlur(gray, (3, 3), 0)
                temp_deadzone_mult = 1.0
            
            dx, dy = 0.0, 0.0
            nose_x, nose_y = None, None

            # 3. 실시간 트래킹 알고리즘 (얼굴 검출 + Optical Flow 기반 특징점 추적)
            if self.tracking_enabled:
                # 3-1. 이전 프레임 정보나 추적점이 없다면 새로 얼굴을 인식하여 특징점 지정
                if self.track_point is None or self.prev_gray is None:
                    # 얼굴 영역 검출
                    face = self._detect_face(gray, w, use_ir)
                    
                    if face is not None:
                        x, y, fw, fh = face
                        self.face_rect_smooth = [float(x), float(y), float(fw), float(fh)]
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
                            face = self._detect_face(gray, w, use_ir)
                            if face is not None:
                                x, y, fw, fh = face
                                if self.face_rect_smooth is None:
                                    self.face_rect_smooth = [float(x), float(y), float(fw), float(fh)]
                                else:
                                    # 85% 이전 값 유지, 15% 새 값 반영하여 바운딩 박스 요동 방지 (EMA)
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
                                cy = y_sm + int(fh_sm * 0.55) # 추정된 코 중심
                                r = int(min(fw_sm, fh_sm) * 0.12) # 코 반경
                                
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
                        
                        # 1) 오리지널 eViacam과 100% 동일한 수식으로 속도(배율), 스무딩(Low-pass), 가속도(Array Curve), 임계값을 모두 처리
                        dx, dy = self.filter.filter(raw_dx, raw_dy)
                        
                        # 2) 마우스 제어 콜백 호출
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
                face = self._detect_face(gray, w, use_ir)
                if face is not None:
                    x, y, fw, fh = face
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

            pass

            # 지연 시간(Latency) 최소화를 위해 수면 시간을 15ms에서 2ms로 대폭 단축
            time.sleep(0.002)

        if self.cap:
            self.cap.release()
