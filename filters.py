class EMASmoothingFilter:
    """
    지수 이동 평균(Exponential Moving Average) 및 데드존(Deadzone)을 결합한 
    마우스 모션 스무딩 필터입니다. 미세한 떨림(Jitter)을 효과적으로 억제합니다.
    """
    def __init__(self, alpha=0.15, deadzone=1.0):
        self.alpha = alpha
        self.deadzone = deadzone
        self.smooth_x = 0.0
        self.smooth_y = 0.0
        self.initialized = False

    def update_alpha(self, new_alpha):
        # alpha는 0.01 ~ 1.0 사이
        self.alpha = max(0.01, min(1.0, new_alpha))

    def update_deadzone(self, new_deadzone):
        # 데드존(움직임 임계값) 업데이트
        self.deadzone = max(0.0, new_deadzone)

    def reset(self):
        self.smooth_x = 0.0
        self.smooth_y = 0.0
        self.initialized = False

    def filter(self, dx, dy):
        """
        입력받은 원본 델타(dx, dy)를 필터링하여 부드러운 델타(smooth_dx, smooth_dy)를 반환합니다.
        속도에 기반한 동적 반응 스무딩(Adaptive Smoothing)과 부드러운 마찰 감쇄(Soft Deadzone)를 결합합니다.
        """
        # 1. 초기값 설정
        if not self.initialized:
            self.smooth_x = dx
            self.smooth_y = dy
            self.initialized = True
            return dx, dy

        # 2. 움직임의 실시간 물리 속도(크기) 계산
        speed = (dx**2 + dy**2)**0.5

        # 3. 어댑티브 알파(Adaptive Alpha) 계산
        # 속도가 빠를수록 alpha를 1.0(실시간 카메라 직접 추적, 지연 0)에 가깝게 폭발시키고,
        # 속도가 느릴(정지/정밀 타겟팅)수록 설정된 smoothing(alpha) 값을 써서 노이즈를 강력 차단
        adaptive_alpha = self.alpha + (1.0 - self.alpha) * min(1.0, speed / 1.0)

        # 4. 동적 알파를 활용한 지수 이동 평균(EMA) 계산
        self.smooth_x = adaptive_alpha * dx + (1.0 - adaptive_alpha) * self.smooth_x
        self.smooth_y = adaptive_alpha * dy + (1.0 - adaptive_alpha) * self.smooth_y

        # 5. 하이브리드 데드존(Hybrid Deadzone) 적용
        # 임계값의 60% 미만인 미세 요동은 완전히 0으로 무력화하여 진동 원천 차단
        if speed < self.deadzone * 0.6:
            return 0.0, 0.0
        # 60% ~ 100% 구간은 부드러운 감쇄 곡선을 적용해 급작스러운 끊김 방지
        elif speed < self.deadzone:
            if self.deadzone > 0.0:
                ratio = speed / self.deadzone
                final_dx = self.smooth_x * (ratio ** 2)
                final_dy = self.smooth_y * (ratio ** 2)
            else:
                final_dx, final_dy = self.smooth_x, self.smooth_y
        else:
            final_dx, final_dy = self.smooth_x, self.smooth_y

        return final_dx, final_dy
