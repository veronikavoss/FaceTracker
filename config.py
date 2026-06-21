import json
import os

CONFIG_FILE = "pyviacam_config.json"

DEFAULT_CONFIG = {
    "camera_id": 0,
    "sensitivity_x": 10,  # 원본 xSpeed 0~30, 기본값 10
    "sensitivity_y": 10,  # 원본 ySpeed 0~30, 기본값 10
    "smoothing": 2,       # 원본 Smoothness 0~8, 기본값 2
    "acceleration": 2,    # 원본 Acceleration 0~5, 기본값 2
    "motion_threshold": 1,# 원본 EasyStop 0~10, 기본값 1
    "tracking_toggle_key": "f12",  # 활성/비활성 전환 키
    "lock_fps_low_light": False,  # 저조도 FPS 드롭 방지 (자동 노출 비활성화)
    "target_fps": 90,             # 카메라 타겟 FPS 설정 (60 또는 90 등 브리오 사양 지원)
    "camera_backend": "DSHOW",    # 카메라 백엔드 API (DSHOW, MSMF, AUTO 중 선택)
    "camera_width": 640,          # 카메라 해상도 가로 (CPU 절약을 위해 640 권장)
    "camera_height": 360,         # 카메라 해상도 세로 (16:9 비율 유지)
    "use_ir_camera": False,       # Logitech Brio 등 Windows Hello 적외선(IR) 카메라 활성화 여부
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
