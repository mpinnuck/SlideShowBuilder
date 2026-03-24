import re
import tkinter as tk
from tkinter import ttk
from pathlib import Path


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
    Build full project paths under ~/SlideShowBuilder/ProjectName/
    Returns: (input_path, output_path)
    """
    if not project_name:
        return ("", "")
    sanitized = sanitize_project_name(project_name)
    from slideshow.config import Config
    base_path = Config.APP_SETTINGS_DIR / sanitized
    input_path = str(base_path / "Slides")
    output_path = str(base_path / "Output")
    return (input_path, output_path)

def build_output_path(base_folder: str, project_name: str) -> str:
    """Build full output path: base_folder/projectname (no spaces)."""
    if not base_folder or not project_name:
        return base_folder
    sanitized = sanitize_project_name(project_name)
    return str(Path(base_folder) / sanitized)
