# olf_bridge_tail.py
# Forwards "#OLF:<cmd>" lines found in the newest .tsv under --root to a Teensy on --olf.
# Example: python olf_bridge_tail.py --root "C:\Users\datta\Documents\2AFC\data\Isabel" --olf COM5

import argparse, time, os, sys, glob
import serial

TAG = "#OLF:"
LINE_END = "\n"

def newest_tsv(root):
    # Recursively find newest .tsv by modification time
    files = glob.glob(os.path.join(root, "**", "*.tsv"), recursive=True)
    if not files:
        return None, None
    newest = max(files, key=os.path.getmtime)
    return newest, os.path.getmtime(newest)

def open_teensy(port, baud):
    while True:
        try:
            s = serial.Serial(port, baudrate=baud, timeout=0.2)
            print(f"[OK] Connected Teensy @ {port} {baud} baud", flush=True)
            return s
        except Exception as e:
            print(f"[WARN] Cannot open {port}: {e}; retrying in 1 s...", flush=True)
            time.sleep(1)

def follow_file(path):
    f = open(path, "r", encoding="utf-8", errors="ignore")
    f.seek(0, os.SEEK_END)  # start at end: only new lines
    return f

def extract_cmd(line):
    # Find first occurrence of TAG and take the immediate token after it
    i = line.find(TAG)
    if i < 0:
        return None
    rest = line[i + len(TAG):].strip()
    # command ends at first whitespace/tab if present
    if not rest:
        return None
    # Keep up to first whitespace to be safe: "o2", "f", "c2", "F0", etc.
    for j, ch in enumerate(rest):
        if ch.isspace():
            return rest[:j]
    return rest

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="Root folder containing subject subfolders with .tsv session files")
    ap.add_argument("--olf", default="COM5", help="Teensy COM port")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--scan_sec", type=float, default=0.5, help="How often to rescan for a newer session file")
    args = ap.parse_args()

    teensy = open_teensy(args.olf, args.baud)

    current_path, current_mtime = None, None
    f = None
    last_size = 0
    last_switch_check = 0.0

    try:
        while True:
            now = time.time()

            # Choose a file if we don't have one yet
            if current_path is None:
                p, m = newest_tsv(args.root)
                if p is not None:
                    current_path, current_mtime = p, m
                    print(f"[INFO] Following: {current_path}", flush=True)
                    f = follow_file(current_path)
                    last_size = f.tell()
                else:
                    time.sleep(args.scan_sec)
                    continue

            # Periodically check if a newer file appeared; if so, switch
            if now - last_switch_check >= args.scan_sec:
                last_switch_check = now
                p, m = newest_tsv(args.root)
                if p and (p != current_path) and (m is not None) and (m >= (current_mtime or 0)):
                    try:
                        if f: f.close()
                    except: pass
                    current_path, current_mtime = p, m
                    print(f"[INFO] Switching to newer file: {current_path}", flush=True)
                    f = follow_file(current_path)
                    last_size = f.tell()

            # Read any newly appended lines
            where = f.tell()
            line = f.readline()
            if not line:
                # no new data
                time.sleep(0.05)
                continue

            last_size = f.tell()
            line = line.rstrip("\r\n")
            cmd = extract_cmd(line)
            if cmd:
                try:
                    teensy.write((cmd + LINE_END).encode())
                    print(f"[FWD] {cmd}", flush=True)
                except Exception as e:
                    print(f"[ERR] Teensy write failed: {e}", flush=True)
                    # try to reopen Teensy until success
                    while True:
                        try:
                            teensy.close()
                        except: pass
                        teensy = open_teensy(args.olf, args.baud)
                        # try one test write (optional)
                        try:
                            teensy.write((cmd + LINE_END).encode())
                            print(f"[FWD] {cmd} (after reconnect)", flush=True)
                            break
                        except Exception as e2:
                            print(f"[WARN] Still failing to write: {e2}", flush=True)
                            time.sleep(1)

    except KeyboardInterrupt:
        pass
    finally:
        try:
            if f: f.close()
        except: pass
        try:
            teensy.close()
        except: pass
        print("[Done] Bridge closed.", flush=True)

if __name__ == "__main__":
    main()
