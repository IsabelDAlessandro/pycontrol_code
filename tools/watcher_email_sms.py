# watcher_email_sms.py – watches your pyControl data folder and emails your phone on SESSION_DONE
# deps: pip install watchdog
import os, time, glob, smtplib, ssl
from email.mime.text import MIMEText
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# --- EDIT THESE ---
DATA_DIR = r"C:\Users\datta\Documents\code\pycontrol_code\data"   # folder where GUI writes .txt logs
SMS_TO   = "9788847725@tmomail.net"              # your phone's email-to-SMS
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
SMTP_USER = "isabeladalessandro@gmail.com"
SMTP_PASS = "ebucrajsqxsrzgjm"
SUBJECT   = "PyControl finished"
BODY      = "🐭 Session finished — time to fetch the animal."
SENTINEL  = "SESSION_DONE"
# ------------------

def send_sms():
    msg = MIMEText(BODY)
    msg["From"] = SMTP_USER
    msg["To"]   = SMS_TO
    msg["Subject"] = SUBJECT
    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx) as server:
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)
    print("[watcher] SMS email sent.")

def newest_txt():
    files = glob.glob(str(Path(DATA_DIR) / "*.txt"))
    return max(files, key=os.path.getmtime) if files else None

def tail_for_sentinel(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        f.seek(0, os.SEEK_END)
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.2)
                continue
            if SENTINEL in line:
                send_sms()
                return

class Handler(FileSystemEventHandler):
    def __init__(self):
        self.tailing = False

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith(".txt") and not self.tailing:
            self.tailing = True
            print("[watcher] Tailing:", event.src_path)
            tail_for_sentinel(event.src_path)
            self.tailing = False

    def on_modified(self, event):
        if not self.tailing:
            latest = newest_txt()
            if latest:
                self.tailing = True
                print("[watcher] Tailing:", latest)
                tail_for_sentinel(latest)
                self.tailing = False

def main():
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)
    print("[watcher] Watching", DATA_DIR)
    latest = newest_txt()
    if latest:
        print("[watcher] Tailing:", latest)
        # run once in the foreground in case a file already exists
        tail_for_sentinel(latest)
    obs = Observer()
    obs.schedule(Handler(), DATA_DIR, recursive=False)
    obs.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        obs.stop()
        obs.join()

if __name__ == "__main__":
    main()
