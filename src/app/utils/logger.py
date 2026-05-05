import collections
from datetime import datetime

# ANSI Color Codes
COLORS = {
    "DEBUG": "\033[96m",    # Cyan
    "INFO": "\033[94m",     # Blue
    "SUCCESS": "\033[92m",  # Green
    "WARN": "\033[93m",     # Yellow
    "ERROR": "\033[91m",    # Red
    "RESET": "\033[0m",     # Reset
    "BOLD": "\033[1m",      # Bold
    "GRAY": "\033[90m"      # Gray
}

class Logger:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Logger, cls).__new__(cls)
            cls._instance.logs = collections.deque(maxlen=200)
        return cls._instance

    def debug(self, message, account=None): self._add("DEBUG", "🔍", message, account)
    def info(self, message, account=None): self._add("INFO", "ℹ️", message, account)
    def error(self, message, account=None): self._add("ERROR", "🚨", message, account)
    def success(self, message, account=None): self._add("SUCCESS", "✅", message, account)
    def warn(self, message, account=None): self._add("WARN", "⚠️", message, account)

    def _add(self, level, icon, message, account=None):
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = f"[{account}] " if account else ""
        
        # Color formatting for terminal
        color = COLORS.get(level, COLORS["RESET"])
        reset = COLORS["RESET"]
        gray = COLORS["GRAY"]
        bold = COLORS["BOLD"]
        
        # Format for UI (no colors, but with icon)
        full_msg = f"{prefix}{icon} {message}"
        self.logs.append(f"[{timestamp}] {full_msg}")
        
        # Format for Terminal (with colors)
        terminal_msg = f"{gray}[{timestamp}]{reset} {color}{bold}{level:<7}{reset} {bold}{prefix}{reset}{message}"
        print(terminal_msg)

    def get_logs(self):
        return list(self.logs)

logger = Logger()
