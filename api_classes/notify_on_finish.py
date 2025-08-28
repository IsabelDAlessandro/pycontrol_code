# api_classes/notify_on_finish.py
import os, requests

class _BaseNotify:
    """Base class implementing the Slack notify behavior."""
    def __init__(self):
        self.interface = None
        self._sent = False
        self.webhook = os.getenv("SLACK_WEBHOOK_URL")
        print("[notify_on_finish] __init__ webhook?", bool(self.webhook))

    def set_interface(self, interface):
        self.interface = interface
        print("[notify_on_finish] set_interface ok")

    def start_run(self, *_, **__):
        self._sent = False
        print("[notify_on_finish] start_run")

    def process_data_user(self, data):
        # Uncomment for verbose stream:
        # print("[notify_on_finish] data:", data)
        if self._sent or not self.webhook:
            return
        if data.get("type") == "print" and "SESSION_DONE" in data.get("text", ""):
            self._notify("🐭 PyControl session finished — time to fetch the animal.")
            self._sent = True

    def _notify(self, body: str):
        try:
            r = requests.post(self.webhook, json={"text": body}, timeout=5)
            msg = "[notify_on_finish] Slack OK" if r.status_code < 300 else \
                  f"[notify_on_finish] Slack {r.status_code}: {r.text[:120]}"
        except Exception as e:
            msg = f"[notify_on_finish] Slack error: {e}"
        print(msg)
        if self.interface:
            try: self.interface.print_to_gui(msg)
            except Exception: pass

# --- Expose multiple class names for different GUI expectations ---
class notify_on_finish(_BaseNotify):  # your GUI is looking for this exact name
    pass

class User_class(_BaseNotify):         # some versions expect this
    pass

class NotifyOnFinish(_BaseNotify):     # some versions expect CamelCase
    pass
