"""OpenCV window keyboard bridge for graphical teleoperation/recording environments."""

from typing import Callable


class OpenCVKeyBridge:
    """Translates OpenCV window key codes (cv2.waitKey) into canonical key names."""

    # Standard ASCII and keycode mappings
    KEY_MAP = {
        27: "esc",
        32: "space",
        13: "enter",
        10: "enter",
        8: "backspace",
        9: "tab",
        # Common arrow keys across OpenCV GUI backends
        81: "left",
        82: "up",
        83: "right",
        84: "down",
        65361: "left",
        65362: "up",
        65363: "right",
        65364: "down",
    }

    def __init__(self, dispatch: Callable[[str], None]):
        self.dispatch = dispatch

    def process_key_code(self, key_code: int) -> str | None:
        """Process keycode returned by cv2.waitKey(delay)."""
        if key_code == -1:
            return None  # No key pressed

        # Normalize 8-bit mask
        code_8bit = key_code & 0xFF

        name = self.KEY_MAP.get(key_code) or self.KEY_MAP.get(code_8bit)
        if name is not None:
            self.dispatch(name)
            return name

        # Printable character
        if 32 <= code_8bit <= 126:
            char_key = chr(code_8bit).lower()
            self.dispatch(char_key)
            return char_key

        return None
