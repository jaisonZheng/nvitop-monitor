#!/usr/bin/env python3
"""
nvitop ANSI capture client — sends raw ANSI terminal output to the monitoring server.

Strategy:
  1. Try `nvitop -1` first (non-interactive one-shot print mode).
     With TERM=xterm-256color this outputs full ANSI color codes and Unicode box chars.
  2. If that fails, fall back to pty-based capture of interactive nvitop.

Sends to POST /update_ansi on the server.
"""

import os
import sys
import pty
import select
import fcntl
import termios
import struct
import signal
import subprocess
import time
import requests
import getpass
import socket
from datetime import datetime

# ── Configuration ──────────────────────────────────────────────────────────────
SERVER_URL = "http://43.136.42.69:8765"
UPDATE_INTERVAL = 1.0   # seconds between each nvitop capture
NVITOP_TIMEOUT = 8      # seconds to wait for nvitop -1 to finish

# Try these paths for nvitop in order
NVITOP_PATHS = [
    "nvitop",
    os.path.expanduser("~/.local/bin/nvitop"),
    "/usr/local/bin/nvitop",
    "/usr/bin/nvitop",
]
# ───────────────────────────────────────────────────────────────────────────────


def find_nvitop() -> str:
    """Return the first usable nvitop binary path."""
    for path in NVITOP_PATHS:
        try:
            r = subprocess.run(
                [path, "--version"],
                capture_output=True, timeout=3
            )
            if r.returncode == 0:
                return path
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    raise FileNotFoundError("nvitop not found. Tried: " + ", ".join(NVITOP_PATHS))


def _ansi_env() -> dict:
    """Environment vars that force nvitop to emit 256-color ANSI codes."""
    env = os.environ.copy()
    env.update({
        "TERM": "xterm-256color",
        "FORCE_COLOR": "1",
        "CLICOLOR_FORCE": "1",
        "COLORTERM": "truecolor",
        "COLUMNS": "200",   # give nvitop plenty of width for bar charts
        "LINES": "50",
    })
    return env


def capture_one_shot(nvitop: str) -> str:
    """
    Run `nvitop -1 --colorful` inside a pty so it thinks it's attached to a
    real terminal (required for ANSI color output).  Returns the raw ANSI text.
    """
    # We need a pty because nvitop checks isatty(stdout) to decide whether
    # to emit color codes.  subprocess.run(capture_output=True) makes stdout
    # a pipe → nvitop sees isatty()=False → no colors.
    master_fd, slave_fd = pty.openpty()

    # Set the pty window size so nvitop lays out bars properly
    ws = struct.pack("HHHH", 50, 200, 0, 0)
    fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, ws)

    env = _ansi_env()
    env["COLUMNS"] = "200"
    env["LINES"] = "50"

    try:
        proc = subprocess.Popen(
            [nvitop, "-1", "--colorful"],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            env=env,
            close_fds=True,
        )
    except Exception:
        # --colorful may not exist in older versions; retry without it
        proc = subprocess.Popen(
            [nvitop, "-1"],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            env=env,
            close_fds=True,
        )

    os.close(slave_fd)

    # Read until process exits or timeout
    buf = b""
    deadline = time.time() + NVITOP_TIMEOUT
    while time.time() < deadline:
        try:
            r, _, _ = select.select([master_fd], [], [], 0.2)
            if r:
                chunk = os.read(master_fd, 8192)
                if not chunk:
                    break
                buf += chunk
        except OSError:
            break
        if proc.poll() is not None:
            # Process done; drain remaining output
            time.sleep(0.05)
            try:
                while True:
                    r, _, _ = select.select([master_fd], [], [], 0.05)
                    if not r:
                        break
                    chunk = os.read(master_fd, 8192)
                    if not chunk:
                        break
                    buf += chunk
            except OSError:
                pass
            break

    try:
        os.close(master_fd)
    except OSError:
        pass

    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()

    text = buf.decode("utf-8", errors="replace")
    return text


def _strip_cr(text: str) -> str:
    """
    PTY output uses \\r\\n line endings.  nvitop -1 does not overwrite lines,
    so we just normalise \\r\\n → \\n and drop any stray \\r.
    """
    return text.replace('\r\n', '\n').replace('\r', '')


