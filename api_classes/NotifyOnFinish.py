# api_classes/NotifyOnFinish.py
import os

class User_class:
    def __init__(self):
        self.interface = None
        self._sent = False
        self.webhook = os.getenv("SLACK_WEBHOOK_URL")
        print("[NotifyOnFinish] __init__ webhook?", bool(self.webhook))

    def set_interface(self, interface):
        self.interface = interface
        print("[NotifyOnFinish] set_interface ok")

    def start_run(self, *_, **__):
        self._sent = False
        print("[NotifyOnFinish] start_run")

    def process_data_user(self, data):
        # Log the first few messages only
        if getattr(self, "_n", 0) < 5:
            print("[NotifyOnFinish] data:", data)
            self._n = getattr(self, "_n", 0) + 1

        if self._sent:
            return
        if data.get("type") == "print" and "SESSION_DONE" in data.get("text", ""):
            print("[NotifyOnFinish] would notify now")
            self._sent = True

NotifyOnFinish = User_class
