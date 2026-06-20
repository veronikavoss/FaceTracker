import tkinter as tk
from tkinter import ttk
import cv2
from PIL import Image, ImageTk
import config
from tracker import WINRT_AVAILABLE

class PyViacamGUI:
    def __init__(self, root, app_config, tracker):
        self.root = root
        self.config = app_config
        self.tracker = tracker
        
        # 윈도우 타이틀 및 크기 설정
        self.root.title("PyViacam Lite - Head Tracking Mouse")
        self.root.geometry("1000x600")
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
        self.image_id = None
        self.update_pending = False

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
        
        # 감도(Sensitivity X/Y) 조절 영역 (가로 병렬 배치)
        self.sens_frame = tk.Frame(self.ctrl_frame, bg=self.card_color)
        self.sens_frame.pack(fill="x", padx=20, pady=(5, 10))
        self.sens_frame.columnconfigure(0, weight=1)
        self.sens_frame.columnconfigure(1, weight=1)
        
        # X축 민감도
        self.sens_x_container = tk.Frame(self.sens_frame, bg=self.card_color)
        self.sens_x_container.grid(row=0, column=0, padx=(0, 10), sticky="ew")
        self.sens_x_label = tk.Label(self.sens_x_container, text=f"민감도 X: {int(self.config['sensitivity_x'])}", font=("Inter", 9), fg=self.text_color, bg=self.card_color)
        self.sens_x_label.pack(anchor="w")
        self.sens_x_scale = tk.Scale(
            self.sens_x_container, from_=0, to=20, resolution=1, orient="horizontal",
            bg=self.card_color, fg=self.text_color, troughcolor="#0F172A", activebackground=self.accent_color,
            highlightthickness=0, bd=0, showvalue=False, command=self.on_sens_x_change
        )
        self.sens_x_scale.set(self.config["sensitivity_x"])
        self.sens_x_scale.pack(fill="x", pady=(2, 0))
        
        # Y축 민감도
        self.sens_y_container = tk.Frame(self.sens_frame, bg=self.card_color)
        self.sens_y_container.grid(row=0, column=1, padx=(10, 0), sticky="ew")
        self.sens_y_label = tk.Label(self.sens_y_container, text=f"민감도 Y: {int(self.config['sensitivity_y'])}", font=("Inter", 9), fg=self.text_color, bg=self.card_color)
        self.sens_y_label.pack(anchor="w")
        self.sens_y_scale = tk.Scale(
            self.sens_y_container, from_=0, to=20, resolution=1, orient="horizontal",
            bg=self.card_color, fg=self.text_color, troughcolor="#0F172A", activebackground=self.accent_color,
            highlightthickness=0, bd=0, showvalue=False, command=self.on_sens_y_change
        )
        self.sens_y_scale.set(self.config["sensitivity_y"])
        self.sens_y_scale.pack(fill="x", pady=(2, 0))
        
        # 필터 (임계값/스무딩) 조절 영역 (가로 병렬 배치)
        self.filter_frame = tk.Frame(self.ctrl_frame, bg=self.card_color)
        self.filter_frame.pack(fill="x", padx=20, pady=(0, 10))
        self.filter_frame.columnconfigure(0, weight=1)
        self.filter_frame.columnconfigure(1, weight=1)
        
        # 움직임 임계값
        self.thresh_container = tk.Frame(self.filter_frame, bg=self.card_color)
        self.thresh_container.grid(row=0, column=0, padx=(0, 10), sticky="ew")
        self.thresh_label = tk.Label(self.thresh_container, text=f"임계값: {int(self.config['motion_threshold'])}", font=("Inter", 9), fg=self.text_color, bg=self.card_color)
        self.thresh_label.pack(anchor="w")
        self.thresh_scale = tk.Scale(
            self.thresh_container, from_=0, to=10, resolution=1, orient="horizontal",
            bg=self.card_color, fg=self.text_color, troughcolor="#0F172A", activebackground=self.accent_color,
            highlightthickness=0, bd=0, showvalue=False, command=self.on_thresh_change
        )
        self.thresh_scale.set(self.config["motion_threshold"])
        self.thresh_scale.pack(fill="x", pady=(2, 0))
        
        # 모션 스무딩(부드러움)
        self.smooth_container = tk.Frame(self.filter_frame, bg=self.card_color)
        self.smooth_container.grid(row=0, column=1, padx=(10, 0), sticky="ew")
        self.smooth_label = tk.Label(self.smooth_container, text=f"스무딩: {int(self.config['smoothing'])}", font=("Inter", 9), fg=self.text_color, bg=self.card_color)
        self.smooth_label.pack(anchor="w")
        self.smooth_scale = tk.Scale(
            self.smooth_container, from_=0, to=8, resolution=1, orient="horizontal",
            bg=self.card_color, fg=self.text_color, troughcolor="#0F172A", activebackground=self.accent_color,
            highlightthickness=0, bd=0, showvalue=False, command=self.on_smooth_change
        )
        self.smooth_scale.set(self.config["smoothing"])
        self.smooth_scale.pack(fill="x", pady=(2, 0))
        
        # 가속도 및 내부 배율 변경 영역 (가로 병렬 배치)
        self.extra_frame = tk.Frame(self.ctrl_frame, bg=self.card_color)
        self.extra_frame.pack(fill="x", padx=20, pady=(0, 15))
        self.extra_frame.columnconfigure(0, weight=1)
        self.extra_frame.columnconfigure(1, weight=1)
        
        # 모션 가속도
        self.accel_container = tk.Frame(self.extra_frame, bg=self.card_color)
        self.accel_container.grid(row=0, column=0, padx=(0, 10), sticky="ew")
        self.accel_label = tk.Label(self.accel_container, text=f"가속도: {int(self.config['acceleration'])}", font=("Inter", 9), fg=self.text_color, bg=self.card_color)
        self.accel_label.pack(anchor="w")
        self.accel_scale = tk.Scale(
            self.accel_container, from_=0, to=5, resolution=1, orient="horizontal",
            bg=self.card_color, fg=self.text_color, troughcolor="#0F172A", activebackground=self.accent_color,
            highlightthickness=0, bd=0, showvalue=False, command=self.on_accel_change
        )
        self.accel_scale.set(self.config["acceleration"])
        self.accel_scale.pack(fill="x", pady=(2, 0))
        
        # 내부 배율
        self.mult_container = tk.Frame(self.extra_frame, bg=self.card_color)
        self.mult_container.grid(row=0, column=1, padx=(10, 0), sticky="ew")
        self.mult_label = tk.Label(self.mult_container, text=f"내부 배율: {self.config.get('internal_multiplier', 40.0):.1f}", font=("Inter", 9), fg=self.text_color, bg=self.card_color)
        self.mult_label.pack(anchor="w")
        self.mult_scale = tk.Scale(
            self.mult_container, from_=0.0, to=80.0, resolution=1.0, orient="horizontal",
            bg=self.card_color, fg=self.text_color, troughcolor="#0F172A", activebackground=self.accent_color,
            highlightthickness=0, bd=0, showvalue=False, command=self.on_mult_change
        )
        self.mult_scale.set(self.config.get("internal_multiplier", 40.0))
        self.mult_scale.pack(fill="x", pady=(2, 0))
        
        # 단축키 설정 영역 프레임 (전체 너비 배치)
        self.hotkey_frame = tk.Frame(self.ctrl_frame, bg=self.card_color)
        self.hotkey_frame.pack(fill="x", padx=20, pady=(0, 15))
        
        self.hotkey_lbl = tk.Label(self.hotkey_frame, text=f"단축키: {self.config['tracking_toggle_key'].upper()}", font=("Inter", 9), fg=self.text_color, bg=self.card_color)
        self.hotkey_lbl.pack(side="left", anchor="w")
        
        self.hotkey_btn = tk.Button(
            self.hotkey_frame, text="단축키 변경", font=("Segoe UI", 9, "bold"),
            bg="#334155", fg=self.text_color, activebackground="#475569", activeforeground=self.text_color,
            bd=0, padx=10, pady=4, relief="flat", cursor="hand2", command=self.start_hotkey_recording
        )
        self.hotkey_btn.pack(side="right")

        # 카메라 상세 제어 프레임 (카메라 설정 & 자동 노출 토글)
        self.cam_ctrl_frame = tk.Frame(self.ctrl_frame, bg=self.card_color)
        self.cam_ctrl_frame.pack(fill="x", padx=20, pady=(0, 15))
        
        # 0. 카메라 선택 드롭다운 프레임
        self.cam_select_frame = tk.Frame(self.cam_ctrl_frame, bg=self.card_color)
        self.cam_select_frame.pack(fill="x", pady=(0, 10))
        
        self.cam_select_label = tk.Label(
            self.cam_select_frame, text="카메라 선택:", font=("Segoe UI", 9, "bold"),
            fg=self.text_color, bg=self.card_color
        )
        self.cam_select_label.pack(side="left", padx=(0, 5))
        
        # 카메라 장치 스캔
        self.camera_list = self.scan_cameras()
        combo_values = [f"카메라 {idx}" for idx in self.camera_list]
        
        # 드롭다운 생성
        self.cam_combo = ttk.Combobox(
            self.cam_select_frame, values=combo_values, state="readonly", width=12
        )
        
        # 스타일 적용 (미드나이트 다크 느낌의 콤보박스 디자인)
        style = ttk.Style()
        style.theme_use('clam')
        style.configure(
            "TCombobox", 
            fieldbackground="#1E293B", 
            background="#334155", 
            foreground="#F8FAFC", 
            arrowcolor="#F8FAFC",
            bordercolor="#334155"
        )
        style.map(
            "TCombobox", 
            fieldbackground=[('readonly', '#1E293B')],
            foreground=[('readonly', '#F8FAFC')]
        )
        
        # 현재 선택된 카메라로 초기값 설정
        current_id = self.config.get("camera_id", 0)
        try:
            current_index = self.camera_list.index(current_id)
            self.cam_combo.current(current_index)
        except ValueError:
            self.cam_combo.set(f"카메라 {current_id}")
            
        self.cam_combo.pack(side="left", fill="x", expand=True)
        self.cam_combo.bind("<<ComboboxSelected>>", self.on_camera_select)
        
        # 0-1. 해상도 및 FPS 선택 프레임
        self.res_fps_frame = tk.Frame(self.cam_ctrl_frame, bg=self.card_color)
        self.res_fps_frame.pack(fill="x", pady=(0, 10))
        
        # 해상도 선택
        self.res_label = tk.Label(self.res_fps_frame, text="해상도:", font=("Segoe UI", 9, "bold"), fg=self.text_color, bg=self.card_color)
        self.res_label.pack(side="left", padx=(0, 5))
        
        res_options = ["320x240", "640x360", "640x480", "1280x720", "1920x1080"]
        self.res_combo = ttk.Combobox(self.res_fps_frame, values=res_options, state="readonly", width=10)
        current_res = f"{self.config.get('camera_width', 640)}x{self.config.get('camera_height', 480)}"
        if current_res not in res_options:
            res_options.append(current_res)
            self.res_combo['values'] = res_options
        self.res_combo.set(current_res)
        self.res_combo.pack(side="left", padx=(0, 15))
        self.res_combo.bind("<<ComboboxSelected>>", self.on_res_fps_select)
        
        # FPS 선택
        self.fps_label = tk.Label(self.res_fps_frame, text="FPS:", font=("Segoe UI", 9, "bold"), fg=self.text_color, bg=self.card_color)
        self.fps_label.pack(side="left", padx=(0, 5))
        
        fps_options = ["30", "60", "90", "120"]
        self.fps_combo = ttk.Combobox(self.res_fps_frame, values=fps_options, state="readonly", width=5)
        current_fps = str(self.config.get("target_fps", 30))
        if current_fps not in fps_options:
            fps_options.append(current_fps)
            self.fps_combo['values'] = fps_options
        self.fps_combo.set(current_fps)
        self.fps_combo.pack(side="left", expand=True)
        self.fps_combo.bind("<<ComboboxSelected>>", self.on_res_fps_select)
        
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
        
        # 1-2. 적외선(IR) 카메라 모드 토글 체크박스
        self.ir_mode_var = tk.BooleanVar(value=self.config.get("use_ir_camera", False))
        ir_state = tk.NORMAL if WINRT_AVAILABLE else tk.DISABLED
        ir_text = "Logitech Brio 적외선(IR) 모드 활성화" if WINRT_AVAILABLE else "Logitech Brio 적외선(IR) 모드 (Windows/WinRT 전용)"
        self.ir_mode_chk = tk.Checkbutton(
            self.cam_ctrl_frame, text=ir_text, 
            variable=self.ir_mode_var, command=self.on_ir_mode_toggle,
            state=ir_state,
            bg=self.card_color, fg=self.text_color if WINRT_AVAILABLE else self.muted_color, selectcolor="#1E293B",
            activebackground=self.card_color, activeforeground=self.text_color,
            font=("Segoe UI", 9), bd=0, highlightthickness=0
        )
        self.ir_mode_chk.pack(anchor="w", pady=(0, 8))
        
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
        self.update_pending = False
        # FPS & 해상도 정보 라벨 갱신
        self.info_label.configure(text=f"FPS: {fps} | {w}x{h}")

        # 640 가로 길이를 고정한 채, 종횡비(w, h)에 맞게 세로 길이를 계산하여 늘림 방지
        display_w = 640
        display_h = int(640 * (h / w)) if w > 0 else 360
        
        # 캔버스 크기 동적 조절
        if int(self.canvas.cget("width")) != display_w or int(self.canvas.cget("height")) != display_h:
            self.canvas.configure(width=display_w, height=display_h)
            self.image_id = None
            self.canvas.delete("all")

        cv_frame = cv2.resize(cv_frame, (display_w, display_h))
        rgb_image = cv2.cvtColor(cv_frame, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb_image)
        
        # Tkinter PhotoImage 메모리 누수(TclError 및 MemoryError) 완벽 방지
        new_photo = ImageTk.PhotoImage(image=pil_img)
        
        # 캔버스에 이미지 업데이트 (delete("all") 대신 itemconfig를 사용하여 깜빡임 방지)
        if self.image_id is None:
            self.canvas.delete("all")  # 대기 상태 텍스트 등을 지우기 위한 초기화
            self.image_id = self.canvas.create_image(0, 0, anchor="nw", image=new_photo)
        else:
            self.canvas.itemconfig(self.image_id, image=new_photo)
            
        # 기존 객체를 명시적으로 해제 (Tcl 가비지 컬렉터 한계 극복)
        old_photo = getattr(self, "photo", None)
        self.photo = new_photo
        if old_photo is not None:
            try:
                # Tcl 엔진 내부의 이미지 버퍼를 즉각 삭제하여 메모리 누수 원천 차단
                self.canvas.tk.call("image", "delete", old_photo.name)
            except Exception:
                pass
            del old_photo
        
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
        sens = int(float(val))
        self.config["sensitivity_x"] = sens
        self.sens_x_label.configure(text=f"민감도 X: {sens}")
        config.save_config(self.config)

    def on_sens_y_change(self, val):
        sens = int(float(val))
        self.config["sensitivity_y"] = sens
        self.sens_y_label.configure(text=f"민감도 Y: {sens}")
        config.save_config(self.config)

    def on_accel_change(self, val):
        accel = int(float(val))
        self.config["acceleration"] = accel
        self.accel_label.configure(text=f"가속도: {accel}")
        config.save_config(self.config)

    def on_thresh_change(self, val):
        thresh = int(float(val))
        self.config["motion_threshold"] = thresh
        self.thresh_label.configure(text=f"임계값: {thresh}")
        config.save_config(self.config)

    def on_smooth_change(self, val):
        smooth = int(float(val))
        self.config["smoothing"] = smooth
        self.smooth_label.configure(text=f"스무딩: {smooth}")
        config.save_config(self.config)

    def on_mult_change(self, val):
        mult = float(val)
        self.config["internal_multiplier"] = mult
        self.mult_label.configure(text=f"내부 배율: {mult:.1f}")
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
        self.hotkey_lbl.configure(text=f"단축키: {final_key.upper()}")
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

    def on_ir_mode_toggle(self):
        val = self.ir_mode_var.get()
        self.config["use_ir_camera"] = val
        config.save_config(self.config)
        print(f"[GUI] 적외선(IR) 모드 설정이 변경되었습니다: {val}")

    def open_camera_settings(self):
        self.tracker.open_camera_settings()

    def scan_cameras(self):
        """
        사용 가능한 카메라 장치 목록을 스캔하여 인덱스 목록을 반환합니다.
        """
        current_id = self.config.get("camera_id", 0)
        available = [current_id]
        
        # 설정 파일로부터 카메라 백엔드 로드 (DSHOW, MSMF, AUTO)
        backend_str = self.config.get("camera_backend", "DSHOW").upper()
        if backend_str == "MSMF":
            backend = cv2.CAP_MSMF
        elif backend_str == "AUTO":
            backend = cv2.CAP_ANY
        else:
            backend = cv2.CAP_DSHOW
            
        for i in range(5):
            if i == current_id:
                continue
            cap = cv2.VideoCapture(i, backend)
            if cap.isOpened():
                available.append(i)
                cap.release()
                
        return sorted(list(set(available)))

    def on_camera_select(self, event):
        selected_str = self.cam_combo.get()
        try:
            selected_idx = int(selected_str.split(" ")[1])
            if self.config["camera_id"] != selected_idx:
                self.config["camera_id"] = selected_idx
                config.save_config(self.config)
                print(f"[GUI] 카메라가 인덱스 {selected_idx}로 변경되었습니다.")
                import tkinter.messagebox as messagebox
                messagebox.showinfo("설정 변경됨", "카메라 변경이 저장되었습니다.\n프로그램을 재시작해야 적용됩니다.")
        except Exception as e:
            print(f"카메라 선택 이벤트 처리 중 오류: {e}")

    def on_res_fps_select(self, event=None):
        res_str = self.res_combo.get()
        fps_str = self.fps_combo.get()
        changed = False
        
        try:
            w_str, h_str = res_str.split("x")
            w, h = int(w_str), int(h_str)
            if self.config.get("camera_width") != w or self.config.get("camera_height") != h:
                self.config["camera_width"] = w
                self.config["camera_height"] = h
                changed = True
        except Exception:
            pass
            
        try:
            fps = int(fps_str)
            if self.config.get("target_fps") != fps:
                self.config["target_fps"] = fps
                changed = True
        except Exception:
            pass
            
        if changed:
            config.save_config(self.config)
            print(f"[GUI] 해상도 {res_str}, FPS {fps_str} 로 변경되었습니다.")
            import tkinter.messagebox as messagebox
            messagebox.showinfo("설정 변경됨", "해상도 및 FPS 설정이 저장되었습니다.\n프로그램을 재시작해야 새 설정으로 카메라가 초기화됩니다.")

    def on_close(self):
        self.tracker.stop_tracker()
        self.root.destroy()
