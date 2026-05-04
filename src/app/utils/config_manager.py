import json
import os

class ConfigManager:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance.config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../data/config.json"))
            cls._instance.settings = cls._instance._load()
        return cls._instance

    def _load(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                    # Asegurar que las nuevas claves existan
                    if "batch_size" not in data["global"]: data["global"]["batch_size"] = 20
                    if "batch_pause" not in data["global"]: data["global"]["batch_pause"] = 60
                    return data
            except: pass
        return {
            "global": {
                "redis_host": "localhost", 
                "redis_port": 6379, 
                "min_delay": 2, 
                "max_delay": 5,
                "batch_size": 20,
                "batch_pause": 60
            },
            "clients": {}
        }

    def save(self):
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, 'w') as f:
            json.dump(self.settings, f, indent=4)

    def get_client_list(self):
        return list(self.settings["clients"].keys())

    def get_client_config(self, name):
        return self.settings["clients"].get(name, {"headless": True})

    def set_client_config(self, name, config):
        if name not in self.settings["clients"]:
            self.settings["clients"][name] = {"headless": True}
        self.settings["clients"][name].update(config)
        self.save()

    def remove_client(self, name):
        if name in self.settings["clients"]:
            del self.settings["clients"][name]
            self.save()

    def get_global(self, key, default=None):
        return self.settings["global"].get(key, default)

config_manager = ConfigManager()
