"""
Video Editor GUI - Visual timeline editor for non-destructive video editing
"""
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from typing import Optional, List
import subprocess
import sys
import threading

from slideshow.video_editor import VideoEditor, SlideshowMetadata, VideoSegment
from slideshow.transitions.ffmpeg_paths import FFmpegPaths


class VideoEditorDialog(tk.Toplevel):
    """Visual timeline editor for slideshow videos"""
    
    def __init__(self, parent, video_path: str, metadata_path: Optional[str] = None):
        super().__init__(parent)
        
        self.video_path = Path(video_path)
        self.metadata_path = Path(metadata_path) if metadata_path else None
        
        # Try to find metadata if not provided
        if not self.metadata_path or not self.metadata_path.exists():
            auto_metadata = Path(str(video_path).rsplit('.', 1)[0] + '.metadata.json')
            if auto_metadata.exists():
                self.metadata_path = auto_metadata
        
        if not self.metadata_path or not self.metadata_path.exists():
            messagebox.showerror("Metadata Not Found", 
                               f"Could not find metadata file for:\n{video_path}\n\n"
                               "Make sure 'Keep intermediate frames for debugging' is enabled in Settings "
                               "and re-render the video.")
            self.destroy()
            return
        
        # Load metadata and create editor
        try:
            self.metadata = SlideshowMetadata.load(self.video_path)
            if self.metadata is None:
                raise FileNotFoundError(f"Metadata file not found for {self.video_path}")
            self.editor = VideoEditor(str(video_path), self.metadata)
            
            # Clean up any old edited videos from previous sessions
            old_edited = self.video_path.parent / f"{self.video_path.stem}_edited{self.video_path.suffix}"
            if old_edited.exists():
                old_edited.unlink()
                
        except Exception as e:
            messagebox.showerror("Editor Error", f"Failed to load video editor:\n{e}")
            self.destroy()
            return
        
        # Track changes
        self.pending_operations = []  # List of (operation, args)
        self.deleted_segments = set()  # Track segments marked for deletion
        self.modified = False
        self.selected_row = None  # Track selected row for highlighting
        self.just_applied_changes = False  # Track if we just applied changes
        
        # Setup window
        self.title(f"Video Editor - {self.video_path.name}")
        self.geometry("750x700")
        self.resizable(True, True)
        
        # Center window on screen
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")
        
        # Make modal and bring to front
        self.transient(parent)
        self.lift()
        self.focus_force()
        
        # Build UI
        try:
            self.create_widgets()
            self.refresh_timeline()
        except Exception as e:
            messagebox.showerror("UI Error", f"Failed to create editor UI:\n{e}")
            import traceback
            traceback.print_exc()
            self.destroy()
            return
        
        # Grab focus after UI is built
        self.grab_set()
        
        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self.on_close)
    
    def create_widgets(self):
        """Create the editor UI"""
        # Main layout: top info, middle timeline, bottom controls
        
        # === TOP: Video Info ===
        info_frame = ttk.Frame(self, padding=5)
        info_frame.pack(fill=tk.X)
        
        ttk.Label(info_frame, text=f"Video: {self.video_path.name}", 
                 font=('Arial', 10, 'bold')).pack(anchor=tk.W)
        
        duration = self.metadata.get_total_duration()
        ttk.Label(info_frame, 
                 text=f"Duration: {self._format_time(duration)} | Segments: {len(self.metadata.segments)}",
                 font=('Arial', 9)).pack(anchor=tk.W)
        
        # === MIDDLE: Timeline (scrollable) ===
        timeline_frame = ttk.LabelFrame(self, text="Timeline", padding=5)
        timeline_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Progress bar at the top
        progress_header = ttk.Frame(timeline_frame)
        progress_header.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(progress_header, text="Segments:", font=('Arial', 9, 'bold')).pack(side=tk.LEFT, padx=(0, 10))
        
        self.progress_var = tk.IntVar(value=0)
        self.progress_bar = ttk.Progressbar(progress_header, variable=self.progress_var, 
                                           maximum=100, mode='determinate')
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Canvas with scrollbar for timeline
        canvas_frame = ttk.Frame(timeline_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        self.timeline_canvas = tk.Canvas(canvas_frame, bg='white', highlightthickness=1, highlightbackground='gray')
        scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.timeline_canvas.yview)
        
        self.timeline_canvas.configure(yscrollcommand=scrollbar.set)
        self.timeline_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Timeline content frame (created dynamically)
        self.timeline_frame = ttk.Frame(self.timeline_canvas)
        self.timeline_window = self.timeline_canvas.create_window((0, 0), window=self.timeline_frame, anchor=tk.NW)
        
        # Bind canvas resize
        self.timeline_frame.bind('<Configure>', self._on_timeline_configure)
        self.timeline_canvas.bind('<Configure>', self._on_canvas_configure)
        
        # Mouse wheel scrolling support - bind to canvas and will bind to children dynamically
        self._bind_mousewheel(self.timeline_canvas)
        self._bind_mousewheel(self.timeline_frame)
        
        # === BOTTOM: Controls ===
        control_frame = ttk.Frame(self, padding=5)
        control_frame.pack(fill=tk.X)
        
        # Left: Action buttons
        left_controls = ttk.Frame(control_frame)
        left_controls.pack(side=tk.LEFT)
        
        ttk.Button(left_controls, text="▶ Play Video", 
                  command=self.play_video).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(left_controls, text="🔄 Refresh", 
                  command=self.refresh_timeline).pack(side=tk.LEFT, padx=(0, 5))
        
        # Right: Save/Cancel buttons
        right_controls = ttk.Frame(control_frame)
        right_controls.pack(side=tk.RIGHT)
        
        self.save_button = ttk.Button(right_controls, text="💾 Apply Changes", 
                                     command=self.apply_changes, state='disabled')
        self.save_button.pack(side=tk.LEFT, padx=(0, 5))
        
        self.save_as_button = ttk.Button(right_controls, text="💾 Save Edited Video As...",
                                        command=self.save_edited_video_as, state='disabled')
        self.save_as_button.pack(side=tk.LEFT, padx=(0, 5))
        
        self.cancel_button = ttk.Button(right_controls, text="↺ Cancel", 
                                       command=self.cancel_changes, state='disabled')
        self.cancel_button.pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(right_controls, text="❌ Close", 
                  command=self.on_close).pack(side=tk.LEFT)
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)
    
    def _bind_mousewheel(self, widget):
        """Bind mouse wheel scrolling to a widget"""
        widget.bind('<MouseWheel>', self._on_mousewheel)  # Windows/Mac
        widget.bind('<Button-4>', self._on_mousewheel)    # Linux scroll up
        widget.bind('<Button-5>', self._on_mousewheel)    # Linux scroll down
    
    def refresh_timeline(self):
        """Rebuild the timeline display"""
        # Clear existing timeline
        for widget in self.timeline_frame.winfo_children():
            widget.destroy()
        
        # Configure grid columns to be uniform and tight
        for col in range(5):
            self.timeline_frame.grid_columnconfigure(col, weight=0, uniform='col')
        
        # Configure ALL rows with minsize=0 to eliminate spacing
        # Pre-configure enough rows for most slideshows
        for row_num in range(5000):  # Support up to 5000 segments
            self.timeline_frame.grid_rowconfigure(row_num, minsize=0, weight=0)
        
        # Header row directly in grid (no intermediate frame)
        header_bg = '#e0e0e0'
        tk.Label(self.timeline_frame, text="#", width=4, height=1, font=('Arial', 8, 'bold'), 
                bg=header_bg, relief=tk.RIDGE, bd=1).grid(row=0, column=0, sticky='nsew', padx=0, pady=0, ipady=0, ipadx=0)
        tk.Label(self.timeline_frame, text="Type", width=11, height=1, font=('Arial', 8, 'bold'),
                bg=header_bg, relief=tk.RIDGE, bd=1).grid(row=0, column=1, sticky='nsew', padx=0, pady=0, ipady=0, ipadx=0)
        tk.Label(self.timeline_frame, text="Duration", width=9, height=1, font=('Arial', 8, 'bold'),
                bg=header_bg, relief=tk.RIDGE, bd=1).grid(row=0, column=2, sticky='nsew', padx=0, pady=0, ipady=0, ipadx=0)
        tk.Label(self.timeline_frame, text="Time Range", width=18, height=1, font=('Arial', 8, 'bold'),
                bg=header_bg, relief=tk.RIDGE, bd=1).grid(row=0, column=3, sticky='nsew', padx=0, pady=0, ipady=0, ipadx=0)
        tk.Label(self.timeline_frame, text="Actions", width=8, height=1, font=('Arial', 8, 'bold'),
                bg=header_bg, relief=tk.RIDGE, bd=1).grid(row=0, column=4, sticky='nsew', padx=0, pady=0, ipady=0, ipadx=0)
        
        # Segments directly in grid (one widget per cell) - skip deleted ones
        row_num = 1
        for segment in self.metadata.segments:
            if segment.index not in self.deleted_segments:
                self._create_segment_row(row_num, segment)
                row_num += 1
        
        # Update scrollregion
        self.timeline_frame.update_idletasks()
        self.timeline_canvas.configure(scrollregion=self.timeline_canvas.bbox('all'))
    
    def _create_segment_row(self, row: int, segment: VideoSegment):
        """Create a single segment row in timeline using direct grid layout"""
        # Determine background color (selection overrides alternating colors)
        if self.selected_row == row:
            bg_color = '#4A90E2'  # Blue highlight for selected row
            fg_color = 'white'
        else:
            bg_color = 'white' if row % 2 else '#f8f8f8'
            fg_color = 'black'
        
        # Store row widgets for later access
        row_widgets = []
        
        # Index cell - minimal height
        idx_label = tk.Label(self.timeline_frame, text=f"{segment.index}", width=4, height=1,
                            font=('Arial', 8), bg=bg_color, fg=fg_color, relief=tk.RIDGE, bd=1, anchor='center')
        idx_label.grid(row=row, column=0, sticky='nsew', padx=0, pady=0, ipady=0, ipadx=0)
        idx_label.bind('<Button-1>', lambda e, r=row: self._select_row(r))
        self._bind_mousewheel(idx_label)
        row_widgets.append(idx_label)
        
        # Type cell with color coding
        type_color = self._get_type_color(segment.type) if self.selected_row != row else bg_color
        type_label = tk.Label(self.timeline_frame, text=segment.type, width=11, height=1,
                             bg=type_color, fg=fg_color, relief=tk.RIDGE, bd=1, font=('Arial', 8), anchor='w', padx=3)
        type_label.grid(row=row, column=1, sticky='nsew', padx=0, pady=0, ipady=0, ipadx=0)
        type_label.bind('<Button-1>', lambda e, r=row: self._select_row(r))
        self._bind_mousewheel(type_label)
        row_widgets.append(type_label)
        
        # Duration cell
        dur_label = tk.Label(self.timeline_frame, text=self._format_time(segment.duration), width=9, height=1,
                            font=('Arial', 8), bg=bg_color, fg=fg_color, relief=tk.RIDGE, bd=1, anchor='e', padx=3)
        dur_label.grid(row=row, column=2, sticky='nsew', padx=0, pady=0, ipady=0, ipadx=0)
        dur_label.bind('<Button-1>', lambda e, r=row: self._select_row(r))
        self._bind_mousewheel(dur_label)
        row_widgets.append(dur_label)
        
        # Time range cell
        time_range = f"{self._format_time(segment.start_time)} → {self._format_time(segment.end_time)}"
        time_label = tk.Label(self.timeline_frame, text=time_range, width=18, height=1, font=('Arial', 8),
                             bg=bg_color, fg=fg_color, relief=tk.RIDGE, bd=1, anchor='center')
        time_label.grid(row=row, column=3, sticky='nsew', padx=0, pady=0, ipady=0, ipadx=0)
        time_label.bind('<Button-1>', lambda e, r=row: self._select_row(r))
        self._bind_mousewheel(time_label)
        row_widgets.append(time_label)
        
        # Actions cell - frame with buttons
        actions_frame = tk.Frame(self.timeline_frame, bg=bg_color, relief=tk.RIDGE, bd=1, height=1)
        actions_frame.grid(row=row, column=4, sticky='nsew', padx=0, pady=0, ipady=0, ipadx=0)
        actions_frame.bind('<Button-1>', lambda e, r=row: self._select_row(r))
        self._bind_mousewheel(actions_frame)
        row_widgets.append(actions_frame)
        
        # Preview button
        preview_btn = tk.Button(actions_frame, text="👁", width=2, font=('Arial', 8),
                               relief=tk.FLAT, bd=0, bg=bg_color, fg=fg_color,
                               command=lambda: self._preview_and_select(segment, row))
        preview_btn.pack(side=tk.LEFT, padx=1, pady=0)
        self._bind_mousewheel(preview_btn)
        
        # Remove button (not for intro)
        if segment.type != 'intro':
            remove_btn = tk.Button(actions_frame, text="🗑", width=2, font=('Arial', 8),
                                  relief=tk.FLAT, bd=0, bg=bg_color, fg=fg_color,
                                  command=lambda: self._remove_segment(segment))
            remove_btn.pack(side=tk.LEFT, padx=1, pady=0)
            self._bind_mousewheel(remove_btn)
    
    def _get_type_color(self, segment_type: str) -> str:
        """Get color for segment type"""
        colors = {
            'intro': '#FFE5B4',      # Peach
            'slide': '#B4E5FF',      # Light blue
            'multi_slide': '#D4B4FF', # Lavender
            'transition': '#B4FFB4'   # Light green
        }
        return colors.get(segment_type, '#EEEEEE')
    
    def _format_time(self, seconds: float) -> str:
        """Format seconds as MM:SS.ms"""
        mins = int(seconds // 60)
        secs = seconds % 60
        return f"{mins:02d}:{secs:05.2f}"
    
    def _select_row(self, row: int):
        """Select and highlight a row"""
        self.selected_row = row
        self.refresh_timeline()
    
    def _preview_and_select(self, segment: VideoSegment, row: int):
        """Preview segment and select the row"""
        self.selected_row = row
        self.refresh_timeline()
        self._preview_segment(segment)
    
    def _on_mousewheel(self, event):
        """Handle mouse wheel scrolling"""
        if sys.platform == 'darwin':  # macOS
            self.timeline_canvas.yview_scroll(int(-1 * event.delta), "units")
        elif event.num == 4:  # Linux scroll up
            self.timeline_canvas.yview_scroll(-1, "units")
        elif event.num == 5:  # Linux scroll down
            self.timeline_canvas.yview_scroll(1, "units")
        else:  # Windows
            self.timeline_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
    
    def _on_timeline_configure(self, event):
        """Update canvas scroll region when timeline changes"""
        self.timeline_canvas.configure(scrollregion=self.timeline_canvas.bbox('all'))
    
    def _on_canvas_configure(self, event):
        """Update timeline frame width when canvas is resized"""
        canvas_width = event.width
        self.timeline_canvas.itemconfig(self.timeline_window, width=canvas_width)
    
    def _preview_segment(self, segment: VideoSegment):
        """Preview a segment by playing the rendered clip"""
        # Always play the rendered clip (the actual slide/transition video)
        # not the source image, since we want to see what's in the final video
        self._play_clip(segment.rendered_path)
    
    def _play_clip(self, clip_path: str):
        """Play a video clip"""
        if not Path(clip_path).exists():
            messagebox.showerror("File Not Found", f"Clip not found:\n{clip_path}\n\n"
                               "Make sure 'Keep intermediate frames' is enabled.")
            return
        
        try:
            if sys.platform == 'darwin':  # macOS
                # Use 'open' to play with default video player
                subprocess.Popen(['open', clip_path])
                self.status_var.set(f"Playing rendered clip: {Path(clip_path).name} (check your video player)")
            elif sys.platform == 'win32':  # Windows
                subprocess.Popen(['start', clip_path], shell=True)
                self.status_var.set(f"Playing: {Path(clip_path).name}")
            else:  # Linux
                subprocess.Popen(['xdg-open', clip_path])
                self.status_var.set(f"Playing: {Path(clip_path).name}")
        except Exception as e:
            messagebox.showerror("Playback Error", f"Failed to play clip:\n{e}")
    
    def _remove_segment(self, segment: VideoSegment):
        """Remove a segment immediately from the list (applied on Apply Changes)"""
        # Add to pending operations and deleted set
        self.pending_operations.append(('remove', segment.index))
        self.deleted_segments.add(segment.index)
        self.modified = True
        self.save_button.configure(state='normal')
        self.cancel_button.configure(state='normal')
        
        # Refresh to hide the deleted segment
        self.refresh_timeline()
        
        # Update status
        try:
            new_duration, descriptions = self.editor.preview_edit("remove", segment.index)
            num_deleted = len(self.deleted_segments)
            segment_type = segment.type.capitalize()
            status_msg = f"Marked {num_deleted} item(s) for deletion → New duration: {new_duration:.2f}s"
            
            # Add note if deleting slides (transitions will still have their frames)
            if segment.type == 'slide':
                status_msg += " (Note: Adjacent transitions may still show slide frames)"
            
            self.status_var.set(status_msg)
        except Exception as e:
            self.status_var.set(f"Marked segment {segment.index} for deletion")
            import traceback
            traceback.print_exc()
    
    def apply_changes(self):
        """Apply all pending operations (threaded)"""
        if not self.pending_operations:
            messagebox.showinfo("No Changes", "No pending changes to apply.")
            return
        
        # Confirm
        num_ops = len(self.pending_operations)
        
        # Check if deleting slides with transitions
        has_slide_deletions = any(op == 'remove' and self.editor.metadata.segments[args[0]].type == 'slide' 
                                  for op, *args in self.pending_operations)
        
        message = f"Apply {num_ops} operation(s) to the video?\n\n" \
                  f"Original: {self.video_path.name}\n" \
                  f"New file will be created: {self.video_path.stem}_edited{self.video_path.suffix}\n\n"
        
        if has_slide_deletions:
            message += "⚠️ Note: Transitions contain frames from adjacent slides.\n" \
                      "Deleted slides may briefly appear in remaining transitions.\n\n"
        
        message += "This may take several minutes..."
        
        result = messagebox.askyesno("Confirm Changes", message)
        
        if not result:
            return
        
        # Disable buttons during processing
        self.save_button.configure(state='disabled')
        self.cancel_button.configure(state='disabled')
        self.status_var.set("Processing changes...")
        
        # Create output path
        self.output_path = self.video_path.parent / f"{self.video_path.stem}_edited{self.video_path.suffix}"
        
        # Run in background thread
        apply_thread = threading.Thread(target=self._apply_changes_thread, daemon=True)
        apply_thread.start()
    
    def _apply_changes_thread(self):
        """Background thread for applying changes"""
        try:
            # Batch all remove operations into one call for efficiency
            remove_indices = [args[0] for operation, *args in self.pending_operations if operation == 'remove']
            
            if remove_indices:
                # Update status
                total_removes = len(remove_indices)
                self.after(0, lambda: self.status_var.set(f"Removing {total_removes} segment(s) in one operation..."))
                
                # Define progress callback
                def update_progress(pct, msg):
                    self.after(0, lambda p=pct: self.progress_var.set(p))
                    self.after(0, lambda m=msg: self.status_var.set(m))
                
                try:
                    # Single batch operation with progress callback
                    success = self.editor.remove_segments(remove_indices, self.output_path, update_progress)
                    if not success:
                        raise RuntimeError(f"Failed to remove segments: {remove_indices}")
                except Exception as seg_error:
                    raise RuntimeError(f"Error removing segments: {str(seg_error)}")
                
                # Set progress to 100%
                self.after(0, lambda: self.progress_var.set(100))
            
            # Success - update UI on main thread
            self.after(0, self._on_apply_success)
            
        except Exception as e:
            # Error - show message on main thread
            import traceback
            error_msg = f"{str(e)}\n\n{traceback.format_exc()}"
            self.after(0, lambda msg=error_msg: self._on_apply_error(msg))
    
    def _on_apply_success(self):
        """Called on main thread after successful apply"""
        # Reset progress bar
        self.progress_var.set(0)
        
        messagebox.showinfo(
            "Success!",
            f"Video edited successfully!\n\n"
            f"New file: {self.output_path.name}\n"
            f"Original preserved: {self.video_path.name}\n\n"
            f"Use 'Save Edited Video As...' to save it elsewhere."
        )
        
        self.pending_operations = []
        self.deleted_segments = set()
        self.modified = False
        self.just_applied_changes = True  # Mark that we just applied changes
        self.save_button.configure(state='disabled')
        self.save_as_button.configure(state='normal')  # Enable Save As button
        self.cancel_button.configure(state='disabled')
        self.status_var.set("Changes applied successfully")
        
        # Reload metadata from new file
        new_metadata_path = Path(str(self.output_path).rsplit('.', 1)[0] + '.metadata.json')
        if new_metadata_path.exists():
            self.metadata = SlideshowMetadata.load(new_metadata_path)
            self.editor = VideoEditor(str(self.output_path), self.metadata)
            self.video_path = self.output_path
            self.refresh_timeline()
    
    def _on_apply_error(self, error_msg: str):
        """Called on main thread after error"""
        # Reset progress bar
        self.progress_var.set(0)
        
        messagebox.showerror("Edit Failed", f"Failed to apply changes:\n{error_msg}")
        self.status_var.set("Error applying changes")
        self.save_button.configure(state='normal')
        self.cancel_button.configure(state='normal')
    
    def play_video(self):
        """Play the full video (edited version only if just applied changes)"""
        # Only play edited version if we just applied changes AND it exists
        edited_path = self.video_path.parent / f"{self.video_path.stem}_edited{self.video_path.suffix}"
        
        if self.just_applied_changes and edited_path.exists():
            video_to_play = edited_path
            play_edited = True
        else:
            video_to_play = self.video_path
            play_edited = False
        
        try:
            if sys.platform == 'darwin':  # macOS
                subprocess.Popen(['open', str(video_to_play)])
            elif sys.platform == 'win32':  # Windows
                subprocess.Popen(['start', str(video_to_play)], shell=True)
            else:  # Linux
                subprocess.Popen(['xdg-open', str(video_to_play)])
            
            if play_edited:
                self.status_var.set(f"Playing edited video: {video_to_play.name}")
            else:
                self.status_var.set(f"Playing original video: {video_to_play.name}")
        except Exception as e:
            messagebox.showerror("Playback Error", f"Failed to play video:\n{e}")
    
    def save_edited_video_as(self):
        """Save the edited video to a user-specified location"""
        from tkinter import filedialog
        import shutil
        
        edited_path = self.video_path.parent / f"{self.video_path.stem}_edited{self.video_path.suffix}"
        
        if not edited_path.exists():
            messagebox.showerror("Error", "No edited video found. Apply changes first.")
            return
        
        # Ask user where to save
        save_path = filedialog.asksaveasfilename(
            title="Save Edited Video As",
            defaultextension=".mp4",
            initialfile=f"{self.video_path.stem}_edited.mp4",
            filetypes=[("MP4 Video", "*.mp4"), ("All Files", "*.*")]
        )
        
        if save_path:
            try:
                shutil.copy2(edited_path, save_path)
                messagebox.showinfo("Success", f"Edited video saved to:\n{save_path}")
                self.status_var.set(f"Edited video saved: {Path(save_path).name}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save video:\n{e}")
    
    def cancel_changes(self):
        """Cancel all pending changes and restore deleted segments"""
        if not self.pending_operations:
            return
        
        # Clear all pending operations and deleted segments
        self.pending_operations = []
        self.deleted_segments = set()
        self.modified = False
        self.just_applied_changes = False  # Clear the flag
        self.save_button.configure(state='disabled')
        self.cancel_button.configure(state='disabled')
        
        # Refresh timeline to show all segments again
        self.refresh_timeline()
        self.status_var.set("All changes cancelled")
    
    def on_close(self):
        """Handle window close"""
        if self.modified and self.pending_operations:
            result = messagebox.askyesnocancel(
                "Unsaved Changes",
                "You have pending changes that haven't been applied.\n\n"
                "Apply changes before closing?"
            )
            
            if result is None:  # Cancel
                return
            elif result:  # Yes - apply changes
                self.apply_changes()
                # Don't close if applying failed
                if self.modified:
                    return
        
        self.destroy()


def open_video_editor(parent, video_path: str):
    """Open the video editor dialog"""
    VideoEditorDialog(parent, video_path)
