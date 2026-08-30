import math

# 원본 eViacam C++ (mousecontrol.cpp) ACCEL_ARRAY_SIZE = 30
ACCEL_ARRAY_SIZE = 30

class EMASmoothingFilter:
    """
    원본 eViacam C++ (mousecontrol.cpp MovePointerRel 함수)의 
    마우스 모션 처리 알고리즘을 1:1로 정확히 복제한 필터입니다.
    
    원본 처리 순서:
      1. Speed Factor (dx *= fDx) — pointeraction.cpp GetSpeedFactor
      2. Low-pass Filter (IIR) — mousecontrol.cpp m_actualMotionWeight
      3. Acceleration (Array lookup) — mousecontrol.cpp SetRelAcceleration2
      4. Delta Threshold (EasyStop) — mousecontrol.cpp m_minDeltaThreshold
    """
    def __init__(self, config):
        self.config = config
        self.dxant = 0.0
        self.dyant = 0.0
        # 가속도 배열 (원본 ACCEL_ARRAY_SIZE = 30)
        self.accel_array = [1.0] * ACCEL_ARRAY_SIZE
        self._build_accel_array()

    def _build_accel_array(self):
        """
        원본 CMouseControl::SetRelAcceleration2 로직을 정확히 재현합니다.
        pointeraction.cpp SetAcceleration(n) → mousecontrol.cpp SetRelAcceleration2(delta0, factor0, delta1, factor1)
        """
        accel = max(0, min(10, int(self.config.get("acceleration", 5))))
        
        delta0 = ACCEL_ARRAY_SIZE  # 기본값: 배열 전체를 1.0으로 채움 (가속 없음)
        factor0 = 1.0
        delta1 = ACCEL_ARRAY_SIZE
        factor1 = 1.0
        
        if accel == 1:
            delta0 = 7; factor0 = 1.5
        elif accel == 2:
            delta0 = 7; factor0 = 2.0
        elif accel == 3:
            delta0 = 7; factor0 = 1.5; delta1 = 14; factor1 = 2.0
        elif accel == 4:
            delta0 = 7; factor0 = 2.0; delta1 = 14; factor1 = 1.5
        elif accel >= 5:
            delta0 = 7; factor0 = 2.0; delta1 = 14; factor1 = 2.0
        
        # 원본 SetRelAcceleration2 로직 그대로
        self.accel_array = [1.0] * ACCEL_ARRAY_SIZE
        for i in range(min(delta0, ACCEL_ARRAY_SIZE)):
            self.accel_array[i] = 1.0
        for i in range(delta0, min(delta1, ACCEL_ARRAY_SIZE)):
            self.accel_array[i] = factor0
        j = 0.0
        for i in range(delta1, ACCEL_ARRAY_SIZE):
            self.accel_array[i] = factor0 * factor1 + j
            j += 0.1

    def reset(self):
        self.dxant = 0.0
        self.dyant = 0.0

    def filter(self, raw_dx, raw_dy):
        # ============================================================
        # 1. Apply Speed Factors (원본: dx *= m_fDx)
        # 원본 공식: pow(e, speed / 6.0)  — pointeraction.h GetSpeedFactor
        # 원본 범위: speed 0~30, 기본값 10
        # ============================================================
        speed_x = self.config.get("sensitivity_x", 10)
        speed_y = self.config.get("sensitivity_y", 10)
        
        fDx = math.exp(speed_x / 6.0)
        fDy = math.exp(speed_y / 6.0)
        
        dx = raw_dx * fDx
        dy = raw_dy * fDy

        # ============================================================
        # 2. Low-pass Filter (원본: IIR 1차 저역통과 필터)
        # 원본: dx = dx * (1 - weight) + dxant * weight
        # weight = log10(smoothness + 1)  — pointeraction.h SetSmoothness
        # 원본 범위: smoothness 0~8, 기본값 2
        # ============================================================
        smoothness = max(0, min(8, int(self.config.get("smoothing", 2))))
        weight = math.log10(smoothness + 1.0)
        
        dx = dx * (1.0 - weight) + self.dxant * weight
        dy = dy * (1.0 - weight) + self.dyant * weight
        self.dxant = dx
        self.dyant = dy

        # ============================================================
        # 3. Acceleration (원본: accel_array 참조 테이블)
        # 원본: distance = sqrt(dx*dx + dy*dy)
        #       idx = (int)(distance + 0.5)
        #       dx *= accel_array[idx]
        # ============================================================
        distance = math.sqrt(dx * dx + dy * dy)
        idx = int(distance + 0.5)
        if idx >= ACCEL_ARRAY_SIZE:
            idx = ACCEL_ARRAY_SIZE - 1
        
        dx *= self.accel_array[idx]
        dy *= self.accel_array[idx]

        # ============================================================
        # 4. Delta Threshold / EasyStop (원본: m_minDeltaThreshold)
        # 원본: if (-threshold < dx < threshold) dx = 0
        # 원본 범위: 0~10, 기본값 1
        # ============================================================
        threshold = float(self.config.get("motion_threshold", 1))
        
        if -threshold < dx < threshold:
            dx = 0.0
        if -threshold < dy < threshold:
            dy = 0.0

        return dx, dy


