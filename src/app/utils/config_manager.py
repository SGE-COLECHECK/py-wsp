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
                    if "send_mode" not in data["global"]: data["global"]["send_mode"] = "typing"
                    if "ycloud_api_key" not in data["global"]: data["global"]["ycloud_api_key"] = ""
                    if "ycloud_from" not in data["global"]: data["global"]["ycloud_from"] = "+51963828458"
                    if "ycloud_url" not in data["global"]: data["global"]["ycloud_url"] = "https://api.ycloud.com/v2/whatsapp/messages/sendDirectly"
                    if "ycloud_cost_usd" not in data["global"]: data["global"]["ycloud_cost_usd"] = 0.02
                    if "ycloud_exchange_pen" not in data["global"]: data["global"]["ycloud_exchange_pen"] = 3.46
                    if "ycloud_colegio" not in data["global"]: data["global"]["ycloud_colegio"] = "Mi Colegio"
                    if "ycloud_numero" not in data["global"]: data["global"]["ycloud_numero"] = "999888777"
                    if "ycloud_template" not in data["global"]: data["global"]["ycloud_template"] = "🚨🇨🇴🇱🇪✅ \nEstimados padres de familia 👨‍👩‍👧‍👦:\nEste año, *{Colegio}* viene implementando un sistema de control de *INGRESO* y *SALIDA* de estudiantes mediante credenciales escolares.\n\n📌 Guarde el siguiente número como:\n👉 colecheck – *{Numero}*  (escribir a ese whatsapp)\n\n📩 Luego envíe:\n\n🏫 Colegio: *{Colegio}*\n🎓 Grado y sección: *5-A* \n👦 Estudiante: *Yhon Yucra Castro*\n\n🎫 *Verifique que su hijo(a) lleve siempre su credencial, ya que las notificaciones dependen de su uso al ingresar y salir del colegio.*\n\n💬 Para mantener activo el servicio, responda o reaccione 👍 a los mensajes enviados."
                    return data
            except: pass
        return {
            "global": {
                "redis_host": "localhost", 
                "redis_port": 6379, 
                "min_delay": 2, 
                "max_delay": 5,
                "batch_size": 20,
                "batch_pause": 60,
                "ycloud_api_key": "",
                "ycloud_from": "+51963828458",
                "ycloud_url": "https://api.ycloud.com/v2/whatsapp/messages/sendDirectly",
                "ycloud_cost_usd": 0.02,
                "ycloud_exchange_pen": 3.46,
                "ycloud_colegio": "Mi Colegio",
                "ycloud_numero": "999888777",
                "ycloud_template": "🚨🇨🇴🇱🇪✅ \nEstimados padres de familia 👨‍👩‍👧‍👦:\nEste año, *{Colegio}* viene implementando un sistema de control de *INGRESO* y *SALIDA* de estudiantes mediante credenciales escolares.\n\n📌 Guarde el siguiente número como:\n👉 colecheck – *{Numero}*  (escribir a ese whatsapp)\n\n📩 Luego envíe:\n\n🏫 Colegio: *{Colegio}*\n🎓 Grado y sección: *5-A* \n👦 Estudiante: *Yhon Yucra Castro*\n\n🎫 *Verifique que su hijo(a) lleve siempre su credencial, ya que las notificaciones dependen de su uso al ingresar y salir del colegio.*\n\n💬 Para mantener activo el servicio, responda o reaccione 👍 a los mensajes enviados."
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
