import tkinter as tk
from tkinter import ttk
from pathlib import Path
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS


class ExifViewerDialog:
    """Dialog that displays EXIF metadata for an image file"""

    def __init__(self, parent, image_path: Path):
        self.parent = parent
        self.image_path = image_path
        self.popup = None

        try:
            img = Image.open(image_path)
            exif_data = img._getexif()
        except Exception:
            exif_data = None

        if not exif_data:
            from slideshow.gui.helpers import wide_messagebox
            wide_messagebox("info", "No EXIF", f"No EXIF data found in {image_path.name}")
            return

        lines = self._format_exif(exif_data)
        self._show_popup(lines)

    def close(self):
        """Close the popup if it exists"""
        if self.popup and self.popup.winfo_exists():
            self.popup.destroy()
            self.popup = None

    def is_open(self):
        """Return True if the popup is currently displayed"""
        return self.popup is not None and self.popup.winfo_exists()

    def _format_exif(self, exif_data: dict) -> list[str]:
        """Format raw EXIF data into human-readable lines"""
        lines = []
        for tag_id, value in sorted(exif_data.items()):
            tag_name = TAGS.get(tag_id, f"Unknown({tag_id})")
            # Skip binary/large blobs
            if isinstance(value, bytes) and len(value) > 64:
                value = f"<{len(value)} bytes>"
            elif isinstance(value, bytes):
                value = value.hex()
            # Expand GPS info
            if tag_name == "GPSInfo" and isinstance(value, dict):
                lines.append(f"{tag_name}:")
                for gps_tag_id, gps_value in value.items():
                    gps_tag_name = GPSTAGS.get(gps_tag_id, f"Unknown({gps_tag_id})")
                    lines.append(f"  {gps_tag_name}: {gps_value}")
                continue
            lines.append(f"{tag_name}: {value}")
        return lines

    def _show_popup(self, lines: list[str]):
        """Show a scrollable popup with the EXIF text, positioned at the right edge of the parent"""
        self.popup = tk.Toplevel(self.parent)
        self.popup.title(f"EXIF Data \u2014 {self.image_path.name}")
        self.popup.transient(self.parent)

        # Size the window to fit all lines (with a reasonable width)
        popup_width = 520
        line_height = 18  # approximate pixels per line at font size 11
        padding = 60  # title bar + margins
        popup_height = max(300, len(lines) * line_height + padding)

        # Position: center of popup on the right edge of parent, vertically centered
        self.parent.update_idletasks()
        parent_x = self.parent.winfo_rootx()
        parent_y = self.parent.winfo_rooty()
        parent_w = self.parent.winfo_width()
        parent_h = self.parent.winfo_height()

        x = parent_x + parent_w - popup_width // 2
        y = parent_y + parent_h // 2 - popup_height // 2

        # Clamp to screen bounds
        screen_w = self.parent.winfo_screenwidth()
        screen_h = self.parent.winfo_screenheight()
        x = max(0, min(x, screen_w - popup_width))
        y = max(0, min(y, screen_h - popup_height))

        self.popup.geometry(f"{popup_width}x{popup_height}+{x}+{y}")

        text_widget = tk.Text(self.popup, wrap=tk.WORD, font=("TkFixedFont", 11))
        scrollbar = ttk.Scrollbar(self.popup, orient=tk.VERTICAL, command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        text_widget.insert(tk.END, "\n".join(lines))
        text_widget.configure(state=tk.DISABLED)
