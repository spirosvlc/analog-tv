import platform
import subprocess
from pathlib import Path


class FolderPickerService:
    """Opens the operating system's native directory picker."""

    def select_folder(self) -> str | None:
        system = platform.system()

        if system == "Darwin":
            return self._select_macos_folder()

        if system == "Linux":
            return self._select_linux_folder()

        if system == "Windows":
            return self._select_tkinter_folder()

        return self._select_tkinter_folder()

    @staticmethod
    def _select_macos_folder() -> str | None:
        script = (
            'POSIX path of '
            '(choose folder with prompt "Select an Analog TV video folder")'
        )

        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            return None

        selected = result.stdout.strip()
        return str(Path(selected).resolve()) if selected else None

    @staticmethod
    def _select_linux_folder() -> str | None:
        commands = [
            [
                "zenity",
                "--file-selection",
                "--directory",
                "--title=Select an Analog TV video folder",
            ],
            [
                "kdialog",
                "--getexistingdirectory",
                str(Path.home()),
                "--title",
                "Select an Analog TV video folder",
            ],
        ]

        for command in commands:
            try:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    check=False,
                )
            except FileNotFoundError:
                continue

            if result.returncode == 0 and result.stdout.strip():
                return str(Path(result.stdout.strip()).resolve())

        return self._select_tkinter_folder()

    @staticmethod
    def _select_tkinter_folder() -> str | None:
        try:
            import tkinter as tk
            from tkinter import filedialog
        except ImportError:
            return None

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        selected = filedialog.askdirectory(
            title="Select an Analog TV video folder"
        )

        root.destroy()
        return str(Path(selected).resolve()) if selected else None
