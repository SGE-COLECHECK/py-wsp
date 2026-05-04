import collections
from datetime import datetime

class LoggerManager:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LoggerManager, cls).__new__(cls)
            cls._instance.logs = collections.deque(maxlen=200)
        return cls._instance

    def log(self, message, type="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = "ℹ️"
        if type == "ERROR": prefix = "🚨"
        if type == "SUCCESS": prefix = "✅"
        if type == "WARN": prefix = "⚠️"
        
        full_msg = f"[{timestamp}] {prefix} {message}"
        self.logs.append(full_msg)
        print(full_msg) # También lo sacamos por terminal por si acaso

    def get_logs(self):
        return list(self.logs)

logger = LoggerManager()
