import collections
from datetime import datetime
import json

# UI Colors (ImGui style: R, G, B, A)
UI_COLORS = [
    (0.4, 0.7, 1.0, 1.0),  # Cyan-ish
    (1.0, 0.4, 0.4, 1.0),  # Red-ish
    (0.4, 1.0, 0.6, 1.0),  # Green-ish
    (1.0, 0.8, 0.2, 1.0),  # Yellow-ish
    (0.8, 0.4, 1.0, 1.0),  # Purple-ish
    (1.0, 0.5, 0.0, 1.0),  # Orange-ish
    (0.2, 0.8, 0.8, 1.0),  # Teal
    (1.0, 0.4, 0.7, 1.0),  # Pink
]

# ANSI Color Codes for Terminal
TERMINAL_COLORS = {
    "DEBUG": "\033[90m",    # Gray
    "INFO": "\033[94m",     # Blue
    "SUCCESS": "\033[92m",  # Green
    "WARN": "\033[93m",     # Yellow
    "ERROR": "\033[91m",    # Red
    "RESET": "\033[0m",
    "BOLD": "\033[1m",
    "GRAY": "\033[90m"
}

from imgui_bundle import icons_fontawesome

class Logger:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Logger, cls).__new__(cls)
            cls._instance.logs = collections.deque(maxlen=300)
            cls._instance.account_colors = {}
            cls._instance.sent_counts = {"morning": 0, "afternoon": 0}
            cls._instance.account_stats = {} # {account: {"morning": 0, "afternoon": 0}}
            cls._instance.last_reset_day = datetime.now().day
        return cls._instance

    def _get_account_color(self, account):
        if not account: return (0.8, 0.8, 0.8, 1.0)
        if account not in self.account_colors:
            idx = len(self.account_colors) % len(UI_COLORS)
            self.account_colors[account] = UI_COLORS[idx]
        return self.account_colors[account]

    # Emojis profesionales para máxima compatibilidad
    ICONS = {
        "DEBUG": "🔍",
        "INFO": "ℹ️",
        "SUCCESS": "✅",
        "WARN": "⚠️",
        "ERROR": "🚨",
        "SEND": "📤",
        "QR": "🔳",
        "SYNC": "🔄",
        "WAIT": "⏳",
        "CHECK_DOUBLE": "✔️✔️"
    }

    def _check_reset(self):
        now = datetime.now()
        # Reset if day changed
        if now.day != self.last_reset_day:
            self.sent_counts = {"morning": 0, "afternoon": 0}
            self.account_stats = {}
            self.last_reset_day = now.day
            self.info("🔄 Contador diario reiniciado.")

    def increment_sent(self, account=None):
        self._check_reset()
        now = datetime.now()
        period = "morning" if now.hour < 12 else "afternoon"
        
        self.sent_counts[period] += 1
        
        if account:
            if account not in self.account_stats:
                self.account_stats[account] = {"morning": 0, "afternoon": 0}
            self.account_stats[account][period] += 1

    def debug(self, message, account=None): self._add("DEBUG", self.ICONS["DEBUG"], message, account)
    def info(self, message, account=None): self._add("INFO", self.ICONS["INFO"], message, account)
    def error(self, message, account=None): self._add("ERROR", self.ICONS["ERROR"], message, account)
    def success(self, message, account=None): self._add("SUCCESS", self.ICONS["SUCCESS"], message, account)
    def warn(self, message, account=None): self._add("WARN", self.ICONS["WARN"], message, account)
    
    # Specific actions for cleaner logs
    def sending(self, message, account=None): self._add("INFO", self.ICONS["SEND"], message, account)
    def qr(self, message, account=None): self._add("WARN", self.ICONS["QR"], message, account)
    def retry(self, message, account=None): self._add("WARN", self.ICONS["SYNC"], message, account)
    def wait(self, message, account=None): self._add("INFO", self.ICONS["WAIT"], message, account)
    def read(self, message, account=None): self._add("SUCCESS", self.ICONS["CHECK_DOUBLE"], message, account)

    def _add(self, level, icon, message, account=None):
        timestamp = datetime.now().strftime("%H:%M:%S")
        color_ui = self._get_account_color(account)
        
        # Log entry for UI
        log_entry = {
            "time": timestamp,
            "level": level,
            "icon": icon,
            "message": message,
            "account": account,
            "account_color": color_ui
        }
        self.logs.append(log_entry)
        
        # Terminal print
        prefix = f"[{account}] " if account else ""
        t_color = TERMINAL_COLORS.get(level, TERMINAL_COLORS["RESET"])
        reset = TERMINAL_COLORS["RESET"]
        gray = TERMINAL_COLORS["GRAY"]
        print(f"{gray}[{timestamp}]{reset} {t_color}{level:<7}{reset} {prefix}{message}")

    def get_logs(self):
        return list(self.logs)

    def get_stats(self):
        self._check_reset()
        return self.sent_counts

    def get_account_stats(self, account):
        self._check_reset()
        stats = self.account_stats.get(account, {"morning": 0, "afternoon": 0})
        return stats["morning"] + stats["afternoon"]

logger = Logger()
