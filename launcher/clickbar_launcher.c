#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <shellapi.h>
#include <stdio.h>
#include <shlwapi.h>

int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, LPSTR lpCmdLine, int nCmdShow) {
    wchar_t exeDir[MAX_PATH];
    GetModuleFileNameW(NULL, exeDir, MAX_PATH);
    PathRemoveFileSpecW(exeDir);

    wchar_t scriptPath[MAX_PATH];
    swprintf(scriptPath, MAX_PATH, L"%s\\click_bar.py", exeDir);

    if (GetFileAttributesW(scriptPath) == INVALID_FILE_ATTRIBUTES) {
        wchar_t parentDir[MAX_PATH];
        wcscpy(parentDir, exeDir);
        PathRemoveFileSpecW(parentDir);
        swprintf(scriptPath, MAX_PATH, L"%s\\click_bar.py", parentDir);
    }

    if (GetFileAttributesW(scriptPath) == INVALID_FILE_ATTRIBUTES) {
        MessageBoxW(NULL, L"click_bar.py 스크립트 파일을 찾을 수 없습니다.", L"ClickBar 오류", MB_OK | MB_ICONERROR);
        return 1;
    }

    const wchar_t* candidates[] = {
        L"D:\\Program Files\\Python\\pythonw.exe",
        L"D:\\Program Files\\Python\\python.exe",
        L"pythonw.exe",
        L"python.exe"
    };

    wchar_t cmdLine[MAX_PATH * 3];
    STARTUPINFOW si;
    PROCESS_INFORMATION pi;
    ZeroMemory(&si, sizeof(si));
    si.cb = sizeof(si);
    si.dwFlags = STARTF_USESHOWWINDOW;
    si.wShowWindow = SW_HIDE;
    ZeroMemory(&pi, sizeof(pi));

    int launched = 0;
    for (int i = 0; i < 4; i++) {
        swprintf(cmdLine, MAX_PATH * 3, L"\"%s\" \"%s\"", candidates[i], scriptPath);
        if (CreateProcessW(NULL, cmdLine, NULL, NULL, FALSE, CREATE_NO_WINDOW, NULL, exeDir, &si, &pi)) {
            launched = 1;
            break;
        }
    }

    if (!launched) {
        MessageBoxW(NULL, L"Python 인터프리터를 찾을 수 없습니다.\nD:\\Program Files\\Python 경로를 확인해 주세요.", L"ClickBar 실행 오류", MB_OK | MB_ICONERROR);
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
