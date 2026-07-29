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
