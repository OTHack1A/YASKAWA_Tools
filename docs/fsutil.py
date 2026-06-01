"""Filesystem helpers shared across the GUI.

Kept dependency-free (only stdlib) so any view can import it without pulling
in heavy modules such as reportlab.
"""
import os
import sys
import subprocess


def reveal_in_explorer(path):
    """Open the destination directory of a generated file.

    On Windows the containing folder is opened with the file selected;
    on macOS via ``open -R``; elsewhere the folder is opened with ``xdg-open``.
    Returns the folder that was opened. Raises on failure so callers can log.
    """
    abs_path = os.path.abspath(path)
    is_file = os.path.isfile(abs_path)
    folder = os.path.dirname(abs_path) if is_file else abs_path
    if sys.platform.startswith("win"):
        if is_file:
            subprocess.Popen(["explorer", "/select,", abs_path])
        else:
            os.startfile(folder)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", abs_path] if is_file else ["open", folder])
    else:
        subprocess.Popen(["xdg-open", folder])
    return folder
