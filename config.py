import json
import os

CONFIG_FILE = "facetracker_config.json"

DEFAULT_CONFIG = {
    # 공통 카메라 및 시스템 설정
    "camera_id": 0,
    "tracking_toggle_key": "f12",  # 활성/비활성 전환 키
    "auto_exposure": True,        # 카메라 자동 노출 활성화
    "lock_fps_low_light": False,  # 수동 노출 고정 여부
    "target_fps": 30,             # 카메라 타겟 FPS 설정
    "camera_backend": "DSHOW",    # 카메라 백엔드 API
    "camera_width": 640,          # 카메라 해상도 가로
    "camera_height": 480,         # 카메라 해상도 세로
    "tracking_engine": "mediapipe", # 트래킹 엔진 ("mediapipe" 또는 "yunet")
    
    # 1. OpenCV YuNet 전용 설정
    "yunet": {
        "sensitivity_x": 27,        # X축 민감도 (0~50)
        "sensitivity_y": 27,        # Y축 민감도 (0~50)
        "motion_threshold": 2,      # 움직임 임계값 (0~4)
        "smoothing": 3,             # 스무딩 (0~6)
        "acceleration": 5,          # 가속도 (0~10)
        "illumination_threshold": 10.0, # 광량 급변 방지 임계값 (1.0~30.0)
        "spike_threshold": 15.0     # 비정상 튐 스파이크 억제 임계값 (5.0~50.0)
    },
    
    # 2. MediaPipe 머리 자세(Head Pose) 기반 5단계 파이프라인 설정
    "mediapipe": {
        "sensitivity_x": 25,        # X축 민감도 (0~50)
        "sensitivity_y": 25,        # Y축 민감도 (0~50)
        "outlier_threshold": 15.0,  # 1. 이상값 각도 튐 억제 (5.0~45.0도)
        "kalman_strength": 5,       # 2. 2D 칼만 필터 강도 (0~10)
        "adaptive_smoothing": 5,    # 3. 속도 적응형 스무딩 (0~10)
        "deadzone": 0.08,           # 4. 각도 데드존 미세 떨림 무시 (0.00~0.50도)
        "curve_power": 1.35,        # 5. 비선형 커브 곡선 지수 (1.0~1.8)
        "acceleration": 5           # 6. 모션 가속도 (0~10)
    }
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                config = DEFAULT_CONFIG.copy()
                # 공통 키 복사
                for k, v in DEFAULT_CONFIG.items():
                    if k in ["yunet", "mediapipe"]:
                        config[k] = DEFAULT_CONFIG[k].copy()
                        if k in loaded and isinstance(loaded[k], dict):
                            for sub_k, sub_v in DEFAULT_CONFIG[k].items():
                                config[k][sub_k] = loaded[k].get(sub_k, sub_v)
                        else:
                            # 이전 단일 설정 파일에서 마이그레이션
                            if k == "yunet":
                                config["yunet"]["sensitivity_x"] = loaded.get("sensitivity_x", 27)
                                config["yunet"]["sensitivity_y"] = loaded.get("sensitivity_y", 27)
                                config["yunet"]["motion_threshold"] = loaded.get("motion_threshold", 2)
                                config["yunet"]["smoothing"] = loaded.get("smoothing", 3)
                                config["yunet"]["acceleration"] = loaded.get("acceleration", 5)
                                config["yunet"]["illumination_threshold"] = loaded.get("illumination_threshold", 10.0)
                                config["yunet"]["spike_threshold"] = loaded.get("spike_threshold", 15.0)
                    elif k in loaded:
                        config[k] = loaded[k]
                return config
        except Exception as e:
            print(f"설정 로드 중 오류 발생: {e}")
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()

def save_config(config):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"설정 저장 중 오류 발생: {e}")
