# C:\Users\datta\Documents\code\pycontrol_code\api_classes\znotify.py
import os, requests

class _Base:
    def __init__(self):
        self.interface = None
        self._sent = False
        self.webhook = os.getenv("SLACK_WEBHOOK_URL")
        print("[znotify] __init__ webhook?", bool(self.webhook))

    def set_interface(self, interface):
        self.interface = interface
        print("[znotify] set_interface ok")

    def start_run(self, *_, **__):
        self._sent = False
        print("[znotify] start_run")

    def process_data_user(self, data):
        if self._sent or not self.webhook:
            return
        if data.get("type") == "print" and "SESSION_DONE" in data.get("text", ""):
            try:
                r = requests.post(self.webhook, json={"text": "🐭 PyControl session finished — time to fetch the animal."}, timeout=5)
                msg = "[znotify] Slack OK" if r.status_code < 300 else f"[znotify] Slack {r.status_code}: {r.text[:120]}"
            except Exception as e:
                msg = f"[znotify] Slack error: {e}"
            print(msg)
            if self.interface:
                try: self.interface.print_to_gui(msg)
                except Exception: pass
            self._sent = True

# Export multiple names so any loader style works:
class znotify(_Base):      # <-- EXACT name the error says it's looking for
    pass

class User_class(_Base):   # fallback for other builds
    pass

class NotifyOnFinish(_Base):  # extra alias
    pass
