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

    # 2. Nuitka 컴파일 실행
    print("[2/4] Nuitka C-컴파일 진행 중 (1~2분 소요)...")
    cmd = [
        python_exe, "-m", "nuitka",
        "--standalone",
        "--enable-plugin=pyside6",
        "--windows-console-mode=disable",
        "--output-dir=dist",
        "--output-filename=FaceTracker.exe",
        "--assume-yes-for-downloads",
        "--jobs=1",
        "--low-memory",
        "--nofollow-import-to=tkinter,unittest,pytest,pydoc,sqlite3,IPython,jupyter,matplotlib,scipy,mediapipe",
        "main.py"
    ]

    t0 = time.time()
    ret = subprocess.run(cmd, cwd=base_dir)
    if ret.returncode != 0:
        print(f"[오류] Nuitka 컴파일 실패 (종료 코드: {ret.returncode})")
        sys.exit(ret.returncode)

    elapsed = time.time() - t0
    print(f"[성공] Nuitka 컴파일 완료 (소요시간: {elapsed:.1f}초)")

    # 3. 산출물 폴더 찾기
    print("[3/4] 패키징 및 리소스 파일 동봉 중...")
    target_dist = os.path.join(dist_dir, "main.dist")
    if not os.path.exists(target_dist):
        alt_dist = os.path.join(dist_dir, "FaceTracker.dist")
        if os.path.exists(alt_dist):
            target_dist = alt_dist

    if not os.path.exists(target_dist):
        print(f"[경고] 생성된 dist 폴더를 찾을 수 없습니다: {target_dist}")
        sys.exit(1)

    # 4. 모델 및 설정 파일 복사
    model_src = os.path.join(base_dir, "face_detection_yunet_2023mar.onnx")
    if os.path.exists(model_src):
        shutil.copy2(model_src, target_dist)
        print(f"  -> ONNX 모델 동봉 완료: {model_src}")

    config_src = os.path.join(base_dir, "facetracker_config.json")
    if os.path.exists(config_src):
        shutil.copy2(config_src, target_dist)
        print(f"  -> 환경설정 파일 동봉 완료: {config_src}")

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

    print("")
    print("==========================================================")
    print("  [SUCCESS] 24/7 무중단 C-컴파일 패키징 완벽 준비 완료!")
    print(f"  실행 파일 위치: {os.path.join(target_dist, 'FaceTracker.exe')}")
    print("==========================================================")

if __name__ == "__main__":
    run_build()
