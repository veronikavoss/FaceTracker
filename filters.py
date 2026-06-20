import math

class EMASmoothingFilter:
    """
    Python + OpenCV 환경에 맞춰 최적화된 하이브리드 지수 이동 평균(EMA) 및 동적 데드존 필터.
    오리지널 eViacam의 UI 스케일(0~20, 0~8 등)을 완벽히 수용하면서도,
    OpenCV(Lucas-Kanade) 특유의 미세 떨림(Micro-jitter)을 효과적으로 억제합니다.
    """
    def __init__(self, config):
        self.config = config
        self.smooth_x = 0.0
        self.smooth_y = 0.0
        self.initialized = False

    def reset(self):
        self.smooth_x = 0.0
        self.smooth_y = 0.0
        self.initialized = False

    def filter(self, raw_dx, raw_dy):
        # 초기화
        if not self.initialized:
            self.smooth_x = raw_dx
            self.smooth_y = raw_dy
            self.initialized = True
            return raw_dx, raw_dy

        # ----------------------------------------------------
        # 1. 데드존 (부드러운 감쇄) - 뚝뚝 끊김 완전 해결!
        # ----------------------------------------------------
        # 사용자가 움직이려고 할 때 절대 0으로 강제로 끊어버리지 않습니다 (Hard deadzone 금지)
        ui_threshold = max(0, min(10, int(self.config.get("motion_threshold", 1))))
        base_deadzone = ui_threshold * 0.1 
        
        raw_speed = math.hypot(raw_dx, raw_dy)
        
        # 속도가 임계값보다 작으면 비율적으로 부드럽게 줄여서 노이즈만 약하게 만듭니다.
        if base_deadzone > 0.0 and raw_speed < base_deadzone:
            ratio = raw_speed / base_deadzone
            # ratio는 0~1 사이의 값. 제곱하여 0 근처에서 부드럽게 감쇄 (뚝 끊기지 않음)
            raw_dx *= (ratio ** 2)
            raw_dy *= (ratio ** 2)

        # ----------------------------------------------------
        # 2. 민감도 (Speed Factor) - 원본 공식
        # ----------------------------------------------------
        speed_x = self.config.get("sensitivity_x", 10)
        speed_y = self.config.get("sensitivity_y", 10)
        
        fDx = math.exp(speed_x / 6.0)
        fDy = math.exp(speed_y / 6.0)
        internal_mult = self.config.get("internal_multiplier", 1.0)
        
        dx = raw_dx * fDx * internal_mult
        dy = raw_dy * fDy * internal_mult

        # ----------------------------------------------------
        # 3. 스무딩 필터 (Low-pass Filter) - 슬로우 모션 방지 보정
        # ----------------------------------------------------
        ui_smooth = max(0, min(8, int(self.config.get("smoothing", 2))))
        weight = math.log10(ui_smooth + 1.0)
        
        # 파이썬(OpenCV)은 30fps로 원본보다 샘플링 레이트가 낮아 
        # 원본 weight(0~0.95)를 그대로 쓰면 슬로우 모션이 매우 심해집니다.
        # 따라서 딜레이를 체감상 비슷하게 맞추기 위해 파이썬 환경에 맞게 보정 계수(0.6)를 곱합니다.
        alpha = 1.0 - (weight * 0.6) 
        # 아주 미세한 alpha 최저방어선 설정 (최소한 10%씩은 최신 프레임 반영)
        alpha = max(0.1, alpha)
        
        dx = alpha * dx + (1.0 - alpha) * self.smooth_x
        dy = alpha * dy + (1.0 - alpha) * self.smooth_y
        
        self.smooth_x = dx
        self.smooth_y = dy

        # ----------------------------------------------------
        # 4. 가속도 (Acceleration) - 원본의 배열 로직 복구
        # ----------------------------------------------------
        accel = max(0, min(5, int(self.config.get("acceleration", 2))))
        
        # 파이썬 30fps 환경의 distance는 원본 고속 루프보다 픽셀 이동량이 큽니다.
        # 따라서 파이썬의 distance를 원본 array index 느낌에 맞게 살짝 축소 스케일링합니다.
        distance = math.hypot(dx, dy)
        idx = int((distance * 0.5) + 0.5)
        
        delta0 = 7
        factor0 = 1.0
        delta1 = 14
        factor1 = 1.0
        
        if accel == 1:
            factor0 = 1.5
        elif accel == 2:
            factor0 = 2.0
        elif accel == 3:
            factor0 = 1.5; factor1 = 2.0
        elif accel == 4:
            factor0 = 2.0; factor1 = 1.5
        elif accel == 5:
            factor0 = 2.0; factor1 = 2.0
            
        accel_factor = 1.0
        if accel > 0:
            if idx < delta0:
                accel_factor = 1.0
            elif idx < delta1:
                accel_factor = factor0
            else:
                accel_factor = (factor0 * factor1) + ((idx - delta1) * 0.1)
                
        dx *= accel_factor
        dy *= accel_factor

        return dx, dy
