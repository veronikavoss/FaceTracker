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
        # 1. 초기화
        if not self.initialized:
            self.smooth_x = raw_dx
            self.smooth_y = raw_dy
            self.initialized = True
            return raw_dx, raw_dy

        # ----------------------------------------------------
        # 2. 칼같은 데드존 (클릭 정확도 극대화, 노이즈 완벽 차단)
        # ----------------------------------------------------
        # 임계값 미만의 움직임은 부드럽게 뭉개지 않고 즉시 '0'으로 차단
        # 미세 조준 시 마우스가 질질 끌리는 현상을 없앱니다.
        ui_threshold = max(0, min(10, int(self.config.get("motion_threshold", 1))))
        base_deadzone = ui_threshold * 0.1 
        
        raw_speed = math.hypot(raw_dx, raw_dy)
        
        if raw_speed < base_deadzone:
            raw_dx = 0.0
            raw_dy = 0.0

        # ----------------------------------------------------
        # 3. 즉각적인 스무딩 필터 (No Delay, No Slow-motion)
        # ----------------------------------------------------
        # 어댑티브(동적) 딜레이를 삭제하고 즉각 반응하도록 고정 Alpha 채용
        ui_smooth = max(0, min(8, int(self.config.get("smoothing", 2))))
        weight = math.log10(ui_smooth + 1.0)
        
        # 슬로우 모션(한 박자 늦게 따라오는 현상)을 원천 차단하기 위해 
        # 파이썬/OpenCV 프레임레이트에 맞춰 Alpha의 최소 하한선을 0.25로 강제 고정
        alpha = max(0.25, 1.0 - (weight * 0.8)) 
        
        self.smooth_x = alpha * raw_dx + (1.0 - alpha) * self.smooth_x
        self.smooth_y = alpha * raw_dy + (1.0 - alpha) * self.smooth_y
        
        fdx = self.smooth_x
        fdy = self.smooth_y

        # ----------------------------------------------------
        # 4. 민감도(Speed Factor) 적용
        # ----------------------------------------------------
        # 원본 공식: pow(e, speed / 6.0)
        speed_x = self.config.get("sensitivity_x", 10)
        speed_y = self.config.get("sensitivity_y", 10)
        
        fDx = math.exp(speed_x / 6.0)
        fDy = math.exp(speed_y / 6.0)
        
        internal_mult = self.config.get("internal_multiplier", 1.0)
        
        dx = fdx * fDx * internal_mult
        dy = fdy * fDy * internal_mult

        # ----------------------------------------------------
        # 5. 가속도 (Acceleration) 적용 (미세 조준 간섭 방지)
        # ----------------------------------------------------
        accel_level = max(0, min(5, int(self.config.get("acceleration", 2))))
        
        final_speed = math.hypot(dx, dy)
        accel_factor = 1.0
        
        # 미세 조준할 때는 가속도가 붙지 않도록(정확도 하락 방지) 속도가 1.5 이상일 때만 발동
        if accel_level > 0 and final_speed > 1.5:
            # 가속 배율 곡선 완화 (휙 돌아가는 멀미 증상 방지)
            max_accel = 1.0 + (accel_level * 0.2) 
            accel_factor = min(max_accel, 1.0 + (final_speed - 1.5) * (accel_level * 0.05))
            
        dx *= accel_factor
        dy *= accel_factor

        return dx, dy
