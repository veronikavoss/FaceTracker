import os
import sys
import shutil
import subprocess
import time

def run_build():
    print("==========================================================")
    print("  FaceTracker - Nuitka C-Compilation Standalone Packaging")
    print("==========================================================")

    python_exe = sys.executable
    base_dir = os.path.dirname(os.path.abspath(__file__))
    dist_dir = os.path.join(base_dir, "dist")

    # 1. 이전 빌드 산출물 청소
    if os.path.exists(dist_dir):
        print("[1/4] 이전 빌드 폴더(dist) 정리 중...")
        try:
            shutil.rmtree(dist_dir)
        except Exception as e:
            print(f"경고: dist 정리 중 일부 파일 잠김 ({e}). 기존 파일 덮어쓰기 모드로 진행.")

    t0_total = time.time()

    # 2. FaceTracker Nuitka C-컴파일 실행
    print("[2/4] FaceTracker.exe Nuitka C-컴파일 진행 중 (1~2분 소요)...")
    cmd_ft = [
        python_exe, "-m", "nuitka",
        "--standalone",
        "--enable-plugin=pyside6",
        "--windows-console-mode=disable",
        "--output-dir=dist",
        "--output-filename=FaceTracker.exe",
        "--windows-icon-from-ico=facetracker.ico",
        "--assume-yes-for-downloads",
        "--jobs=2",
        "--low-memory",
        "--nofollow-import-to=tkinter,unittest,pytest,pydoc,sqlite3,IPython,jupyter,matplotlib,scipy,mediapipe",
        "main.py"
    ]

    t0 = time.time()
    ret_ft = subprocess.run(cmd_ft, cwd=base_dir)
    if ret_ft.returncode != 0:
        print(f"[오류] FaceTracker Nuitka 컴파일 실패 (종료 코드: {ret_ft.returncode})")
        sys.exit(ret_ft.returncode)
    print(f"[성공] FaceTracker.exe 컴파일 완료 ({time.time() - t0:.1f}초)")

    # 3. 산출물 폴더 찾기
    print("[3/4] 패키징 및 산출물 경로 확인 중...")
    target_dist = os.path.join(dist_dir, "main.dist")
    if not os.path.exists(target_dist):
        alt_dist = os.path.join(dist_dir, "FaceTracker.dist")
        if os.path.exists(alt_dist):
            target_dist = alt_dist
        else:
            final_check = os.path.join(dist_dir, "FaceTracker")
            if os.path.exists(final_check):
                target_dist = final_check

    if not os.path.exists(target_dist):
        print(f"[경고] 생성된 dist 폴더를 찾을 수 없습니다: {target_dist}")
        sys.exit(1)

    # 4. 모델, 사운드, 설정 파일 및 클릭바 동봉
    print("[4/4] 모델, 사운드, 설정 파일 및 머무름 클릭바 동봉 중...")
    model_src = os.path.join(base_dir, "face_detection_yunet_2023mar.onnx")
    if os.path.exists(model_src):
        shutil.copy2(model_src, target_dist)
        print(f"  -> ONNX 모델 동봉 완료: {model_src}")

    config_src = os.path.join(base_dir, "facetracker_config.json")
    if os.path.exists(config_src):
        shutil.copy2(config_src, target_dist)
        print(f"  -> 환경설정 파일 동봉 완료: {config_src}")

    cb_cfg_src = os.path.join(base_dir, "clickbar_config.json")
    if os.path.exists(cb_cfg_src):
        shutil.copy2(cb_cfg_src, target_dist)
        print(f"  -> 클릭바 설정 파일 동봉 완료: {cb_cfg_src}")

    cb_py_src = os.path.join(base_dir, "click_bar.py")
    if os.path.exists(cb_py_src):
        shutil.copy2(cb_py_src, target_dist)
        print(f"  -> 머무름 클릭 바 스크립트 동봉 완료: {cb_py_src}")

    for ico in ["facetracker.ico", "clickbar.ico"]:
        ico_src = os.path.join(base_dir, ico)
        if os.path.exists(ico_src):
            shutil.copy2(ico_src, target_dist)
            print(f"  -> 아이콘 파일 동봉 완료: {ico}")

    click_wav_src = os.path.join(base_dir, "click.wav")
    if os.path.exists(click_wav_src):
        shutil.copy2(click_wav_src, target_dist)
        print(f"  -> 클릭 사운드 파일 동봉 완료: {click_wav_src}")

    final_dist = os.path.join(dist_dir, "FaceTracker")
    if target_dist != final_dist:
        if os.path.exists(final_dist):
            shutil.rmtree(final_dist, ignore_errors=True)
        os.rename(target_dist, final_dist)
        target_dist = final_dist

    # 임시 빌드 캐시 정리
    build_cache = os.path.join(dist_dir, "main.build")
    if os.path.exists(build_cache):
        shutil.rmtree(build_cache, ignore_errors=True)

    total_elapsed = time.time() - t0_total
    print("")
    print("==========================================================")
    print(f"  [SUCCESS] 24/7 무중단 C-컴파일 패키징 완벽 준비 완료! ({total_elapsed:.1f}초)")
    print(f"  FaceTracker: {os.path.join(target_dist, 'FaceTracker.exe')}")
    print("==========================================================")

if __name__ == "__main__":
    run_build()
