import json
import os

CONFIG_FILE = "pyviacam_config.json"

DEFAULT_CONFIG = {
    "camera_id": 0,
    "sensitivity_x": 1.5,
    "sensitivity_y": 1.5,
    "smoothing": 0.15,  # 0~1 사이의 값. 작을수록 더 부드러워지지만 미세한 지연 증가.
    "acceleration": 2.0,  # 마우스 가속도 배율 (1.0 = 가속 없음, 최대 5.0)
    "motion_threshold": 0.5,  # 가만히 있을 때의 미세 움직임 필터 임계값 (데드존)
    "tracking_toggle_key": "f12",  # 활성/비활성 전환 키
    "lock_fps_low_light": False,  # 저조도 FPS 드롭 방지 (자동 노출 비활성화)
    "target_fps": 90,             # 카메라 타겟 FPS 설정 (60 또는 90 등 브리오 사양 지원)
    "camera_backend": "DSHOW",    # 카메라 백엔드 API (DSHOW, MSMF, AUTO 중 선택)
    "camera_width": 640,          # 카메라 해상도 가로 (CPU 절약을 위해 640 권장)
    "camera_height": 360,         # 카메라 해상도 세로 (16:9 비율 유지)
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                # 누락된 필드가 있다면 기본값으로 채움
                for k, v in DEFAULT_CONFIG.items():
                    if k not in config:
                        config[k] = v
                return config
        except Exception:
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()

def save_config(config):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"설정 저장 중 오류 발생: {e}")
