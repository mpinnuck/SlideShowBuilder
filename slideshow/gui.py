import tkinter as tk
from tkinter import ttk, filedialog, messagebox, font
import threading
import sys
import re
from pathlib import Path
from PIL import Image, ImageTk, ImageOps
from slideshow.config import load_config, save_config, save_app_settings, load_app_settings, get_project_config_path, add_to_project_history, get_project_history, add_to_project_history, get_project_history
from slideshow.transitions.ffmpeg_cache import FFmpegCache

def wide_messagebox(msg_type, title, message):
    """Create a messagebox that's 3 times wider than default."""
    top = tk.Toplevel()
    top.title(title)
    top.resizable(False, False)
    
    # Make window modal
    top.transient()
    top.grab_set()
    
    # Create wider frame
    frame = ttk.Frame(top, padding=20)
    frame.pack(fill=tk.BOTH, expand=True)
    
    # Add icon and message with wider label (3x normal width ~= 900 pixels)
    msg_frame = ttk.Frame(frame)
    msg_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
    
    # Icon
    if msg_type == "info":
        icon = "ℹ️"
    elif msg_type == "error":
        icon = "⚠️"
    elif msg_type == "question":
        icon = "❓"
    else:
        icon = ""
    
    if icon:
        ttk.Label(msg_frame, text=icon, font=('Arial', 32)).pack(side=tk.LEFT, padx=(0, 10))
    
    # Message with wider width
    msg_label = ttk.Label(msg_frame, text=message, wraplength=800, justify=tk.LEFT)
    msg_label.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    
    # Button frame
    btn_frame = ttk.Frame(frame)
    btn_frame.pack()
    
    result = [None]
    
    def on_yes():
        result[0] = True
        top.destroy()
    
    def on_no():
        result[0] = False
        top.destroy()
    
    def on_ok():
        result[0] = True
        top.destroy()
    
    # Add buttons based on type
    if msg_type == "question":
        ttk.Button(btn_frame, text="Yes", command=on_yes, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="No", command=on_no, width=10).pack(side=tk.LEFT, padx=5)
    else:
        ttk.Button(btn_frame, text="OK", command=on_ok, width=10).pack()
    
    # Center window
    top.update_idletasks()
    width = top.winfo_width()
    height = top.winfo_height()
    x = (top.winfo_screenwidth() // 2) - (width // 2)
    y = (top.winfo_screenheight() // 2) - (height // 2)
    top.geometry(f"+{x}+{y}")
    
    top.wait_window()
    return result[0]

def sanitize_project_name(name: str) -> str:
    """Remove spaces and special characters from project name for folder."""
    return re.sub(r'[\s\-]+', '', name)

def build_project_paths(project_name: str) -> tuple[str, str]:
    """
    Build full project paths under ~/SlideshowBuilder/ProjectName/
    Returns: (input_path, output_path)
    """
    if not project_name:
        return ("", "")
    sanitized = sanitize_project_name(project_name)
    base_path = Path.home() / "SlideshowBuilder" / sanitized
    input_path = str(base_path / "Slides")
    output_path = str(base_path / "Output")
    return (input_path, output_path)

def build_output_path(base_folder: str, project_name: str) -> str:
    """Build full output path: base_folder/projectname (no spaces)."""
    if not base_folder or not project_name:
        return base_folder
    sanitized = sanitize_project_name(project_name)
    return str(Path(base_folder) / sanitized)

class GUI(tk.Tk):
    def __init__(self, version="1.0.0"):
        super().__init__()
        self.title(f"Slideshow Builder v{version}")
        
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
        self.create_widgets()
        self.center_window()
        
        # Check initial Play button state
        self._check_play_button_state()
    
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
        
        # Use combobox for project name with history
        self.name_combo = ttk.Combobox(self, textvariable=self.name_var, width=38, values=self.project_history)
        self.name_combo.grid(row=0, column=1, columnspan=2, sticky="we")
        self.name_combo.bind('<FocusIn>', lambda e: self._on_project_name_focus_in())
        self.name_combo.bind('<FocusOut>', lambda e: self._on_project_name_focus_out())
        self.name_combo.bind('<Return>', lambda e: self._on_project_name_focus_out())
        self.name_combo.bind('<<ComboboxSelected>>', lambda e: self._on_project_selected())
        
        # Store the project name when focus is gained
        self._project_name_on_focus = ""

        # Input Folder
        ttk.Label(self, text="Input Folder:").grid(row=1, column=0, sticky="e")
        self.input_var = tk.StringVar(value=self.config_data.get("input_folder", ""))
        self.input_var.trace_add('write', lambda *args: self._auto_save_config())
        ttk.Entry(self, textvariable=self.input_var, width=40).grid(row=1, column=1, sticky="we")
        ttk.Button(self, text="Browse", command=self.select_input_folder).grid(row=1, column=2)

        # Output Folder
        ttk.Label(self, text="Output Folder:").grid(row=2, column=0, sticky="e")
        self.output_var = tk.StringVar(value=self.config_data.get("output_folder", ""))
        output_entry = ttk.Entry(self, textvariable=self.output_var, width=40)
        output_entry.grid(row=2, column=1, sticky="we")
        output_entry.bind('<FocusOut>', lambda e: self._auto_save_config())
        output_entry.bind('<Return>', lambda e: self._auto_save_config())
        ttk.Button(self, text="Browse", command=self.select_output_folder).grid(row=2, column=2)

        # Soundtrack
        ttk.Label(self, text="Soundtrack File:").grid(row=3, column=0, sticky="e")
        self.soundtrack_var = tk.StringVar(value=self.config_data.get("soundtrack", ""))
        self.soundtrack_var.trace_add('write', lambda *args: self._auto_save_config())
        ttk.Entry(self, textvariable=self.soundtrack_var, width=40).grid(row=3, column=1, sticky="we")
        ttk.Button(self, text="Browse", command=self.select_soundtrack).grid(row=3, column=2)

        # Durations
        ttk.Label(self, text="Photo Duration (s):").grid(row=4, column=0, sticky="e")
        self.photo_dur_var = tk.IntVar(value=self.config_data.get("photo_duration", 3))
        self.photo_dur_var.trace_add('write', lambda *args: self._auto_save_config())
        ttk.Entry(self, textvariable=self.photo_dur_var, width=5).grid(row=4, column=1, sticky="w", padx=(5, 0))

        # Transition Type (positioned right after Photo Duration in same column area)
        ttk.Label(self, text="Transition:").grid(row=4, column=1, sticky="w", padx=(80, 5))
        self.transition_var = tk.StringVar(value=self.config_data.get("transition_type", "fade"))
        self.transition_var.trace_add('write', lambda *args: self._auto_save_config())
        # Log the change for manual verification
        self.transition_var.trace_add('write', lambda *args: self.log_message(f"Transition type changed to: {self.transition_var.get()}"))
        self.transition_combo = ttk.Combobox(self, textvariable=self.transition_var, width=12, state="readonly")
        self.transition_combo.grid(row=4, column=1, sticky="w", padx=(150, 0))
        self._populate_transitions()

        ttk.Label(self, text="Video Duration (s):").grid(row=5, column=0, sticky="e")
        self.video_dur_var = tk.IntVar(value=self.config_data.get("video_duration", 10))
        self.video_dur_var.trace_add('write', lambda *args: self._auto_save_config())
        ttk.Entry(self, textvariable=self.video_dur_var, width=5).grid(row=5, column=1, sticky="w", padx=(5, 0))

        # MultiSlide Frequency (positioned right after Video Duration in same column area)
        ttk.Label(self, text="MultiSlide Freq:").grid(row=5, column=1, sticky="w", padx=(80, 5))
        self.multislide_freq_var = tk.IntVar(value=self.config_data.get("multislide_frequency", 10))
        self.multislide_freq_var.trace_add('write', lambda *args: self._auto_save_config())
        ttk.Entry(self, textvariable=self.multislide_freq_var, width=5).grid(row=5, column=1, sticky="w", padx=(200, 0))
        ttk.Label(self, text="(0=off)", font=("TkDefaultFont", 8)).grid(row=5, column=1, sticky="w", padx=(270, 0))

        ttk.Label(self, text="Transition Duration (s):").grid(row=6, column=0, sticky="e")
        self.trans_dur_var = tk.IntVar(value=self.config_data.get("transition_duration", 1))
        self.trans_dur_var.trace_add('write', lambda *args: self._auto_save_config())
        ttk.Entry(self, textvariable=self.trans_dur_var, width=5).grid(row=6, column=1, sticky="w", padx=(5, 0))

        # Video Quality (positioned right after Transition Duration in same column area as MultiSlide Freq)
        ttk.Label(self, text="Video Quality:").grid(row=6, column=1, sticky="w", padx=(80, 5))
        self.video_quality_var = tk.StringVar(value=self.config_data.get("video_quality", "maximum"))
        self.video_quality_var.trace_add('write', lambda *args: self._on_video_quality_change())
        quality_combo = ttk.Combobox(self, textvariable=self.video_quality_var, width=10, state="readonly")
        quality_combo['values'] = ('maximum', 'high', 'medium', 'fast')
        quality_combo.grid(row=6, column=1, sticky="w", padx=(190, 0))

        # Buttons
        self.button_frame = ttk.Frame(self)
        self.button_frame.grid(row=7, column=0, columnspan=4, sticky="w", pady=5)
        
        self.export_button = ttk.Button(self.button_frame, text="Export Video", command=self.export_video)
        self.export_button.pack(side=tk.LEFT, padx=(0, 3))
        self.play_button = ttk.Button(self.button_frame, text="Play Slideshow", command=self.play_slideshow)
        self.play_button.pack(side=tk.LEFT, padx=(0, 6))  # Double spacing before Settings
        ttk.Button(self.button_frame, text="Preview & Rotate Images", command=self.open_image_rotator).pack(side=tk.LEFT, padx=(0, 3))
        ttk.Button(self.button_frame, text="Settings", command=self.open_settings).pack(side=tk.LEFT, padx=(0, 3))
        ttk.Button(self.button_frame, text="Save Config", command=self.save_config).pack(side=tk.LEFT, padx=(0, 3))
        self.cancel_button = ttk.Button(self.button_frame, text="Cancel", command=self.cancel_export, state='disabled')
        self.cancel_button.pack(side=tk.LEFT)

        # Progress Bar
        ttk.Label(self, text="Progress:").grid(row=8, column=0, sticky="nw", pady=(10, 0))
        self.progress = ttk.Progressbar(self, mode='determinate')
        self.progress.grid(row=8, column=1, columnspan=3, sticky="ew", padx=(5, 0), pady=(10, 0))

        # Log Panel
        ttk.Label(self, text="Log:").grid(row=9, column=0, sticky="nw", pady=(10, 0))
        
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
                    FFmpegCache.clear_cache()
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

    def _on_project_name_focus_in(self):
        """Handle focus-in: Push current project in edit control to top of history"""
        current_name = self.name_var.get().strip()
        
        # Store what's currently at top of queue for comparison on focus-out
        self._project_name_on_focus = current_name
        
        # Push current project name to top of history
        if current_name:
            add_to_project_history(current_name)
            self._refresh_project_history()
    
    def _on_project_name_focus_out(self):
        """Handle focus-out: Compare with stored name, only push to history if different"""
        new_name = self.name_var.get().strip()
        
        # Compare with what was at top when focus gained
        if new_name != self._project_name_on_focus:
            # Name changed - handle rename logic
            self._on_project_name_change()
            
            # Push changed name to top of history
            if new_name:
                add_to_project_history(new_name)
                self._refresh_project_history()
        # If same as stored name, do nothing (already at top from focus-in)
    
    def _on_project_selected(self):
        """Handle selection from project history dropdown"""
        selected_name = self.name_var.get().strip()
        if not selected_name:
            return
        
        # Just update the project name - the user will need to set/select the output folder
        self.log_message(f"Selected project from history: {selected_name}")
        # The name is already set in name_var by the combobox selection
        # Trigger the name change handler
        self._on_project_name_change()
    
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
    
    def _refresh_project_history(self):
        """Refresh the project history dropdown"""
        self.project_history = get_project_history()  # Returns list of strings
        self.name_combo['values'] = self.project_history
    
    def _on_project_name_change(self):
        """Handle project name changes on focus loss - update folder paths and load/save config."""
        new_project_name = self.name_var.get()
        self.log_message(f"Project name changed to: {new_project_name}")
        
        current_output = self.output_var.get()
        current_input = self.input_var.get()
        
        # Check if we're using the standard SlideshowBuilder structure
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
                    # New project - save current config
                    self.log_message(f"Creating new project: {new_project_name}")
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
    
    def _refresh_project_history(self):
        """Refresh the project history dropdown"""
        self.project_history = get_project_history()  # Returns list of strings
        self.name_combo['values'] = self.project_history
    
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
            except:
                pass
            
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
                FFmpegCache.clear_cache()
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
        else:
            # If no output folder yet, just update app settings with current config
            # This will be saved properly once output folder is selected
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
        finally:
            self._updating_ui = False

    def open_settings(self):
        """Open the comprehensive settings dialog"""
        try:
            SettingsDialog(self)
        except Exception as e:
            self.log_message(f"Error opening settings: {e}")
            messagebox.showerror("Settings Error", f"Failed to open settings dialog: {e}")

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
    
    def _on_progress(self, current, total):
        """Thread-safe progress update callback"""
        self.after(0, lambda: self.update_progress(current, total))
    
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
        self.log_message("Starting video export...")
        self.reset_progress()
        
        # Disable export button during processing
        self.export_button.configure(state='disabled')
        self.play_button.configure(state='disabled')  # Disable play during export
        self.cancel_button.configure(state='normal')  # Enable cancel during export
        
        # Reset cancellation flag
        self.cancel_requested = False
        
        # Run export in background thread
        export_thread = threading.Thread(target=self._export_video_thread, daemon=True)
        export_thread.start()
    
    def _export_video_thread(self):
        """Background thread for video export"""
        output_path = None
        try:
            # Build output path
            output_path = Path(self.config_data["output_folder"]) / f"{self.config_data['project_name']}.mp4"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create slideshow and pass cancellation check
            from slideshow.slideshowmodel import Slideshow
            slideshow = Slideshow(self.config_data, log_callback=self._on_log_message, progress_callback=self._on_progress)
            slideshow.cancel_check = lambda: self.cancel_requested
            
            # Render the slideshow
            slideshow.render(output_path)
            
            # Check if cancelled at the end
            if self.cancel_requested:
                self.after(0, lambda: self.log_message("[GUI] Export cancelled by user"))
                return
            
            # Success
            if output_path:
                self.after(0, lambda: self.log_message(f"[GUI] Slideshow successfully exported → {output_path}"))
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
    
    def open_image_rotator(self):
        """Open the image preview and rotation dialog"""
        input_folder = self.input_var.get().strip()
        if not input_folder:
            wide_messagebox("error", "Error", "Please select an input folder first.")
            return
        
        if not Path(input_folder).exists():
            wide_messagebox("error", "Error", "Input folder does not exist.")
            return
        
        ImageRotatorDialog(self)


class ImageRotatorDialog:
    """Dialog for previewing and rotating images"""
    
    def __init__(self, parent):
        self.parent = parent
        self.config_data = parent.config_data
        self.input_folder = Path(parent.input_var.get().strip())
        
        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Preview & Rotate Images")
        self.dialog.geometry("1200x800")
        self.dialog.transient(parent)
        
        # Find all image files
        self.image_files = []
        for ext in ['.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG']:
            self.image_files.extend(self.input_folder.glob(f'*{ext}'))
        
        # Sort all files together by name (case-insensitive for better sorting)
        self.image_files = sorted(self.image_files, key=lambda p: p.name.lower())
        
        if not self.image_files:
            wide_messagebox("error", "Error", "No image files found in the input folder.")
            self.dialog.destroy()
            return
        
        self.current_index = 0
        self.thumbnail_cache = {}  # Cache thumbnails for performance
        
        self._create_widgets()
        self._center_dialog()
        self._load_image()
    
    def _center_dialog(self):
        """Center the dialog on the screen"""
        self.dialog.update_idletasks()
        
        dialog_w = self.dialog.winfo_width()
        dialog_h = self.dialog.winfo_height()
        
        screen_w = self.dialog.winfo_screenwidth()
        screen_h = self.dialog.winfo_screenheight()
        
        x = (screen_w // 2) - (dialog_w // 2)
        y = (screen_h // 2) - (dialog_h // 2)
        
        self.dialog.geometry(f"{dialog_w}x{dialog_h}+{x}+{y}")
    
    def _create_widgets(self):
        """Create the dialog widgets"""
        # Top frame with navigation
        top_frame = ttk.Frame(self.dialog)
        top_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(top_frame, text="◀ Previous", command=self._prev_image).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_frame, text="Next ▶", command=self._next_image).pack(side=tk.LEFT, padx=5)
        
        self.counter_label = ttk.Label(top_frame, text="")
        self.counter_label.pack(side=tk.LEFT, padx=20)
        
        ttk.Label(top_frame, text="Jump to:").pack(side=tk.LEFT, padx=(20, 5))
        self.jump_var = tk.StringVar()
        jump_entry = ttk.Entry(top_frame, textvariable=self.jump_var, width=8)
        jump_entry.pack(side=tk.LEFT)
        jump_entry.bind('<Return>', lambda e: self._jump_to_image())
        
        ttk.Button(top_frame, text="Go", command=self._jump_to_image).pack(side=tk.LEFT, padx=5)
        
        # Slider for rapid scrolling (right side of top frame)
        ttk.Label(top_frame, text="Scroll:").pack(side=tk.LEFT, padx=(20, 5))
        self.slider_var = tk.IntVar(value=1)
        self.slider = ttk.Scale(
            top_frame, 
            from_=1, 
            to=len(self.image_files),
            orient=tk.HORIZONTAL,
            variable=self.slider_var,
            command=self._on_slider_change,
            length=400
        )
        self.slider.pack(side=tk.LEFT, padx=5)
        
        # Filename label
        self.filename_label = ttk.Label(self.dialog, text="", font=("TkDefaultFont", 10, "bold"))
        self.filename_label.pack(pady=(0, 10))
        
        # Main frame with preview
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Image canvas
        canvas_frame = ttk.Frame(main_frame, relief=tk.SUNKEN, borderwidth=2)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(canvas_frame, bg='gray20')
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Rotation controls
        rotation_frame = ttk.Frame(self.dialog)
        rotation_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(rotation_frame, text="Rotate:").pack(side=tk.LEFT, padx=5)
        ttk.Button(rotation_frame, text="↶ 90° Left", command=lambda: self._rotate(-90)).pack(side=tk.LEFT, padx=5)
        ttk.Button(rotation_frame, text="↷ 90° Right", command=lambda: self._rotate(90)).pack(side=tk.LEFT, padx=5)
        ttk.Button(rotation_frame, text="↻ 180°", command=lambda: self._rotate(180)).pack(side=tk.LEFT, padx=5)
        ttk.Button(rotation_frame, text="🗑 Delete", command=self._delete_image).pack(side=tk.LEFT, padx=(20, 5))
        
        self.rotation_label = ttk.Label(rotation_frame, text="", font=("TkDefaultFont", 10))
        self.rotation_label.pack(side=tk.LEFT, padx=20)
        
        # Bottom frame with buttons
        bottom_frame = ttk.Frame(self.dialog)
        bottom_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(bottom_frame, text="Close", command=self._close).pack(side=tk.RIGHT, padx=5)
        ttk.Button(bottom_frame, text="Save", command=self._save).pack(side=tk.RIGHT, padx=5)
        ttk.Button(bottom_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
        
        # Keyboard shortcuts
        self.dialog.bind('<Left>', lambda e: self._prev_image())
        self.dialog.bind('<Right>', lambda e: self._next_image())
        self.dialog.bind('<Shift-Left>', lambda e: self._rotate(-90))
        self.dialog.bind('<Shift-Right>', lambda e: self._rotate(90))
        self.dialog.bind('<Delete>', lambda e: self._delete_image())
        self.dialog.bind('<BackSpace>', lambda e: self._delete_image())  # Alternative for Delete
    
    def _load_image(self):
        """Load and display the current image"""
        if not self.image_files:
            return
        
        image_path = self.image_files[self.current_index]
        filename = image_path.name
        
        # Update counter and filename
        self.counter_label.config(text=f"Image {self.current_index + 1} of {len(self.image_files)}")
        self.filename_label.config(text=filename)
        
        # Update slider to match current index (without triggering callback)
        self.slider_var.set(self.current_index + 1)
        
        # Clear rotation label
        self.rotation_label.config(text="")
        
        # Load image
        try:
            img = Image.open(image_path)
            
            # Apply EXIF orientation to display portrait images correctly
            img = ImageOps.exif_transpose(img)
            
            # Resize to fit canvas while maintaining aspect ratio
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            
            # Use a default size if canvas hasn't been drawn yet
            if canvas_width <= 1:
                canvas_width = 1000
            if canvas_height <= 1:
                canvas_height = 600
            
            # Calculate scaling
            img_ratio = img.width / img.height
            canvas_ratio = canvas_width / canvas_height
            
            if img_ratio > canvas_ratio:
                # Image is wider - fit to width
                new_width = canvas_width - 40
                new_height = int(new_width / img_ratio)
            else:
                # Image is taller - fit to height
                new_height = canvas_height - 40
                new_width = int(new_height * img_ratio)
            
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Convert to PhotoImage
            self.photo = ImageTk.PhotoImage(img)
            
            # Display on canvas
            self.canvas.delete("all")
            x = canvas_width // 2
            y = canvas_height // 2
            self.canvas.create_image(x, y, image=self.photo)
            
        except Exception as e:
            self.parent.log_message(f"Error loading image {filename}: {e}")
    
    def _rotate(self, degrees):
        """Rotate and save the current image by the specified degrees"""
        if not self.image_files:
            return
        
        image_path = self.image_files[self.current_index]
        filename = image_path.name
        
        try:
            # Load the current image from disk
            img = Image.open(image_path)
            
            # Apply EXIF orientation first to get the correct base orientation
            img = ImageOps.exif_transpose(img)
            
            # Rotate the image (PIL rotates counter-clockwise, so negate)
            img_rotated = img.rotate(-degrees, expand=True)
            
            # Save back to the same file
            img_rotated.save(image_path)
            
            # Log the rotation
            self.parent.log_message(f"Rotated and saved {filename} by {degrees}°")
            
            # Clear the thumbnail cache for this image
            self.thumbnail_cache.pop(filename, None)
            
            # Reload to show the saved version
            self._load_image()
            
        except Exception as e:
            self.parent.log_message(f"Error rotating image {filename}: {e}")
            wide_messagebox("error", "Error", f"Failed to rotate image: {e}")
    
    def _prev_image(self):
        """Go to previous image"""
        if self.current_index > 0:
            self.current_index -= 1
            self._load_image()
    
    def _next_image(self):
        """Go to next image"""
        if self.current_index < len(self.image_files) - 1:
            self.current_index += 1
            self._load_image()
    
    def _jump_to_image(self):
        """Jump to a specific image number"""
        try:
            target = int(self.jump_var.get()) - 1  # Convert to 0-based index
            if 0 <= target < len(self.image_files):
                self.current_index = target
                self._load_image()
            else:
                wide_messagebox("error", "Error", f"Please enter a number between 1 and {len(self.image_files)}")
        except ValueError:
            wide_messagebox("error", "Error", "Please enter a valid number")
    
    def _on_slider_change(self, value):
        """Handle slider value change for rapid scrolling"""
        # Convert slider value (1-based) to array index (0-based)
        target = int(float(value)) - 1
        if 0 <= target < len(self.image_files) and target != self.current_index:
            self.current_index = target
            self._load_image()
    
    def _delete_image(self):
        """Delete the current image after confirmation"""
        if not self.image_files:
            return
        
        image_path = self.image_files[self.current_index]
        filename = image_path.name
        
        # Confirm deletion
        result = wide_messagebox("question", "Confirm Delete", 
                                f"Are you sure you want to delete '{filename}'?\n\nThis action cannot be undone!")
        
        if result:
            try:
                # Delete the file
                import os
                os.remove(image_path)
                
                # Log the deletion
                self.parent.log_message(f"Deleted image: {filename}")
                
                # Remove from our list
                del self.image_files[self.current_index]
                
                # Clear thumbnail cache
                self.thumbnail_cache.pop(filename, None)
                
                # Update slider range
                self.slider.config(to=len(self.image_files))
                
                # Check if we have any images left
                if not self.image_files:
                    wide_messagebox("info", "No Images", "No more images in folder.")
                    self.dialog.destroy()
                    return
                
                # Adjust index if needed
                if self.current_index >= len(self.image_files):
                    self.current_index = len(self.image_files) - 1
                
                # Load the next/previous image
                self._load_image()
                
            except Exception as e:
                self.parent.log_message(f"Error deleting image {filename}: {e}")
                wide_messagebox("error", "Error", f"Failed to delete image: {e}")
    
    def _save(self):
        """Images are already saved to disk - nothing to save"""
        self.parent.log_message("Image rotation changes have been saved to disk")
    
    def _close(self):
        """Close dialog"""
        self._save()
        self.dialog.destroy()


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
        
        # Transition Settings Tab
        self.transition_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.transition_frame, text="Transitions")
        
        # Title Settings Tab
        self.title_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.title_frame, text="Title/Intro")
        
        # Advanced Settings Tab
        self.advanced_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.advanced_frame, text="Advanced")
    
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
        
        self.font_path_var = tk.StringVar(value=intro_config.get("font_path", "/System/Library/Fonts/Arial.ttf"))
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
        
        self.auto_cleanup_var = tk.BooleanVar(value=self.config_data.get("auto_cleanup", True))
        ttk.Checkbutton(scrollable_frame, text="Automatically clean up temporary files", 
                       variable=self.auto_cleanup_var).grid(row=9, column=0, columnspan=2, sticky="w")
        
        self.keep_frames_var = tk.BooleanVar(value=self.config_data.get("keep_intermediate_frames", False))
        ttk.Checkbutton(scrollable_frame, text="Keep intermediate frames for debugging", 
                       variable=self.keep_frames_var).grid(row=10, column=0, columnspan=2, sticky="w")
        
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
            initialdir="/System/Library/Fonts"
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
            
            # Configure cache with current settings to get accurate stats
            cache_dir = self.ffmpeg_cache_dir_var.get().strip()
            if not cache_dir:
                # Use default location
                output_folder = self.config_data.get("output_folder", "data/output")
                cache_dir = f"{output_folder}/working/ffmpeg_cache"
            
            FFmpegCache.configure(cache_dir)
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
                                "This will delete all cached video clips and frames.")
        if result:
            try:
                from slideshow.transitions.ffmpeg_cache import FFmpegCache
                from pathlib import Path
                
                # Configure cache path before clearing
                # Use the working directory from current project config
                config = self.parent.model.config if hasattr(self.parent, 'model') else {}
                output_folder = config.get("output_folder", "")
                
                if output_folder:
                    working_dir = Path(output_folder) / "working"
                    cache_dir = working_dir / "ffmpeg_cache"
                    FFmpegCache.configure(cache_dir)
                
                # Now clear the cache
                FFmpegCache.clear_cache()
                if hasattr(self, 'parent') and hasattr(self.parent, 'log_message'):
                    self.parent.log_message("[FFmpegCache] Cache cleared successfully")
            except Exception as e:
                wide_messagebox("error", "Error", f"Failed to clear cache:\n{str(e)}")
                if hasattr(self, 'parent') and hasattr(self.parent, 'log_message'):
                    self.parent.log_message(f"[FFmpegCache] Error clearing cache: {e}")
    
    def _cleanup_cache(self):
        """Clean up old cache entries"""
        result = wide_messagebox("question", "Cleanup Cache",
                                "Remove cache entries older than 30 days?")
        if result:
            try:
                from slideshow.transitions.ffmpeg_cache import FFmpegCache
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
                
                # Configure cache with current settings first
                cache_dir = self.ffmpeg_cache_dir_var.get().strip()
                if not cache_dir:
                    output_folder = self.config_data.get("output_folder", "data/output")
                    cache_dir = f"{output_folder}/working/ffmpeg_cache"
                
                FFmpegCache.configure(cache_dir)
                FFmpegCache.reset_stats()
                
                # No confirmation - user already pressed OK
            except Exception as e:
                wide_messagebox("error", "Error", f"Failed to reset cache statistics:\n{str(e)}")
    
    def _browse_cache_contents(self):
        """Show detailed cache contents browser"""
        try:
            from slideshow.transitions.ffmpeg_cache import FFmpegCache
            
            # Configure cache with current settings
            cache_dir = self.ffmpeg_cache_dir_var.get().strip()
            if not cache_dir:
                output_folder = self.config_data.get("output_folder", "data/output")
                cache_dir = f"{output_folder}/working/ffmpeg_cache"
            
            FFmpegCache.configure(cache_dir)
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
            browser_window.update_idletasks()  # Ensure window size is calculated
            window_width = 900
            window_height = 600
            
            # Get screen dimensions
            screen_width = browser_window.winfo_screenwidth()
            screen_height = browser_window.winfo_screenheight()
            
            # Calculate center position
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
            
            # Set the centered position
            browser_window.geometry(f"{window_width}x{window_height}+{x}+{y}")
            
            # Main frame with scrollbar
            main_frame = ttk.Frame(browser_window)
            main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # Info label
            cache_entries = cache_data.get('entries', [])
            clips = [e for e in cache_entries if e['type'] == 'clip']
            frames = [e for e in cache_entries if e['type'] == 'frame']
            
            info_label = ttk.Label(main_frame, 
                                 text=f"Cache Contents: {len(clips)} clips, {len(frames)} frames ({cache_data['total_entries']} total)",
                                 font=("Arial", 12, "bold"))
            info_label.pack(pady=(0, 10))
            
            # Create notebook for tabs
            notebook = ttk.Notebook(main_frame)
            notebook.pack(fill=tk.BOTH, expand=True)
            
            # Create tabs for clips and frames
            clips_frame = ttk.Frame(notebook)
            frames_frame = ttk.Frame(notebook)
            
            notebook.add(clips_frame, text=f"Video Clips ({len(clips)})")
            notebook.add(frames_frame, text=f"Extracted Frames ({len(frames)})")
            
            # Function to create treeview for each tab
            def create_cache_tree(parent_frame, entries, show_frame_number=False):
                # Create frame for treeview and scrollbars (using grid)
                tree_frame = ttk.Frame(parent_frame)
                tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
                
                # Create treeview for cache entries
                if show_frame_number:
                    columns = ('Source File', 'Operation', 'Frame #', 'Size (MB)', 'Cache File')
                else:
                    columns = ('Source File', 'Operation', 'Duration', 'Size (MB)', 'Cache File')
                
                tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=12)
                
                # Configure columns
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
                
                # Add scrollbars
                v_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
                h_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=tree.xview)
                tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
                
                # Grid treeview and scrollbars within tree_frame
                tree.grid(row=0, column=0, sticky='nsew')
                v_scrollbar.grid(row=0, column=1, sticky='ns')
                h_scrollbar.grid(row=1, column=0, sticky='ew')
                
                tree_frame.grid_rowconfigure(0, weight=1)
                tree_frame.grid_columnconfigure(0, weight=1)
                
                # Populate tree with cache entries
                for entry in entries:
                    if show_frame_number:
                        # Extract frame number from parameters if available
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
                        # Extract duration from parameters if available
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
            
            # Create trees for each tab
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
            
            # Handle tree selection for both trees
            def on_tree_select(event):
                # Get the tree that triggered the event
                selected_tree = event.widget
                selection = selected_tree.selection()
                if selection:
                    item = selected_tree.item(selection[0])
                    source_file = item['values'][0]
                    
                    # Clear selection from the other tree
                    if selected_tree == clips_tree:
                        frames_tree.selection_remove(frames_tree.selection())
                    else:
                        clips_tree.selection_remove(clips_tree.selection())
                    
                    # Find the full entry details
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
            
            # Handle double-click to view
            def on_double_click(event):
                # Get the tree that triggered the event
                selected_tree = event.widget
                selection = selected_tree.selection()
                
                if not selection:
                    return
                
                try:
                    item = selected_tree.item(selection[0])
                    source_file = item['values'][0]
                    
                    # Find the entry details
                    for entry in cache_data.get('entries', []):
                        if entry['source_file'] == source_file:
                            cache_file_path = entry['cached_file']
                            
                            if entry['type'] == 'clip':
                                # Open video file with default player
                                import subprocess
                                subprocess.run(['open', cache_file_path], check=True)
                            else:
                                # Open image file with default viewer
                                import subprocess
                                subprocess.run(['open', cache_file_path], check=True)
                            break
                    else:
                        messagebox.showerror("Error", f"Cache file not found for: {source_file}")
                        
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to open cache file:\n{str(e)}")
            
            # Bind selection and double-click events to both trees
            clips_tree.bind('<<TreeviewSelect>>', on_tree_select)
            frames_tree.bind('<<TreeviewSelect>>', on_tree_select)
            clips_tree.bind('<Double-1>', on_double_click)
            frames_tree.bind('<Double-1>', on_double_click)
            
            # Add View button for selected entry
            def view_selected():
                # Determine which tree has a selection
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
                    
                    # Find the entry details
                    for entry in cache_data.get('entries', []):
                        if entry['source_file'] == source_file:
                            cache_file_path = entry['cached_file']
                            
                            if entry['type'] == 'clip':
                                # Open video file with default player
                                import subprocess
                                subprocess.run(['open', cache_file_path], check=True)
                            else:
                                # Open image file with default viewer
                                import subprocess
                                subprocess.run(['open', cache_file_path], check=True)
                            break
                    else:
                        messagebox.showerror("Error", f"Cache file not found for: {source_file}")
                        
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to open cache file:\n{str(e)}")
            
            # Button frame
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(pady=(10, 0))
            
            # Copy to clipboard function
            def copy_to_clipboard():
                """Copy cache contents to clipboard in a readable format"""
                try:
                    import json
                    
                    # Build a readable text representation
                    text = f"Cache Contents Summary\n"
                    text += f"{'='*60}\n\n"
                    text += f"Total Entries: {cache_data['total_entries']}\n"
                    text += f"Video Clips: {len(clips)}\n"
                    text += f"Extracted Frames: {len(frames)}\n\n"
                    
                    # Add clips details
                    if clips:
                        text += f"\nVIDEO CLIPS ({len(clips)}):\n"
                        text += f"{'-'*60}\n"
                        for i, entry in enumerate(clips, 1):
                            text += f"\n{i}. {entry['source_file']}\n"
                            text += f"   Operation: {entry['operation']}\n"
                            text += f"   Size: {entry['size_mb']} MB\n"
                            text += f"   Cache Key: {entry['cache_key']}\n"
                            text += f"   Parameters: {json.dumps(entry['params'], indent=6)}\n"
                    
                    # Add frames details
                    if frames:
                        text += f"\n\nEXTRACTED FRAMES ({len(frames)}):\n"
                        text += f"{'-'*60}\n"
                        for i, entry in enumerate(frames, 1):
                            text += f"\n{i}. {entry['source_file']}\n"
                            text += f"   Operation: {entry['operation']}\n"
                            text += f"   Size: {entry['size_mb']} MB\n"
                            text += f"   Cache Key: {entry['cache_key']}\n"
                            text += f"   Parameters: {json.dumps(entry['params'], indent=6)}\n"
                    
                    # Copy to clipboard
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
            
            # Close button
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
        self.config_data["auto_cleanup"] = self.auto_cleanup_var.get()
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

