import math

ACCEL_ARRAY_SIZE = 30

class EMASmoothingFilter:
    """
    원본 eViacam C++ (mousecontrol.cpp MovePointerRel 함수)의 
    마우스 모션 처리 알고리즘을 1:1로 정확히 복제한 필터입니다.
    """
    def __init__(self, config):
        self.config = config
        self.dxant = 0.0
        self.dyant = 0.0
        self.accel_array = [1.0] * ACCEL_ARRAY_SIZE
        self._build_accel_array()

    def _build_accel_array(self):
        accel = max(0, min(10, int(self.config.get("acceleration", 5))))
        delta0 = ACCEL_ARRAY_SIZE
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

    def filter(self, raw_dx, raw_dy, actual_fps=30.0):
        # 1. FPS 정규화 비율 계산 (30 FPS 기준 불변 속도 모델)
        fps = max(5.0, min(60.0, float(actual_fps) if actual_fps > 0 else 30.0))
        fps_ratio = 30.0 / fps  # 30FPS 기준 시간 비율 (예: 30FPS->1.0, 15FPS->2.0, 10FPS->3.0)

        # 2. 카메라 측정 변위를 30FPS 기준 1프레임 변위로 완벽 환산 (물리적 정규화)
        #    사용자가 같은 속도로 머리를 움직일 때 15FPS에서는 raw_dx가 2배로 측정되므로,
        #    fps_ratio로 나누면 정확히 30FPS일 때와 100% 동일한 변위가 됩니다.
        norm_raw_dx = raw_dx / fps_ratio
        norm_raw_dy = raw_dy / fps_ratio

        # 3. 비정상적 값으로 인한 math.exp OverflowError 방어를 위한 안전 클램핑 (0 ~ 50)
        speed_x = max(0, min(50, float(self.config.get("sensitivity_x", 10))))
        speed_y = max(0, min(50, float(self.config.get("sensitivity_y", 10))))
        
        fDx = math.exp(speed_x / 6.0)
        fDy = math.exp(speed_y / 6.0)
        
        dx = norm_raw_dx * fDx
        dy = norm_raw_dy * fDy

        # 4. 30FPS 기준 원본 스무딩 (EMA) 적용 (지수 왜곡 없음)
        smoothness = max(0, min(8, int(self.config.get("smoothing", 2))))
        weight = math.log10(smoothness + 1.0)
        
        dx = dx * (1.0 - weight) + self.dxant * weight
        dy = dy * (1.0 - weight) + self.dyant * weight
        self.dxant = dx
        self.dyant = dy

        # 5. 30FPS 기준 원본 가속도 테이블 적용 (인덱스 왜곡 및 급발진 0%)
        distance = math.sqrt(dx * dx + dy * dy)
        idx = int(distance + 0.5)
        if idx >= ACCEL_ARRAY_SIZE:
            idx = ACCEL_ARRAY_SIZE - 1
        
        dx *= self.accel_array[idx]
        dy *= self.accel_array[idx]

        # 6. 30FPS 기준 원본 데드존 적용 (저프레임 질식/멈춤 0%)
        threshold = float(self.config.get("motion_threshold", 1))
        if -threshold < dx < threshold:
            dx = 0.0
        if -threshold < dy < threshold:
            dy = 0.0

        # 7. 현재 카메라 FPS 환경에 맞춰 30FPS 초당 속도 복원 (Scale to Frame Rate)
        #    15FPS 환경에서는 프레임이 초당 15번 오므로 fps_ratio(2.0)를 곱해 총 이동 거리를 30FPS와 100% 일치시킴
        final_dx = dx * fps_ratio
        final_dy = dy * fps_ratio

        return final_dx, final_dy

