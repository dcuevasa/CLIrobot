"""Cross-platform keyboard input handler supporting Linux, macOS, and Windows.

Provides non-blocking and blocking key reads for TUI menu navigation and real-time robotics teleoperation.
"""

import sys
import os
import time
import signal
import atexit
import threading
from typing import Callable

# Platform detection
IS_WINDOWS = sys.platform.startswith("win")
IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")

# Import platform-specific low-level I/O
if IS_WINDOWS:
    try:
        import msvcrt
        WINDOWS_KEYBOARD_AVAILABLE = True
    except ImportError:
        WINDOWS_KEYBOARD_AVAILABLE = False
    TERMIOS_AVAILABLE = False
else:
    WINDOWS_KEYBOARD_AVAILABLE = False
    try:
        import termios
        import tty
        import select
        TERMIOS_AVAILABLE = True
    except ImportError:
        TERMIOS_AVAILABLE = False


def is_keyboard_supported() -> bool:
    """Check whether raw/unbuffered keyboard input is supported on current OS."""
    if IS_WINDOWS:
        return WINDOWS_KEYBOARD_AVAILABLE
    return TERMIOS_AVAILABLE and sys.stdin.isatty()


# ============================================================================
# Windows Key Reader
# ============================================================================

WINDOWS_SPECIAL_KEYS = {
    "H": "up",
    "P": "down",
    "K": "left",
    "M": "right",
    "S": "delete",
    "G": "home",
    "O": "end",
    "I": "page_up",
    "Q": "page_down",
}


def _read_key_windows(timeout: float | None = None) -> str | None:
    """Read a single key on Windows using msvcrt."""
    if not WINDOWS_KEYBOARD_AVAILABLE:
        return None

    start_time = time.time()
    while True:
        if msvcrt.kbhit():
            ch = msvcrt.getwch()
            # Prefix for extended keys (arrows, function keys)
            if ch in ("\x00", "\xe0"):
                ch2 = msvcrt.getwch()
                return WINDOWS_SPECIAL_KEYS.get(ch2, f"win_ext_{ch2}")
            elif ch in ("\r", "\n"):
                return "enter"
            elif ch in ("\x08", "\x7f"):
                return "backspace"
            elif ch == "\x1b":
                return "esc"
            elif ch == " ":
                return "space"
            elif ch == "\t":
                return "tab"
            elif ch == "\x03":
                return "ctrl_c"
            else:
                return ch.lower()

        if timeout is not None:
            if time.time() - start_time >= timeout:
                return None
            time.sleep(0.01)
        else:
            time.sleep(0.01)


# ============================================================================
# POSIX (Linux & macOS) Key Reader
# ============================================================================

def _read_char_posix(fd: int, timeout: float = 0.05) -> str | None:
    """Read a single character from fd with timeout using select."""
    if not TERMIOS_AVAILABLE:
        return None
    r, _, _ = select.select([fd], [], [], timeout)
    if r:
        try:
            return os.read(fd, 1).decode("utf-8", errors="replace")
        except Exception:
            return None
    return None


def parse_posix_escape_sequence(first_char: str, fd: int) -> str:
    """Parse character or multi-byte ANSI escape sequence (arrows, function keys) on Linux/macOS."""
    if first_char == "\x1b":
        # Check if more characters follow immediately
        next1 = _read_char_posix(fd, timeout=0.03)
        if next1 is None:
            return "esc"

        if next1 == "[":
            next2 = _read_char_posix(fd, timeout=0.03)
            if next2 == "A":
                return "up"
            elif next2 == "B":
                return "down"
            elif next2 == "C":
                return "right"
            elif next2 == "D":
                return "left"
            elif next2 in ("1", "2", "3", "4", "5", "6"):
                # Handle extended keys like Delete or PageUp
                _read_char_posix(fd, timeout=0.03)  # consume trailing ~
                return f"extended_{next2}"
            return f"esc_[_{next2}"
        elif next1 == "O":  # Application mode cursor keys
            next2 = _read_char_posix(fd, timeout=0.03)
            app_map = {"A": "up", "B": "down", "C": "right", "D": "left"}
            return app_map.get(next2, f"esc_O_{next2}")
        else:
            return f"alt_{next1}"

    elif first_char in ("\r", "\n"):
        return "enter"
    elif first_char == " ":
        return "space"
    elif first_char == "\t":
        return "tab"
    elif first_char in ("\x08", "\x7f"):
        return "backspace"
    elif first_char == "\x03":
        return "ctrl_c"
    else:
        return first_char.lower()


# ============================================================================
# Universal Raw Mode Context Manager
# ============================================================================

