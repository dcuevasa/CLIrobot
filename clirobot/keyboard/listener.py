"""Unified multi-backend keyboard manager and event state tracker."""

import sys
import threading
from typing import Callable, Any
from clirobot.keyboard.terminal import TerminalKeyReader
from clirobot.keyboard.cv2_bridge import OpenCVKeyBridge


class KeyboardManager:
    """Universal keyboard listener and event coordinator for teleop and recording.
    
    Provides reliable keystroke capture across pure terminal sessions (SSH, headless, tmux)
    and OpenCV graphical viewer windows.
    """

    def __init__(self, on_action: Callable[[str], None] | None = None):
        self.on_action = on_action
        self._lock = threading.Lock()

        # State flags
        self.is_recording = False
        self.is_paused = False
        self.rerecord_requested = False
        self.next_requested = False
        self.stop_requested = False
        self.last_key: str | None = None
        self.key_history: list[str] = []

        # Backend readers
        self._terminal_reader = TerminalKeyReader(callback=self._handle_key_event)
        self._cv2_bridge = OpenCVKeyBridge(dispatch=self._handle_key_event)
        self._active_backend = "none"

    @property
    def active_backend(self) -> str:
        return self._active_backend

    def start(self) -> bool:
        """Start listening for keyboard input."""
        if self._terminal_reader.is_supported():
            success = self._terminal_reader.start()
            if success:
                self._active_backend = "terminal_raw"
                return True

        self._active_backend = "opencv_only"
        return False

    def stop(self) -> None:
        """Stop listening and restore terminal."""
        self._terminal_reader.stop()
        self._active_backend = "stopped"

    def feed_opencv_key(self, key_code: int) -> str | None:
        """Feed a key code obtained from cv2.waitKey() in camera display loops."""
        return self._cv2_bridge.process_key_code(key_code)

    def _handle_key_event(self, key: str) -> None:
        """Internal dispatch for canonical key names."""
        with self._lock:
            self.last_key = key
            self.key_history.append(key)
            if len(self.key_history) > 20:
                self.key_history.pop(0)

            # Map hotkeys to canonical robotics recording events
            if key in ("space", "p"):
                self.is_paused = not self.is_paused
            elif key in ("r", "left"):
                self.rerecord_requested = True
            elif key in ("n", "right", "s"):
                self.next_requested = True
            elif key in ("q", "esc", "ctrl_c"):
                self.stop_requested = True

        if self.on_action:
            try:
                self.on_action(key)
            except Exception:
                pass

    def get_events(self) -> dict[str, bool]:
        """Fetch and clear one-shot event triggers (rerecord, next, stop)."""
        with self._lock:
            events = {
                "is_paused": self.is_paused,
                "rerecord_requested": self.rerecord_requested,
                "next_requested": self.next_requested,
                "stop_requested": self.stop_requested,
            }
            # Clear one-shot requests
            self.rerecord_requested = False
            self.next_requested = False
            return events

    def reset_state(self) -> None:
        """Reset state flags."""
        with self._lock:
            self.is_recording = False
            self.is_paused = False
            self.rerecord_requested = False
            self.next_requested = False
            self.stop_requested = False
            self.last_key = None
