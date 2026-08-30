import tkinter as tk
from tkinter import ttk
import cv2
from PIL import Image, ImageTk
import config

class FaceTrackerGUI:
    def __init__(self, root, app_config, tracker, frame_queue):
        self.root = root
        self.config = app_config
        self.tracker = tracker
        self.frame_queue = frame_queue
        
        # 윈도우 타이틀 및 크기 설정 (설정 패널 확장에 맞춘 높이 660px)
        self.root.title("Face Tracker")
        self.root.geometry("1020x660")
        self.root.resizable(False, False)
        
        # 스타일 테마 정의 (Modern Premium Dark Mode)
        self.bg_color = "#0F172A"       # 미드나이트 다크 블루
        self.card_color = "#1E293B"     # 다크 슬레이트 카드 배경
        self.text_color = "#F8FAFC"     # 부드러운 화이트 텍스트
        self.accent_color = "#3B82F6"   # 네온 아쿠아 블루 (활성화)
        self.mp_accent_color = "#06B6D4"# 시안 (MediaPipe 테마)
        self.inactive_color = "#EF4444" # 부드러운 레드 (비활성화)
        self.muted_color = "#94A3B8"    # 뮤트 그레이 텍스트
        
        self.root.configure(bg=self.bg_color)
        
        # 스타일러 구성
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure(".", background=self.bg_color, foreground=self.text_color)
        self.style.configure(
            "TCombobox", 
            fieldbackground="#1E293B", 
            background="#334155", 
            foreground="#F8FAFC", 
            arrowcolor="#F8FAFC",
            bordercolor="#334155"
        )
        self.style.map(
            "TCombobox", 
            fieldbackground=[('readonly', '#1E293B')],
            foreground=[('readonly', '#F8FAFC')]
        )
        
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
        
        # 비디오 표시 캔버스
        self.canvas = tk.Canvas(self.cam_frame, width=640, height=360, bg="#020617", bd=0, highlightthickness=0)
        self.canvas.pack(padx=15, pady=5, fill="both", expand=True)
        
        # 초기 카메라 대기 상태 텍스트
        self.canvas.create_text(320, 180, text="카메라 연결 대기 중...", fill=self.muted_color, font=("Segoe UI", 12))

    def _init_control_panel(self):
        # 우측 컨트롤 프레임
        self.ctrl_frame = tk.Frame(self.root, bg=self.card_color, bd=0, highlightthickness=2, highlightbackground="#334155")
        self.ctrl_frame.grid(row=0, column=1, padx=(0, 20), pady=20, sticky="nsew")
        
        # 프로그램 이름 및 상태 헤더
        header_label = tk.Label(self.ctrl_frame, text="Face Tracker", font=("Outfit", 18, "bold"), fg=self.text_color, bg=self.card_color)
        header_label.pack(anchor="w", padx=20, pady=(15, 2))
        
        self.status_label = tk.Label(self.ctrl_frame, text="비활성 상태 (F12키로 활성화)", font=("Inter", 9, "bold"), fg=self.inactive_color, bg=self.card_color)
        self.status_label.pack(anchor="w", padx=20, pady=(0, 8))
        
        # 트래킹 엔진 선택 프레임
        self.engine_frame = tk.Frame(self.ctrl_frame, bg=self.card_color)
        self.engine_frame.pack(fill="x", padx=20, pady=(0, 10))
        
        self.engine_label = tk.Label(
            self.engine_frame, text="트래킹 엔진:", font=("Segoe UI", 9, "bold"),
            fg=self.accent_color, bg=self.card_color
        )
        self.engine_label.pack(side="left", padx=(0, 8))
        
        engine_options = ["MediaPipe (정밀 3D)", "YuNet (초경량 AI)"]
        self.engine_combo = ttk.Combobox(
            self.engine_frame, values=engine_options, state="readonly", width=18
        )
        
        curr_engine = self.config.get("tracking_engine", "mediapipe").lower()
        if curr_engine == "yunet":
            self.engine_combo.current(1)
        else:
            self.engine_combo.current(0)
            
        self.engine_combo.pack(side="left", fill="x", expand=True)
        self.engine_combo.bind("<<ComboboxSelected>>", self.on_engine_select)
        
        # 구분선
        self.sep1 = tk.Frame(self.ctrl_frame, height=1, bg="#334155")
        self.sep1.pack(fill="x", padx=20, pady=(0, 10))
        
        # ========================================================
        # [패널 1] MediaPipe 전용 5단계 파이프라인 패널
        # ========================================================
        self.mp_panel = tk.Frame(self.ctrl_frame, bg=self.card_color)
        self._build_mediapipe_panel()
        
        # ========================================================
        # [패널 2] YuNet 전용 파이프라인 패널
        # ========================================================
        self.yn_panel = tk.Frame(self.ctrl_frame, bg=self.card_color)
        self._build_yunet_panel()
        
        # 현재 선택된 엔진 패널 표시
        self._switch_panel(curr_engine)
        
        # 구분선 2
        self.sep2 = tk.Frame(self.ctrl_frame, height=1, bg="#334155")
        self.sep2.pack(fill="x", padx=20, pady=(5, 10))

        # 공통 시스템 컨트롤 (단축키, 카메라 선택, 해상도, FPS, 노출)
        self._build_common_controls()

    def _build_mediapipe_panel(self):
        """MediaPipe Head Pose (머리 자세 5단계) 전용 컨트롤 패널 구축"""
        mp_cfg = self.config.get("mediapipe", {})
        
        # 1. 민감도 X / Y (2열 가로 배치)
        sens_f = tk.Frame(self.mp_panel, bg=self.card_color)
        sens_f.pack(fill="x", pady=(0, 4))
        sens_f.columnconfigure(0, weight=1)
        sens_f.columnconfigure(1, weight=1)
        
        # X 민감도
        c_x = tk.Frame(sens_f, bg=self.card_color)
        c_x.grid(row=0, column=0, padx=(0, 5), sticky="ew")
        init_x = int(mp_cfg.get("sensitivity_x", 25))
        self.mp_sx_lbl = tk.Label(c_x, text=f"민감도 X (Yaw): {init_x}", font=("Inter", 8, "bold"), fg=self.text_color, bg=self.card_color)
        self.mp_sx_lbl.pack(anchor="w")
        self.mp_sx_scale = tk.Scale(
            c_x, from_=0, to=50, resolution=1, orient="horizontal",
            bg=self.card_color, fg=self.text_color, troughcolor="#0F172A", activebackground=self.mp_accent_color,
            highlightthickness=0, bd=0, showvalue=False, command=self.on_mp_sx_change
        )
        self.mp_sx_scale.set(init_x)
        self.mp_sx_scale.pack(fill="x", pady=(1, 0))
        
        # Y 민감도
        c_y = tk.Frame(sens_f, bg=self.card_color)
        c_y.grid(row=0, column=1, padx=(5, 0), sticky="ew")
        init_y = int(mp_cfg.get("sensitivity_y", 25))
        self.mp_sy_lbl = tk.Label(c_y, text=f"민감도 Y (Pitch): {init_y}", font=("Inter", 8, "bold"), fg=self.text_color, bg=self.card_color)
        self.mp_sy_lbl.pack(anchor="w")
        self.mp_sy_scale = tk.Scale(
            c_y, from_=0, to=50, resolution=1, orient="horizontal",
            bg=self.card_color, fg=self.text_color, troughcolor="#0F172A", activebackground=self.mp_accent_color,
            highlightthickness=0, bd=0, showvalue=False, command=self.on_mp_sy_change
        )
        self.mp_sy_scale.set(init_y)
        self.mp_sy_scale.pack(fill="x", pady=(1, 0))
        
        # 2열 그리드: (1. 2D 칼만 필터, 2. 속도 적응 스무딩)
        row1_f = tk.Frame(self.mp_panel, bg=self.card_color)
        row1_f.pack(fill="x", pady=(0, 4))
        row1_f.columnconfigure(0, weight=1)
        row1_f.columnconfigure(1, weight=1)
        
        # 1. 2D 칼만 필터 (0 ~ 10)
        c_k = tk.Frame(row1_f, bg=self.card_color)
        c_k.grid(row=0, column=0, padx=(0, 5), sticky="ew")
        init_k = int(mp_cfg.get("kalman_strength", 5))
        self.mp_k_lbl = tk.Label(c_k, text=f"1. 칼만 필터: {init_k}", font=("Inter", 8), fg=self.text_color, bg=self.card_color)
        self.mp_k_lbl.pack(anchor="w")
        self.mp_k_scale = tk.Scale(
            c_k, from_=0, to=10, resolution=1, orient="horizontal",
            bg=self.card_color, fg=self.text_color, troughcolor="#0F172A", activebackground=self.mp_accent_color,
            highlightthickness=0, bd=0, showvalue=False, command=self.on_mp_k_change
        )
        self.mp_k_scale.set(init_k)
        self.mp_k_scale.pack(fill="x", pady=(1, 0))
        
        # 2. 속도 적응 스무딩 (0 ~ 10)
        c_as = tk.Frame(row1_f, bg=self.card_color)
        c_as.grid(row=0, column=1, padx=(5, 0), sticky="ew")
        init_as = int(mp_cfg.get("adaptive_smoothing", 5))
        self.mp_as_lbl = tk.Label(c_as, text=f"2. 적응 스무딩: {init_as}", font=("Inter", 8), fg=self.text_color, bg=self.card_color)
        self.mp_as_lbl.pack(anchor="w")
        self.mp_as_scale = tk.Scale(
            c_as, from_=0, to=10, resolution=1, orient="horizontal",
            bg=self.card_color, fg=self.text_color, troughcolor="#0F172A", activebackground=self.mp_accent_color,
            highlightthickness=0, bd=0, showvalue=False, command=self.on_mp_as_change
        )
        self.mp_as_scale.set(init_as)
        self.mp_as_scale.pack(fill="x", pady=(1, 0))
        
        # 2열 그리드: (3. 각도 데드존, 4. 비선형 커브 지수)
        row2_f = tk.Frame(self.mp_panel, bg=self.card_color)
        row2_f.pack(fill="x", pady=(0, 4))
        row2_f.columnconfigure(0, weight=1)
        row2_f.columnconfigure(1, weight=1)
        
        # 3. 각도 데드존 (0.00 ~ 0.50도)
        c_dz = tk.Frame(row2_f, bg=self.card_color)
        c_dz.grid(row=0, column=0, padx=(0, 5), sticky="ew")
        init_dz = float(mp_cfg.get("deadzone", 0.08))
        self.mp_dz_lbl = tk.Label(c_dz, text=f"3. 각도 데드존: {init_dz}°", font=("Inter", 8), fg=self.text_color, bg=self.card_color)
        self.mp_dz_lbl.pack(anchor="w")
        self.mp_dz_scale = tk.Scale(
            c_dz, from_=0.00, to=0.50, resolution=0.01, orient="horizontal",
            bg=self.card_color, fg=self.text_color, troughcolor="#0F172A", activebackground=self.mp_accent_color,
            highlightthickness=0, bd=0, showvalue=False, command=self.on_mp_dz_change
        )
        self.mp_dz_scale.set(init_dz)
        self.mp_dz_scale.pack(fill="x", pady=(1, 0))
        
        # 4. 비선형 커브 지수 (1.0 ~ 1.8)
        c_cp = tk.Frame(row2_f, bg=self.card_color)
        c_cp.grid(row=0, column=1, padx=(5, 0), sticky="ew")
        init_cp = float(mp_cfg.get("curve_power", 1.35))
        self.mp_cp_lbl = tk.Label(c_cp, text=f"4. 비선형 커브: {init_cp}", font=("Inter", 8), fg=self.text_color, bg=self.card_color)
        self.mp_cp_lbl.pack(anchor="w")
        self.mp_cp_scale = tk.Scale(
            c_cp, from_=1.0, to=1.8, resolution=0.05, orient="horizontal",
            bg=self.card_color, fg=self.text_color, troughcolor="#0F172A", activebackground=self.mp_accent_color,
            highlightthickness=0, bd=0, showvalue=False, command=self.on_mp_cp_change
        )
        self.mp_cp_scale.set(init_cp)
        self.mp_cp_scale.pack(fill="x", pady=(1, 0))
        
        # 5. 가속도 (Acceleration) & 초기화 버튼
        row3_f = tk.Frame(self.mp_panel, bg=self.card_color)
        row3_f.pack(fill="x", pady=(0, 2))
        row3_f.columnconfigure(0, weight=3)
        row3_f.columnconfigure(1, weight=2)
        
        c_acc = tk.Frame(row3_f, bg=self.card_color)
        c_acc.grid(row=0, column=0, padx=(0, 5), sticky="ew")
        init_acc = int(mp_cfg.get("acceleration", 5))
        self.mp_acc_lbl = tk.Label(c_acc, text=f"5. 모션 가속도: {init_acc}", font=("Inter", 8), fg=self.text_color, bg=self.card_color)
        self.mp_acc_lbl.pack(anchor="w")
        self.mp_acc_scale = tk.Scale(
            c_acc, from_=0, to=10, resolution=1, orient="horizontal",
            bg=self.card_color, fg=self.text_color, troughcolor="#0F172A", activebackground=self.mp_accent_color,
            highlightthickness=0, bd=0, showvalue=False, command=self.on_mp_acc_change
        )
        self.mp_acc_scale.set(init_acc)
        self.mp_acc_scale.pack(fill="x", pady=(1, 0))
        
        # MediaPipe 기본값 초기화 버튼
        c_rst = tk.Frame(row3_f, bg=self.card_color)
        c_rst.grid(row=0, column=1, padx=(5, 0), sticky="se", pady=(0, 2))
        self.mp_reset_btn = tk.Button(
            c_rst, text="↺ MP 설정 초기화", font=("Segoe UI", 8, "bold"),
            bg="#334155", fg=self.text_color, activebackground="#475569", activeforeground=self.text_color,
            bd=0, padx=6, pady=4, relief="flat", cursor="hand2", command=self.reset_mediapipe_defaults
        )
        self.mp_reset_btn.pack(fill="x")

    def _build_yunet_panel(self):
        """YuNet 전용 컨트롤 패널 구축"""
        yn_cfg = self.config.get("yunet", {})
        
        # 감도(Sensitivity X/Y)
        sens_f = tk.Frame(self.yn_panel, bg=self.card_color)
        sens_f.pack(fill="x", pady=(0, 6))
        sens_f.columnconfigure(0, weight=1)
        sens_f.columnconfigure(1, weight=1)
        
        # X 민감도
        c_x = tk.Frame(sens_f, bg=self.card_color)
        c_x.grid(row=0, column=0, padx=(0, 5), sticky="ew")
        init_x = int(yn_cfg.get("sensitivity_x", 27))
        self.yn_sx_lbl = tk.Label(c_x, text=f"민감도 X: {init_x}", font=("Inter", 8, "bold"), fg=self.text_color, bg=self.card_color)
        self.yn_sx_lbl.pack(anchor="w")
        self.yn_sx_scale = tk.Scale(
            c_x, from_=0, to=50, resolution=1, orient="horizontal",
            bg=self.card_color, fg=self.text_color, troughcolor="#0F172A", activebackground=self.accent_color,
            highlightthickness=0, bd=0, showvalue=False, command=self.on_yn_sx_change
        )
        self.yn_sx_scale.set(init_x)
        self.yn_sx_scale.pack(fill="x", pady=(1, 0))
        
        # Y 민감도
        c_y = tk.Frame(sens_f, bg=self.card_color)
        c_y.grid(row=0, column=1, padx=(5, 0), sticky="ew")
        init_y = int(yn_cfg.get("sensitivity_y", 27))
        self.yn_sy_lbl = tk.Label(c_y, text=f"민감도 Y: {init_y}", font=("Inter", 8, "bold"), fg=self.text_color, bg=self.card_color)
        self.yn_sy_lbl.pack(anchor="w")
        self.yn_sy_scale = tk.Scale(
            c_y, from_=0, to=50, resolution=1, orient="horizontal",
            bg=self.card_color, fg=self.text_color, troughcolor="#0F172A", activebackground=self.accent_color,
            highlightthickness=0, bd=0, showvalue=False, command=self.on_yn_sy_change
        )
        self.yn_sy_scale.set(init_y)
        self.yn_sy_scale.pack(fill="x", pady=(1, 0))
        
        # 임계값 / 스무딩
        row1_f = tk.Frame(self.yn_panel, bg=self.card_color)
        row1_f.pack(fill="x", pady=(0, 6))
        row1_f.columnconfigure(0, weight=1)
        row1_f.columnconfigure(1, weight=1)
        
        # 임계값
        c_th = tk.Frame(row1_f, bg=self.card_color)
        c_th.grid(row=0, column=0, padx=(0, 5), sticky="ew")
        init_th = int(yn_cfg.get("motion_threshold", 2))
        self.yn_th_lbl = tk.Label(c_th, text=f"임계값: {init_th}", font=("Inter", 8), fg=self.text_color, bg=self.card_color)
        self.yn_th_lbl.pack(anchor="w")
        self.yn_th_scale = tk.Scale(
            c_th, from_=0, to=4, resolution=1, orient="horizontal",
            bg=self.card_color, fg=self.text_color, troughcolor="#0F172A", activebackground=self.accent_color,
            highlightthickness=0, bd=0, showvalue=False, command=self.on_yn_th_change
        )
        self.yn_th_scale.set(init_th)
        self.yn_th_scale.pack(fill="x", pady=(1, 0))
        
        # 스무딩
        c_sm = tk.Frame(row1_f, bg=self.card_color)
        c_sm.grid(row=0, column=1, padx=(5, 0), sticky="ew")
        init_sm = int(yn_cfg.get("smoothing", 3))
        self.yn_sm_lbl = tk.Label(c_sm, text=f"스무딩: {init_sm}", font=("Inter", 8), fg=self.text_color, bg=self.card_color)
        self.yn_sm_lbl.pack(anchor="w")
        self.yn_sm_scale = tk.Scale(
            c_sm, from_=0, to=6, resolution=1, orient="horizontal",
            bg=self.card_color, fg=self.text_color, troughcolor="#0F172A", activebackground=self.accent_color,
            highlightthickness=0, bd=0, showvalue=False, command=self.on_yn_sm_change
        )
        self.yn_sm_scale.set(init_sm)
        self.yn_sm_scale.pack(fill="x", pady=(1, 0))
        
        # 가속도
        acc_f = tk.Frame(self.yn_panel, bg=self.card_color)
        acc_f.pack(fill="x", pady=(0, 6))
        init_acc = int(yn_cfg.get("acceleration", 5))
        self.yn_acc_lbl = tk.Label(acc_f, text=f"가속도: {init_acc}", font=("Inter", 8), fg=self.text_color, bg=self.card_color)
        self.yn_acc_lbl.pack(anchor="w")
        self.yn_acc_scale = tk.Scale(
            acc_f, from_=0, to=10, resolution=1, orient="horizontal",
            bg=self.card_color, fg=self.text_color, troughcolor="#0F172A", activebackground=self.accent_color,
            highlightthickness=0, bd=0, showvalue=False, command=self.on_yn_acc_change
        )
        self.yn_acc_scale.set(init_acc)
        self.yn_acc_scale.pack(fill="x", pady=(1, 0))
        
        # 광량 감지 / 튐 억제 (2열)
        shock_f = tk.Frame(self.yn_panel, bg=self.card_color)
        shock_f.pack(fill="x", pady=(0, 2))
        shock_f.columnconfigure(0, weight=1)
        shock_f.columnconfigure(1, weight=1)
        
        # 광량 감지
        c_il = tk.Frame(shock_f, bg=self.card_color)
        c_il.grid(row=0, column=0, padx=(0, 5), sticky="ew")
        init_il = float(yn_cfg.get("illumination_threshold", 10.0))
        self.yn_il_lbl = tk.Label(c_il, text=f"광량 감지: {init_il}", font=("Inter", 8), fg=self.text_color, bg=self.card_color)
        self.yn_il_lbl.pack(anchor="w")
        self.yn_il_scale = tk.Scale(
            c_il, from_=1.0, to=30.0, resolution=0.5, orient="horizontal",
            bg=self.card_color, fg=self.text_color, troughcolor="#0F172A", activebackground=self.accent_color,
            highlightthickness=0, bd=0, showvalue=False, command=self.on_yn_il_change
        )
        self.yn_il_scale.set(init_il)
        self.yn_il_scale.pack(fill="x", pady=(1, 0))
        
        # 튐 억제
        c_sp = tk.Frame(shock_f, bg=self.card_color)
        c_sp.grid(row=0, column=1, padx=(5, 0), sticky="ew")
        init_sp = float(yn_cfg.get("spike_threshold", 15.0))
        self.yn_sp_lbl = tk.Label(c_sp, text=f"튐 억제: {init_sp}px", font=("Inter", 8), fg=self.text_color, bg=self.card_color)
        self.yn_sp_lbl.pack(anchor="w")
        self.yn_sp_scale = tk.Scale(
            c_sp, from_=5.0, to=50.0, resolution=1.0, orient="horizontal",
            bg=self.card_color, fg=self.text_color, troughcolor="#0F172A", activebackground=self.accent_color,
            highlightthickness=0, bd=0, showvalue=False, command=self.on_yn_sp_change
        )
        self.yn_sp_scale.set(init_sp)
        self.yn_sp_scale.pack(fill="x", pady=(1, 0))
        
        # YuNet 기본값 초기화 버튼
        yn_rst_f = tk.Frame(self.yn_panel, bg=self.card_color)
        yn_rst_f.pack(fill="x", pady=(4, 0))
        self.yn_reset_btn = tk.Button(
            yn_rst_f, text="↺ YuNet 설정 초기화", font=("Segoe UI", 8, "bold"),
            bg="#334155", fg=self.text_color, activebackground="#475569", activeforeground=self.text_color,
            bd=0, padx=6, pady=4, relief="flat", cursor="hand2", command=self.reset_yunet_defaults
        )
        self.yn_reset_btn.pack(side="right")

    def _switch_panel(self, engine_name):
        """엔진에 따라 패널을 동적으로 교체 표시"""
        if engine_name == "yunet":
            self.mp_panel.pack_forget()
            self.yn_panel.pack(fill="x", padx=20, pady=(0, 6))
        else:
            self.yn_panel.pack_forget()
            self.mp_panel.pack(fill="x", padx=20, pady=(0, 6))

    def _build_common_controls(self):
        """공통 시스템 및 카메라 제어 UI 구축"""
        # 단축키 설정 영역
        self.hotkey_frame = tk.Frame(self.ctrl_frame, bg=self.card_color)
        self.hotkey_frame.pack(fill="x", padx=20, pady=(0, 8))
        
        self.hotkey_lbl = tk.Label(self.hotkey_frame, text=f"단축키: {self.config['tracking_toggle_key'].upper()}", font=("Inter", 8), fg=self.text_color, bg=self.card_color)
        self.hotkey_lbl.pack(side="left", anchor="w")
        
        self.hotkey_btn = tk.Button(
            self.hotkey_frame, text="단축키 변경", font=("Segoe UI", 8, "bold"),
            bg="#334155", fg=self.text_color, activebackground="#475569", activeforeground=self.text_color,
            bd=0, padx=8, pady=3, relief="flat", cursor="hand2", command=self.start_hotkey_recording
        )
        self.hotkey_btn.pack(side="right")

        # 카메라 상세 제어 프레임
        self.cam_ctrl_frame = tk.Frame(self.ctrl_frame, bg=self.card_color)
        self.cam_ctrl_frame.pack(fill="x", padx=20, pady=(0, 8))
        
        # 0. 카메라 선택 드롭다운
        self.cam_select_frame = tk.Frame(self.cam_ctrl_frame, bg=self.card_color)
        self.cam_select_frame.pack(fill="x", pady=(0, 6))
        
        self.cam_select_label = tk.Label(
            self.cam_select_frame, text="카메라 선택:", font=("Segoe UI", 8, "bold"),
            fg=self.text_color, bg=self.card_color
        )
        self.cam_select_label.pack(side="left", padx=(0, 5))
        
        self.camera_list = self.scan_cameras()
        combo_values = [f"카메라 {idx}" for idx in self.camera_list]
        self.cam_combo = ttk.Combobox(self.cam_select_frame, values=combo_values, state="readonly", width=12)
        
        current_id = self.config.get("camera_id", 0)
        try:
            current_index = self.camera_list.index(current_id)
            self.cam_combo.current(current_index)
        except ValueError:
            self.cam_combo.set(f"카메라 {current_id}")
            
        self.cam_combo.pack(side="left", fill="x", expand=True)
        self.cam_combo.bind("<<ComboboxSelected>>", self.on_camera_select)
        
        # 0-1. 해상도 및 FPS 선택
        self.res_fps_frame = tk.Frame(self.cam_ctrl_frame, bg=self.card_color)
        self.res_fps_frame.pack(fill="x", pady=(0, 6))
        
        self.res_label = tk.Label(self.res_fps_frame, text="해상도:", font=("Segoe UI", 8, "bold"), fg=self.text_color, bg=self.card_color)
        self.res_label.pack(side="left", padx=(0, 3))
        
        res_options = ["320x240", "640x360", "640x480", "1280x720", "1920x1080"]
        self.res_combo = ttk.Combobox(self.res_fps_frame, values=res_options, state="readonly", width=9)
        current_res = f"{self.config.get('camera_width', 640)}x{self.config.get('camera_height', 480)}"
        if current_res not in res_options:
            res_options.append(current_res)
            self.res_combo['values'] = res_options
        self.res_combo.set(current_res)
        self.res_combo.pack(side="left", padx=(0, 10))
        self.res_combo.bind("<<ComboboxSelected>>", self.on_res_fps_select)
        
        self.fps_label = tk.Label(self.res_fps_frame, text="FPS:", font=("Segoe UI", 8, "bold"), fg=self.text_color, bg=self.card_color)
        self.fps_label.pack(side="left", padx=(0, 3))
        
        fps_options = ["30", "60", "90", "120"]
        self.fps_combo = ttk.Combobox(self.res_fps_frame, values=fps_options, state="readonly", width=4)
        current_fps = str(self.config.get("target_fps", 30))
        if current_fps not in fps_options:
            fps_options.append(current_fps)
            self.fps_combo['values'] = fps_options
        self.fps_combo.set(current_fps)
        self.fps_combo.pack(side="left", expand=True)
        self.fps_combo.bind("<<ComboboxSelected>>", self.on_res_fps_select)
        
        # 1. 자동 노출 체크박스
        auto_exp_default = self.config.get("auto_exposure", not self.config.get("lock_fps_low_light", False))
        self.auto_exposure_var = tk.BooleanVar(value=auto_exp_default)
        self.auto_exp_chk = tk.Checkbutton(
            self.cam_ctrl_frame, text="카메라 자동 노출 (Auto Exposure)", 
            variable=self.auto_exposure_var, command=self.on_auto_exposure_toggle,
            bg=self.card_color, fg=self.text_color, selectcolor="#1E293B",
            activebackground=self.card_color, activeforeground=self.text_color,
            font=("Segoe UI", 8), bd=0, highlightthickness=0
        )
        self.auto_exp_chk.pack(anchor="w", pady=(0, 4))

        # 활성화 토글 버튼
        self.toggle_btn = tk.Button(
            self.ctrl_frame, text=f"추적 시작 / 중지 ({self.config['tracking_toggle_key'].upper()})", font=("Inter", 10, "bold"),
            bg="#3B82F6", fg="#FFFFFF", activebackground="#2563EB", activeforeground="#FFFFFF",
            bd=0, padx=8, pady=8, relief="flat", cursor="hand2", command=self.manual_toggle
        )
        self.toggle_btn.pack(fill="x", padx=20, pady=(4, 8))
        
        self.recording_hotkey = False

    def on_engine_select(self, event=None):
        selected_text = self.engine_combo.get()
        engine_name = "yunet" if "YuNet" in selected_text else "mediapipe"
        
        if self.config.get("tracking_engine") != engine_name:
            self.config["tracking_engine"] = engine_name
            config.save_config(self.config)
            self.tracker.set_tracking_engine(engine_name)
            self._switch_panel(engine_name)
            print(f"[GUI] 트래킹 엔진이 '{engine_name}'(으)로 변경되었습니다.")

    # ========================================================
    # MediaPipe Head Pose 슬라이더 이벤트 핸들러
    # ========================================================
    def on_mp_sx_change(self, val):
        v = int(float(val))
        self.config["mediapipe"]["sensitivity_x"] = v
        self.mp_sx_lbl.configure(text=f"민감도 X (Yaw): {v}")
        config.save_config(self.config)

    def on_mp_sy_change(self, val):
        v = int(float(val))
        self.config["mediapipe"]["sensitivity_y"] = v
        self.mp_sy_lbl.configure(text=f"민감도 Y (Pitch): {v}")
        config.save_config(self.config)

    def on_mp_k_change(self, val):
        v = int(float(val))
        self.config["mediapipe"]["kalman_strength"] = v
        self.mp_k_lbl.configure(text=f"1. 칼만 필터: {v}")
        config.save_config(self.config)

    def on_mp_as_change(self, val):
        v = int(float(val))
        self.config["mediapipe"]["adaptive_smoothing"] = v
        self.mp_as_lbl.configure(text=f"2. 적응 스무딩: {v}")
        config.save_config(self.config)

    def on_mp_dz_change(self, val):
        v = round(float(val), 2)
        self.config["mediapipe"]["deadzone"] = v
        self.mp_dz_lbl.configure(text=f"3. 각도 데드존: {v}°")
        config.save_config(self.config)

    def on_mp_cp_change(self, val):
        v = round(float(val), 2)
        self.config["mediapipe"]["curve_power"] = v
        self.mp_cp_lbl.configure(text=f"4. 비선형 커브: {v}")
        config.save_config(self.config)

    def on_mp_acc_change(self, val):
        v = int(float(val))
        self.config["mediapipe"]["acceleration"] = v
        self.mp_acc_lbl.configure(text=f"5. 모션 가속도: {v}")
        config.save_config(self.config)

    def reset_mediapipe_defaults(self):
        """MediaPipe의 모든 설정값 및 필터 상태를 초기 기본값으로 리셋합니다."""
        defaults = config.DEFAULT_CONFIG["mediapipe"].copy()
        self.config["mediapipe"] = defaults
        config.save_config(self.config)
        
        # 슬라이더 및 라벨 리셋
        self.mp_sx_scale.set(defaults["sensitivity_x"])
        self.mp_sy_scale.set(defaults["sensitivity_y"])
        self.mp_k_scale.set(defaults["kalman_strength"])
        self.mp_as_scale.set(defaults["adaptive_smoothing"])
        self.mp_dz_scale.set(defaults["deadzone"])
        self.mp_cp_scale.set(defaults["curve_power"])
        self.mp_acc_scale.set(defaults["acceleration"])
        
        self.mp_sx_lbl.configure(text=f"민감도 X (Yaw): {defaults['sensitivity_x']}")
        self.mp_sy_lbl.configure(text=f"민감도 Y (Pitch): {defaults['sensitivity_y']}")
        self.mp_k_lbl.configure(text=f"1. 칼만 필터: {defaults['kalman_strength']}")
        self.mp_as_lbl.configure(text=f"2. 적응 스무딩: {defaults['adaptive_smoothing']}")
        self.mp_dz_lbl.configure(text=f"3. 각도 데드존: {defaults['deadzone']}°")
        self.mp_cp_lbl.configure(text=f"4. 비선형 커브: {defaults['curve_power']}")
        self.mp_acc_lbl.configure(text=f"5. 모션 가속도: {defaults['acceleration']}")
        
        # 트래커 내부 필터 상태 완벽 리셋
        if hasattr(self.tracker, "mp_pipeline"):
            self.tracker.mp_pipeline.reset()
            
        print("[GUI] MediaPipe 설정 및 필터가 기본값으로 초기화되었습니다.")

    # ========================================================
    # YuNet 슬라이더 이벤트 핸들러
    # ========================================================
    def on_yn_sx_change(self, val):
        v = int(float(val))
        self.config["yunet"]["sensitivity_x"] = v
        self.yn_sx_lbl.configure(text=f"민감도 X: {v}")
        config.save_config(self.config)

    def on_yn_sy_change(self, val):
        v = int(float(val))
        self.config["yunet"]["sensitivity_y"] = v
        self.yn_sy_lbl.configure(text=f"민감도 Y: {v}")
        config.save_config(self.config)

    def on_yn_th_change(self, val):
        v = int(float(val))
        self.config["yunet"]["motion_threshold"] = v
        self.yn_th_lbl.configure(text=f"임계값: {v}")
        config.save_config(self.config)

    def on_yn_sm_change(self, val):
        v = int(float(val))
        self.config["yunet"]["smoothing"] = v
        self.yn_sm_lbl.configure(text=f"스무딩: {v}")
        config.save_config(self.config)

    def on_yn_acc_change(self, val):
        v = int(float(val))
        self.config["yunet"]["acceleration"] = v
        self.yn_acc_lbl.configure(text=f"가속도: {v}")
        if hasattr(self.tracker, "yunet_filter"):
            self.tracker.yunet_filter._build_accel_array()
        config.save_config(self.config)

    def on_yn_il_change(self, val):
        v = round(float(val), 1)
        self.config["yunet"]["illumination_threshold"] = v
        self.yn_il_lbl.configure(text=f"광량 감지: {v}")
        config.save_config(self.config)

    def on_yn_sp_change(self, val):
        v = round(float(val), 1)
        self.config["yunet"]["spike_threshold"] = v
        self.yn_sp_lbl.configure(text=f"튐 억제: {v}px")
        config.save_config(self.config)

    def reset_yunet_defaults(self):
        """YuNet의 모든 설정값 및 필터 상태를 초기 기본값으로 리셋합니다."""
        defaults = config.DEFAULT_CONFIG["yunet"].copy()
        self.config["yunet"] = defaults
        config.save_config(self.config)
        
        # 슬라이더 및 라벨 리셋
        self.yn_sx_scale.set(defaults["sensitivity_x"])
        self.yn_sy_scale.set(defaults["sensitivity_y"])
        self.yn_th_scale.set(defaults["motion_threshold"])
        self.yn_sm_scale.set(defaults["smoothing"])
        self.yn_acc_scale.set(defaults["acceleration"])
        self.yn_il_scale.set(defaults["illumination_threshold"])
        self.yn_sp_scale.set(defaults["spike_threshold"])
        
        self.yn_sx_lbl.configure(text=f"민감도 X: {defaults['sensitivity_x']}")
        self.yn_sy_lbl.configure(text=f"민감도 Y: {defaults['sensitivity_y']}")
        self.yn_th_lbl.configure(text=f"임계값: {defaults['motion_threshold']}")
        self.yn_sm_lbl.configure(text=f"스무딩: {defaults['smoothing']}")
        self.yn_acc_lbl.configure(text=f"가속도: {defaults['acceleration']}")
        self.yn_il_lbl.configure(text=f"광량 감지: {defaults['illumination_threshold']}")
        self.yn_sp_lbl.configure(text=f"튐 억제: {defaults['spike_threshold']}px")
        
        if hasattr(self.tracker, "yunet_filter"):
            self.tracker.yunet_filter.config = self.config["yunet"]
            self.tracker.yunet_filter.reset()
            self.tracker.yunet_filter._build_accel_array()
            
        print("[GUI] YuNet 설정 및 필터가 기본값으로 초기화되었습니다.")

    def start_poll_loop(self):
        self.poll_frame_queue()

    def poll_frame_queue(self):
        try:
            latest_data = None
            while not self.frame_queue.empty():
                try:
                    latest_data = self.frame_queue.get_nowait()
                except Exception:
                    break
            
            if latest_data is not None:
                if len(latest_data) == 8:
                    frame, tracking_enabled, nose_x, nose_y, fps, w, h, engine_name = latest_data
                else:
                    frame, tracking_enabled, nose_x, nose_y, fps, w, h = latest_data[:7]
                    engine_name = "MediaPipe"
                self.update_frame(frame, tracking_enabled, nose_x, nose_y, fps, w, h, engine_name)
        except Exception as e:
            print(f"[GUI] 폴링 루프 에러: {e}")
        finally:
            if self.root.winfo_exists():
                self.root.after(15, self.poll_frame_queue)

    def update_frame(self, cv_frame, tracking_enabled, nose_x, nose_y, fps, w, h, engine_name="MediaPipe"):
        """
        프레임 렌더링 최적화 (Tkinter PhotoImage 메모리 안정화)
        """
        self.info_label.configure(text=f"FPS: {fps} | {engine_name} | {w}x{h}")

        display_w = 640
        display_h = int(640 * (h / w)) if w > 0 else 360
        
        if int(self.canvas.cget("width")) != display_w or int(self.canvas.cget("height")) != display_h:
            self.canvas.configure(width=display_w, height=display_h)
            self.image_id = None
            self.canvas.delete("all")
            self.photo = None

        resized = cv2.resize(cv_frame, (display_w, display_h))
        rgb_image = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb_image)
        
        # PhotoImage 안전 갱신
        self.photo = ImageTk.PhotoImage(image=pil_img)
        
        if self.image_id is None:
            self.canvas.delete("all")
            self.image_id = self.canvas.create_image(0, 0, anchor="nw", image=self.photo)
        else:
            self.canvas.itemconfig(self.image_id, image=self.photo)
            
        del pil_img
        del rgb_image
        del resized
        
        hotkey = self.config.get('tracking_toggle_key', 'F12').upper()
        if tracking_enabled:
            accent = self.mp_accent_color if engine_name == "MediaPipe" else self.accent_color
            self.cam_frame.configure(highlightbackground=accent)
            self.status_label.configure(text=f"[{engine_name}] 추적 활성화 중...", fg=accent)
            self.toggle_btn.configure(bg=self.inactive_color, text=f"추적 일시정지 ({hotkey})")
        else:
            self.cam_frame.configure(highlightbackground="#334155")
            self.status_label.configure(text=f"비활성 상태 ({hotkey}키로 활성화)", fg=self.inactive_color)
            self.toggle_btn.configure(bg=self.accent_color, text=f"추적 시작 ({hotkey})")

    def manual_toggle(self):
        new_state = not self.tracker.tracking_enabled
        self.tracker.set_tracking(new_state)

    def start_hotkey_recording(self):
        self.recording_hotkey = True
        self.hotkey_btn.configure(text="키를 누르세요...", bg=self.inactive_color)
        self.root.bind("<Key>", self.record_hotkey)
        self.hotkey_btn.focus_set()

    def record_hotkey(self, event):
        if not self.recording_hotkey:
            return
            
        keysym = event.keysym.lower()
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
        self.config["tracking_toggle_key"] = final_key
        config.save_config(self.config)
        
        self.hotkey_lbl.configure(text=f"단축키: {final_key.upper()}")
        self.status_label.configure(text=f"비활성 상태 ({final_key.upper()}키로 활성화)")
        self.toggle_btn.configure(text=f"추적 시작 / 중지 ({final_key.upper()})")
        
        self.recording_hotkey = False
        self.hotkey_btn.configure(text="단축키 변경", bg="#334155")
        self.root.unbind("<Key>")

    def on_auto_exposure_toggle(self):
        val = self.auto_exposure_var.get()
        self.config["auto_exposure"] = val
        self.config["lock_fps_low_light"] = not val
        config.save_config(self.config)
        self.tracker.set_auto_exposure(val)

    def scan_cameras(self):
        current_id = self.config.get("camera_id", 0)
        available = [current_id]
        backend_str = self.config.get("camera_backend", "DSHOW").upper()
        backend = cv2.CAP_MSMF if backend_str == "MSMF" else (cv2.CAP_ANY if backend_str == "AUTO" else cv2.CAP_DSHOW)
            
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
            if self.config.get("camera_id") != selected_idx:
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