class TerminalRawMode:
    """Cross-platform context manager for safe raw/cbreak terminal mode.
    
    Guarantees that terminal settings (echo, canonical buffering) are restored
    even if unhandled exceptions, SIGINT, or SIGTERM occur.
    """

    def __init__(self):
        self._fd = None
        self._old_attr = None
        self._active = False

    def __enter__(self):
        if IS_WINDOWS:
            # Windows msvcrt does not alter global terminal termios
            self._active = True
            return self

        if not TERMIOS_AVAILABLE or not sys.stdin.isatty():
            return self

        self._fd = sys.stdin.fileno()
        try:
            self._old_attr = termios.tcgetattr(self._fd)
            new_attr = termios.tcgetattr(self._fd)
            # Disable echo and canonical mode (line buffering)
            new_attr[3] = new_attr[3] & ~termios.ECHO & ~termios.ICANON
            new_attr[6][termios.VMIN] = 1
            new_attr[6][termios.VTIME] = 0
            termios.tcsetattr(self._fd, termios.TCSANOW, new_attr)
            self._active = True
        except Exception:
            self._old_attr = None

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.restore()

    def restore(self) -> None:
        """Restore original terminal attributes."""
        if not self._active:
            return
        self._active = False

        if not IS_WINDOWS and self._fd is not None and self._old_attr is not None and TERMIOS_AVAILABLE:
            try:
                termios.tcsetattr(self._fd, termios.TCSANOW, self._old_attr)
            except Exception:
                pass
            self._old_attr = None


# ============================================================================
# Synchronous Key Reader
# ============================================================================

def read_key(timeout: float | None = None) -> str | None:
    """Read a single key stroke cross-platform (Linux, macOS, Windows).
    
    Returns:
        Canonical key string ('up', 'down', 'left', 'right', 'enter', 'esc', 'space', 'q', etc.)
        or None if timeout expires without input.
    """
    if IS_WINDOWS:
        return _read_key_windows(timeout=timeout)

    if not TERMIOS_AVAILABLE or not sys.stdin.isatty():
        # Fallback for piped input or unsupported platforms
        try:
            line = sys.stdin.readline()
            return line.strip().lower() if line else None
        except Exception:
            return None

    fd = sys.stdin.fileno()
    with TerminalRawMode():
        start_time = time.time()
        while True:
            remaining = timeout - (time.time() - start_time) if timeout is not None else 0.1
            if timeout is not None and remaining <= 0:
                return None

            wait_time = min(remaining, 0.1) if timeout is not None else 0.1
            r, _, _ = select.select([fd], [], [], wait_time)
            if r:
                try:
                    ch = os.read(fd, 1).decode("utf-8", errors="replace")
                    if ch:
                        return parse_posix_escape_sequence(ch, fd)
                except Exception:
                    return None

            if timeout is not None and (time.time() - start_time) >= timeout:
                return None


# ============================================================================
# Asynchronous Daemon Key Reader (for teleop / recording loops)
# ============================================================================

class TerminalKeyReader:
    """Asynchronous background thread reader for continuous keystroke streaming.
    
    Safe across Linux, macOS, and Windows.
    """

    def __init__(self, callback: Callable[[str], None] | None = None):
        self.callback = callback
        self._running = False
        self._thread: threading.Thread | None = None
        self._raw_context = TerminalRawMode()

    def is_supported(self) -> bool:
        return is_keyboard_supported()

    def start(self) -> bool:
        if not self.is_supported() or self._running:
            return False

        self._raw_context.__enter__()
        atexit.register(self.stop)
        self._register_signals()

        self._running = True
        self._thread = threading.Thread(target=self._loop, name="CLIrobot-AsyncKeyReader", daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        self._raw_context.restore()
        try:
            atexit.unregister(self.stop)
        except Exception:
            pass

    def _register_signals(self) -> None:
        if IS_WINDOWS:
            return
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                prev_handler = signal.getsignal(sig)
                def make_handler(original_handler):
                    def handler(signum, frame):
                        self.stop()
                        if callable(original_handler):
                            original_handler(signum, frame)
                        elif original_handler == signal.SIG_DFL:
                            sys.exit(128 + signum)
                    return handler
                signal.signal(sig, make_handler(prev_handler))
            except Exception:
                pass

    def _parse_key(self, ch: str) -> str:
        """Parse character for testing or direct dispatch."""
        fd = sys.stdin.fileno() if sys.stdin.isatty() else 0
        return parse_posix_escape_sequence(ch, fd)

    def _loop(self) -> None:
        while self._running:
            try:
                key = read_key(timeout=0.1)
                if key and self.callback:
                    self.callback(key)
            except Exception:
                break
