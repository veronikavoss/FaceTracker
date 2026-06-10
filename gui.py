import tkinter as tk
from tkinter import ttk
import cv2
from PIL import Image, ImageTk
import config

class PyViacamGUI:
    def __init__(self, root, app_config, tracker):
        self.root = root
        self.config = app_config
        self.tracker = tracker
        
        # 윈도우 타이틀 및 크기 설정
        self.root.title("PyViacam Lite - Head Tracking Mouse")
        self.root.geometry("900x560")
        self.root.resizable(False, False)
        
        # 스타일 테마 정의 (Modern Premium Dark Mode)
        self.bg_color = "#0F172A"       # 미드나이트 다크 블루
        self.card_color = "#1E293B"     # 다크 슬레이트 카드 배경
        self.text_color = "#F8FAFC"     # 부드러운 화이트 텍스트
        self.accent_color = "#3B82F6"   # 네온 아쿠아 블루 (활성화)
        self.inactive_color = "#EF4444" # 부드러운 레드 (비활성화)
        self.muted_color = "#94A3B8"    # 뮤트 그레이 텍스트
        
        self.root.configure(bg=self.bg_color)
        
        # 스타일러 구성
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure(".", background=self.bg_color, foreground=self.text_color)
        
        # 전체 그리드 레이아웃
        self.root.columnconfigure(0, weight=3) # 카메라 화면 영역
        self.root.columnconfigure(1, weight=2) # 컨트롤 패널 영역
        self.root.rowconfigure(0, weight=1)
        
        self._init_camera_panel()
        self._init_control_panel()
        
        # 종료 시 리소스 정리
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        self.photo = None

    def _init_camera_panel(self):
        # 카메라 패널 프레임 (Card 스타일)
        self.cam_frame = tk.Frame(self.root, bg=self.card_color, bd=0, highlightthickness=2, highlightbackground="#334155")
        self.cam_frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        
        # 헤더 영역 프레임 (타이틀 & FPS/해상도 정보 표시)
        self.cam_header = tk.Frame(self.cam_frame, bg=self.card_color)
        self.cam_header.pack(fill="x", padx=15, pady=10)
        
        # 타이틀
        self.cam_title = tk.Label(self.cam_header, text="LIVE VIDEO FEED", font=("Inter", 12, "bold"), fg=self.accent_color, bg=self.card_color)
        self.cam_title.pack(side="left")
        
        # FPS & 해상도 정보 표시 라벨
        self.info_label = tk.Label(self.cam_header, text="FPS: -- | --x--", font=("Inter", 10, "bold"), fg=self.muted_color, bg=self.card_color)
        self.info_label.pack(side="right")
        
        # 비디오 표시 캔버스 (1280x720 카메라 해상도 맞춤 16:9 비율)
        self.canvas = tk.Canvas(self.cam_frame, width=640, height=360, bg="#020617", bd=0, highlightthickness=0)
        self.canvas.pack(padx=15, pady=5, fill="both", expand=True)
        
        # 초기 카메라 대기 상태 텍스트
        self.canvas.create_text(320, 180, text="카메라 연결 대기 중...", fill=self.muted_color, font=("Segoe UI", 12))

    def _init_control_panel(self):
        # 우측 컨트롤 프레임
        self.ctrl_frame = tk.Frame(self.root, bg=self.card_color, bd=0, highlightthickness=2, highlightbackground="#334155")
        self.ctrl_frame.grid(row=0, column=1, padx=(0, 20), pady=20, sticky="nsew")
        
        # 프로그램 이름 및 상태 헤더
        header_label = tk.Label(self.ctrl_frame, text="PyViacam Lite", font=("Outfit", 20, "bold"), fg=self.text_color, bg=self.card_color)
        header_label.pack(anchor="w", padx=20, pady=(20, 5))
        
        self.status_label = tk.Label(self.ctrl_frame, text="비활성 상태 (F12키로 활성화)", font=("Inter", 10, "bold"), fg=self.inactive_color, bg=self.card_color)
        self.status_label.pack(anchor="w", padx=20, pady=(0, 20))
        
        # 구분선
        separator = tk.Frame(self.ctrl_frame, height=1, bg="#334155")
        separator.pack(fill="x", padx=20, pady=(0, 20))
        
        # 감도(Sensitivity X) 조절 영역
        self.sens_x_label = tk.Label(self.ctrl_frame, text=f"X축 민감도: {self.config['sensitivity_x']:.2f}", font=("Inter", 10), fg=self.text_color, bg=self.card_color)
        self.sens_x_label.pack(anchor="w", padx=20, pady=(5, 2))
        
        self.sens_x_scale = tk.Scale(
            self.ctrl_frame, from_=0.1, to=20.0, resolution=0.1, orient="horizontal",
            bg=self.card_color, fg=self.text_color, troughcolor="#0F172A", activebackground=self.accent_color,
            highlightthickness=0, bd=0, showvalue=False, command=self.on_sens_x_change
        )
        self.sens_x_scale.set(self.config["sensitivity_x"])
        self.sens_x_scale.pack(fill="x", padx=20, pady=(0, 15))
        
        # 감도(Sensitivity Y) 조절 영역
        self.sens_y_label = tk.Label(self.ctrl_frame, text=f"Y축 민감도: {self.config['sensitivity_y']:.2f}", font=("Inter", 10), fg=self.text_color, bg=self.card_color)
        self.sens_y_label.pack(anchor="w", padx=20, pady=(5, 2))
        
        self.sens_y_scale = tk.Scale(
            self.ctrl_frame, from_=0.1, to=20.0, resolution=0.1, orient="horizontal",
            bg=self.card_color, fg=self.text_color, troughcolor="#0F172A", activebackground=self.accent_color,
            highlightthickness=0, bd=0, showvalue=False, command=self.on_sens_y_change
        )
        self.sens_y_scale.set(self.config["sensitivity_y"])
        self.sens_y_scale.pack(fill="x", padx=20, pady=(0, 15))
        
        # 모션 가속도(Acceleration) 조절 영역
        self.accel_label = tk.Label(self.ctrl_frame, text=f"모션 가속도: {self.config['acceleration']:.2f}", font=("Inter", 10), fg=self.text_color, bg=self.card_color)
        self.accel_label.pack(anchor="w", padx=20, pady=(5, 2))
        
        self.accel_scale = tk.Scale(
            self.ctrl_frame, from_=1.0, to=5.0, resolution=0.1, orient="horizontal",
            bg=self.card_color, fg=self.text_color, troughcolor="#0F172A", activebackground=self.accent_color,
            highlightthickness=0, bd=0, showvalue=False, command=self.on_accel_change
        )
        self.accel_scale.set(self.config["acceleration"])
        self.accel_scale.pack(fill="x", padx=20, pady=(0, 15))
        
        # 움직임 임계값(Motion Threshold) 조절 영역
        self.thresh_label = tk.Label(self.ctrl_frame, text=f"움직임 임계값: {self.config['motion_threshold']:.2f}", font=("Inter", 10), fg=self.text_color, bg=self.card_color)
        self.thresh_label.pack(anchor="w", padx=20, pady=(5, 2))
        
        self.thresh_scale = tk.Scale(
            self.ctrl_frame, from_=0.0, to=5.0, resolution=0.01, orient="horizontal",
            bg=self.card_color, fg=self.text_color, troughcolor="#0F172A", activebackground=self.accent_color,
            highlightthickness=0, bd=0, showvalue=False, command=self.on_thresh_change
        )
        self.thresh_scale.set(self.config["motion_threshold"])
        self.thresh_scale.pack(fill="x", padx=20, pady=(0, 15))
        
        # 흔들림 방지(Smoothing) 조절 영역
        self.smooth_label = tk.Label(self.ctrl_frame, text=f"모션 스무딩(부드러움): {self.config['smoothing']:.2f}", font=("Inter", 10), fg=self.text_color, bg=self.card_color)
        self.smooth_label.pack(anchor="w", padx=20, pady=(5, 2))
        
        self.smooth_scale = tk.Scale(
            self.ctrl_frame, from_=0.01, to=0.5, resolution=0.01, orient="horizontal",
            bg=self.card_color, fg=self.text_color, troughcolor="#0F172A", activebackground=self.accent_color,
            highlightthickness=0, bd=0, showvalue=False, command=self.on_smooth_change
        )
        self.smooth_scale.set(self.config["smoothing"])
        self.smooth_scale.pack(fill="x", padx=20, pady=(0, 20))

        # 카메라 상세 제어 프레임 (카메라 설정 & 자동 노출 토글)
        self.cam_ctrl_frame = tk.Frame(self.ctrl_frame, bg=self.card_color)
        self.cam_ctrl_frame.pack(fill="x", padx=20, pady=(0, 15))
        
        # 1. 자동 노출 끄기 (FPS 고정) 체크박스
        self.auto_exposure_var = tk.BooleanVar(value=self.config.get("lock_fps_low_light", False))
        self.auto_exp_chk = tk.Checkbutton(
            self.cam_ctrl_frame, text="저조도 FPS 드롭 방지 (수동 노출 고정)", 
            variable=self.auto_exposure_var, command=self.on_auto_exposure_toggle,
            bg=self.card_color, fg=self.text_color, selectcolor="#1E293B",
            activebackground=self.card_color, activeforeground=self.text_color,
            font=("Segoe UI", 9), bd=0, highlightthickness=0
        )
        self.auto_exp_chk.pack(anchor="w", pady=(0, 8))
        
        # 2. 카메라 설정 다이얼로그 호출 버튼
        self.cam_settings_btn = tk.Button(
            self.cam_ctrl_frame, text="📷 카메라 고급 설정 창 열기", font=("Segoe UI", 9, "bold"),
            bg="#1E293B", fg=self.text_color, activebackground="#334155", activeforeground=self.text_color,
            bd=0, padx=10, pady=6, relief="flat", cursor="hand2", command=self.open_camera_settings
        )
        self.cam_settings_btn.pack(fill="x")

        # 활성화 토글 수동 버튼 (동적 단축키 명칭 적용)
        self.toggle_btn = tk.Button(
            self.ctrl_frame, text=f"추적 시작 / 중지 ({self.config['tracking_toggle_key'].upper()})", font=("Inter", 11, "bold"),
            bg="#3B82F6", fg="#FFFFFF", activebackground="#2563EB", activeforeground="#FFFFFF",
            bd=0, padx=10, pady=10, relief="flat", cursor="hand2", command=self.manual_toggle
        )
        self.toggle_btn.pack(fill="x", padx=20, pady=(10, 15))

        # 단축키 설정 영역 프레임
        self.hotkey_frame = tk.Frame(self.ctrl_frame, bg=self.card_color)
        self.hotkey_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        self.hotkey_lbl = tk.Label(
            self.hotkey_frame, 
            text=f"토글 단축키: {self.config['tracking_toggle_key'].upper()}", 
            font=("Inter", 10), fg=self.text_color, bg=self.card_color
        )
        self.hotkey_lbl.pack(side="left", anchor="w")
        
        self.hotkey_btn = tk.Button(
            self.hotkey_frame, text="단축키 변경", font=("Segoe UI", 9, "bold"),
            bg="#334155", fg=self.text_color, activebackground="#475569", activeforeground=self.text_color,
            bd=0, padx=10, pady=4, relief="flat", cursor="hand2", command=self.start_hotkey_recording
        )
        self.hotkey_btn.pack(side="right")
        
        self.recording_hotkey = False

        # 도움말 영역
        help_frame = tk.Frame(self.ctrl_frame, bg="#0F172A", bd=0, highlightthickness=1, highlightbackground="#334155")
        help_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        help_text = (
            "💡 조작 안내\n"
            f"• [{self.config['tracking_toggle_key'].upper()}] 키를 누르면 즉시 머리 추적 제어가 시작/중지됩니다.\n"
            "• 코 끝을 기준으로 마우스 좌표가 제어됩니다.\n"
            "• 움직임이 끊기면 스무딩 값을 낮추어 반응성을 높이세요.\n"
            "• 마우스가 떨리면 스무딩 값을 높이거나 감도를 조절해 보세요."
        )
        self.help_lbl = tk.Label(help_frame, text=help_text, justify="left", font=("Segoe UI", 9), fg=self.muted_color, bg="#0F172A", anchor="nw", padx=10, pady=10)
        self.help_lbl.pack(fill="both", expand=True)

    def update_frame(self, cv_frame, tracking_enabled, nose_x, nose_y, fps, w, h):
        """
        카메라 스레드로부터 실시간 프레임을 전달받아 GUI에 렌더링합니다.
        """
        # FPS & 해상도 정보 라벨 갱신
        self.info_label.configure(text=f"FPS: {fps} | {w}x{h}")

        # 640 가로 길이를 고정한 채, 종횡비(w, h)에 맞게 세로 길이를 계산하여 늘림 방지
        display_w = 640
        display_h = int(640 * (h / w)) if w > 0 else 360
        
        # 캔버스 크기 동적 조절
        if int(self.canvas.cget("width")) != display_w or int(self.canvas.cget("height")) != display_h:
            self.canvas.configure(width=display_w, height=display_h)

        cv_frame = cv2.resize(cv_frame, (display_w, display_h))
        rgb_image = cv2.cvtColor(cv_frame, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb_image)
        
        # Tkinter PhotoImage 객체 생성
        self.photo = ImageTk.PhotoImage(image=pil_img)
        
        # 캔버스에 이미지 업데이트
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.photo)
        
        # 트래킹 상태에 따라 카드 테두리 및 텍스트 상태 변경 (동적 단축키 반영)
        hotkey = self.config['tracking_toggle_key'].upper()
        if tracking_enabled:
            self.cam_frame.configure(highlightbackground=self.accent_color)
            self.status_label.configure(text="추적 활성화 중...", fg=self.accent_color)
            self.toggle_btn.configure(bg=self.inactive_color, text=f"추적 일시정지 ({hotkey})")
        else:
            self.cam_frame.configure(highlightbackground="#334155")
            self.status_label.configure(text=f"비활성 상태 ({hotkey}키로 활성화)", fg=self.inactive_color)
            self.toggle_btn.configure(bg=self.accent_color, text=f"추적 시작 ({hotkey})")

    def manual_toggle(self):
        """
        UI 토글 버튼 누를 시 트래커 상태 반전
        """
        new_state = not self.tracker.tracking_enabled
        self.tracker.set_tracking(new_state)

    def on_sens_x_change(self, val):
        sens = float(val)
        self.config["sensitivity_x"] = sens
        self.sens_x_label.configure(text=f"X축 민감도: {sens:.2f}")
        config.save_config(self.config)

    def on_sens_y_change(self, val):
        sens = float(val)
        self.config["sensitivity_y"] = sens
        self.sens_y_label.configure(text=f"Y축 민감도: {sens:.2f}")
        config.save_config(self.config)

    def on_accel_change(self, val):
        accel = float(val)
        self.config["acceleration"] = accel
        self.accel_label.configure(text=f"모션 가속도: {accel:.2f}")
        config.save_config(self.config)

    def on_thresh_change(self, val):
        thresh = float(val)
        self.config["motion_threshold"] = thresh
        self.thresh_label.configure(text=f"움직임 임계값: {thresh:.2f}")
        self.tracker.update_deadzone(thresh)
        config.save_config(self.config)

    def on_smooth_change(self, val):
        smooth = float(val)
        self.config["smoothing"] = smooth
        self.smooth_label.configure(text=f"모션 스무딩(부드러움): {smooth:.2f}")
        self.tracker.update_filter_alpha(smooth)
        config.save_config(self.config)

    def start_hotkey_recording(self):
        """
        단축키 변경 레코딩 모드 진입
        """
        self.recording_hotkey = True
        self.hotkey_btn.configure(text="키를 누르세요...", bg=self.inactive_color)
        self.root.bind("<Key>", self.record_hotkey)
        self.hotkey_btn.focus_set()

    def record_hotkey(self, event):
        """
        눌린 키를 캡처하여 새로운 핫키로 할당
        """
        if not self.recording_hotkey:
            return
            
        keysym = event.keysym.lower()
        
        # Tkinter -> pynput 키 문자 매핑 테이블 (특수키 매칭)
        KEYSYM_MAP = {
            "f1": "f1", "f2": "f2", "f3": "f3", "f4": "f4", "f5": "f5",
            "f6": "f6", "f7": "f7", "f8": "f8", "f9": "f9", "f10": "f10",
            "f11": "f11", "f12": "f12",
            "insert": "insert", "delete": "delete",
            "home": "home", "end": "end",
            "prior": "page_up", "next": "page_down",
            "space": "space", "escape": "esc",
            "plus": "+", "kp_add": "+",
            "minus": "-", "kp_subtract": "-",
            "asterisk": "*", "kp_multiply": "*",
            "slash": "/", "kp_divide": "/",
            "return": "enter", "tab": "tab",
            "backspace": "backspace"
        }
        
        final_key = KEYSYM_MAP.get(keysym, keysym)
        
        # 설정 업데이트 및 세이브
        self.config["tracking_toggle_key"] = final_key
        config.save_config(self.config)
        
        # UI 라벨 및 도움말 동적 갱신
        self.hotkey_lbl.configure(text=f"토글 단축키: {final_key.upper()}")
        self.status_label.configure(text=f"비활성 상태 ({final_key.upper()}키로 활성화)")
        self.toggle_btn.configure(text=f"추적 시작 / 중지 ({final_key.upper()})")
        self.update_help_text(final_key)
        
        # 레코딩 모드 정상 해제
        self.recording_hotkey = False
        self.hotkey_btn.configure(text="단축키 변경", bg="#334155")
        self.root.unbind("<Key>")

    def update_help_text(self, hotkey):
        """
        도움말 텍스트의 단축키 설명을 동적으로 갱신
        """
        help_text = (
            "💡 조작 안내\n"
            f"• [{hotkey.upper()}] 키를 누르면 즉시 머리 추적 제어가 시작/중지됩니다.\n"
            "• 코 끝을 기준으로 마우스 좌표가 제어됩니다.\n"
            "• 움직임이 끊기면 스무딩 값을 낮추어 반응성을 높이세요.\n"
            "• 마우스가 떨리면 스무딩 값을 높이거나 감도를 조절해 보세요."
        )
        self.help_lbl.configure(text=help_text)

    def on_auto_exposure_toggle(self):
        val = self.auto_exposure_var.get()
        self.config["lock_fps_low_light"] = val
        config.save_config(self.config)
        self.tracker.set_auto_exposure(not val)

    def open_camera_settings(self):
        self.tracker.open_camera_settings()

    def on_close(self):
        self.tracker.stop_tracker()
        self.root.destroy()
