import collections
from datetime import datetime

class Logger:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Logger, cls).__new__(cls)
            cls._instance.logs = collections.deque(maxlen=200)
        return cls._instance

    def info(self, message): self._add("INFO", "ℹ️", message)
    def error(self, message): self._add("ERROR", "🚨", message)
    def success(self, message): self._add("SUCCESS", "✅", message)
    def warn(self, message): self._add("WARN", "⚠️", message)

    def _add(self, level, icon, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        full_msg = f"[{timestamp}] {icon} {message}"
        self.logs.append(full_msg)
        print(f"[{level}] {full_msg}")

    def get_logs(self):
        return list(self.logs)

logger = Logger()
