#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <shellapi.h>
#include <stdio.h>
#include <shlwapi.h>

int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, LPSTR lpCmdLine, int nCmdShow) {
    wchar_t exeDir[MAX_PATH];
    GetModuleFileNameW(NULL, exeDir, MAX_PATH);
    PathRemoveFileSpecW(exeDir);

    STARTUPINFOW si;
    PROCESS_INFORMATION pi;
    ZeroMemory(&si, sizeof(si));
    si.cb = sizeof(si);
    si.dwFlags = STARTF_USESHOWWINDOW;
    si.wShowWindow = SW_HIDE;
    ZeroMemory(&pi, sizeof(pi));

    // 0. 단일 인스턴스 가드: 이미 ClickBar 창이 떠 있으면 중복 실행하지 않고 기존 창 활성화 후 즉시 종료
    HWND existingWnd = FindWindowW(NULL, L"ClickBar");
    if (!existingWnd) existingWnd = FindWindowW(NULL, L"Enable Viacam - ClickBar");
    if (existingWnd) {
        ShowWindow(existingWnd, SW_RESTORE);
        SetForegroundWindow(existingWnd);
        return 0;
    }

    int launched = 0;
    wchar_t cmdLine[MAX_PATH * 3];

    // 1. 배포 환경: 같은 디렉터리 또는 상위 디렉터리의 FaceTracker.exe를 찾아 --click-bar 인자로 실행 (click_bar.py 소스 불필요)
    wchar_t ftPath[MAX_PATH];
    swprintf(ftPath, MAX_PATH, L"%s\\FaceTracker.exe", exeDir);

    if (GetFileAttributesW(ftPath) == INVALID_FILE_ATTRIBUTES) {
        wchar_t parentDir[MAX_PATH];
        wcscpy(parentDir, exeDir);
        PathRemoveFileSpecW(parentDir);
        swprintf(ftPath, MAX_PATH, L"%s\\FaceTracker.exe", parentDir);
    }

    if (GetFileAttributesW(ftPath) != INVALID_FILE_ATTRIBUTES) {
        swprintf(cmdLine, MAX_PATH * 3, L"\"%s\" --click-bar", ftPath);
        if (CreateProcessW(ftPath, cmdLine, NULL, NULL, FALSE, CREATE_NO_WINDOW, NULL, exeDir, &si, &pi)) {
            launched = 1;
        }
    }

    // 2. 개발 환경 Fallback: FaceTracker.exe가 없을 때 click_bar.py 스크립트 실행
    if (!launched) {
        wchar_t scriptPath[MAX_PATH];
        swprintf(scriptPath, MAX_PATH, L"%s\\click_bar.py", exeDir);

        if (GetFileAttributesW(scriptPath) == INVALID_FILE_ATTRIBUTES) {
            wchar_t parentDir[MAX_PATH];
            wcscpy(parentDir, exeDir);
            PathRemoveFileSpecW(parentDir);
            swprintf(scriptPath, MAX_PATH, L"%s\\click_bar.py", parentDir);
        }

        if (GetFileAttributesW(scriptPath) != INVALID_FILE_ATTRIBUTES) {
            const wchar_t* candidates[] = {
                L"pythonw.exe",
                L"D:\\Program Files\\Python\\pythonw.exe",
                L"python.exe",
                L"D:\\Program Files\\Python\\python.exe"
            };

            for (int i = 0; i < 4; i++) {
                swprintf(cmdLine, MAX_PATH * 3, L"\"%s\" \"%s\"", candidates[i], scriptPath);
                if (CreateProcessW(NULL, cmdLine, NULL, NULL, FALSE, CREATE_NO_WINDOW, NULL, exeDir, &si, &pi)) {
                    launched = 1;
                    break;
                }
            }
        }
    }

    if (!launched) {
        MessageBoxW(NULL, L"ClickBar 실행 대상을 찾을 수 없습니다.\nFaceTracker.exe 파일이 같은 폴더에 있는지 확인해 주세요.", L"ClickBar 실행 오류", MB_OK | MB_ICONERROR);
        return 1;
    }

    // 자식 프로세스가 살아있는 동안 대기
    WaitForSingleObject(pi.hProcess, INFINITE);

    DWORD exitCode = 0;
    GetExitCodeProcess(pi.hProcess, &exitCode);
    CloseHandle(pi.hProcess);
    CloseHandle(pi.hThread);

    return (int)exitCode;
}
