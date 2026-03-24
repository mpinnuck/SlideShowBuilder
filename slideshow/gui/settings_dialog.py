import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

from slideshow.gui.helpers import wide_messagebox


class SettingsDialog:
    """Comprehensive settings dialog for transitions, titles, and advanced options"""
    
    def __init__(self, parent):
        self.parent = parent
        self.config_data = parent.config_data.copy()
        
        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Slideshow Settings")
        self.dialog.geometry("950x700")  # Increased width from 800 to 950 for cache buttons
        self.dialog.resizable(True, True)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Set minimum size to prevent clipping
        self.dialog.minsize(900, 600)  # Increased minimum width from 750 to 900
        
        # Center the dialog
        self._center_dialog()
        
        # Create the tabbed interface
        self._create_tabs()
        
        # Create bottom buttons
        self._create_buttons()
        
        # Initialize tab content
        self._init_tabs()
    
    def _center_dialog(self):
        """Center the dialog over the parent window"""
        self.dialog.update_idletasks()
        parent_x = self.parent.winfo_x()
        parent_y = self.parent.winfo_y()
        parent_w = self.parent.winfo_width()
        parent_h = self.parent.winfo_height()
        
        dialog_w = self.dialog.winfo_width()
        dialog_h = self.dialog.winfo_height()
        
        x = parent_x + (parent_w // 2) - (dialog_w // 2)
        y = parent_y + (parent_h // 2) - (dialog_h // 2)
        
        self.dialog.geometry(f"{dialog_w}x{dialog_h}+{x}+{y}")
    
    def _create_tabs(self):
        """Create the tabbed notebook interface"""
        self.notebook = ttk.Notebook(self.dialog)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Advanced Settings Tab (first tab)
        self.advanced_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.advanced_frame, text="Advanced")
        
        # Transition Settings Tab
        self.transition_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.transition_frame, text="Transitions")
        
        # Title Settings Tab
        self.title_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.title_frame, text="Title/Intro")
    
    def _create_buttons(self):
        """Create OK, Cancel, and Apply buttons"""
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        ttk.Button(button_frame, text="OK", command=self._ok_clicked).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_frame, text="Cancel", command=self._cancel_clicked).pack(side=tk.RIGHT)
        ttk.Button(button_frame, text="Apply", command=self._apply_clicked).pack(side=tk.RIGHT, padx=(0, 10))
        ttk.Button(button_frame, text="Reset to Defaults", command=self._reset_clicked).pack(side=tk.LEFT)
    
    def _init_tabs(self):
        """Initialize all tab content"""
        self._create_transition_settings()
        self._create_title_settings()
        self._create_advanced_settings()
    
    def _create_transition_settings(self):
        """Create transition settings controls"""
        frame = self.transition_frame
        
        # Create scrollable frame
        canvas = tk.Canvas(frame)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Transition Type Selection
        ttk.Label(scrollable_frame, text="Transition Type:", font=("Arial", 12, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 10))
        
        self.transition_type_var = tk.StringVar(value=self.config_data.get("transition_type", "fade"))
        
        # Get available transitions
        self.transition_options = self._get_transition_options()
        
        row = 1
        for transition_name, transition_info in self.transition_options.items():
            ttk.Radiobutton(
                scrollable_frame, 
                text=f"{transition_info['display_name']}", 
                variable=self.transition_type_var, 
                value=transition_name
            ).grid(row=row, column=0, sticky="w", padx=(20, 0))
            
            # Add description if available
            if 'description' in transition_info:
                desc_label = ttk.Label(scrollable_frame, text=transition_info['description'], foreground="gray")
                desc_label.grid(row=row, column=1, sticky="w", padx=(10, 0))
            
            row += 1
        
        # Origami-specific settings (shown when origami is selected)
        ttk.Separator(scrollable_frame, orient="horizontal").grid(row=row, column=0, columnspan=2, sticky="ew", pady=20)
        row += 1
        
        ttk.Label(scrollable_frame, text="Origami Transition Settings:", font=("Arial", 12, "bold")).grid(row=row, column=0, sticky="w", pady=(0, 10))
        row += 1
        
        # Easing Function
        ttk.Label(scrollable_frame, text="Animation Easing:").grid(row=row, column=0, sticky="w")
        self.easing_var = tk.StringVar(value=self.config_data.get("origami_easing", "quad"))
        easing_combo = ttk.Combobox(scrollable_frame, textvariable=self.easing_var, 
                                   values=["linear", "quad", "cubic", "back"], state="readonly", width=20)
        easing_combo.grid(row=row, column=1, sticky="w", padx=(10, 0))
        row += 1
        
        # Lighting
        self.lighting_var = tk.BooleanVar(value=self.config_data.get("origami_lighting", True))
        ttk.Checkbutton(scrollable_frame, text="Enable realistic lighting", variable=self.lighting_var).grid(row=row, column=0, columnspan=2, sticky="w", pady=5)
        row += 1
        
        # Fold Direction (for origami)
        ttk.Label(scrollable_frame, text="Fold Direction:").grid(row=row, column=0, sticky="w")
        self.fold_direction_var = tk.StringVar(value=self.config_data.get("origami_fold", ""))
        fold_combo = ttk.Combobox(scrollable_frame, textvariable=self.fold_direction_var,
                                 values=["", "left", "right", "up", "down", "centerhoriz", "centervert", 
                                        "slide_left", "slide_right", "multileft", "multiright"], 
                                 state="readonly", width=20)
        fold_combo.grid(row=row, column=1, sticky="w", padx=(10, 0))
        row += 1
        
        # Add tooltip for fold direction
        ttk.Label(scrollable_frame, text="(Leave empty for random)", foreground="gray").grid(row=row, column=1, sticky="w", padx=(10, 0))
    
    def _create_title_settings(self):
        """Create title/intro settings controls"""
        frame = self.title_frame
        
        # Create scrollable frame
        canvas = tk.Canvas(frame)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        # Configure grid weights for proper expansion in title settings
        scrollable_frame.columnconfigure(1, weight=1)
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        intro_config = self.config_data.get("intro_title", {})
        
        # Enable/Disable Intro Title
        self.intro_enabled_var = tk.BooleanVar(value=intro_config.get("enabled", False))
        ttk.Checkbutton(scrollable_frame, text="Enable Intro Title", variable=self.intro_enabled_var,
                       command=self._toggle_intro_controls).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
        
        # Title Text - Multi-line support
        ttk.Label(scrollable_frame, text="Title Text:").grid(row=1, column=0, sticky="nw")
        text_frame = ttk.Frame(scrollable_frame)
        text_frame.grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=(0, 5))
        text_frame.columnconfigure(0, weight=1)  # Make text widget expand
        
        # Create text widget with scrollbar for multi-line input
        self.title_text_widget = tk.Text(text_frame, width=50, height=4, wrap=tk.WORD)
        text_scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=self.title_text_widget.yview)
        self.title_text_widget.configure(yscrollcommand=text_scrollbar.set)
        
        self.title_text_widget.grid(row=0, column=0, sticky="ew")
        text_scrollbar.grid(row=0, column=1, sticky="ns")
        
        # Insert current text
        current_text = intro_config.get("text", "").replace('\\n', '\n')
        self.title_text_widget.insert(1.0, current_text)
        
        # Add helper label
        helper_label = ttk.Label(scrollable_frame, text="(Use Enter for new lines)", foreground="gray")
        helper_label.grid(row=2, column=1, sticky="w", padx=(10, 0))
        
        # Duration
        ttk.Label(scrollable_frame, text="Duration (seconds):").grid(row=3, column=0, sticky="w")
        self.title_duration_var = tk.DoubleVar(value=intro_config.get("duration", 5.0))
        duration_spin = ttk.Spinbox(scrollable_frame, from_=1.0, to=30.0, increment=0.5, 
                                   textvariable=self.title_duration_var, width=10)
        duration_spin.grid(row=3, column=1, sticky="w", padx=(10, 0))
        
        # Line Spacing
        ttk.Label(scrollable_frame, text="Line Spacing:").grid(row=4, column=0, sticky="w")
        self.line_spacing_var = tk.DoubleVar(value=intro_config.get("line_spacing", 1.2))
        spacing_spin = ttk.Spinbox(scrollable_frame, from_=0.8, to=3.0, increment=0.1, 
                                  textvariable=self.line_spacing_var, width=10, format="%.1f")
        spacing_spin.grid(row=4, column=1, sticky="w", padx=(10, 0))
        
        # Font Settings Section
        ttk.Label(scrollable_frame, text="Font:", font=("Arial", 10, "bold")).grid(row=5, column=0, sticky="w", pady=(10, 5))
        
        # Font Path
        ttk.Label(scrollable_frame, text="Font File:").grid(row=6, column=0, sticky="w")
        font_path_frame = ttk.Frame(scrollable_frame)
        font_path_frame.grid(row=6, column=1, sticky="ew", padx=(10, 0))
        font_path_frame.columnconfigure(0, weight=1)  # Make entry expand
        
        self.font_path_var = tk.StringVar(value=intro_config.get("font_path", ""))
        font_path_entry = ttk.Entry(font_path_frame, textvariable=self.font_path_var, width=45)
        font_path_entry.grid(row=0, column=0, sticky="ew")
        ttk.Button(font_path_frame, text="Browse", command=self._browse_font_file).grid(row=0, column=1, padx=(5, 0))
        
        # Font Size
        ttk.Label(scrollable_frame, text="Font Size:").grid(row=7, column=0, sticky="w")
        self.font_size_var = tk.IntVar(value=intro_config.get("font_size", 120))
        font_spin = ttk.Spinbox(scrollable_frame, from_=20, to=300, increment=10, 
                               textvariable=self.font_size_var, width=10)
        font_spin.grid(row=7, column=1, sticky="w", padx=(10, 0))
        
        # Font Weight
        ttk.Label(scrollable_frame, text="Font Weight:").grid(row=8, column=0, sticky="w")
        self.font_weight_var = tk.StringVar(value=intro_config.get("font_weight", "normal"))
        weight_combo = ttk.Combobox(scrollable_frame, textvariable=self.font_weight_var,
                                   values=["light", "normal", "bold"], state="readonly", width=10)
        weight_combo.grid(row=8, column=1, sticky="w", padx=(10, 0))
        
        # Text Color
        ttk.Label(scrollable_frame, text="Text Color (RGBA):").grid(row=9, column=0, sticky="w")
        color_frame = ttk.Frame(scrollable_frame)
        color_frame.grid(row=9, column=1, sticky="ew", padx=(10, 0))
        
        text_color = intro_config.get("text_color", [255, 255, 255, 255])
        self.text_r_var = tk.IntVar(value=text_color[0])
        self.text_g_var = tk.IntVar(value=text_color[1])
        self.text_b_var = tk.IntVar(value=text_color[2])
        self.text_a_var = tk.IntVar(value=text_color[3])
        
        for i, (var, label) in enumerate([(self.text_r_var, "R"), (self.text_g_var, "G"), 
                                         (self.text_b_var, "B"), (self.text_a_var, "A")]):
            ttk.Label(color_frame, text=f"{label}:").grid(row=0, column=i*2, sticky="w", padx=(0 if i == 0 else 5, 2))
            ttk.Spinbox(color_frame, from_=0, to=255, textvariable=var, width=6).grid(row=0, column=i*2+1, padx=(0, 8))
        
        # Shadow Color
        ttk.Label(scrollable_frame, text="Shadow Color (RGBA):").grid(row=10, column=0, sticky="w")
        shadow_frame = ttk.Frame(scrollable_frame)
        shadow_frame.grid(row=10, column=1, sticky="ew", padx=(10, 0))
        
        shadow_color = intro_config.get("shadow_color", [0, 0, 0, 180])
        self.shadow_r_var = tk.IntVar(value=shadow_color[0])
        self.shadow_g_var = tk.IntVar(value=shadow_color[1])
        self.shadow_b_var = tk.IntVar(value=shadow_color[2])
        self.shadow_a_var = tk.IntVar(value=shadow_color[3])
        
        for i, (var, label) in enumerate([(self.shadow_r_var, "R"), (self.shadow_g_var, "G"), 
                                         (self.shadow_b_var, "B"), (self.shadow_a_var, "A")]):
            ttk.Label(shadow_frame, text=f"{label}:").grid(row=0, column=i*2, sticky="w", padx=(0 if i == 0 else 5, 2))
            ttk.Spinbox(shadow_frame, from_=0, to=255, textvariable=var, width=6).grid(row=0, column=i*2+1, padx=(0, 8))
        
        # Shadow Offset
        ttk.Label(scrollable_frame, text="Shadow Offset (X, Y):").grid(row=11, column=0, sticky="w")
        offset_frame = ttk.Frame(scrollable_frame)
        offset_frame.grid(row=11, column=1, sticky="w", padx=(10, 0))
        
        shadow_offset = intro_config.get("shadow_offset", [4, 4])
        self.shadow_x_var = tk.IntVar(value=shadow_offset[0])
        self.shadow_y_var = tk.IntVar(value=shadow_offset[1])
        
        ttk.Label(offset_frame, text="X:").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(offset_frame, from_=-20, to=20, textvariable=self.shadow_x_var, width=5).grid(row=0, column=1, padx=(2, 10))
        ttk.Label(offset_frame, text="Y:").grid(row=0, column=2, sticky="w")
        ttk.Spinbox(offset_frame, from_=-20, to=20, textvariable=self.shadow_y_var, width=5).grid(row=0, column=3, padx=(2, 0))
        
        # Rotation Settings
        ttk.Label(scrollable_frame, text="Rotation:", font=("Arial", 10, "bold")).grid(row=12, column=0, sticky="w", pady=(20, 5))
        
        rotation_config = intro_config.get("rotation", {})
        
        ttk.Label(scrollable_frame, text="Rotation Axis:").grid(row=13, column=0, sticky="w")
        self.rotation_axis_var = tk.StringVar(value=rotation_config.get("axis", "y"))
        axis_combo = ttk.Combobox(scrollable_frame, textvariable=self.rotation_axis_var,
                                 values=["x", "y", "z"], state="readonly", width=10)
        axis_combo.grid(row=13, column=1, sticky="w", padx=(10, 0))
        
        self.rotation_clockwise_var = tk.BooleanVar(value=rotation_config.get("clockwise", True))
        ttk.Checkbutton(scrollable_frame, text="Clockwise rotation", variable=self.rotation_clockwise_var).grid(row=14, column=0, columnspan=2, sticky="w", pady=5)
        
        # Store title controls for enable/disable
        self.title_controls = [self.title_text_widget, duration_spin, spacing_spin, font_path_entry, font_spin, weight_combo] + \
                             [child for child in color_frame.winfo_children() if isinstance(child, ttk.Spinbox)] + \
                             [child for child in shadow_frame.winfo_children() if isinstance(child, ttk.Spinbox)] + \
                             [child for child in offset_frame.winfo_children() if isinstance(child, ttk.Spinbox)] + \
                             [axis_combo]
        
        # Initial state
        self._toggle_intro_controls()
    
    def _create_advanced_settings(self):
        """Create advanced settings controls"""
        frame = self.advanced_frame
        
        # Create scrollable frame
        canvas = tk.Canvas(frame)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Video Quality Settings
        ttk.Label(scrollable_frame, text="Video Quality:", font=("Arial", 12, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 10))
        
        # Resolution
        ttk.Label(scrollable_frame, text="Resolution:").grid(row=1, column=0, sticky="w")
        current_res = self.config_data.get("resolution", [1920, 1080])
        self.resolution_var = tk.StringVar(value=f"{current_res[0]}x{current_res[1]}")
        res_combo = ttk.Combobox(scrollable_frame, textvariable=self.resolution_var,
                                values=["1920x1080", "1280x720", "3840x2160", "2560x1440"], 
                                state="readonly", width=15)
        res_combo.grid(row=1, column=1, sticky="w", padx=(10, 0))
        
        # FPS
        ttk.Label(scrollable_frame, text="Frame Rate (FPS):").grid(row=2, column=0, sticky="w")
        self.fps_var = tk.IntVar(value=self.config_data.get("fps", 30))
        fps_combo = ttk.Combobox(scrollable_frame, textvariable=self.fps_var,
                                values=[24, 25, 30, 50, 60], state="readonly", width=10)
        fps_combo.grid(row=2, column=1, sticky="w", padx=(10, 0))
        
        # Performance Settings
        ttk.Separator(scrollable_frame, orient="horizontal").grid(row=3, column=0, columnspan=2, sticky="ew", pady=20)
        ttk.Label(scrollable_frame, text="Performance:", font=("Arial", 12, "bold")).grid(row=4, column=0, sticky="w", pady=(0, 10))
        
        # Hardware Acceleration
        self.hw_accel_var = tk.BooleanVar(value=self.config_data.get("hardware_acceleration", False))
        ttk.Checkbutton(scrollable_frame, text="Enable hardware acceleration (experimental)", 
                       variable=self.hw_accel_var).grid(row=5, column=0, columnspan=2, sticky="w")
        
        # Temp Directory
        ttk.Label(scrollable_frame, text="Temporary Directory:").grid(row=6, column=0, sticky="w", pady=(10, 0))
        self.temp_dir_var = tk.StringVar(value=self.config_data.get("temp_directory", ""))
        temp_frame = ttk.Frame(scrollable_frame)
        temp_frame.grid(row=6, column=1, sticky="w", padx=(10, 0), pady=(10, 0))
        ttk.Entry(temp_frame, textvariable=self.temp_dir_var, width=30).grid(row=0, column=0)
        ttk.Button(temp_frame, text="Browse", command=self._browse_temp_dir).grid(row=0, column=1, padx=(5, 0))
        
        # Cleanup Settings
        ttk.Separator(scrollable_frame, orient="horizontal").grid(row=7, column=0, columnspan=2, sticky="ew", pady=20)
        ttk.Label(scrollable_frame, text="Cleanup:", font=("Arial", 12, "bold")).grid(row=8, column=0, sticky="w", pady=(0, 10))
        
        self.keep_frames_var = tk.BooleanVar(value=self.config_data.get("keep_intermediate_frames", False))
        ttk.Checkbutton(scrollable_frame, text="Keep intermediate frames for debugging (required for video editor)", 
                       variable=self.keep_frames_var).grid(row=9, column=0, columnspan=2, sticky="w")
        
        # FFmpeg Cache Settings
        ttk.Separator(scrollable_frame, orient="horizontal").grid(row=11, column=0, columnspan=2, sticky="ew", pady=20)
        ttk.Label(scrollable_frame, text="FFmpeg Cache:", font=("Arial", 12, "bold")).grid(row=12, column=0, sticky="w", pady=(0, 10))
        
        self.ffmpeg_cache_enabled_var = tk.BooleanVar(value=self.config_data.get("ffmpeg_cache_enabled", True))
        ttk.Checkbutton(scrollable_frame, text="Enable FFmpeg caching (improves performance)", 
                       variable=self.ffmpeg_cache_enabled_var,
                       command=self._toggle_cache_controls).grid(row=13, column=0, columnspan=2, sticky="w")
        
        # Cache Directory
        ttk.Label(scrollable_frame, text="Cache Directory:").grid(row=14, column=0, sticky="w", pady=(10, 0))
        self.ffmpeg_cache_dir_var = tk.StringVar(value=self.config_data.get("ffmpeg_cache_dir", ""))
        cache_frame = ttk.Frame(scrollable_frame)
        cache_frame.grid(row=14, column=1, sticky="w", padx=(10, 0), pady=(10, 0))
        self.cache_dir_entry = ttk.Entry(cache_frame, textvariable=self.ffmpeg_cache_dir_var, width=30)
        self.cache_dir_entry.grid(row=0, column=0)
        self.cache_browse_btn = ttk.Button(cache_frame, text="Browse", command=self._browse_cache_dir)
        self.cache_browse_btn.grid(row=0, column=1, padx=(5, 0))
        
        # Cache info and management
        cache_info_frame = ttk.Frame(scrollable_frame)
        cache_info_frame.grid(row=15, column=0, columnspan=2, sticky="w", pady=(10, 0))
        ttk.Label(cache_info_frame, text="(Leave empty to use default: output_folder/working/ffmpeg_cache)",
                 foreground="gray").grid(row=0, column=0, sticky="w")
        
        # Cache management buttons
        cache_mgmt_frame = ttk.Frame(scrollable_frame)
        cache_mgmt_frame.grid(row=16, column=0, columnspan=2, sticky="w", pady=(10, 0))
        self.cache_stats_btn = ttk.Button(cache_mgmt_frame, text="View Cache Stats", command=self._show_cache_stats)
        self.cache_stats_btn.grid(row=0, column=0, padx=(0, 10))
        self.cache_browse_btn2 = ttk.Button(cache_mgmt_frame, text="Browse Cache Contents", command=self._browse_cache_contents)
        self.cache_browse_btn2.grid(row=0, column=1, padx=(0, 10))
        self.cache_clear_btn = ttk.Button(cache_mgmt_frame, text="Clear Cache", command=self._clear_cache)
        self.cache_clear_btn.grid(row=0, column=2, padx=(0, 10))
        self.cache_cleanup_btn = ttk.Button(cache_mgmt_frame, text="Cleanup Old Entries", command=self._cleanup_cache)
        self.cache_cleanup_btn.grid(row=0, column=3, padx=(0, 10))
        self.cache_reset_stats_btn = ttk.Button(cache_mgmt_frame, text="Reset Stats", command=self._reset_cache_stats)
        self.cache_reset_stats_btn.grid(row=0, column=4)
        
        # Set initial state of cache controls
        self._toggle_cache_controls()
    
    def _get_transition_options(self):
        """Get available transition options with descriptions"""
        try:
            from slideshow.transitions import list_available_transitions
            available = list_available_transitions()
            
            options = {}
            for trans in available:
                options[trans['name']] = {
                    'display_name': trans['display_name'],
                    'description': trans.get('description', '')
                }
            
            # Add manual descriptions for key transitions
            descriptions = {
                'fade': 'Simple cross-fade between slides',
                'origami': 'Advanced paper-folding animation with realistic lighting',
                'wipe': 'Slide wipe transition',
                'push': 'Push transition effect'
            }
            
            for name, desc in descriptions.items():
                if name in options and not options[name]['description']:
                    options[name]['description'] = desc
            
            return options
        except:
            # Fallback
            return {
                'fade': {'display_name': 'Fade', 'description': 'Simple cross-fade between slides'},
                'origami': {'display_name': 'Origami', 'description': 'Advanced paper-folding animation'}
            }
    
    def _toggle_intro_controls(self):
        """Enable/disable intro title controls based on checkbox"""
        state = "normal" if self.intro_enabled_var.get() else "disabled"
        for control in self.title_controls:
            if hasattr(control, 'configure'):
                control.configure(state=state)
    
    def _browse_font_file(self):
        """Browse for font file"""
        from tkinter import filedialog
        from slideshow.config import Config
        
        # Common font file extensions
        filetypes = [
            ("Font Files", "*.ttf *.otf *.ttc"),
            ("TrueType Fonts", "*.ttf"),
            ("OpenType Fonts", "*.otf"), 
            ("TrueType Collections", "*.ttc"),
            ("All Files", "*.*")
        ]
        
        filename = filedialog.askopenfilename(
            title="Select Font File",
            filetypes=filetypes,
            initialdir=Config.instance().get_font_initial_dir()
        )
        
        if filename:
            self.font_path_var.set(filename)
    
    def _browse_temp_dir(self):
        """Browse for temporary directory"""
        import os
        from tkinter import filedialog
        current_dir = self.temp_dir_var.get()
        initial_dir = current_dir if current_dir else os.path.expanduser('~')
        directory = filedialog.askdirectory(initialdir=initial_dir)
        if directory:
            self.temp_dir_var.set(directory)
    
    def _browse_cache_dir(self):
        """Browse for FFmpeg cache directory"""
        import os
        from tkinter import filedialog
        current_dir = self.ffmpeg_cache_dir_var.get()
        initial_dir = current_dir if current_dir else os.path.expanduser('~')
        directory = filedialog.askdirectory(initialdir=initial_dir)
        if directory:
            self.ffmpeg_cache_dir_var.set(directory)
    
    def _toggle_cache_controls(self):
        """Enable/disable cache controls based on cache enabled checkbox"""
        enabled = self.ffmpeg_cache_enabled_var.get()
        state = "normal" if enabled else "disabled"
        
        self.cache_dir_entry.config(state=state)
        self.cache_browse_btn.config(state=state)
        self.cache_stats_btn.config(state=state)
        self.cache_browse_btn2.config(state=state)
        self.cache_clear_btn.config(state=state)
        self.cache_cleanup_btn.config(state=state)
        self.cache_reset_stats_btn.config(state=state)
    
    def _show_cache_stats(self):
        """Show cache statistics in a dialog"""
        try:
            from slideshow.transitions.ffmpeg_cache import FFmpegCache
            
            # Cache auto-configures itself now
            stats = FFmpegCache.get_cache_stats()
            
            if stats.get("enabled", False):
                total_requests = stats.get('total_requests', 0)
                hit_rate = stats.get('hit_rate_percent', 0)
                operations = stats.get('operations', {})
                
                # Always show performance info section
                performance_info = f"""
Performance Statistics:
- Cache Hits: {stats.get('cache_hits', 0)}
- Cache Misses: {stats.get('cache_misses', 0)}
- Hit Rate: {hit_rate}% ({total_requests} total requests)

Cache Effectiveness: {'Excellent' if hit_rate >= 80 else 'Good' if hit_rate >= 50 else 'Poor' if hit_rate >= 20 else 'Very Poor' if total_requests > 10 else 'No usage data yet'}"""
                
                operations_info = ""
                if operations:
                    operations_info = f"""
Cached Operations:
""" + "\n".join([f"- {op}: {count} entries" for op, count in operations.items()])
                
                message = f"""FFmpeg Cache Statistics:
                
Cache Directory: {stats['cache_dir']}
Total Entries: {stats['total_entries']}
- Video Clips: {stats['clip_count']}
- Extracted Frames: {stats['frame_count']}
Total Size: {stats['total_size_mb']:.1f} MB{operations_info}{performance_info}

Cache Status: {'Enabled' if stats['enabled'] else 'Disabled'}"""
            else:
                message = "FFmpeg cache is disabled."
                
            wide_messagebox("info", "Cache Statistics", message)
            
        except Exception as e:
            wide_messagebox("error", "Error", f"Failed to get cache statistics:\\n{str(e)}")
    
    def _clear_cache(self):
        """Clear the entire FFmpeg cache"""
        result = wide_messagebox("question", "Clear Cache",
                                "Are you sure you want to clear the entire FFmpeg cache?\n"
                                "This will delete all cached video clips, frames, and slide order cache.")
        if result:
            try:
                import shutil
                
                # Get output folder from config
                output_folder = Path(self.config_data.get("output_folder", ""))
                if not output_folder or not output_folder.exists():
                    wide_messagebox("error", "Error", "Output folder not configured")
                    return
                
                # Working dir is output_folder/working
                working_dir = output_folder / "working"
                cache_dir = working_dir / "ffmpeg_cache"
                
                if cache_dir.exists():
                    shutil.rmtree(cache_dir)
                    if hasattr(self, 'parent') and hasattr(self.parent, 'log_message'):
                        self.parent.log_message("[Cache] All caches cleared successfully")
                    wide_messagebox("info", "Success", "Cache cleared successfully")
                else:
                    wide_messagebox("info", "Info", "Cache directory does not exist")
            except Exception as e:
                wide_messagebox("error", "Error", f"Failed to clear cache:\n{str(e)}")
                if hasattr(self, 'parent') and hasattr(self.parent, 'log_message'):
                    self.parent.log_message(f"[Cache] Error clearing cache: {e}")
    
    def _cleanup_cache(self):
        """Clean up old cache entries"""
        result = wide_messagebox("question", "Cleanup Cache",
                                "Remove cache entries older than 30 days?")
        if result:
            try:
                from slideshow.transitions.ffmpeg_cache import FFmpegCache
                
                # Cache auto-configures itself now
                FFmpegCache.cleanup_old_entries(30)
                # No confirmation - user already pressed OK
            except Exception as e:
                wide_messagebox("error", "Error", f"Failed to cleanup cache:\n{str(e)}")
    
    def _reset_cache_stats(self):
        """Reset cache hit/miss statistics"""
        result = wide_messagebox("question", "Reset Cache Statistics",
                                "Reset cache hit/miss statistics to zero?\n\nThis will not affect cached files, only the performance counters.")
        if result:
            try:
                from slideshow.transitions.ffmpeg_cache import FFmpegCache
                
                # Cache auto-configures itself now
                FFmpegCache.reset_stats()
                
                # No confirmation - user already pressed OK
            except Exception as e:
                wide_messagebox("error", "Error", f"Failed to reset cache statistics:\n{str(e)}")
    
    def _browse_cache_contents(self):
        """Show detailed cache contents browser"""
        try:
            from slideshow.transitions.ffmpeg_cache import FFmpegCache
            
            # Cache auto-configures itself now
            cache_data = FFmpegCache.get_cache_entries_with_sources()
            
            if not cache_data.get("enabled", False):
                messagebox.showinfo("Cache Browser", "FFmpeg cache is disabled.")
                return
            
            # Create cache browser window
            browser_window = tk.Toplevel(self.parent)
            browser_window.title("Cache Contents Browser")
            browser_window.geometry("900x600")
            browser_window.transient(self.parent)
            browser_window.grab_set()
            
            # Center the window on the desktop
            browser_window.update_idletasks()
            window_width = 900
            window_height = 600
            
            screen_width = browser_window.winfo_screenwidth()
            screen_height = browser_window.winfo_screenheight()
            
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
            
            browser_window.geometry(f"{window_width}x{window_height}+{x}+{y}")
            
            # Main frame with scrollbar
            main_frame = ttk.Frame(browser_window)
            main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # Info label
            clips = cache_data.get('clips', [])
            frames = cache_data.get('frames', [])
            
            info_label = ttk.Label(main_frame, 
                                 text=f"Cache Contents: {len(clips)} clips, {len(frames)} frames ({cache_data['total_entries']} total)",
                                 font=("Arial", 12, "bold"))
            info_label.pack(pady=(0, 10))
            
            # Create notebook for tabs
            notebook = ttk.Notebook(main_frame)
            notebook.pack(fill=tk.BOTH, expand=True)
            
            clips_frame = ttk.Frame(notebook)
            frames_frame = ttk.Frame(notebook)
            
            notebook.add(clips_frame, text=f"Video Clips ({len(clips)})")
            notebook.add(frames_frame, text=f"Extracted Frames ({len(frames)})")
            
            def create_cache_tree(parent_frame, entries, show_frame_number=False):
                tree_frame = ttk.Frame(parent_frame)
                tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
                
                if show_frame_number:
                    columns = ('Source File', 'Operation', 'Frame #', 'Size (MB)', 'Cache File')
                else:
                    columns = ('Source File', 'Operation', 'Duration', 'Size (MB)', 'Cache File')
                
                tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=12)
                
                tree.heading('Source File', text='Source File')
                tree.heading('Operation', text='Operation')
                if show_frame_number:
                    tree.heading('Frame #', text='Frame #')
                else:
                    tree.heading('Duration', text='Duration (s)')
                tree.heading('Size (MB)', text='Size (MB)')
                tree.heading('Cache File', text='Cache File')
                
                tree.column('Source File', width=200)
                tree.column('Operation', width=150)
                if show_frame_number:
                    tree.column('Frame #', width=80)
                else:
                    tree.column('Duration', width=80)
                tree.column('Size (MB)', width=80)
                tree.column('Cache File', width=300)
                
                v_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
                h_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=tree.xview)
                tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
                
                tree.grid(row=0, column=0, sticky='nsew')
                v_scrollbar.grid(row=0, column=1, sticky='ns')
                h_scrollbar.grid(row=1, column=0, sticky='ew')
                
                tree_frame.grid_rowconfigure(0, weight=1)
                tree_frame.grid_columnconfigure(0, weight=1)
                
                for entry in entries:
                    if show_frame_number:
                        frame_num = "N/A"
                        if 'params' in entry and 'timestamp' in entry['params']:
                            frame_num = f"{entry['params']['timestamp']:.2f}s"
                        
                        tree.insert('', tk.END, values=(
                            entry['source_file'],
                            entry['operation'],
                            frame_num,
                            entry['size_mb'],
                            entry['cache_key'] + '.png'
                        ))
                    else:
                        duration = "N/A"
                        if 'params' in entry and 'duration' in entry['params']:
                            duration = f"{entry['params']['duration']:.1f}"
                        
                        tree.insert('', tk.END, values=(
                            entry['source_file'],
                            entry['operation'],
                            duration,
                            entry['size_mb'],
                            entry['cache_key'] + '.mp4'
                        ))
                
                return tree
            
            clips_tree = create_cache_tree(clips_frame, clips, show_frame_number=False)
            frames_tree = create_cache_tree(frames_frame, frames, show_frame_number=True)
            
            # Details frame
            details_frame = ttk.LabelFrame(main_frame, text="Entry Details", padding=10)
            details_frame.pack(fill=tk.BOTH, expand=False, pady=(10, 0))
            
            details_text = tk.Text(details_frame, height=8, width=80, wrap=tk.WORD)
            details_scrollbar = ttk.Scrollbar(details_frame, orient=tk.VERTICAL, command=details_text.yview)
            details_text.configure(yscrollcommand=details_scrollbar.set)
            details_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            details_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            def on_tree_select(event):
                selected_tree = event.widget
                selection = selected_tree.selection()
                if selection:
                    item = selected_tree.item(selection[0])
                    source_file = item['values'][0]
                    
                    if selected_tree == clips_tree:
                        frames_tree.selection_remove(frames_tree.selection())
                    else:
                        clips_tree.selection_remove(clips_tree.selection())
                    
                    for entry in cache_data.get('entries', []):
                        if entry['source_file'] == source_file:
                            details = f"""Source File: {entry['source_file']}
Full Source Path: {entry['source_path']}
Operation: {entry['operation']}
Type: {entry['type']}
Size: {entry['size_mb']} MB
Cache Key: {entry['cache_key']}
Cached File: {entry['cached_file']}

Parameters:
"""
                            for key, value in entry['params'].items():
                                details += f"  {key}: {value}\n"
                            
                            details_text.delete(1.0, tk.END)
                            details_text.insert(1.0, details)
                            break
            
            def on_double_click(event):
                selected_tree = event.widget
                selection = selected_tree.selection()
                
                if not selection:
                    return
                
                try:
                    item = selected_tree.item(selection[0])
                    source_file = item['values'][0]
                    
                    for entry in cache_data.get('entries', []):
                        if entry['source_file'] == source_file:
                            cache_file_path = entry['cached_file']
                            import subprocess
                            subprocess.run(['open', cache_file_path], check=True)
                            break
                    else:
                        messagebox.showerror("Error", f"Cache file not found for: {source_file}")
                        
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to open cache file:\n{str(e)}")
            
            clips_tree.bind('<<TreeviewSelect>>', on_tree_select)
            frames_tree.bind('<<TreeviewSelect>>', on_tree_select)
            clips_tree.bind('<Double-1>', on_double_click)
            frames_tree.bind('<Double-1>', on_double_click)
            
            def view_selected():
                clips_selection = clips_tree.selection()
                frames_selection = frames_tree.selection()
                
                selected_tree = None
                selection = None
                
                if clips_selection:
                    selected_tree = clips_tree
                    selection = clips_selection
                elif frames_selection:
                    selected_tree = frames_tree
                    selection = frames_selection
                
                if not selection:
                    messagebox.showinfo("No Selection", "Please select a cache entry to view.")
                    return
                
                try:
                    item = selected_tree.item(selection[0])
                    source_file = item['values'][0]
                    
                    for entry in cache_data.get('entries', []):
                        if entry['source_file'] == source_file:
                            cache_file_path = entry['cached_file']
                            import subprocess
                            subprocess.run(['open', cache_file_path], check=True)
                            break
                    else:
                        messagebox.showerror("Error", f"Cache file not found for: {source_file}")
                        
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to open cache file:\n{str(e)}")
            
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(pady=(10, 0))
            
            def copy_to_clipboard():
                """Copy cache contents to clipboard in a readable format"""
                try:
                    import json
                    
                    text = f"Cache Contents Summary\n"
                    text += f"{'='*60}\n\n"
                    text += f"Total Entries: {cache_data['total_entries']}\n"
                    text += f"Video Clips: {len(clips)}\n"
                    text += f"Extracted Frames: {len(frames)}\n\n"
                    
                    if clips:
                        text += f"\nVIDEO CLIPS ({len(clips)}):\n"
                        text += f"{'-'*60}\n"
                        for i, entry in enumerate(clips, 1):
                            text += f"\n{i}. {entry['source_file']}\n"
                            text += f"   Operation: {entry['operation']}\n"
                            text += f"   Size: {entry['size_mb']} MB\n"
                            text += f"   Cache Key: {entry['cache_key']}\n"
                            text += f"   Parameters: {json.dumps(entry['params'], indent=6)}\n"
                    
                    if frames:
                        text += f"\n\nEXTRACTED FRAMES ({len(frames)}):\n"
                        text += f"{'-'*60}\n"
                        for i, entry in enumerate(frames, 1):
                            text += f"\n{i}. {entry['source_file']}\n"
                            text += f"   Operation: {entry['operation']}\n"
                            text += f"   Size: {entry['size_mb']} MB\n"
                            text += f"   Cache Key: {entry['cache_key']}\n"
                            text += f"   Parameters: {json.dumps(entry['params'], indent=6)}\n"
                    
                    browser_window.clipboard_clear()
                    browser_window.clipboard_append(text)
                    browser_window.update()
                    
                    messagebox.showinfo("Success", "Cache contents copied to clipboard!")
                    
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to copy to clipboard:\n{str(e)}")
            
            copy_btn = ttk.Button(button_frame, text="Copy to Clipboard", command=copy_to_clipboard)
            copy_btn.pack(side=tk.LEFT, padx=(0, 10))
            
            view_btn = ttk.Button(button_frame, text="View Selected", command=view_selected)
            view_btn.pack(side=tk.LEFT, padx=(0, 10))
            
            close_btn = ttk.Button(button_frame, text="Close", command=browser_window.destroy)
            close_btn.pack(side=tk.LEFT)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to browse cache contents:\\n{str(e)}")
    
    def _apply_settings(self):
        """Apply current settings to config"""
        # Basic transition settings
        self.config_data["transition_type"] = self.transition_type_var.get()
        self.config_data["origami_easing"] = self.easing_var.get()
        self.config_data["origami_lighting"] = self.lighting_var.get()
        self.config_data["origami_fold"] = self.fold_direction_var.get()
        
        # Title settings
        title_text = self.title_text_widget.get(1.0, tk.END).strip()
        # Convert actual newlines to \\n for JSON storage
        title_text = title_text.replace('\n', '\\n')
        
        intro_config = {
            "enabled": self.intro_enabled_var.get(),
            "text": title_text,
            "duration": self.title_duration_var.get(),
            "font_path": self.font_path_var.get(),
            "font_size": self.font_size_var.get(),
            "font_weight": self.font_weight_var.get(),
            "line_spacing": self.line_spacing_var.get(),
            "text_color": [self.text_r_var.get(), self.text_g_var.get(), self.text_b_var.get(), self.text_a_var.get()],
            "shadow_color": [self.shadow_r_var.get(), self.shadow_g_var.get(), self.shadow_b_var.get(), self.shadow_a_var.get()],
            "shadow_offset": [self.shadow_x_var.get(), self.shadow_y_var.get()],
            "rotation": {
                "axis": self.rotation_axis_var.get(),
                "clockwise": self.rotation_clockwise_var.get()
            }
        }
        self.config_data["intro_title"] = intro_config
        
        # Advanced settings
        res_str = self.resolution_var.get()
        width, height = map(int, res_str.split('x'))
        self.config_data["resolution"] = [width, height]
        self.config_data["fps"] = self.fps_var.get()
        self.config_data["hardware_acceleration"] = self.hw_accel_var.get()
        self.config_data["temp_directory"] = self.temp_dir_var.get()
        self.config_data["keep_intermediate_frames"] = self.keep_frames_var.get()
        
        # FFmpeg cache settings
        self.config_data["ffmpeg_cache_enabled"] = self.ffmpeg_cache_enabled_var.get()
        self.config_data["ffmpeg_cache_dir"] = self.ffmpeg_cache_dir_var.get().strip()
        
        # Update parent's config and GUI
        self.parent.config_data = self.config_data
        self.parent._auto_save_config()
        
        # Update transition combo in main GUI if needed
        if hasattr(self.parent, 'transition_var'):
            self.parent.transition_var.set(self.config_data["transition_type"])
    
    def _reset_clicked(self):
        """Reset all settings to defaults"""
        from slideshow.config import DEFAULT_CONFIG
        result = messagebox.askyesno("Reset Settings", 
                                   "This will reset all settings to their default values. Continue?")
        if result:
            self.config_data = DEFAULT_CONFIG.copy()
            self.dialog.destroy()
            # Reopen with defaults
            SettingsDialog(self.parent)
    
    def _ok_clicked(self):
        """OK button clicked - apply and close"""
        self._apply_settings()
        self.parent.log_message("Settings saved successfully")
        self.dialog.destroy()
    
    def _apply_clicked(self):
        """Apply button clicked - apply without closing"""
        self._apply_settings()
        self.parent.log_message("Settings applied")
    
    def _cancel_clicked(self):
        """Cancel button clicked - close without saving"""
        self.dialog.destroy()
