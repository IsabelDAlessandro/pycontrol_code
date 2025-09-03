# watcher_slack_min_recursive.py — recursively scan for newest .tsv and post to Slack on SESSION_DONE
# deps: requests  (pip install requests)
import os, time, glob
from pathlib import Path
import requests

# ==== EDIT THIS ONE LINE (base directory to search recursively) ====
BASE_DIR = r"C:\Users\datta\Documents\2AFC\data\Isabel"  # watcher searches all subfolders
# ===================================================================

SENTINEL = "SESSION_DONE"
WEBHOOK = "https://hooks.slack.com/services/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"

def newest_file():
    # Search **recursively** for .tsv files
    files = glob.glob(str(Path(BASE_DIR) / "**" / "*.tsv"), recursive=True)
    return max(files, key=os.path.getmtime) if files else None

def send_slack(body="🐭 PyControl session finished — time to fetch the animal."):
    if not WEBHOOK:
        print("[watcher] ERROR: SLACK_WEBHOOK_URL not set in this environment.")
        return
    try:
        r = requests.post(WEBHOOK, json={"text": body}, timeout=5)
        print(f"[watcher] Slack status {r.status_code}")
    except Exception as e:
        print(f"[watcher] Slack error: {e}")

def tail_until_sentinel(path):
    print("[watcher] Tailing:", path)
    # Start reading at current end so we only see NEW lines for this session
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        f.seek(0, os.SEEK_END)
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.25)
                # If a newer file appears in the tree, switch to it
                latest = newest_file()
                if latest and latest != path:
                    return latest  # switch target
                continue
            if SENTINEL in line:
                print("[watcher] Found sentinel. Posting to Slack...")
                send_slack()
                # Disarm: wait for the next NEW file before watching again
                return None

def main():
    Path(BASE_DIR).mkdir(parents=True, exist_ok=True)
    print("[watcher] Recursively watching:", BASE_DIR)
    current = newest_file()
    if current:
        # If you prefer to catch the sentinel even if it’s already in the file,
        # comment out the next 2 lines and we’ll scan from the start instead.
        print("[watcher] Initial target:", current)
    while True:
        if not current or not os.path.exists(current):
            current = newest_file()
            time.sleep(0.25)
            continue
        switch_to = tail_until_sentinel(current)
        if switch_to is None:
            # Wait for a file newer than the one we just finished
            last_mtime = os.path.getmtime(current) if os.path.exists(current) else 0
            while True:
                latest = newest_file()
                if latest and os.path.getmtime(latest) > last_mtime:
                    current = latest
                    break
                time.sleep(0.25)
        else:
            current = switch_to

if __name__ == "__main__":
    main()