class HeadPoseKalman2D:
    """
    머리 회전 각도(Yaw, Pitch) 및 각속도를 추정하는 2D 칼만 필터
    상태 벡터: [yaw, pitch, v_yaw, v_pitch]^T
    """
    def __init__(self, process_noise=0.01, measurement_noise=0.2):
        self.dt = 1.0 / 30.0
        self.yaw = 0.0
        self.pitch = 0.0
        self.v_yaw = 0.0
        self.v_pitch = 0.0
        
        self.p00, self.p11, self.p22, self.p33 = 1.0, 1.0, 1.0, 1.0
        self.q = process_noise
        self.r = measurement_noise
        self.initialized = False

    def reset(self, init_yaw=0.0, init_pitch=0.0):
        self.yaw = init_yaw
        self.pitch = init_pitch
        self.v_yaw = 0.0
        self.v_pitch = 0.0
        self.p00, self.p11, self.p22, self.p33 = 1.0, 1.0, 1.0, 1.0
        self.initialized = True

    def set_kalman_strength(self, strength_slider):
        # strength_slider (0 ~ 10): 클수록 센서 노이즈 R이 커져 부드러움 극대화
        val = max(0, min(10, int(strength_slider)))
        self.r = 0.05 + (val ** 1.3) * 0.08
        self.q = 0.01 + (10 - val) * 0.005

    def update(self, m_yaw, m_pitch, dt=0.033):
        if not self.initialized:
            self.reset(m_yaw, m_pitch)
            return m_yaw, m_pitch, 0.0, 0.0

        dt = max(0.005, min(0.1, dt))
        
        # 1. Predict
        pred_yaw = self.yaw + self.v_yaw * dt
        pred_pitch = self.pitch + self.v_pitch * dt
        
        p_yaw = self.p00 + dt * dt * self.p22 + self.q
        p_pitch = self.p11 + dt * dt * self.p33 + self.q
        
        # 2. Update
        k_yaw = p_yaw / (p_yaw + self.r)
        k_pitch = p_pitch / (p_pitch + self.r)
        
        self.yaw = pred_yaw + k_yaw * (m_yaw - pred_yaw)
        self.pitch = pred_pitch + k_pitch * (m_pitch - pred_pitch)
        
        self.v_yaw = self.v_yaw + (dt / (p_yaw + self.r)) * (m_yaw - pred_yaw)
        self.v_pitch = self.v_pitch + (dt / (p_pitch + self.r)) * (m_pitch - pred_pitch)
        
        self.p00 = (1.0 - k_yaw) * p_yaw
        self.p11 = (1.0 - k_pitch) * p_pitch
        self.p22 = self.p22 + self.q
        self.p33 = self.p33 + self.q
        
        return self.yaw, self.pitch, self.v_yaw, self.v_pitch


