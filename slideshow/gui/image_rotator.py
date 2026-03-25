import tkinter as tk
from tkinter import ttk
from pathlib import Path
from PIL import Image, ImageOps, ImageTk

from slideshow.gui.helpers import wide_messagebox


class ImageRotatorDialog:
    """Dialog for previewing and rotating images"""
    
    def __init__(self, parent, slides):
        self.parent = parent
        self.config_data = parent.config_data
        self.input_folder = Path(parent.input_var.get().strip())
        
        # Store slides (mix of PhotoSlide, VideoSlide, MultiSlide)
        self.slides = slides
        
        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Preview & Rotate Images")
        self.dialog.geometry("1200x800")
        self.dialog.transient(parent)
        
        self.current_index = 0
        self.thumbnail_cache = {}  # Cache thumbnails for performance
        
        self._create_widgets()
        self._load_image()
        
        # Center dialog after widgets are created and image loaded
        self.dialog.update_idletasks()
        self._center_dialog()
    
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
            to=len(self.slides),
            orient=tk.HORIZONTAL,
            variable=self.slider_var,
            command=self._on_slider_change,
            length=400
        )
        self.slider.pack(side=tk.LEFT, padx=5)
        
        # Filename and date frame
        filename_frame = ttk.Frame(self.dialog)
        filename_frame.pack(pady=(0, 10))
        
        self.filename_label = ttk.Label(filename_frame, text="", font=("TkDefaultFont", 10, "bold"))
        self.filename_label.pack(side=tk.LEFT, padx=(0, 10))
        
        self.date_label = ttk.Label(filename_frame, text="", font=("TkDefaultFont", 10))
        self.date_label.pack(side=tk.LEFT)
        
        # Main frame with preview
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Image canvas
        canvas_frame = ttk.Frame(main_frame, relief=tk.SUNKEN, borderwidth=2)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(canvas_frame, bg='gray20')
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Rotation controls
        self.rotation_frame = ttk.Frame(self.dialog)
        self.rotation_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # MultiSlide image selector (shown only for MultiSlides)
        self.multi_selector_frame = ttk.Frame(self.rotation_frame)
        ttk.Label(self.multi_selector_frame, text="Select Image:").pack(side=tk.LEFT, padx=5)
        self.multi_image_var = tk.IntVar(value=0)
        ttk.Radiobutton(self.multi_selector_frame, text="1st", variable=self.multi_image_var, value=0, command=self._on_multi_image_select).pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(self.multi_selector_frame, text="2nd", variable=self.multi_image_var, value=1, command=self._on_multi_image_select).pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(self.multi_selector_frame, text="3rd", variable=self.multi_image_var, value=2, command=self._on_multi_image_select).pack(side=tk.LEFT, padx=2)
        ttk.Label(self.multi_selector_frame, text="│").pack(side=tk.LEFT, padx=10)
        
        # Standard rotation controls (work for both PhotoSlide and selected MultiSlide image)
        ttk.Label(self.rotation_frame, text="Rotate:").pack(side=tk.LEFT, padx=5)
        ttk.Button(self.rotation_frame, text="↶ 90° Left", command=lambda: self._rotate(-90)).pack(side=tk.LEFT, padx=5)
        ttk.Button(self.rotation_frame, text="↷ 90° Right", command=lambda: self._rotate(90)).pack(side=tk.LEFT, padx=5)
        ttk.Button(self.rotation_frame, text="↻ 180°", command=lambda: self._rotate(180)).pack(side=tk.LEFT, padx=5)
        ttk.Button(self.rotation_frame, text="🗑 Delete", command=self._delete_image).pack(side=tk.LEFT, padx=(20, 5))
        
        self.rotation_label = ttk.Label(self.rotation_frame, text="", font=("TkDefaultFont", 10))
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
        """Load and display the current slide (photo, video, or multi)"""
        if not self.slides:
            return
        
        slide = self.slides[self.current_index]
        from slideshow.slides.photo_slide import PhotoSlide
        from slideshow.slides.video_slide import VideoSlide
        from slideshow.slides.multi_slide import MultiSlide
        
        # Update counter
        self.counter_label.config(text=f"Slide {self.current_index + 1} of {len(self.slides)}")
        
        # Update slider to match current index (without triggering callback)
        self.slider_var.set(self.current_index + 1)
        
        # Clear rotation label
        self.rotation_label.config(text="")
        
        # Show/hide MultiSlide selector based on slide type
        if isinstance(slide, MultiSlide):
            self.multi_selector_frame.pack(side=tk.LEFT)
        else:
            self.multi_selector_frame.pack_forget()
        
        # Handle different slide types
        if isinstance(slide, VideoSlide):
            # Show video placeholder
            self._show_video_placeholder(slide)
        elif isinstance(slide, MultiSlide):
            # Show MultiSlide composite preview
            self._show_multislide_preview(slide)
        elif isinstance(slide, PhotoSlide):
            # Show normal photo
            self._show_photo(slide)
        else:
            self.parent.log_message(f"Unknown slide type: {type(slide)}")
    
    def _show_photo(self, slide):
        """Display a PhotoSlide"""
        image_path = slide.path
        filename = image_path.name
        
        self.filename_label.config(text=filename)
        
        # Load image using the slide's preview method
        try:
            img = slide.get_preview_image()
            
            # Extract creation date from EXIF
            date_str = self._extract_creation_date_from_image(img, image_path)
            self.date_label.config(text=date_str)
            
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
    
    def _show_video_placeholder(self, slide):
        """Show placeholder for VideoSlide"""
        video_path = slide.path
        filename = video_path.name
        
        self.filename_label.config(text=f"{filename} [VIDEO]")
        self.date_label.config(text="Video file")
        
        # Show text placeholder
        self.canvas.delete("all")
        canvas_width = self.canvas.winfo_width() or 1000
        canvas_height = self.canvas.winfo_height() or 600
        
        self.canvas.create_text(
            canvas_width // 2, canvas_height // 2,
            text=f"VIDEO\n{filename}",
            font=("Arial", 24, "bold"),
            fill="gray"
        )
    
    def _on_multi_image_select(self):
        """Called when a radio button is clicked to show the selected individual image."""
        if not self.slides:
            return
        slide = self.slides[self.current_index]
        from slideshow.slides.multi_slide import MultiSlide
        if not isinstance(slide, MultiSlide):
            return
        
        component_index = self.multi_image_var.get()
        image_path = slide.media_files[component_index]
        self.filename_label.config(text=f"[MULTI image {component_index + 1}] {image_path.name}")
        self.date_label.config(text=f"Image {component_index + 1} of {len(slide.media_files)}")
        
        try:
            img = Image.open(image_path)
            img = ImageOps.exif_transpose(img)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            canvas_width = self.canvas.winfo_width() or 1000
            canvas_height = self.canvas.winfo_height() or 600
            
            img_ratio = img.width / img.height
            canvas_ratio = canvas_width / canvas_height
            
            if img_ratio > canvas_ratio:
                new_width = canvas_width - 40
                new_height = int(new_width / img_ratio)
            else:
                new_height = canvas_height - 40
                new_width = int(new_height * img_ratio)
            
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            self.photo = ImageTk.PhotoImage(img)
            self.canvas.delete("all")
            self.canvas.create_image(canvas_width // 2, canvas_height // 2, image=self.photo)
        except Exception as e:
            self.parent.log_message(f"Error loading MultiSlide component image: {e}")
    
    def _show_multislide_preview(self, slide):
        """Show preview of MultiSlide composite"""
        # Reset radio selection to first image
        self.multi_image_var.set(0)
        
        # Show the first image file name with [MULTI] indicator
        first_file = slide.media_files[0]
        filenames = " + ".join([f.name for f in slide.media_files])
        
        self.filename_label.config(text=f"[MULTI] {filenames}")
        self.date_label.config(text="Multi-slide composite (3 images)")
        
        # Generate composite preview using slide's preview method
        try:
            img = slide.get_preview_image()
            if img:
                
                # Resize to fit canvas
                canvas_width = self.canvas.winfo_width() or 1000
                canvas_height = self.canvas.winfo_height() or 600
                
                img_ratio = img.width / img.height
                canvas_ratio = canvas_width / canvas_height
                
                if img_ratio > canvas_ratio:
                    new_width = canvas_width - 40
                    new_height = int(new_width / img_ratio)
                else:
                    new_height = canvas_height - 40
                    new_width = int(new_height * img_ratio)
                
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                self.photo = ImageTk.PhotoImage(img)
                self.canvas.delete("all")
                self.canvas.create_image(canvas_width // 2, canvas_height // 2, image=self.photo)
        except Exception as e:
            self.parent.log_message(f"Error creating MultiSlide preview: {e}")
            # Fallback to text
            self.canvas.delete("all")
            canvas_width = self.canvas.winfo_width() or 1000
            canvas_height = self.canvas.winfo_height() or 600
            self.canvas.create_text(
                canvas_width // 2, canvas_height // 2,
                text=f"MULTI-SLIDE\n{filenames}",
                font=("Arial", 18),
                fill="blue"
            )
    
    def _rotate(self, degrees):
        """Rotate and save the current image by the specified degrees"""
        if not self.slides:
            return
        
        slide = self.slides[self.current_index]
        from slideshow.slides.photo_slide import PhotoSlide
        from slideshow.slides.multi_slide import MultiSlide
        
        # Handle MultiSlide - select component then rotate
        if isinstance(slide, MultiSlide):
            component_index = self.multi_image_var.get()
            slide.select_component(component_index)
            if slide.rotate(degrees):
                filename = slide.media_files[component_index].name
                self.parent.log_message(f"Rotated MultiSlide image #{component_index + 1} ({filename}) by {degrees}°")
                # Invalidate cached preview so composite regenerates next time
                slide._preview_image = None
                # Show the rotated individual image (not the composite)
                self._on_multi_image_select()
            else:
                wide_messagebox("error", "Error", "Failed to rotate MultiSlide component image")
            return
        
        # Handle PhotoSlide and other slide types
        if slide.rotate(degrees):
            self.parent.log_message(f"Rotated and saved {slide.path.name} by {degrees}° (EXIF preserved)")
            self.thumbnail_cache.pop(slide.path.name, None)
            self._load_image()
        else:
            wide_messagebox("info", "Info", "Rotation is not supported for this slide type")
    
    def _extract_creation_date_from_image(self, img: Image.Image, image_path: Path) -> str:
        """Extract creation date from an already-opened image (optimized to avoid re-opening)"""
        try:
            import datetime as dt
            ext = image_path.suffix.lower()
            
            # Try EXIF date first for photos (using the already-opened image)
            if ext in ('.jpg', '.jpeg', '.heic', '.heif'):
                try:
                    from PIL.ExifTags import TAGS
                    exif_data = img._getexif()
                    if exif_data:
                        for tag_id, value in exif_data.items():
                            tag = TAGS.get(tag_id, tag_id)
                            if tag == 'DateTimeOriginal':
                                # Parse EXIF date format: "2023:12:25 14:30:45"
                                date_obj = dt.datetime.strptime(value, '%Y:%m:%d %H:%M:%S')
                                return date_obj.strftime('%Y-%m-%d %H:%M:%S')
                except Exception:
                    pass  # Fall through to file timestamp
            
            # Fall back to file creation/modification time
            stat = image_path.stat()
            timestamp = getattr(stat, 'st_birthtime', stat.st_mtime)
            date_obj = dt.datetime.fromtimestamp(timestamp)
            return date_obj.strftime('%Y-%m-%d %H:%M:%S')
            
        except Exception:
            return ""
    
    def _prev_image(self):
        """Go to previous image"""
        if self.current_index > 0:
            self.current_index -= 1
            self._load_image()
    
    def _next_image(self):
        """Go to next slide"""
        if self.current_index < len(self.slides) - 1:
            self.current_index += 1
            self._load_image()
    
    def _jump_to_image(self):
        """Jump to a specific slide number"""
        try:
            target = int(self.jump_var.get()) - 1  # Convert to 0-based index
            if 0 <= target < len(self.slides):
                self.current_index = target
                self._load_image()
            else:
                wide_messagebox("error", "Error", f"Please enter a number between 1 and {len(self.slides)}")
        except ValueError:
            wide_messagebox("error", "Error", "Please enter a valid number")
    
    def _on_slider_change(self, value):
        """Handle slider value change for rapid scrolling"""
        # Convert slider value (1-based) to array index (0-based)
        target = int(float(value)) - 1
        if 0 <= target < len(self.slides) and target != self.current_index:
            self.current_index = target
            self._load_image()
    
    def _delete_image(self):
        """Delete the current slide after confirmation"""
        if not self.slides:
            return
        
        slide = self.slides[self.current_index]
        from slideshow.slides.photo_slide import PhotoSlide
        
        # Only allow deletion of PhotoSlides (not videos or multislides)
        if not isinstance(slide, PhotoSlide):
            wide_messagebox("info", "Info", "Only individual photo slides can be deleted")
            return
        
        image_path = slide.path
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
                del self.slides[self.current_index]
                
                # Clear thumbnail cache
                self.thumbnail_cache.pop(filename, None)
                
                # Update slider range
                self.slider.config(to=len(self.slides))
                
                # Check if we have any slides left
                if not self.slides:
                    wide_messagebox("info", "No Images", "No more slides in folder.")
                    self.dialog.destroy()
                    return
                
                # Adjust index if needed
                if self.current_index >= len(self.slides):
                    self.current_index = len(self.slides) - 1
                
                # Load the next/previous slide
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
