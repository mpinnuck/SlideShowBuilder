import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, font
import threading
import sys
import re
import shutil
from pathlib import Path
from PIL import Image, ImageTk, ImageOps
from slideshow.config import load_config, save_config, save_app_settings, load_app_settings, get_project_config_path, add_to_project_history, get_project_history
from slideshow.transitions.ffmpeg_cache import FFmpegCache

from slideshow.gui.helpers import wide_messagebox, sanitize_project_name, build_project_paths, build_output_path
from slideshow.gui.image_rotator import ImageRotatorDialog
from slideshow.gui.settings_dialog import SettingsDialog
from slideshow.gui.app_settings_dialog import AppSettingsDialog


class GUI(tk.Tk):
    def __init__(self, version="1.0.0"):
        super().__init__()
        self.title(f"Slideshow Builder v{version}")
        
        # Load custom slideshows base directory if configured
        self._load_custom_slideshows_dir()
        
        # Set application icon
        try:
            icon_path = Path(__file__).parent.parent / "assets" / "slideshowbuilder.png"
            if icon_path.exists():
                icon_photo = tk.PhotoImage(file=str(icon_path))
                self.iconphoto(True, icon_photo)
        except Exception as e:
            # Silently continue if icon can't be loaded
            pass
        
        # Load config - will try to load from last project
        self.config_data = load_config()
        self.cancel_requested = False  # Flag for cancellation
        self.cached_slides = None  # Cache slides from export to reuse in preview
        self.create_widgets()
        self.center_window()
        
        # Check initial Play button state
        self._check_play_button_state()
    
    def _load_custom_slideshows_dir(self):
        """Load custom slideshows base directory from app settings"""
        from slideshow.config import Config
        import json
        
        # First check the default location for settings file
        default_settings_dir = Path.home() / "SlideShowBuilder"
        default_settings_file = default_settings_dir / "slideshow_settings.json"
        
        custom_dir = str(default_settings_dir)  # Start with default
        
        # Try to load settings from default location
        if default_settings_file.exists():
            try:
                with open(default_settings_file, "r") as f:
                    settings = json.load(f)
                    custom_dir = settings.get("slideshows_base_dir", str(default_settings_dir))
            except (json.JSONDecodeError, OSError):
                pass  # Use default if loading fails
        
        # Update the Config class constants with the configured directory
        # Use expanduser() to handle ~ in paths
        Config.APP_SETTINGS_DIR = Path(custom_dir).expanduser()
        Config.APP_SETTINGS_FILE = Config.APP_SETTINGS_DIR / "slideshow_settings.json"
        
        # Ensure the directory exists
        Config.APP_SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    
    def center_window(self):
            # Set initial size before centering
            initial_width = 920  # 15% larger than 800 (800 * 1.15 = 920)
            initial_height = 600  # Keep height same
            
            self.update_idletasks()
            
            # Use our preferred size if larger than the natural size
            natural_width = self.winfo_width()
            natural_height = self.winfo_height()
            
            w = max(initial_width, natural_width)
            h = max(initial_height, natural_height)
            
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            x = (sw // 2) - (w // 2)
            y = (sh // 2) - (h // 2)
            self.geometry(f"{w}x{h}+{x}+{y}")
            self.minsize(920, 500)  # Update minimum width to match initial

    def create_widgets(self):
        # Project Info with history dropdown
        ttk.Label(self, text="Project Name:").grid(row=0, column=0, sticky="e")
        self.name_var = tk.StringVar(value=self.config_data.get("project_name", "Untitled"))
        
        # Get project history for dropdown
        self.project_history = get_project_history()
        
        # Use combobox for project name with history - display names only
        project_names = [entry["name"] for entry in self.project_history]
        self.name_combo = ttk.Combobox(self, textvariable=self.name_var, width=38, values=project_names)
        self.name_combo.grid(row=0, column=1, columnspan=2, sticky="we")
        self.name_combo.bind('<FocusIn>', lambda e: self._on_project_name_focus_in())
        self.name_combo.bind('<FocusOut>', lambda e: self._on_project_name_focus_out())
        self.name_combo.bind('<Return>', lambda e: self._on_project_name_focus_out())
        self.name_combo.bind('<<ComboboxSelected>>', lambda e: self._on_project_selected())
        
        # Store the project name when focus is gained
        self._project_name_on_focus = ""
        
        # Project Path (read-only display below project name)
        ttk.Label(self, text="Project Path:").grid(row=1, column=0, sticky="e")
        self.project_path_var = tk.StringVar(value="")
        path_label = ttk.Label(self, textvariable=self.project_path_var, foreground="gray")
        path_label.grid(row=1, column=1, columnspan=2, sticky="w", padx=(5, 0))
        
        ttk.Button(self, text="Browse", command=self.select_slideshows_folder).grid(row=1, column=2)

        # Input Folder (now row 2)
        ttk.Label(self, text="Input Folder:").grid(row=2, column=0, sticky="e")
        self.input_var = tk.StringVar(value=self.config_data.get("input_folder", ""))
        self.input_var.trace_add('write', lambda *args: self._invalidate_slide_cache())
        self.input_var.trace_add('write', lambda *args: self._auto_save_config())
        ttk.Entry(self, textvariable=self.input_var, width=40).grid(row=2, column=1, sticky="we")
        ttk.Button(self, text="Browse", command=self.select_input_folder).grid(row=2, column=2)

        # Output Folder
        ttk.Label(self, text="Output Folder:").grid(row=3, column=0, sticky="e")
        self.output_var = tk.StringVar(value=self.config_data.get("output_folder", ""))
        output_entry = ttk.Entry(self, textvariable=self.output_var, width=40)
        output_entry.grid(row=3, column=1, sticky="we")
        output_entry.bind('<FocusOut>', lambda e: self._auto_save_config())
        output_entry.bind('<Return>', lambda e: self._auto_save_config())
        ttk.Button(self, text="Browse", command=self.select_output_folder).grid(row=3, column=2)

        # Soundtrack
        ttk.Label(self, text="Soundtrack File:").grid(row=4, column=0, sticky="e")
        self.soundtrack_var = tk.StringVar(value=self.config_data.get("soundtrack", ""))
        self.soundtrack_var.trace_add('write', lambda *args: self._auto_save_config())
        ttk.Entry(self, textvariable=self.soundtrack_var, width=40).grid(row=4, column=1, sticky="we")
        ttk.Button(self, text="Browse", command=self.select_soundtrack).grid(row=4, column=2)

        # Durations
        ttk.Label(self, text="Photo Duration (s):").grid(row=5, column=0, sticky="e")
        self.photo_dur_var = tk.IntVar(value=self.config_data.get("photo_duration", 3))
        self.photo_dur_var.trace_add('write', lambda *args: self._auto_save_config())
        ttk.Entry(self, textvariable=self.photo_dur_var, width=5).grid(row=5, column=1, sticky="w", padx=(5, 0))

        # Transition Type (positioned right after Photo Duration in same column area)
        ttk.Label(self, text="Transition:").grid(row=5, column=1, sticky="w", padx=(80, 5))
        self.transition_var = tk.StringVar(value=self.config_data.get("transition_type", "fade"))
        self.transition_var.trace_add('write', lambda *args: self._auto_save_config())
        # Log the change for manual verification
        self.transition_var.trace_add('write', lambda *args: self.log_message(f"Transition type changed to: {self.transition_var.get()}"))
        self.transition_combo = ttk.Combobox(self, textvariable=self.transition_var, width=12, state="readonly")
        self.transition_combo.grid(row=5, column=1, sticky="w", padx=(150, 0))
        self._populate_transitions()
        
        # Checkboxes frame (to the right of transition)
        options_frame = ttk.Frame(self)
        options_frame.grid(row=5, column=1, columnspan=2, sticky="e", padx=(0, 5))
        
        # Sort by filename checkbox (leftmost)
        self.sort_by_filename_var = tk.BooleanVar(value=self.config_data.get("sort_by_filename", False))
        self.sort_by_filename_var.trace_add('write', lambda *args: self._invalidate_slide_cache())
        self.sort_by_filename_var.trace_add('write', lambda *args: self._auto_save_config())
        sort_by_filename_check = ttk.Checkbutton(options_frame, text="Sort by Filename", 
                                                   variable=self.sort_by_filename_var)
        sort_by_filename_check.grid(row=0, column=0, sticky="w", padx=(0, 10))
        
        # Recurse checkbox (rightmost)
        self.recurse_var = tk.BooleanVar(value=self.config_data.get("recurse_folders", False))
        self.recurse_var.trace_add('write', lambda *args: self._invalidate_slide_cache())
        self.recurse_var.trace_add('write', lambda *args: self._auto_save_config())
        recurse_check = ttk.Checkbutton(options_frame, text="Recurse", variable=self.recurse_var)
        recurse_check.grid(row=0, column=1, sticky="w")

        ttk.Label(self, text="Video Duration (s):").grid(row=6, column=0, sticky="e")
        self.video_dur_var = tk.IntVar(value=self.config_data.get("video_duration", 10))
        self.video_dur_var.trace_add('write', lambda *args: self._auto_save_config())
        ttk.Entry(self, textvariable=self.video_dur_var, width=5).grid(row=6, column=1, sticky="w", padx=(5, 0))

        # MultiSlide Frequency (positioned right after Video Duration in same column area)
        ttk.Label(self, text="MultiSlide Freq:").grid(row=6, column=1, sticky="w", padx=(80, 5))
        self.multislide_freq_var = tk.IntVar(value=self.config_data.get("multislide_frequency", 10))
        self.multislide_freq_var.trace_add('write', lambda *args: self._auto_save_config())
        ttk.Entry(self, textvariable=self.multislide_freq_var, width=5).grid(row=6, column=1, sticky="w", padx=(200, 0))
        ttk.Label(self, text="(0=off)", font=("TkDefaultFont", 8)).grid(row=6, column=1, sticky="w", padx=(270, 0))

        ttk.Label(self, text="Transition Duration (s):").grid(row=7, column=0, sticky="e")
        self.trans_dur_var = tk.IntVar(value=self.config_data.get("transition_duration", 1))
        self.trans_dur_var.trace_add('write', lambda *args: self._auto_save_config())
        ttk.Entry(self, textvariable=self.trans_dur_var, width=5).grid(row=7, column=1, sticky="w", padx=(5, 0))

        # Video Quality (positioned right after Transition Duration in same column area as MultiSlide Freq)
        ttk.Label(self, text="Video Quality:").grid(row=7, column=1, sticky="w", padx=(80, 5))
        self.video_quality_var = tk.StringVar(value=self.config_data.get("video_quality", "maximum"))
        self.video_quality_var.trace_add('write', lambda *args: self._on_video_quality_change())
        quality_combo = ttk.Combobox(self, textvariable=self.video_quality_var, width=10, state="readonly")
        quality_combo['values'] = ('maximum', 'high', 'medium', 'fast')
        quality_combo.grid(row=7, column=1, sticky="w", padx=(190, 0))

        # Buttons
        self.button_frame = ttk.Frame(self)
        self.button_frame.grid(row=8, column=0, columnspan=4, sticky="w", pady=5)
        
        self.export_button = ttk.Button(self.button_frame, text="Export Video", command=self.export_video)
        self.export_button.pack(side=tk.LEFT, padx=(0, 3))
        self.play_button = ttk.Button(self.button_frame, text="Play Slideshow", command=self.play_slideshow)
        self.play_button.pack(side=tk.LEFT, padx=(0, 6))  # Double spacing before next section
        ttk.Button(self.button_frame, text="Preview & Rotate Images", command=self.open_image_rotator).pack(side=tk.LEFT, padx=(0, 3))
        ttk.Button(self.button_frame, text="Settings", command=self.open_settings).pack(side=tk.LEFT, padx=(0, 3))
        ttk.Button(self.button_frame, text="App Settings", command=self.open_app_settings).pack(side=tk.LEFT, padx=(0, 3))
        ttk.Button(self.button_frame, text="Save Config", command=self.save_config).pack(side=tk.LEFT, padx=(0, 3))
        self.cancel_button = ttk.Button(self.button_frame, text="Cancel", command=self.cancel_export, state='disabled')
        self.cancel_button.pack(side=tk.LEFT, padx=(0, 3))
        ttk.Button(self.button_frame, text="Project Rename", command=self.rename_project).pack(side=tk.LEFT)

        # Progress Bar
        ttk.Label(self, text="Progress:").grid(row=9, column=0, sticky="nw", pady=(10, 0))
        self.progress = ttk.Progressbar(self, mode='determinate')
        self.progress.grid(row=9, column=1, columnspan=3, sticky="ew", padx=(5, 0), pady=(10, 0))

        # Log Panel
        ttk.Label(self, text="Log:").grid(row=10, column=0, sticky="nw", pady=(10, 0))
        
        # Create frame for log panel with scrollbars
        log_frame = ttk.Frame(self)
        log_frame.grid(row=11, column=0, columnspan=4, sticky="ewns", padx=5, pady=5)
        
        # Configure log frame grid
        log_frame.grid_rowconfigure(0, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)
        
        # Text widget for log
        self.log_text = tk.Text(log_frame, height=8, width=80, wrap=tk.WORD, state=tk.DISABLED)
        self.log_text.grid(row=0, column=0, sticky="ewns")
        
        # Add clipboard support for log panel
        self._setup_log_clipboard_support()
        
        # Vertical scrollbar
        v_scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=v_scrollbar.set)
        
        # Horizontal scrollbar
        h_scrollbar = ttk.Scrollbar(log_frame, orient=tk.HORIZONTAL, command=self.log_text.xview)
        h_scrollbar.grid(row=1, column=0, sticky="ew")
        self.log_text.configure(xscrollcommand=h_scrollbar.set)
        
        # Configure main window grid weights for resizing
        self.grid_rowconfigure(11, weight=1)  # Log panel row expands
        self.grid_columnconfigure(1, weight=1)  # Middle column expands for entry fields
        
        # Add initial log message
        self.log_message("Slideshow Builder initialized")
        
        # Log available transitions now that log panel is ready
        self._log_available_transitions()
        
        # Update project path display now that all variables are initialized
        self._update_project_path_display()

    def log_message(self, message):
        """Add a message to the log panel with timestamp or overwrite last line if message ends with \r"""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        
        self.log_text.configure(state=tk.NORMAL)

        if message.endswith("\r"):
            # Overwrite the last line instead of adding a new one
            message = message.rstrip("\r")
            self.log_text.delete("end-2l", "end-1l")
            log_entry = f"[{timestamp}] {message}\n"
            self.log_text.insert(tk.END, log_entry)
        else:
            # Normal log: write entry and leave an extra blank line ready for overwrite logs
            log_entry = f"[{timestamp}] {message}\n"
            self.log_text.insert(tk.END, log_entry)

        self.log_text.configure(state=tk.DISABLED)
        self.log_text.see(tk.END)


    def _setup_log_clipboard_support(self):
        """Setup clipboard support for the log panel"""
        # Create context menu for log panel
        self.log_context_menu = tk.Menu(self, tearoff=0)
        self.log_context_menu.add_command(label="Copy All", command=self._copy_all_log)
        self.log_context_menu.add_command(label="Copy Selected", command=self._copy_selected_log)
        self.log_context_menu.add_separator()
        self.log_context_menu.add_command(label="Clear Log", command=self._clear_log)
        
        # Bind right-click to show context menu
        self.log_text.bind("<Button-3>", self._show_log_context_menu)  # Right-click on macOS/Linux
        self.log_text.bind("<Control-Button-1>", self._show_log_context_menu)  # Ctrl+click on macOS
        
        # Bind keyboard shortcuts
        self.log_text.bind("<Command-c>", lambda e: self._copy_selected_log())  # macOS
        self.log_text.bind("<Control-c>", lambda e: self._copy_selected_log())  # Windows/Linux
        self.log_text.bind("<Command-a>", lambda e: self._select_all_log())  # macOS
        self.log_text.bind("<Control-a>", lambda e: self._select_all_log())  # Windows/Linux
        
        # Enable text selection
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.configure(state=tk.DISABLED)

    def _show_log_context_menu(self, event):
        """Show context menu for log panel"""
        try:
            # Check if there's selected text
            if self.log_text.tag_ranges(tk.SEL):
                self.log_context_menu.entryconfig("Copy Selected", state=tk.NORMAL)
            else:
                self.log_context_menu.entryconfig("Copy Selected", state=tk.DISABLED)
            
            self.log_context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.log_context_menu.grab_release()

    def _copy_all_log(self):
        """Copy all log content to clipboard"""
        try:
            self.log_text.configure(state=tk.NORMAL)
            content = self.log_text.get(1.0, tk.END)
            self.clipboard_clear()
            self.clipboard_append(content.strip())
            self.log_text.configure(state=tk.DISABLED)
            self.log_message("All log content copied to clipboard")
        except Exception as e:
            self.log_message(f"Failed to copy log content: {e}")

    def _copy_selected_log(self):
        """Copy selected log content to clipboard"""
        try:
            if self.log_text.tag_ranges(tk.SEL):
                self.log_text.configure(state=tk.NORMAL)
                selected_text = self.log_text.selection_get()
                self.clipboard_clear()
                self.clipboard_append(selected_text)
                self.log_text.configure(state=tk.DISABLED)
                self.log_message("Selected log content copied to clipboard")
            else:
                # If no selection, copy current line
                self.log_text.configure(state=tk.NORMAL)
                current_line = self.log_text.get("insert linestart", "insert lineend")
                if current_line.strip():
                    self.clipboard_clear()
                    self.clipboard_append(current_line.strip())
                    self.log_message("Current line copied to clipboard")
                self.log_text.configure(state=tk.DISABLED)
        except tk.TclError:
            # No selection
            self.log_message("No text selected to copy")
        except Exception as e:
            self.log_message(f"Failed to copy selected text: {e}")

    def _select_all_log(self):
        """Select all text in log panel"""
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.tag_add(tk.SEL, "1.0", tk.END)
        self.log_text.mark_set(tk.INSERT, "1.0")
        self.log_text.see(tk.INSERT)
        self.log_text.configure(state=tk.DISABLED)

    def _clear_log(self):
        """Clear all log content"""
        result = messagebox.askyesno("Clear Log", "Are you sure you want to clear all log content?")
        if result:
            self.log_text.configure(state=tk.NORMAL)
            self.log_text.delete(1.0, tk.END)
            self.log_text.configure(state=tk.DISABLED)
            self.log_message("Log cleared")

    def update_progress(self, value, maximum=100):
        """Update progress bar with current value"""
        self.progress['maximum'] = maximum
        self.progress['value'] = value
        self.update_idletasks()  # Force GUI update

    def reset_progress(self):
        """Reset progress bar to 0"""
        self.progress['value'] = 0
        self.update_idletasks()

    def select_input_folder(self):
        import os
        old_folder = self.input_var.get()
        initial_dir = old_folder if old_folder else os.path.expanduser('~')
        folder = filedialog.askdirectory(initialdir=initial_dir)
        if folder and folder != old_folder:
            self.input_var.set(folder)
            self.log_message(f"Input folder selected: {folder}")
            
            # Clear FFmpeg cache when input folder changes
            if old_folder:  # Only clear if there was a previous folder
                try:
                    if FFmpegCache.clear_cache():
                        self.log_message("[FFmpegCache] Cache cleared due to input folder change")
                except Exception as e:
                    self.log_message(f"[FFmpegCache] Warning: Failed to clear cache: {e}")

    def select_output_folder(self):
        import os
        current_folder = self.output_var.get()
        # Strip project name folder if it exists to get base folder
        if current_folder:
            parent = str(Path(current_folder).parent)
            initial_dir = parent if parent != '.' else os.path.expanduser('~')
        else:
            initial_dir = os.path.expanduser('~')
        
        folder = filedialog.askdirectory(initialdir=initial_dir)
        if folder:
            # Build full path with project name
            project_name = self.name_var.get()
            full_path = build_output_path(folder, project_name)
            self.output_var.set(full_path)
            self.log_message(f"Output folder selected: {full_path}")
            
            # Try to load project config from this folder
            try:
                project_config = load_config(full_path)
                self.config_data.update(project_config)
                self._update_ui_from_config()
                self.log_message(f"Loaded project settings from {full_path}")
            except Exception as e:
                self.log_message(f"No existing project settings in folder (will create on save)")

    def select_slideshows_folder(self):
        """Browse for a new base Slideshows folder location"""
        from slideshow.config import Config
        import os
        
        # Get current slideshows directory
        current_dir = str(Config.APP_SETTINGS_DIR)
        initial_dir = current_dir if os.path.exists(current_dir) else os.path.expanduser('~')
        
        folder = filedialog.askdirectory(
            initialdir=initial_dir,
            title="Select Base Slideshows Folder Location"
        )
        
        if folder:
            # Update the APP_SETTINGS_DIR
            new_base_dir = Path(folder)
            Config.APP_SETTINGS_DIR = new_base_dir
            Config.APP_SETTINGS_FILE = new_base_dir / "slideshow_settings.json"
            
            # Ensure the directory exists
            new_base_dir.mkdir(parents=True, exist_ok=True)
            
            # Save this preference in app settings
            app_settings = load_app_settings()
            app_settings["slideshows_base_dir"] = str(new_base_dir)
            save_app_settings(app_settings)
            
            self.log_message(f"Slideshows base folder changed to: {folder}")
            
            # Update project path display
            self._update_project_path_display()
            
            # Update input/output paths to use new base
            project_name = self.name_var.get().strip()
            if project_name:
                new_input, new_output = build_project_paths(project_name)
                self.input_var.set(new_input)
                self.output_var.set(new_output)
                self.log_message(f"Updated project paths to new location")

    def _on_project_name_focus_in(self):
        """Handle focus-in: Store current project name for comparison on focus-out"""
        current_name = self.name_var.get().strip()
        
        # Store what's currently at top of queue for comparison on focus-out
        self._project_name_on_focus = current_name
    
    def _on_project_name_focus_out(self):
        """Handle focus-out: Compare with stored name, only update if different"""
        new_name = self.name_var.get().strip()
        
        # Compare with what was at top when focus gained
        if new_name != self._project_name_on_focus:
            # Name changed - handle rename logic
            self._on_project_name_change()
        
        # Update project path display
        self._update_project_path_display()
    
    def _update_project_path_display(self):
        """Update the project path display label to show the project's base folder."""
        # Check if variables exist yet (during initialization)
        if not hasattr(self, 'output_var') or not hasattr(self, 'name_var') or not hasattr(self, 'project_path_var'):
            return
        
        from slideshow.config import Config
        
        # Show the project's base directory: Slideshows/ProjectName
        project_name = self.name_var.get().strip()
        if project_name:
            project_path = str(Config.APP_SETTINGS_DIR / sanitize_project_name(project_name))
            self.project_path_var.set(project_path)
        else:
            # No project name, just show base directory
            self.project_path_var.set(str(Config.APP_SETTINGS_DIR))
    
    def _on_project_selected(self):
        """Handle selection from project history dropdown"""
        selected_name = self.name_var.get().strip()
        if not selected_name:
            return
        
        # Update the stored name to prevent focus-out from triggering changes
        self._project_name_on_focus = selected_name
        
        # Find the selected project in history to get its path
        for entry in self.project_history:
            if entry["name"] == selected_name:
                project_folder = entry.get("path", "")
                
                if project_folder:
                    project_path = Path(project_folder)
                    
                    # Load the project from its saved path (project folder)
                    self.log_message(f"Loading project from history: {selected_name} at {project_path}")
                    try:
                        # Build default paths from project folder
                        default_input_folder = str(project_path / "Slides")
                        output_folder = str(project_path / "Output")
                        
                        config = load_config(output_folder)
                        
                        # Determine input folder: use config value if present, else default
                        config_input = config.get("input_folder", "").strip()
                        input_folder = config_input if config_input else default_input_folder
                        
                        # Update UI with loaded config
                        self._updating_ui = True
                        self.config_data = config
                        
                        # Update config_data with corrected paths and project name
                        self.config_data["input_folder"] = input_folder
                        self.config_data["output_folder"] = output_folder
                        self.config_data["project_name"] = selected_name
                        
                        # Update all UI fields - use selected name and determined paths
                        self.name_var.set(selected_name)  # Use selected name from dropdown
                        self.input_var.set(input_folder)  # Use config or default path
                        self.output_var.set(output_folder)  # Use calculated path
                        self.soundtrack_var.set(config.get("soundtrack", ""))
                        self.photo_dur_var.set(config.get("photo_duration", 3))
                        self.video_dur_var.set(config.get("video_duration", 10))
                        self.multislide_freq_var.set(config.get("multislide_frequency", 10))
                        self.video_quality_var.set(config.get("video_quality", "maximum"))
                        self.trans_dur_var.set(config.get("transition_duration", 1))
                        self.recurse_var.set(config.get("recurse_folders", False))
                        self.sort_by_filename_var.set(config.get("sort_by_filename", False))
                        
                        # Update transition dropdown
                        self.transition_var.set(config.get("transition_type", "fade"))
                        
                        # Update the stored name to match the selected name
                        self._project_name_on_focus = selected_name
                        
                        self._updating_ui = False
                        
                        self.log_message(f"Loaded project: {selected_name}")
                        self._check_play_button_state()
                        
                        # If we corrected the path, update the history to fix it permanently
                        if str(project_path) != project_folder:
                            add_to_project_history(selected_name, str(project_path))
                            self._refresh_project_history()
                            self.log_message(f"Updated project history with corrected path")
                        
                    except Exception as e:
                        self._updating_ui = False
                        self.log_message(f"Error loading project: {e}")
                else:
                    # No path saved, build default paths based on name
                    self.log_message(f"Selected project from history: {selected_name} (no saved path)")
                    new_input, new_output = build_project_paths(selected_name)
                    self.input_var.set(new_input)
                    self.output_var.set(new_output)
                
                self._update_project_path_display()
                return
        
        # Fallback if not found in history
        self.log_message(f"Selected project from history: {selected_name}")
        # Build default paths for the selected name
        new_input, new_output = build_project_paths(selected_name)
        self.input_var.set(new_input)
        self.output_var.set(new_output)
        self._update_project_path_display()
    
    def _refresh_project_history(self):
        """Refresh the project history dropdown"""
        self.project_history = get_project_history()  # Returns list of dicts with name and path
        # Update combobox with just the names
        project_names = [entry["name"] for entry in self.project_history]
        self.name_combo['values'] = project_names
    
    def _on_project_name_change(self):
        """Handle project name changes on focus loss - update folder paths and load/save config."""
        new_project_name = self.name_var.get()
        self.log_message(f"Project name changed to: {new_project_name}")
        
        current_output = self.output_var.get()
        current_input = self.input_var.get()
        
        # Check if we're using the standard SlideShowBuilder structure
        if current_output:
            # Build new paths based on project name
            new_input_path, new_output_path = build_project_paths(new_project_name)
            
            if new_output_path != current_output:
                self.output_var.set(new_output_path)
                self.input_var.set(new_input_path)
                self.log_message(f"Project paths updated:")
                self.log_message(f"  Input: {new_input_path}")
                self.log_message(f"  Output: {new_output_path}")
                
                # Check if the new path exists
                output_path = Path(new_output_path)
                if output_path.exists() and (output_path / "slideshow_config.json").exists():
                    # Load existing project config
                    try:
                        existing_config = load_config(new_output_path)
                        self.config_data.update(existing_config)
                        self._update_ui_from_config()
                        self.log_message(f"Loaded existing project settings from: {new_output_path}")
                        
                        # Update global settings to remember this project
                        app_settings = load_app_settings()
                        app_settings["last_project_path"] = str(get_project_config_path(new_output_path))
                        save_app_settings(app_settings)
                    except Exception as e:
                        self.log_message(f"Could not load config from {new_output_path}: {e}")
                else:
                    # New project - reset intro_title to defaults before saving
                    self.log_message(f"Creating new project: {new_project_name}")
                    from slideshow.config import DEFAULT_CONFIG
                    self.config_data["intro_title"] = dict(DEFAULT_CONFIG["intro_title"])
                    self._auto_save_config()
            else:
                # No path change, just save
                self._auto_save_config()
        else:
            # No output path yet - set default paths
            new_input_path, new_output_path = build_project_paths(new_project_name)
            self.input_var.set(new_input_path)
            self.output_var.set(new_output_path)
            self._auto_save_config()
    
    def _load_project_from_path(self, project_path: str, project_name: str):
        """Load a project from its path"""
        try:
            # Extract output folder (parent of project folder)
            project_path_obj = Path(project_path)
            output_folder = str(project_path_obj.parent)
            
            # Load config from project
            config = load_config(output_folder)
            
            # Update UI with loaded config
            self._updating_ui = True
            self.config_data = config
            
            # Update all UI fields
            self.name_var.set(config.get("project_name", project_name))
            self.input_var.set(config.get("input_folder", ""))
            self.output_var.set(output_folder)
            self.soundtrack_var.set(config.get("soundtrack", ""))
            self.photo_dur_var.set(config.get("photo_duration", 3))
            self.video_dur_var.set(config.get("video_duration", 10))
            self.multislide_freq_var.set(config.get("multislide_frequency", 10))
            self.video_quality_var.set(config.get("video_quality", "maximum"))
            self.trans_dur_var.set(config.get("transition_duration", 1))
            self.recurse_var.set(config.get("recurse_folders", False))
            self.sort_by_filename_var.set(config.get("sort_by_filename", False))
            
            # Update transition dropdown
            self.transition_var.set(config.get("transition_type", "fade"))
            
            self._updating_ui = False
            
            self.log_message(f"Loaded project: {project_name}")
            
            # Update global settings to remember this project
            app_settings = load_app_settings()
            app_settings["last_project_path"] = str(get_project_config_path(output_folder))
            save_app_settings(app_settings)
            
            self._check_play_button_state()
            
        except Exception as e:
            self._updating_ui = False
            self.log_message(f"Error loading project: {e}")
    
    def select_soundtrack(self):
        import os
        current_file = self.soundtrack_var.get()
        initial_dir = os.path.dirname(current_file) if current_file else os.path.expanduser('~')
        file = filedialog.askopenfilename(initialdir=initial_dir, filetypes=[("Audio Files", "*.mp3 *.wav")])
        if file:
            self.soundtrack_var.set(file)
            self.log_message(f"Soundtrack selected: {file}")

    def _populate_transitions(self):
        """Populate the transition dropdown with available transitions"""
        from slideshow.transitions import list_available_transitions
        
        try:
            available_transitions = list_available_transitions()
            transition_names = [t['name'] for t in available_transitions]
            
            if not transition_names:
                # Fallback if no transitions available
                transition_names = ['fade']
            
            self.transition_combo['values'] = transition_names
            
            # Set default value if current selection not available
            current = self.transition_var.get()
            if current not in transition_names:
                self.transition_var.set(transition_names[0])
                
        except Exception as e:
            # Fallback to just fade if there's an error
            self.transition_combo['values'] = ['fade']
            self.transition_var.set('fade')
            print(f"Warning: Could not load transitions ({e}), using fade only")

    def _log_available_transitions(self):
        """Log available transitions to the log panel"""
        from slideshow.transitions import list_available_transitions
        
        try:
            available_transitions = list_available_transitions()
            if available_transitions:
                transition_info = [f"{t['display_name']}" for t in available_transitions]
                self.log_message(f"Available transitions: {', '.join(transition_info)}")
            else:
                self.log_message("Available transitions: Fade (default)")
        except Exception as e:
            self.log_message(f"Warning: Could not load transitions ({e}), using fade only")
    
    def _get_current_config(self) -> dict:
        """Get current configuration from GUI widgets with error handling"""
        config = {
            "project_name": self.name_var.get(),
            "input_folder": self.input_var.get(),
            "output_folder": self.output_var.get(),
            "transition_type": self.transition_var.get(),
            "soundtrack": self.soundtrack_var.get(),
            "resolution": self.config_data.get("resolution", [1920, 1080])
        }
        
        # Handle numeric fields with validation and error reporting
        def safe_get_float(var, field_name, default_value):
            try:
                # Get raw string value first
                raw_value = var._tk.globalgetvar(var._name)
                if raw_value == "" or raw_value is None:
                    return default_value
                return float(raw_value)
            except (ValueError, TypeError, tk.TclError, AttributeError) as e:
                error_msg = f"Invalid {field_name} - using previous value ({default_value})"
                self.log_message(error_msg)
                return default_value
        
        def safe_get_int(var, field_name, default_value):
            try:
                # Get raw string value first
                raw_value = var._tk.globalgetvar(var._name)
                if raw_value == "" or raw_value is None:
                    return default_value
                return int(raw_value)
            except (ValueError, TypeError, tk.TclError, AttributeError) as e:
                error_msg = f"Invalid {field_name} - using previous value ({default_value})"
                self.log_message(error_msg)
                return default_value
        
        # Get numeric values with validation
        config["photo_duration"] = safe_get_float(
            self.photo_dur_var, "photo duration", 
            self.config_data.get("photo_duration", 3.0)
        )
        
        config["video_duration"] = safe_get_float(
            self.video_dur_var, "video duration", 
            self.config_data.get("video_duration", 5.0)
        )
        
        config["transition_duration"] = safe_get_float(
            self.trans_dur_var, "transition duration", 
            self.config_data.get("transition_duration", 1.0)
        )
        
        config["multislide_frequency"] = safe_get_int(
            self.multislide_freq_var, "multislide frequency",
            self.config_data.get("multislide_frequency", 10)
        )
        
        config["video_quality"] = self.video_quality_var.get()
        config["recurse_folders"] = self.recurse_var.get()
        config["sort_by_filename"] = self.sort_by_filename_var.get()
        
        return config
    
    def _on_video_quality_change(self):
        """Handle video quality changes - clear cache and save config"""
        # Skip if we're updating UI from loaded config
        if getattr(self, '_updating_ui', False):
            return
        
        # Get current quality from GUI (new value)
        new_quality = self.video_quality_var.get()
        
        # Get old quality from config_data (before save)
        old_quality = self.config_data.get("video_quality", "maximum")
        
        self.log_message(f"[Debug] Quality change detected: {old_quality} → {new_quality}")
        
        # Check if quality actually changed
        if old_quality != new_quality:
            # Get cache stats before clearing
            try:
                cache_stats_before = FFmpegCache.get_cache_stats()
                entries_before = cache_stats_before.get("total_entries", 0)
                self.log_message(f"[Debug] Cache before clear: {entries_before} entries")
            except Exception as e:
                self.log_message(f"[Debug] Could not get cache stats: {e}")
            
            # Clear cache BEFORE saving config
            try:
                FFmpegCache.clear_cache()
                self.log_message(f"[FFmpegCache] Cache cleared due to video quality change: {old_quality} → {new_quality}")
                
                # Verify cache was actually cleared
                cache_stats_after = FFmpegCache.get_cache_stats()
                entries_after = cache_stats_after.get("total_entries", 0)
                self.log_message(f"[Debug] Cache after clear: {entries_after} entries")
                
            except Exception as e:
                self.log_message(f"[FFmpegCache] Warning: Failed to clear cache: {e}")
        else:
            self.log_message(f"[Debug] Quality unchanged: {new_quality}")
        
        # Now save the config (this will update self.config_data)
        self._auto_save_config()
    
    def _auto_save_config(self):
        """Automatically update and save config when controls change"""
        # Skip if we're updating UI from loaded config
        if getattr(self, '_updating_ui', False):
            return
        
        old_input_folder = self.config_data.get("input_folder", "")
        old_output_folder = self.config_data.get("output_folder", "")
        new_config = self._get_current_config()
        new_input_folder = new_config.get("input_folder", "")
        new_output_folder = new_config.get("output_folder", "")
        
        # Check if input folder changed and clear cache if so
        if old_input_folder and new_input_folder != old_input_folder:
            try:
                if FFmpegCache.clear_cache():
                    self.log_message("[FFmpegCache] Cache cleared due to input folder change")
            except Exception as e:
                self.log_message(f"[FFmpegCache] Warning: Failed to clear cache: {e}")
        
        self.config_data.update(new_config)
        
        # Save config to output folder if specified
        output_folder = new_config.get("output_folder", "")
        if output_folder:
            output_path = Path(output_folder)
            config_file = output_path / "slideshow_config.json"
            
            # Only load existing config if output folder changed
            output_folder_changed = old_output_folder != new_output_folder
            
            if output_folder_changed and output_path.exists() and config_file.exists():
                # Output folder changed to existing project - load its config
                try:
                    existing_config = load_config(output_folder)
                    self.config_data.update(existing_config)
                    self._update_ui_from_config()
                    self.log_message(f"Loaded existing project config from: {output_folder}")
                    
                    # Update global settings to remember this existing project
                    app_settings = load_app_settings()
                    app_settings["last_project_path"] = str(get_project_config_path(output_folder))
                    save_app_settings(app_settings)
                except Exception as e:
                    # If load fails, save current config (which also updates global settings)
                    save_config(self.config_data, output_folder)
            else:
                # Save current config (new project or updating existing project settings)
                save_config(self.config_data, output_folder)
            
            # Update project history with project folder path (not output folder)
            project_name = new_config.get("project_name", "")
            if project_name:
                project_folder = str(Path(output_folder).parent)
                add_to_project_history(project_name, project_folder)
                self._refresh_project_history()
            
            # Update project path display
            self._update_project_path_display()
        else:
            # If no output folder yet, just update app settings with current config
            # This will be saved properly once output folder is selected
            self._update_project_path_display()
            pass
        
        self._check_play_button_state()  # Update Play button state
    
    def _update_ui_from_config(self):
        """Update all UI controls to match current config_data"""
        # Temporarily disable auto-save while updating UI
        self._updating_ui = True
        try:
            self.name_var.set(self.config_data.get("project_name", "Untitled"))
            self.input_var.set(self.config_data.get("input_folder", ""))
            self.output_var.set(self.config_data.get("output_folder", ""))
            self.soundtrack_var.set(self.config_data.get("soundtrack", ""))
            self.photo_dur_var.set(self.config_data.get("photo_duration", 3))
            self.video_dur_var.set(self.config_data.get("video_duration", 10))
            self.transition_var.set(self.config_data.get("transition_type", "fade"))
            self.trans_dur_var.set(self.config_data.get("transition_duration", 1))
            self.multislide_freq_var.set(self.config_data.get("multislide_frequency", 10))
            self.video_quality_var.set(self.config_data.get("video_quality", "maximum"))
            self.recurse_var.set(self.config_data.get("recurse_folders", False))
            self.sort_by_filename_var.set(self.config_data.get("sort_by_filename", False))
        finally:
            self._updating_ui = False

    def open_settings(self):
        """Open the comprehensive settings dialog"""
        try:
            SettingsDialog(self)
        except Exception as e:
            self.log_message(f"Error opening settings: {e}")
            messagebox.showerror("Settings Error", f"Failed to open settings dialog: {e}")

    def open_app_settings(self):
        """Open the global app settings dialog"""
        try:
            AppSettingsDialog(self)
        except Exception as e:
            self.log_message(f"Error opening app settings: {e}")
            messagebox.showerror("App Settings Error", f"Failed to open app settings dialog: {e}")

    def save_config(self):
        """Manual save config - auto-save already handles updates"""
        self._auto_save_config()
        self.log_message("Configuration saved successfully")

    def play_slideshow(self):
        """Play the exported slideshow video"""
        import os
        import subprocess
        
        # Get the expected output path from current config
        current_config = self._get_current_config()
        output_path = Path(current_config["output_folder"]) / f"{current_config['project_name']}.mp4"
        
        if output_path.exists():
            self.log_message(f"Opening slideshow: {output_path}")
            try:
                if sys.platform == 'darwin':  # macOS
                    # First try to open with QuickTime Player directly
                    result = subprocess.run([
                        'open', '-a', 'QuickTime Player', str(output_path)
                    ], capture_output=True, text=True)
                    
                    if result.returncode == 0:
                        self.log_message("Opening in QuickTime Player...")
                        # Brief pause then try to autoplay
                        import time
                        time.sleep(1.0)  # Give QuickTime time to load
                        
                        # Try to autoplay
                        subprocess.run([
                            'osascript', '-e',
                            'tell application "QuickTime Player" to play the front document'
                        ], capture_output=True)
                        self.log_message("Slideshow should start playing automatically")
                    else:
                        # Fallback to default player
                        subprocess.run(['open', str(output_path)], capture_output=True)
                        self.log_message("Opened with default video player")
                        
                elif os.name == 'nt':  # Windows
                    os.startfile(str(output_path))
                    self.log_message("Slideshow opened in default player")
                else:  # Linux
                    subprocess.run(['xdg-open', str(output_path)], capture_output=True)
                    self.log_message("Slideshow opened in default player")
                    
            except Exception as e:
                self.log_message(f"Failed to open slideshow: {e}")
                # Final fallback
                try:
                    if sys.platform == 'darwin':
                        subprocess.run(['open', str(output_path)], capture_output=True)
                    elif os.name == 'nt':
                        os.startfile(str(output_path))
                    else:
                        subprocess.run(['xdg-open', str(output_path)], capture_output=True)
                    self.log_message("Slideshow opened with basic method")
                except Exception as e2:
                    self.log_message(f"All methods failed: {e2}")
        else:
            self.log_message(f"Slideshow not found: {output_path}. Please export the slideshow first.")
    
    def _on_progress(self, current, total, message=None):
        """Thread-safe progress update callback"""
        if message:
            self.after(0, lambda: self._update_progress_with_message(current, total, message))
        else:
            self.after(0, lambda: self.update_progress(current, total))
    
    def _update_progress_with_message(self, current, total, message):
        """Update progress bar and optionally log message"""
        self.update_progress(current, total)
        # Log message with carriage return to overwrite previous progress messages
        if message:
            self.log_message(message + "\r")
    
    def _on_log_message(self, message):
        """Thread-safe log message callback"""
        self.after(0, lambda: self.log_message(message))
    
    def _check_play_button_state(self):
        """Enable/disable Play button based on output file existence"""
        current_config = self._get_current_config()
        output_path = Path(current_config["output_folder"]) / f"{current_config['project_name']}.mp4"
        if output_path.exists():
            self.play_button.configure(state='normal')
        else:
            self.play_button.configure(state='disabled')

    def export_video(self):
        # Quick validation of input folder before starting export
        input_folder = Path(self.input_var.get().strip())
        
        if not input_folder.exists():
            wide_messagebox("error", "Input Folder Missing", 
                          f"The input folder does not exist:\n{input_folder}\n\n"
                          "Please select a valid input folder.")
            return
        
        # Warn if intro title hasn't been configured
        intro_config = self.config_data.get("intro_title", {})
        intro_enabled = intro_config.get("enabled", False)
        intro_text = intro_config.get("text", "").strip()
        
        if not intro_enabled:
            proceed = wide_messagebox("question", "Intro Title Disabled",
                "The intro title is currently disabled.\n\n"
                "Do you want to continue exporting without an intro title?")
            if not proceed:
                return
        elif not intro_text or intro_text == "Project Title\nHere":
            proceed = wide_messagebox("question", "Intro Title Not Set",
                "The intro title is enabled but the title text has not been set.\n\n"
                "Do you want to continue exporting without a custom title?")
            if not proceed:
                return
        
        self.log_message("Starting video export...")
        self.reset_progress()
        
        # Disable export button during processing
        self.export_button.configure(state='disabled')
        self.play_button.configure(state='disabled')  # Disable play during export
        self.cancel_button.configure(state='normal')  # Enable cancel during export
        
        # Reset cancellation flag
        self.cancel_requested = False
        
        # Run export in background thread (validation moved to thread to avoid blocking UI)
        export_thread = threading.Thread(target=self._export_video_thread, daemon=True)
        export_thread.start()
    
    def _export_video_thread(self):
        """Background thread for video export"""
        output_path = None
        try:
            self.after(0, lambda: self.log_message("Validating input folder..."))
            
            # Validate that input folder has media files (do this in background thread to avoid blocking UI)
            input_folder = Path(self.config_data.get("input_folder", "").strip())
            recurse_folders = self.config_data.get("recurse_folders", False)
            media_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.heic', '.heif', 
                              '.mp4', '.mov', '.avi', '.mkv', '.m4v'}
            
            # Quick check: just look for ANY media file (don't enumerate all files)
            has_media = False
            if recurse_folders:
                # Check recursively in all subdirectories
                for item in input_folder.rglob("*"):
                    if item.is_file() and item.suffix.lower() in media_extensions:
                        has_media = True
                        break
            else:
                # Check only in the root folder
                for item in input_folder.iterdir():
                    if item.is_file() and item.suffix.lower() in media_extensions:
                        has_media = True
                        break
            
            if not has_media:
                recurse_msg = " (including subdirectories)" if recurse_folders else ""
                self.after(0, lambda: wide_messagebox("error", "No Media Files", 
                              f"The input folder contains no media files{recurse_msg}:\n{input_folder}\n\n"
                              "Please add photos or videos before exporting."))
                return
            
            self.after(0, lambda: self.log_message("Loading slides..."))
            
            # Ensure config_data is synchronized with current UI state before export
            current_config = self._get_current_config()
            
            # Validate and rebuild output folder from project name to ensure consistency
            # Note: Input folder can be anywhere (NAS, external drive, etc.) so we don't validate it
            project_name = current_config.get("project_name", "").strip()
            if project_name:
                default_input_folder, correct_output_folder = build_project_paths(project_name)
                
                # Always ensure output folder matches the project structure
                current_output = current_config.get("output_folder", "")
                if current_output != correct_output_folder:
                    current_config["output_folder"] = correct_output_folder
                    self.after(0, lambda out=correct_output_folder: self.output_var.set(out))
                    self.after(0, lambda out=correct_output_folder: self.log_message(f"Output folder updated: {out}"))
                else:
                    # Output folder is already correct, use it
                    correct_output_folder = current_output
                
                # Always set cache directory to match output folder (prevents stale cache paths)
                correct_cache_dir = str(Path(correct_output_folder) / "working" / "ffmpeg_cache")
                current_config["ffmpeg_cache_dir"] = correct_cache_dir
                
                # Also set temp directory to match output folder structure
                current_temp = current_config.get("temp_directory", "")
                if current_temp:
                    # Check if temp directory is under the wrong output folder
                    try:
                        temp_path = Path(current_temp)
                        output_path_check = Path(correct_output_folder)
                        # If temp is not under the correct output folder, clear it
                        if not temp_path.is_relative_to(output_path_check):
                            current_config["temp_directory"] = ""
                    except (ValueError, OSError):
                        # If path comparison fails, clear it to be safe
                        current_config["temp_directory"] = ""
                
                # Only set input folder to default if it's completely empty
                current_input = current_config.get("input_folder", "").strip()
                if not current_input:
                    current_config["input_folder"] = default_input_folder
                    self.after(0, lambda inp=default_input_folder: self.input_var.set(inp))
                    self.after(0, lambda inp=default_input_folder: self.log_message(f"Input folder set to default: {inp}"))
            
            self.config_data.update(current_config)
            
            # Build output path
            output_path = Path(self.config_data["output_folder"]) / f"{self.config_data['project_name']}.mp4"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create slideshow and pass cancellation check
            from slideshow.slideshowmodel import Slideshow
            slideshow = Slideshow(self.config_data, log_callback=self._on_log_message, progress_callback=self._on_progress)
            slideshow.cancel_check = lambda: self.cancel_requested
            
            # Cache the slides for preview reuse
            self.cached_slides = slideshow.slides
            
            # Render the slideshow
            slideshow.render(output_path)
            
            # Check if cancelled at the end
            if self.cancel_requested:
                self.after(0, lambda: self.log_message("[GUI] Export cancelled by user"))
                return
            
            # Success
            if output_path:
                self.after(0, lambda: self.update_progress(100, 100))
                # Brief pause to show 100% completion
                import time
                time.sleep(0.5)
                self.after(500, self.reset_progress)  # Reset progress bar after brief pause
                self.after(0, self._check_play_button_state)  # Enable Play button
        except Exception as e:
            # Check if it was a cancellation
            if self.cancel_requested:
                error_msg = "Export cancelled by user"
            else:
                error_msg = f"Export failed: {str(e)}"
            self.after(0, lambda msg=error_msg: self.log_message(msg))
            self.after(0, self.reset_progress)  # Reset progress on error too
        finally:
            # Re-enable export button and disable cancel button
            self.after(0, self._re_enable_export_button)
    
    def _re_enable_export_button(self):
        """Re-enable the export button after processing"""
        self.export_button.configure(state='normal')
        self.cancel_button.configure(state='disabled')  # Disable cancel when not exporting
        # Play button state will be set by _check_play_button_state() call

    def cancel_export(self):
        """Cancel the current export operation"""
        self.cancel_requested = True
        self.log_message("Cancelling export... please wait")
        self.cancel_button.configure(state='disabled')  # Disable after clicked
    
    def rename_project(self):
        """Rename the current project folder and update all paths"""
        current_project_name = self.name_var.get().strip()
        if not current_project_name:
            wide_messagebox("error", "Error", "No project is currently loaded.")
            return
        
        current_output = self.output_var.get().strip()
        if not current_output:
            wide_messagebox("error", "Error", "No project output folder is set.")
            return
        
        # Get current project folder
        current_project_folder = Path(current_output).parent
        if not current_project_folder.exists():
            wide_messagebox("error", "Error", f"Current project folder does not exist: {current_project_folder}")
            return
        
        # Show rename dialog
        new_name = self._show_rename_dialog(current_project_name)
        if not new_name or new_name == current_project_name:
            return  # User cancelled or didn't change the name
        
        # Sanitize the new name for folder
        sanitized_new = sanitize_project_name(new_name)
        sanitized_current = sanitize_project_name(current_project_name)
        
        if sanitized_new == sanitized_current:
            # Just update the display name in config, no folder rename needed
            self.name_var.set(new_name)
            self.config_data["project_name"] = new_name
            self._auto_save_config()
            self.log_message(f"Project display name updated to: {new_name}")
            return
        
        # Build new project folder path
        new_project_folder = current_project_folder.parent / sanitized_new
        
        if new_project_folder.exists():
            wide_messagebox("error", "Error", f"A project folder with that name already exists: {new_project_folder}")
            return
        
        try:
            # Check if input folder is inside the project folder BEFORE renaming
            current_input = Path(self.input_var.get().strip()) if self.input_var.get().strip() else None
            input_is_internal = False
            
            if current_input and current_input.exists():
                try:
                    # Check if current input is relative to old project folder
                    current_input.relative_to(current_project_folder)
                    input_is_internal = True
                except ValueError:
                    # Input folder is external (like NAS)
                    input_is_internal = False
            
            # Now rename the project folder
            self.log_message(f"Renaming project folder from {current_project_folder.name} to {sanitized_new}...")
            current_project_folder.rename(new_project_folder)
            
            # Update input path based on whether it was internal or external
            if input_is_internal:
                new_input_path = str(new_project_folder / "Slides")
                self.log_message(f"Input folder updated to new project location: {new_input_path}")
            elif current_input:
                new_input_path = str(current_input)
                self.log_message(f"Input folder unchanged (external location): {new_input_path}")
            else:
                # No input folder was set, use default in new project
                new_input_path = str(new_project_folder / "Slides")
                self.log_message(f"Input folder set to new project location: {new_input_path}")
            
            new_output_path = str(new_project_folder / "Output")
            
            # Rename any MP4 files in the Output folder that contain the old project name
            output_folder = new_project_folder / "Output"
            if output_folder.exists():
                mp4_files = list(output_folder.glob("*.mp4"))
                for mp4_file in mp4_files:
                    # Check if filename contains the old sanitized project name
                    if sanitized_current in mp4_file.name:
                        # Replace old name with new name in filename
                        new_filename = mp4_file.name.replace(sanitized_current, sanitized_new)
                        new_mp4_path = output_folder / new_filename
                        try:
                            mp4_file.rename(new_mp4_path)
                            self.log_message(f"Renamed output video: {mp4_file.name} → {new_filename}")
                        except Exception as rename_error:
                            self.log_message(f"Warning: Could not rename {mp4_file.name}: {rename_error}")
            
            # Update UI
            self.name_var.set(new_name)
            self.input_var.set(new_input_path)
            self.output_var.set(new_output_path)
            
            # Update config
            self.config_data["project_name"] = new_name
            self.config_data["input_folder"] = new_input_path
            self.config_data["output_folder"] = new_output_path
            
            # Update temp and cache paths in config
            cache_dir = new_output_path + "/working/ffmpeg_cache"
            self.config_data["ffmpeg_cache_dir"] = cache_dir
            if "temp_directory" in self.config_data:
                self.config_data["temp_directory"] = new_output_path + "/working"
            
            # Save updated config to new location
            new_config_path = new_project_folder / "slideshow_config.json"
            save_config(self.config_data, new_output_path)
            
            # Verify old folder is gone and clean it up if it still exists
            old_config_path = current_project_folder / "slideshow_config.json"
            if current_project_folder.exists():
                self.log_message(f"Warning: Old project folder still exists, removing it: {current_project_folder}")
                try:
                    shutil.rmtree(current_project_folder)
                except Exception as cleanup_error:
                    self.log_message(f"Warning: Could not remove old folder: {cleanup_error}")
            
            # Update app settings
            from slideshow.config import Config
            app_settings = load_app_settings()
            
            # Update last_project_path
            app_settings["last_project_path"] = str(new_config_path)
            
            # Remove ALL old history entries related to the old project
            # Need to check both path formats and old project folder name
            if "project_history" in app_settings:
                old_path_str = str(old_config_path)
                old_folder_str = str(current_project_folder)
                
                def is_old_project(entry):
                    """Check if entry matches the old project"""
                    entry_path = entry.get("path", "")
                    # Match if path equals old config path
                    if entry_path == old_path_str:
                        return True
                    # Match if path equals old folder (without config file)
                    if entry_path == old_folder_str:
                        return True
                    # Match if path starts with old folder path
                    if entry_path.startswith(old_folder_str + "/"):
                        return True
                    return False
                
                app_settings["project_history"] = [
                    entry for entry in app_settings["project_history"]
                    if not is_old_project(entry)
                ]
            
            # Add the renamed project to the front of history
            app_settings["project_history"] = app_settings.get("project_history", [])
            app_settings["project_history"].insert(0, {
                "name": new_name,
                "path": str(new_project_folder)
            })
            
            # Keep only last 10 entries
            app_settings["project_history"] = app_settings["project_history"][:10]
            
            # Save updated settings
            save_app_settings(app_settings)
            
            # Refresh project history dropdown
            self._refresh_project_history()
            
            self.log_message(f"Project successfully renamed to: {new_name}")
            self.log_message(f"New project folder: {new_project_folder}")
            self.log_message(f"Old project removed from history and folder deleted")
            
        except Exception as e:
            wide_messagebox("error", "Error", f"Failed to rename project: {e}")
            self.log_message(f"Error renaming project: {e}")
    
    def _show_rename_dialog(self, current_name: str) -> str:
        """Show dialog to enter new project name. Returns new name or None if cancelled."""
        dialog = tk.Toplevel(self)
        dialog.title("Rename Project")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        
        # Create frame with padding
        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Label and entry
        ttk.Label(frame, text="Enter new project name:").pack(anchor=tk.W, pady=(0, 5))
        
        name_var = tk.StringVar(value=current_name)
        entry = ttk.Entry(frame, textvariable=name_var, width=40)
        entry.pack(fill=tk.X, pady=(0, 15))
        entry.select_range(0, tk.END)
        entry.focus_set()
        
        result = [None]
        
        def on_ok():
            new_name = name_var.get().strip()
            if new_name:
                result[0] = new_name
            dialog.destroy()
        
        def on_cancel():
            dialog.destroy()
        
        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack()
        
        ttk.Button(btn_frame, text="OK", command=on_ok, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=on_cancel, width=10).pack(side=tk.LEFT, padx=5)
        
        # Bind Enter key to OK
        entry.bind('<Return>', lambda e: on_ok())
        dialog.bind('<Escape>', lambda e: on_cancel())
        
        # Center dialog
        dialog.update_idletasks()
        width = dialog.winfo_width()
        height = dialog.winfo_height()
        x = (dialog.winfo_screenwidth() // 2) - (width // 2)
        y = (dialog.winfo_screenheight() // 2) - (height // 2)
        dialog.geometry(f"+{x}+{y}")
        
        dialog.wait_window()
        return result[0]
    
    def open_image_rotator(self):
        """Open the image preview and rotation dialog"""
        input_folder = self.input_var.get().strip()
        if not input_folder:
            wide_messagebox("error", "Error", "Please select an input folder first.")
            return
        
        if not Path(input_folder).exists():
            wide_messagebox("error", "Error", "Input folder does not exist.")
            return
        
        # Load and cache slides if not already loaded
        # The _load_and_cache_slides method now handles opening the dialog when done
        if not self.cached_slides:
            self._load_and_cache_slides()
        else:
            # Slides already cached, open dialog immediately
            ImageRotatorDialog(self, self.cached_slides)
    
    def _load_and_cache_slides(self):
        """Load slides using slideshow model and cache them for reuse"""
        # Show a loading dialog with progress bar
        loading_dialog = tk.Toplevel(self)
        loading_dialog.title("Loading Slides")
        loading_dialog.geometry("500x120")
        loading_dialog.transient(self)
        
        # Center the dialog on screen
        loading_dialog.update_idletasks()
        width = loading_dialog.winfo_width()
        height = loading_dialog.winfo_height()
        x = (loading_dialog.winfo_screenwidth() // 2) - (width // 2)
        y = (loading_dialog.winfo_screenheight() // 2) - (height // 2)
        loading_dialog.geometry(f"{width}x{height}+{x}+{y}")
        
        loading_label = ttk.Label(loading_dialog, text="Loading slides, please wait...", font=("Arial", 12))
        loading_label.pack(expand=True, pady=(10, 5))
        
        # Add progress bar
        progress_bar = ttk.Progressbar(loading_dialog, mode='determinate', length=400, maximum=100)
        progress_bar.pack(pady=(5, 10), padx=20)
        
        loading_dialog.update()
        
        # Store results from thread
        result_container = {'slideshow': None, 'error': None}
        
        # Store progress state (accessed by both threads)
        progress_state = {'current': 0, 'total': 0, 'message': "Loading slides, please wait..."}
        
        # Create progress callback that updates state
        def update_progress(current, total, message=""):
            """Called from worker thread - update shared state"""
            progress_state['current'] = current
            progress_state['total'] = total
            if message:
                progress_state['message'] = message
        
        # Load slides in background thread
        def load_thread():
            try:
                from slideshow.slideshowmodel import Slideshow
                
                # Create slideshow and load slides with progress callback
                slideshow = Slideshow(self.config_data, log_callback=self.log_message, progress_callback=update_progress)
                
                result_container['slideshow'] = slideshow
                
            except Exception as e:
                import traceback
                result_container['error'] = {
                    'exception': e,
                    'traceback': traceback.format_exc()
                }
        
        # Start loading thread
        thread = threading.Thread(target=load_thread, daemon=True)
        thread.start()
        
        # Poll for completion and update progress in a blocking loop
        while thread.is_alive():
            # Update GUI with current progress state
            try:
                current = progress_state['current']
                total = progress_state['total']
                message = progress_state['message']
                
                if total > 0:
                    percent = int((current / total) * 100)
                    progress_bar['value'] = percent
                    loading_label.config(text=message)
                
                # Process pending events
                loading_dialog.update()
            except:
                break  # Dialog was destroyed
            
            # Wait 50ms before next check
            time.sleep(0.05)
        
        # Thread finished - cleanup
        try:
            loading_dialog.destroy()
        except:
            pass
        
        if result_container['error']:
            # Handle error
            error = result_container['error']
            self.log_message(f"Error loading slides: {error['exception']}")
            self.log_message(f"Traceback:\n{error['traceback']}")
            wide_messagebox("error", "Error", f"Failed to load slides:\n{error['exception']}")
            self.cached_slides = None
        elif result_container['slideshow']:
            # Success - cache the slides
            self.cached_slides = result_container['slideshow'].slides
            
            # Now open the preview dialog
            if self.cached_slides:
                ImageRotatorDialog(self, self.cached_slides)

    
    def _invalidate_slide_cache(self):
        """Invalidate cached slides when input folder or sort settings change"""
        self.cached_slides = None
    
    def _get_sorted_image_files(self):
        """Get sorted list of image files using same logic as slideshow export"""
        
        input_folder = Path(self.input_var.get().strip())
        recurse_folders = self.config_data.get("recurse_folders", False)
        sort_by_filename = self.config_data.get("sort_by_filename", False)
        older_images_no_exif = self.config_data.get("older_images_no_exif", False)
        
        # Find all image files (same extensions as preview supports)
        supported_image_extensions = {'.jpg', '.jpeg', '.png', '.heic'}
        image_files = []
        
        # Show a loading dialog
        loading_dialog = tk.Toplevel(self)
        loading_dialog.title("Loading Images")
        loading_dialog.geometry("400x100")
        loading_dialog.transient(self)
        
        # Center the dialog on screen
        loading_dialog.update_idletasks()
        width = loading_dialog.winfo_width()
        height = loading_dialog.winfo_height()
        x = (loading_dialog.winfo_screenwidth() // 2) - (width // 2)
        y = (loading_dialog.winfo_screenheight() // 2) - (height // 2)
        loading_dialog.geometry(f"{width}x{height}+{x}+{y}")
        
        loading_label = ttk.Label(loading_dialog, text="Finding image files...", font=("Arial", 12))
        loading_label.pack(expand=True)
        loading_dialog.update()
        
        # Log to main panel
        self.log_message("Finding image files...")
        
        try:
            if recurse_folders:
                image_files = [f for f in input_folder.rglob("*") if f.is_file() and f.suffix.lower() in supported_image_extensions]
            else:
                image_files = [f for f in input_folder.glob("*") if f.is_file() and f.suffix.lower() in supported_image_extensions]
            
            if not image_files:
                loading_dialog.destroy()
                recurse_msg = " (including subdirectories)" if recurse_folders else ""
                msg = f"No image files found in the input folder{recurse_msg}."
                self.log_message(msg)
                wide_messagebox("error", "Error", msg)
                return None
            
            msg = f"Found {len(image_files)} images. Sorting..."
            loading_label.config(text=msg)
            loading_dialog.update()
            self.log_message(msg)
            
            # Sort using the same logic as slideshow export
            if sort_by_filename:
                # Sort alphabetically by filename
                image_files = sorted(image_files, key=lambda p: p.name.lower())
                self.log_message(f"Sorted {len(image_files)} images alphabetically by filename")
            else:
                # Sort by date taken (same as slideshow model)
                import datetime
                from PIL import Image
                from PIL.ExifTags import TAGS
                
                timestamp_cache = {}
                
                def get_file_timestamp(path: Path) -> float:
                    """Get timestamp - same logic as slideshowmodel.py"""
                    if path in timestamp_cache:
                        return timestamp_cache[path]
                    
                    ext = path.suffix.lower()
                    stat = path.stat()
                    timestamp = getattr(stat, 'st_birthtime', stat.st_mtime)
                    
                    if ext in ('.jpg', '.jpeg', '.heic', '.heif') and not older_images_no_exif:
                        try:
                            with Image.open(path) as img:
                                exif_data = img._getexif()
                                if exif_data:
                                    for tag_id, value in exif_data.items():
                                        tag = TAGS.get(tag_id, tag_id)
                                        if tag == 'DateTimeOriginal':
                                            date_obj = datetime.datetime.strptime(value, '%Y:%m:%d %H:%M:%S')
                                            timestamp = date_obj.timestamp()
                                            break
                        except Exception:
                            pass  # Use file creation/modification time fallback
                    
                    timestamp_cache[path] = timestamp
                    return timestamp
                
                # Sort with progress updates
                total = len(image_files)
                for i, img_file in enumerate(image_files, 1):
                    get_file_timestamp(img_file)
                    if i % 10 == 0 or i == total:
                        msg = f"Processing {i} of {total} images..."
                        loading_label.config(text=msg)
                        loading_dialog.update()
                        if i % 50 == 0 or i == total:  # Log every 50 images to avoid spam
                            self.log_message(msg)
                
                msg = f"Sorting {total} images by date..."
                loading_label.config(text=msg)
                loading_dialog.update()
                self.log_message(msg)
                
                image_files = sorted(image_files, key=get_file_timestamp)
                self.log_message(f"Sorted {len(image_files)} images by date taken")
            
            loading_dialog.destroy()
            self.log_message(f"Successfully loaded {len(image_files)} images for preview")
            return image_files
            
        except Exception as e:
            loading_dialog.destroy()
            error_msg = f"Failed to load images: {e}"
            self.log_message(error_msg)
            wide_messagebox("error", "Error", error_msg)
            return None