class MediaPipeHeadPosePipeline:
    """
    MediaPipe Facial Transformation Matrix 기반 머리 자세(Head Pose) 5단계 정밀 파이프라인
    
    1. Transformation Matrix 오일러 각 추출 (Yaw, Pitch) & 이상값 튐 필터
    2. 2D Kalman Filter: 자세 및 각속도 예측 & 노이즈 제거
    3. 속도 기반 Adaptive Smoothing: 저속 시 떨림 0, 고속 시 딜레이 0
    4. 정밀 Dead Zone: 미세 호흡/떨림 완벽 차단
    5. Non-linear Curved Mapping & Acceleration: 중앙 정밀 조준 + 가장자리 고속 도달
    """
    def __init__(self, mp_config):
        self.config = mp_config
        self.kalman = HeadPoseKalman2D()
        self.prev_yaw = None
        self.prev_pitch = None
        self.smoothed_d_yaw = 0.0
        self.smoothed_d_pitch = 0.0
        self.last_update_time = None

    def reset(self):
        self.kalman.reset()
        self.prev_yaw = None
        self.prev_pitch = None
        self.last_f_yaw = None
        self.last_f_pitch = None
        self.smoothed_d_yaw = 0.0
        self.smoothed_d_pitch = 0.0
        self.last_update_time = None

    def process_matrix(self, matrix_4x4, current_time=None):
        """
        MediaPipe가 반환한 4x4 facial_transformation_matrix로부터
        오일러 각(Yaw, Pitch)을 계산하여 파이프라인을 수행합니다.
        """
        # 3x3 Rotation 행렬 추출
        R = matrix_4x4[:3, :3]
        
        # 오일러 각도 계산 (라디안 -> 도 단위 변환)
        # Pitch: 상하 고개 끄덕임 (X축 회전)
        pitch_rad = math.atan2(R[2, 1], R[2, 2])
        # Yaw: 좌우 고개 회전 (Y축 회전)
        yaw_rad = math.atan2(-R[2, 0], math.sqrt(R[2, 1]**2 + R[2, 2]**2))
        
        yaw_deg = math.degrees(yaw_rad)
        pitch_deg = math.degrees(pitch_rad)
        
        return self.process_pose(yaw_deg, pitch_deg, current_time)

    def process_pose(self, raw_yaw, raw_pitch, current_time=None):
        import time
        now = current_time if current_time is not None else time.time()
        dt = (now - self.last_update_time) if self.last_update_time is not None else 0.033
        dt = max(0.005, min(0.1, dt))
        self.last_update_time = now

        # 첫 프레임 초기화
        if self.prev_yaw is None:
            self.prev_yaw = raw_yaw
            self.prev_pitch = raw_pitch
            self.kalman.reset(raw_yaw, raw_pitch)
            self.smoothed_d_yaw = 0.0
            self.smoothed_d_pitch = 0.0
            return 0.0, 0.0

        # ============================================================
        # 1. 이상값 튐 제거 (Outlier Angle Filter)
        # ============================================================
        outlier_limit = float(self.config.get("outlier_threshold", 15.0)) # 도 단위
        d_raw_yaw = abs(raw_yaw - self.prev_yaw)
        d_raw_pitch = abs(raw_pitch - self.prev_pitch)
        
        if d_raw_yaw > outlier_limit:
            raw_yaw = self.prev_yaw
        else:
            self.prev_yaw = raw_yaw
            
        if d_raw_pitch > outlier_limit:
            raw_pitch = self.prev_pitch
        else:
            self.prev_pitch = raw_pitch

        # ============================================================
        # 2. 2D Kalman Filter (움직임 및 각속도 추정)
        # ============================================================
        k_strength = int(self.config.get("kalman_strength", 5))
        self.kalman.set_kalman_strength(k_strength)
        
        f_yaw, f_pitch, _, _ = self.kalman.update(raw_yaw, raw_pitch, dt)
        
        if not hasattr(self, 'last_f_yaw') or self.last_f_yaw is None:
            self.last_f_yaw = f_yaw
            self.last_f_pitch = f_pitch
            return 0.0, 0.0
            
        # 칼만 필터링된 각도의 차분(Delta Angle) 계산
        d_yaw = f_yaw - self.last_f_yaw
        d_pitch = f_pitch - self.last_f_pitch
        self.last_f_yaw = f_yaw
        self.last_f_pitch = f_pitch

        # ============================================================
        # 3. 속도 기반 Adaptive Smoothing (1€ 필터 원리)
        # ============================================================
        smooth_slider = int(self.config.get("adaptive_smoothing", 5)) # 0 ~ 10
        ang_speed = math.sqrt(d_yaw ** 2 + d_pitch ** 2) / dt # deg/sec
        
        # 각속도가 빠를수록 cutoff 증가 -> 즉각 반응
        base_cutoff = 0.8 + (10 - smooth_slider) * 0.4
        speed_cutoff = base_cutoff + 0.08 * ang_speed
        
        tau = 1.0 / (2.0 * math.pi * speed_cutoff)
        alpha = dt / (dt + tau)
        alpha = max(0.08, min(1.0, alpha))
        
        self.smoothed_d_yaw = alpha * d_yaw + (1.0 - alpha) * self.smoothed_d_yaw
        self.smoothed_d_pitch = alpha * d_pitch + (1.0 - alpha) * self.smoothed_d_pitch
        
        cur_yaw = self.smoothed_d_yaw
        cur_pitch = self.smoothed_d_pitch

        # ============================================================
        # 4. Dead Zone (각도 정밀 데드존)
        # ============================================================
        deadzone = float(self.config.get("deadzone", 0.08)) # 도 단위 (0.01 ~ 0.5 deg)
        ang_mag = math.sqrt(cur_yaw ** 2 + cur_pitch ** 2)
        
        if ang_mag < deadzone:
            cur_yaw = 0.0
            cur_pitch = 0.0
        else:
            if ang_mag > 0.0001:
                scale = (ang_mag - deadzone) / ang_mag
                cur_yaw *= scale
                cur_pitch *= scale

        # ============================================================
        # 5. Non-linear Curved Mapping & 가속도 곡선
        # (중앙 정밀 조준 + 가장자리 고속 도달)
        # ============================================================
        curve_p = float(self.config.get("curve_power", 1.35)) # 1.0 ~ 1.8
        accel_val = int(self.config.get("acceleration", 5))    # 0 ~ 10
        
        def non_linear_curve(val):
            if val == 0.0:
                return 0.0
            sign = 1.0 if val > 0 else -1.0
            mag = abs(val)
            # 비선형 거듭제곱 매핑
            mapped = sign * (mag ** curve_p)
            return mapped

        out_dx = non_linear_curve(cur_yaw)
        out_dy = non_linear_curve(cur_pitch)
        
        # 빠른 움직임 가속도 배율
        step_mag = math.sqrt(out_dx ** 2 + out_dy ** 2)
        if accel_val > 0 and step_mag > 0.2:
            accel_factor = 1.0 + (accel_val / 5.0) * min(2.5, (step_mag / 1.5) ** 1.1)
            out_dx *= accel_factor
            out_dy *= accel_factor

        # ============================================================
        # 6. 민감도(Sensitivity X/Y) 화면 좌표 변환
        # ============================================================
        sens_x = float(self.config.get("sensitivity_x", 25))
        sens_y = float(self.config.get("sensitivity_y", 25))
        
        # 각도당 마우스 픽셀 스케일링
        speed_factor_x = math.exp(sens_x / 6.0) * 1.8
        speed_factor_y = math.exp(sens_y / 6.0) * 1.8
        
        final_dx = out_dx * speed_factor_x
        # 고개를 위로 들면 Pitch가 -이므로 마우스 Y축 방향과 일치되도록 조정
        final_dy = out_dy * speed_factor_y

        return final_dx, final_dy


