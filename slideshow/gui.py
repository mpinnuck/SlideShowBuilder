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


class SettingsDialog:
    """Comprehensive settings dialog for transitions, titles, and advanced options"""
    
    def __init__(self, parent):
        self.parent = parent
        self.config_data = parent.config_data.copy()
        
        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Slideshow Settings")
        self.dialog.geometry("800x600")  # Increased width from 600 to 800
        self.dialog.resizable(True, True)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Set minimum size to prevent clipping
        self.dialog.minsize(750, 500)
        
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
        from tkinter import filedialog
        directory = filedialog.askdirectory()
        if directory:
            self.temp_dir_var.set(directory)
    
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

