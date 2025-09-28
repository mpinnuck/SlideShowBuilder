import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import sys
from pathlib import Path
from slideshow.config import load_config, save_config

class GUI(tk.Tk):
    def __init__(self, controller, version="1.0.0"):
        super().__init__()
        self.title(f"Slideshow Builder v{version}")
        self.controller = controller
        self.config_data = load_config()
        self.create_widgets()
        self.center_window()
        
        # Register callbacks with controller
        if self.controller:
            self.controller.register_progress_callback(self._on_progress)
            self.controller.register_log_callback(self._on_log_message)
        
        # Check initial Play button state
        self._check_play_button_state()
    
    def center_window(self):
            # Set initial size before centering
            initial_width = 800  # Make window wider
            initial_height = 600  # Make window taller too
            
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
            self.minsize(800, 500)  # Increase minimum size too

    def create_widgets(self):
        # Project Info
        ttk.Label(self, text="Project Name:").grid(row=0, column=0, sticky="e")
        self.name_var = tk.StringVar(value=self.config_data.get("project_name", "Untitled"))
        self.name_var.trace_add('write', lambda *args: self._auto_save_config())
        ttk.Entry(self, textvariable=self.name_var, width=40).grid(row=0, column=1, columnspan=2, sticky="we")

        # Input Folder
        ttk.Label(self, text="Input Folder:").grid(row=1, column=0, sticky="e")
        self.input_var = tk.StringVar(value=self.config_data.get("input_folder", ""))
        self.input_var.trace_add('write', lambda *args: self._auto_save_config())
        ttk.Entry(self, textvariable=self.input_var, width=40).grid(row=1, column=1, sticky="we")
        ttk.Button(self, text="Browse", command=self.select_input_folder).grid(row=1, column=2)

        # Output Folder
        ttk.Label(self, text="Output Folder:").grid(row=2, column=0, sticky="e")
        self.output_var = tk.StringVar(value=self.config_data.get("output_folder", ""))
        self.output_var.trace_add('write', lambda *args: self._auto_save_config())
        ttk.Entry(self, textvariable=self.output_var, width=40).grid(row=2, column=1, sticky="we")
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

        ttk.Label(self, text="Transition Duration (s):").grid(row=6, column=0, sticky="e")
        self.trans_dur_var = tk.IntVar(value=self.config_data.get("transition_duration", 1))
        self.trans_dur_var.trace_add('write', lambda *args: self._auto_save_config())
        ttk.Entry(self, textvariable=self.trans_dur_var, width=5).grid(row=6, column=1, sticky="w", padx=(5, 0))

        # Buttons
        self.button_frame = ttk.Frame(self)
        self.button_frame.grid(row=7, column=0, columnspan=4, sticky="w", pady=5)
        
        self.export_button = ttk.Button(self.button_frame, text="Export Video", command=self.export_video)
        self.export_button.pack(side=tk.LEFT, padx=(0, 3))
        self.play_button = ttk.Button(self.button_frame, text="Play Slideshow", command=self.play_slideshow)
        self.play_button.pack(side=tk.LEFT, padx=(0, 6))  # Double spacing before Settings
        ttk.Button(self.button_frame, text="Settings", command=self.open_settings).pack(side=tk.LEFT, padx=(0, 3))
        ttk.Button(self.button_frame, text="Save Config", command=self.save_config).pack(side=tk.LEFT)

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
        folder = filedialog.askdirectory()
        if folder:
            self.input_var.set(folder)
            self.log_message(f"Input folder selected: {folder}")

    def select_output_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_var.set(folder)
            self.log_message(f"Output folder selected: {folder}")

    def select_soundtrack(self):
        file = filedialog.askopenfilename(filetypes=[("Audio Files", "*.mp3 *.wav")])
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
        
        return config
    
    def _auto_save_config(self):
        """Automatically update and save config when controls change"""
        self.config_data.update(self._get_current_config())
        save_config(self.config_data)
        self._check_play_button_state()  # Update Play button state

    def open_settings(self):
        self.log_message("Settings dialog coming soon...")

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
                        subprocess.run(['open', str(output_path)])
                        self.log_message("Opened with default video player")
                        
                elif os.name == 'nt':  # Windows
                    os.startfile(str(output_path))
                    self.log_message("Slideshow opened in default player")
                else:  # Linux
                    subprocess.run(['xdg-open', str(output_path)])
                    self.log_message("Slideshow opened in default player")
                    
            except Exception as e:
                self.log_message(f"Failed to open slideshow: {e}")
                # Final fallback
                try:
                    if sys.platform == 'darwin':
                        subprocess.run(['open', str(output_path)])
                    elif os.name == 'nt':
                        os.startfile(str(output_path))
                    else:
                        subprocess.run(['xdg-open', str(output_path)])
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
        
        # Run export in background thread
        export_thread = threading.Thread(target=self._export_video_thread, daemon=True)
        export_thread.start()
    
    def _export_video_thread(self):
        """Background thread for video export"""
        try:
            path = self.controller.export(self.config_data)
            if path:
                self.after(0, lambda: self.log_message(f"Video export completed: {path}"))
                self.after(0, lambda: self.update_progress(100, 100))
                # Brief pause to show 100% completion
                import time
                time.sleep(0.5)
                self.after(500, self.reset_progress)  # Reset progress bar after brief pause
                self.after(0, self._check_play_button_state)  # Enable Play button
        except Exception as e:
            error_msg = f"Export failed: {str(e)}"
            self.after(0, lambda: self.log_message(error_msg))
            self.after(0, self.reset_progress)  # Reset progress on error too
        finally:
            # Re-enable export button
            self.after(0, self._re_enable_export_button)
    
    def _re_enable_export_button(self):
        """Re-enable the export button after processing"""
        self.export_button.configure(state='normal')
        # Play button state will be set by _check_play_button_state() call

