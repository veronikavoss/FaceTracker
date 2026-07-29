import json
import os

CONFIG_FILE = "facetracker_config.json"

DEFAULT_CONFIG = {
    "camera_id": 0,
    "sensitivity_x": 25,  # 기본값 25 (슬라이더 범위 0~50 중앙)
    "sensitivity_y": 25,  # 기본값 25 (슬라이더 범위 0~50 중앙)
    "smoothing": 3,       # 기본값 3  (슬라이더 범위 0~6 중앙)
    "acceleration": 5,    # 기본값 5  (슬라이더 범위 0~10 중앙)
    "motion_threshold": 2,# 기본값 2  (슬라이더 범위 0~4 중앙)
    "tracking_toggle_key": "f12",  # 활성/비활성 전환 키
    "auto_exposure": True,        # 카메라 자동 노출 사용 여부 (기본값: True)
    "lock_fps_low_light": False,  # 수동 고속 노출 고정 여부
    "target_fps": 30,             # 카메라 타겟 FPS 설정
    "camera_backend": "DSHOW",    # 카메라 백엔드 API (DSHOW, MSMF, AUTO 중 선택)
    "camera_width": 640,          # 카메라 해상도 가로
    "camera_height": 480,         # 카메라 해상도 세로
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
