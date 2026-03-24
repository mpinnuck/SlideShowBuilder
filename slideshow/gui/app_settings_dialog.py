import tkinter as tk
from tkinter import ttk
from pathlib import Path


class AppSettingsDialog:
    """Dialog for viewing and editing global app settings (~/SlideShowBuilder/slideshow_settings.json)"""

    def __init__(self, parent):
        self.parent = parent

        from slideshow.config import Config
        self.cfg = Config.instance()
        self.settings = self.cfg.load_app_settings()

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("App Settings")
        self.dialog.geometry("700x480")
        self.dialog.resizable(True, True)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        self.dialog.minsize(600, 400)

        self._center_dialog()
        self._create_content()
        self._create_buttons()

    def _center_dialog(self):
        self.dialog.update_idletasks()
        px = self.parent.winfo_x()
        py = self.parent.winfo_y()
        pw = self.parent.winfo_width()
        ph = self.parent.winfo_height()
        dw = self.dialog.winfo_width()
        dh = self.dialog.winfo_height()
        self.dialog.geometry(f"{dw}x{dh}+{px + pw // 2 - dw // 2}+{py + ph // 2 - dh // 2}")

    def _create_content(self):
        main = ttk.Frame(self.dialog, padding=15)
        main.pack(fill=tk.BOTH, expand=True)
        main.columnconfigure(1, weight=1)

        row = 0

        # --- Section: Directories ---
        ttk.Label(main, text="Directories", font=("Arial", 11, "bold")).grid(
            row=row, column=0, columnspan=3, sticky="w", pady=(0, 5))
        row += 1

        ttk.Label(main, text="Slideshows Base Dir:").grid(row=row, column=0, sticky="w")
        self.base_dir_var = tk.StringVar(value=self.settings.get("slideshows_base_dir", ""))
        entry = ttk.Entry(main, textvariable=self.base_dir_var)
        entry.grid(row=row, column=1, sticky="ew", padx=5)
        ttk.Button(main, text="Browse", command=lambda: self._browse_dir(self.base_dir_var)).grid(
            row=row, column=2)
        row += 1

        # --- Section: FFmpeg ---
        ttk.Label(main, text="FFmpeg", font=("Arial", 11, "bold")).grid(
            row=row, column=0, columnspan=3, sticky="w", pady=(15, 5))
        row += 1

        ttk.Label(main, text="ffmpeg Path:").grid(row=row, column=0, sticky="w")
        self.ffmpeg_var = tk.StringVar(value=self.settings.get("ffmpeg_path", ""))
        ttk.Entry(main, textvariable=self.ffmpeg_var).grid(row=row, column=1, sticky="ew", padx=5)
        ttk.Button(main, text="Browse", command=lambda: self._browse_file(
            self.ffmpeg_var, "Select ffmpeg executable", [("All Files", "*.*")])).grid(
            row=row, column=2)
        row += 1

        ttk.Label(main, text="ffprobe Path:").grid(row=row, column=0, sticky="w")
        self.ffprobe_var = tk.StringVar(value=self.settings.get("ffprobe_path", ""))
        ttk.Entry(main, textvariable=self.ffprobe_var).grid(row=row, column=1, sticky="ew", padx=5)
        ttk.Button(main, text="Browse", command=lambda: self._browse_file(
            self.ffprobe_var, "Select ffprobe executable", [("All Files", "*.*")])).grid(
            row=row, column=2)
        row += 1

        # Auto-detect hint
        ttk.Label(main, text="(Leave empty for auto-detect)", foreground="gray").grid(
            row=row, column=1, sticky="w", padx=5)
        row += 1

        # --- Section: Fonts ---
        ttk.Label(main, text="Fonts", font=("Arial", 11, "bold")).grid(
            row=row, column=0, columnspan=3, sticky="w", pady=(15, 5))
        row += 1

        ttk.Label(main, text="Default Font:").grid(row=row, column=0, sticky="w")
        self.font_var = tk.StringVar(value=self.settings.get("default_font_path", ""))
        ttk.Entry(main, textvariable=self.font_var).grid(row=row, column=1, sticky="ew", padx=5)
        ttk.Button(main, text="Browse", command=self._browse_font).grid(row=row, column=2)
        row += 1

        ttk.Label(main, text="(Leave empty for auto-detect)", foreground="gray").grid(
            row=row, column=1, sticky="w", padx=5)
        row += 1

        ttk.Label(main, text="Extra Font Dirs:").grid(row=row, column=0, sticky="nw")
        font_dirs = self.settings.get("font_search_paths", [])
        self.font_dirs_var = tk.StringVar(value=", ".join(font_dirs))
        ttk.Entry(main, textvariable=self.font_dirs_var).grid(row=row, column=1, sticky="ew", padx=5)
        ttk.Label(main, text="(comma-separated)", foreground="gray").grid(
            row=row, column=2, sticky="w")
        row += 1

        # --- Section: Info ---
        ttk.Separator(main, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=(15, 5))
        row += 1

        settings_path = str(self.cfg.APP_SETTINGS_FILE)
        ttk.Label(main, text=f"Settings file: {settings_path}", foreground="gray",
                  font=("Arial", 9)).grid(row=row, column=0, columnspan=3, sticky="w")

    def _create_buttons(self):
        frame = ttk.Frame(self.dialog)
        frame.pack(fill=tk.X, padx=15, pady=(0, 10))
        ttk.Button(frame, text="OK", command=self._ok).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT)

    def _browse_dir(self, var):
        from tkinter import filedialog
        d = filedialog.askdirectory(initialdir=var.get() or str(Path.home()))
        if d:
            var.set(d)

    def _browse_file(self, var, title, filetypes):
        from tkinter import filedialog
        current = var.get()
        initial = str(Path(current).parent) if current and Path(current).parent.is_dir() else str(Path.home())
        f = filedialog.askopenfilename(title=title, filetypes=filetypes, initialdir=initial)
        if f:
            var.set(f)

    def _browse_font(self):
        from tkinter import filedialog
        filetypes = [
            ("Font Files", "*.ttf *.otf *.ttc"),
            ("All Files", "*.*")
        ]
        initial = self.cfg.get_font_initial_dir()
        f = filedialog.askopenfilename(title="Select Default Font", filetypes=filetypes,
                                       initialdir=initial)
        if f:
            self.font_var.set(f)

    def _ok(self):
        # Update settings with values from the dialog
        self.settings["slideshows_base_dir"] = self.base_dir_var.get().strip()
        self.settings["ffmpeg_path"] = self.ffmpeg_var.get().strip()
        self.settings["ffprobe_path"] = self.ffprobe_var.get().strip()
        self.settings["default_font_path"] = self.font_var.get().strip()

        raw_dirs = self.font_dirs_var.get().strip()
        if raw_dirs:
            self.settings["font_search_paths"] = [d.strip() for d in raw_dirs.split(",") if d.strip()]
        else:
            self.settings["font_search_paths"] = []

        self.cfg.save_app_settings(self.settings)

        # Reset ffmpeg path cache so new paths take effect
        from slideshow.transitions.ffmpeg_paths import FFmpegPaths
        FFmpegPaths().reset()

        self.parent.log_message("App settings saved")
        self.dialog.destroy()