def clean_pty_output(raw: str) -> str:
    """
    Clean up PTY output:
    - Strip cursor-movement and screen-control CSI sequences
      (but KEEP color/attribute SGR sequences: ESC[...m)
    - Handle \r\n correctly
    - Remove ESC[?...h/l (private mode sequences)
    - Remove ESC[...J / ESC[...K (erase sequences)
    - Remove ESC[...H / ESC[...;Hf (cursor position sequences)
    - Remove ESC[...A/B/C/D (cursor movement sequences)
    """
    import re

    # Step 1: process \r by stripping them (we'll let the normal \n split work)
    # But first do line-based \r processing
    cleaned = _strip_cr(raw)

    # Step 2: strip non-SGR ESC sequences that got captured
    # Keep:  ESC [ <params> m          (SGR — colors/attributes)
    # Strip: everything else
    def replace_esc(m):
        seq = m.group(0)
        # Keep SGR: ends with 'm'
        inner = m.group(1) if m.lastindex else ''
        cmd = m.group(2) if m.lastindex and m.lastindex >= 2 else ''
        if cmd == 'm':
            return seq   # preserve color/attribute codes
        return ''        # strip cursor movement, erase, private mode, etc.

    # Match CSI sequences: ESC [ params cmd
    cleaned = re.sub(r'\x1b\[([0-9;:<=>?]*)([A-Za-z@`])', replace_esc, cleaned)
    # Strip any remaining lone ESC sequences (OSC, etc.)
    cleaned = re.sub(r'\x1b[^[\]]', '', cleaned)
    cleaned = re.sub(r'\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)', '', cleaned)
    # Strip bell
    cleaned = cleaned.replace('\x07', '')

    return cleaned


def send_ansi(ansi_text: str, hostname: str, username: str) -> bool:
    """POST the cleaned ANSI text to the server."""
    data = {
        "timestamp": datetime.now().strftime("%a %b %d %H:%M:%S %Y"),
        "raw_ansi": ansi_text,
        "hostname": hostname,
        "username": username,
    }
    try:
        resp = requests.post(
            f"{SERVER_URL}/update_ansi",
            json=data,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        return resp.status_code == 200
    except requests.RequestException as e:
        print(f"  ✗ send failed: {e}", flush=True)
        return False


def main():
    print("=== nvitop ANSI capture client ===", flush=True)
    print(f"Server: {SERVER_URL}", flush=True)

    try:
        nvitop = find_nvitop()
    except FileNotFoundError as e:
        print(f"ERROR: {e}", flush=True)
        sys.exit(1)

    print(f"Found nvitop: {nvitop}", flush=True)
    hostname = socket.gethostname()
    username = getpass.getuser()
    print(f"Host: {hostname}  User: {username}", flush=True)
    print("Press Ctrl+C to stop.\n", flush=True)

    while True:
        t0 = time.time()
        try:
            raw = capture_one_shot(nvitop)
            if not raw.strip():
                print(f"[{datetime.now().strftime('%H:%M:%S')}] nvitop returned empty output", flush=True)
            else:
                ansi = clean_pty_output(raw)
                print(
                    f"[{datetime.now().strftime('%H:%M:%S')}] "
                    f"captured {len(raw)} bytes → {len(ansi)} cleaned",
                    flush=True,
                )
                # Quick sanity check: should contain NVITOP header
                has_header = 'NVITOP' in ansi or 'nvitop' in ansi.lower()
                has_colors = '\x1b[' in ansi
                print(
                    f"  header={'yes' if has_header else 'NO'} "
                    f"colors={'yes' if has_colors else 'NO'}",
                    flush=True,
                )
                ok = send_ansi(ansi, hostname, username)
                print(f"  {'✓ sent' if ok else '✗ send failed'}", flush=True)
        except KeyboardInterrupt:
            print("\nStopped.", flush=True)
            break
        except Exception as e:
            print(f"  Error: {e}", flush=True)

        # Sleep for remainder of interval
        elapsed = time.time() - t0
        wait = max(0, UPDATE_INTERVAL - elapsed)
        if wait > 0:
            time.sleep(wait)


if __name__ == "__main__":
    main()
