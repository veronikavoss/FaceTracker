import math

class EMASmoothingFilter:
    """
    오리지널 eViacam(C++)의 트래킹 수학 공식을 100% 동일하게 재현한 필터입니다.
    기존의 Python 호환 필터 대신 원본의 SpeedFactor(pow), LowPassFilter(log10),
    그리고 SetRelAcceleration2 배열 방식의 가속도 커브를 그대로 적용합니다.
    """
    def __init__(self, config):
        self.config = config
        self.dxant = 0.0
        self.dyant = 0.0

    def reset(self):
        self.dxant = 0.0
        self.dyant = 0.0

    def filter(self, raw_dx, raw_dy):
        # 1. Apply factors (Speed / 민감도 변환 공식)
        speed_x = self.config.get("sensitivity_x", 10)
        speed_y = self.config.get("sensitivity_y", 10)
        
        # 원본 공식: pow(e, speed / 6.0)
        fDx = math.exp(speed_x / 6.0)
        fDy = math.exp(speed_y / 6.0)
        
        # 내부 배율 적용 (해상도 및 픽셀 좌표 차이 보정용. 원본은 화면 절대 좌표의 정규화를 사용하나, 
        # 파이썬 버전에서는 cv2 캔버스 기반이므로 픽셀 변화량에 대한 기본 스케일 보정이 조금 필요할 수 있습니다.
        # 일단 원본 비율과 1:1 매칭되도록 맞춥니다.)
        internal_mult = self.config.get("internal_multiplier", 1.0)
        
        dx = raw_dx * fDx * internal_mult
        dy = raw_dy * fDy * internal_mult

        # 2. Low-pass filter (Smoothness)
        smoothness = self.config.get("smoothing", 2)
        smoothness = max(0, min(8, int(smoothness)))
        m_actualMotionWeight = math.log10(smoothness + 1.0)
        
        dx = dx * (1.0 - m_actualMotionWeight) + self.dxant * m_actualMotionWeight
        dy = dy * (1.0 - m_actualMotionWeight) + self.dyant * m_actualMotionWeight
        self.dxant = dx
        self.dyant = dy

        # 3. Acceleration (SetRelAcceleration2 로직)
        accel = self.config.get("acceleration", 2)
        accel = max(0, min(5, int(accel)))
        distance = math.hypot(dx, dy)
        idx = int(distance + 0.5)
        
        delta0 = 9999
        factor0 = 1.0
        delta1 = 9999
        factor1 = 1.0
        
        if accel == 1:
            delta0 = 7; factor0 = 1.5
        elif accel == 2:
            delta0 = 7; factor0 = 2.0
        elif accel == 3:
            delta0 = 7; factor0 = 1.5; delta1 = 14; factor1 = 2.0
        elif accel == 4:
            delta0 = 7; factor0 = 2.0; delta1 = 14; factor1 = 1.5
        elif accel == 5:
            delta0 = 7; factor0 = 2.0; delta1 = 14; factor1 = 2.0
            
        factor = 1.0
        if idx < delta0:
            factor = 1.0
        elif idx < delta1:
            factor = factor0
        else:
            factor = (factor0 * factor1) + ((idx - delta1) * 0.1)
            
        dx *= factor
        dy *= factor

        # 4. Apply delta threshold (EasyStop / motion_threshold)
        threshold = self.config.get("motion_threshold", 1)
        if -threshold < dx < threshold:
            dx = 0.0
        if -threshold < dy < threshold:
            dy = 0.0

        return dx, dy
