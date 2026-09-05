import json
import os
import sys

def get_base_dir():
    """실행 파일(Nuitka/PyInstaller) 환경과 일반 스크립트 실행 환경을 자동 감지하여 기준 폴더 반환"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(get_base_dir(), "facetracker_config.json")

DEFAULT_PROFILE_DATA = {
    "sensitivity_x": 25,
    "sensitivity_y": 25,
    "motion_threshold": 2,
    "smoothing": 3,
    "acceleration": 5,
    "correction_interval": 5,
    "illumination_threshold": 10.0,
    "spike_threshold": 15.0
}

DEFAULT_CONFIG = {
    "camera_id": 0,
    "tracking_toggle_key": "f12",  # 활성/비활성 전환 키
    "auto_exposure": True,        # 카메라 자동 노출 활성화
    "lock_fps_low_light": False,  # 수동 노출 고정 여부
    "target_fps": 30,             # 카메라 타겟 FPS 설정
    "camera_backend": "DSHOW",    # 카메라 백엔드 API
    "camera_width": 640,          # 카메라 해상도 가로
    "camera_height": 480,         # 카메라 해상도 세로
    "current_profile": "기본",
    "profiles": {
        "기본": DEFAULT_PROFILE_DATA.copy()
    },
    # 기본 프로필 값 복사
    **DEFAULT_PROFILE_DATA
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                config = DEFAULT_CONFIG.copy()
                for k, v in DEFAULT_CONFIG.items():
                    if k in loaded:
                        config[k] = loaded[k]
                    elif "yunet" in loaded and isinstance(loaded["yunet"], dict) and k in loaded["yunet"]:
                        config[k] = loaded["yunet"][k]
                
                # profiles 검증 및 보정
                if "profiles" not in config or not isinstance(config["profiles"], dict) or len(config["profiles"]) == 0:
                    config["profiles"] = {"기본": DEFAULT_PROFILE_DATA.copy()}
                if "current_profile" not in config or config["current_profile"] not in config["profiles"]:
                    config["current_profile"] = list(config["profiles"].keys())[0]
                    
                return config
        except Exception as e:
            print(f"설정 로드 중 오류 발생: {e}")
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()

def save_config(config):
    """원자적(Atomic) 파일 쓰기를 통해 비정상 종료 시에도 파일 손실 및 0바이트 손상을 방지합니다."""
    temp_file = CONFIG_FILE + ".tmp"
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_file, CONFIG_FILE)
    except Exception as e:
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except Exception:
                pass
        print(f"설정 저장 중 오류 발생: {e}")

def get_current_profile_data(config):
    """현재 슬라이더 설정값을 딕셔너리로 추출"""
    return {
        "sensitivity_x": config.get("sensitivity_x", 27),
        "sensitivity_y": config.get("sensitivity_y", 27),
        "motion_threshold": config.get("motion_threshold", 2),
        "smoothing": config.get("smoothing", 3),
        "acceleration": config.get("acceleration", 5),
        "correction_interval": config.get("correction_interval", 5),
        "illumination_threshold": config.get("illumination_threshold", 10.0),
        "spike_threshold": config.get("spike_threshold", 15.0)
    }
