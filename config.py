import json
import os
import sys

def get_base_dir():
    """
    실행 파일(Nuitka/PyInstaller) 환경과 일반 스크립트 실행 환경을 자동 감지하여 기준 폴더 반환.
    Nuitka standalone, PyInstaller, 일반 python 실행 모두에서 항상 정확한 실행 폴더 절대 경로를 반환합니다.
    """
    # 1. PyInstaller (sys.frozen) 또는 Nuitka (__compiled__) 환경 감지
    if getattr(sys, 'frozen', False) or hasattr(sys, '__compiled__') or '__compiled__' in globals():
        return os.path.dirname(os.path.abspath(sys.executable))
    
    # 2. sys.executable이 python.exe / pythonw.exe가 아닌 경우 (컴파일된 exe 실행 파일인 경우)
    exe_name = os.path.basename(sys.executable).lower()
    if not exe_name.startswith("python"):
        return os.path.dirname(os.path.abspath(sys.executable))
        
    # 3. 개발 중 .py 직접 실행 환경
    return os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(get_base_dir(), "facetracker_config.json")

from typing import Any, Dict

DEFAULT_PROFILE_DATA: Dict[str, Any] = {
    "sensitivity_x": 25,
    "sensitivity_y": 25,
    "motion_threshold": 2,
    "smoothing": 3,
    "acceleration": 5,
    "correction_interval": 5,
    "illumination_threshold": 10.0,
    "spike_threshold": 15.0
}

DEFAULT_CONFIG: Dict[str, Any] = {
    "camera_id": 0,
    "tracking_toggle_key": "f12",  # 활성/비활성 전환 키
    "auto_exposure": True,        # 카메라 자동 노출 활성화
    "lock_fps_low_light": False,  # 수동 노출 고정 여부
    "low_light_compensation": False, # 낮은 빛 보상 활성화 여부 (기본 해제)
    "target_fps": 30,             # 카메라 타겟 FPS 설정
    "camera_backend": "DSHOW",    # 카메라 백엔드 API
    "camera_width": 640,          # 카메라 해상도 가로
    "camera_height": 480,         # 카메라 해상도 세로
    "enable_click_bar": False,    # 머무름 클릭 바 자동 실행 여부
    "close_clickbar_on_exit": True, # 페이스 트래커 종료 시 클릭바도 함께 닫기 여부
    "auto_start_windows": False,  # 윈도우 부팅 시 자동 시작 여부
    "auto_start_tracking": False, # 앱 실행 시 코끝 추적 자동 시작 여부
    "current_profile": "기본",
    "profiles": {
        "기본": DEFAULT_PROFILE_DATA.copy()
    },
    # 기본 프로필 값 복사
    "sensitivity_x": 25,
    "sensitivity_y": 25,
    "motion_threshold": 2,
    "smoothing": 3,
    "acceleration": 5,
    "correction_interval": 5,
    "illumination_threshold": 10.0,
    "spike_threshold": 15.0
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

# ========================================================
# Windows 작업 세트(Working Set) 메모리 최적화 유틸리티
# ========================================================
_kernel32 = None
if sys.platform == "win32":
    try:
        import ctypes
        from ctypes import wintypes
        _kernel32 = ctypes.windll.kernel32
        _kernel32.SetProcessWorkingSetSize.argtypes = [wintypes.HANDLE, ctypes.c_size_t, ctypes.c_size_t]
        _kernel32.SetProcessWorkingSetSize.restype = wintypes.BOOL
    except Exception:
        _kernel32 = None

def trim_process_memory():
    """Windows OS에 프로세스의 불필요한 작업 세트(Working Set) 메모리를 즉시 반환하도록 요청하여 메모리 점유율을 극소화"""
    try:
        import gc
        gc.collect()
        if _kernel32:
            import ctypes
            h_process = _kernel32.GetCurrentProcess()
            _kernel32.SetProcessWorkingSetSize(h_process, ctypes.c_size_t(-1), ctypes.c_size_t(-1))
    except Exception:
        pass

