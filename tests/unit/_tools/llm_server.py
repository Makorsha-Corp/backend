"""Start or stop the local llama-server used by local_coder.py.

    python tests/unit/_tools/llm_server.py up      # start if not running, wait until the model is loaded
    python tests/unit/_tools/llm_server.py down    # stop every llama-server process
    python tests/unit/_tools/llm_server.py status

The command line is the one the owner uses by hand. Server output goes to
tests/unit/_tools/llm_server.log (not committed).
"""
from __future__ import annotations

import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

EXE = r"C:\llama-cuda\llama-server.exe"
MODEL = r"E:\Projects\models\Qwen_Qwen3.6-35B-A3B-Q4_K_M.gguf"
PORT = 8080
ARGS = [EXE, "-m", MODEL, "-c", "16384", "--flash-attn", "on", "-ngl", "99", "-np", "1", "-lm", "none",
        "--port", str(PORT)]
HEALTH = f"http://127.0.0.1:{PORT}/health"
LOG = Path(__file__).with_name("llm_server.log")
WAIT_SECONDS = 900


def health() -> int | None:
    """HTTP status of /health (200 = ready, 503 = loading), None if nothing answers."""
    try:
        with urllib.request.urlopen(HEALTH, timeout=5) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except (urllib.error.URLError, OSError):
        return None


def running() -> bool:
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq llama-server.exe", "/NH"],
                         capture_output=True, text=True).stdout
    return "llama-server.exe" in out


def up() -> int:
    if health() == 200:
        print("server already up")
        return 0
    if not running():
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        with LOG.open("ab") as log:
            subprocess.Popen(ARGS, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                             creationflags=flags, close_fds=True)
        print("server starting")
    deadline = time.monotonic() + WAIT_SECONDS
    while time.monotonic() < deadline:
        if health() == 200:
            print("server ready")
            return 0
        if not running():
            print(f"server exited while loading; see {LOG}")
            return 3
        time.sleep(5)
    print(f"server not ready after {WAIT_SECONDS} s; see {LOG}")
    return 4


def down() -> int:
    if not running():
        print("server already down")
        return 0
    subprocess.run(["taskkill", "/IM", "llama-server.exe", "/F"], capture_output=True, text=True)
    for _ in range(30):
        if not running():
            print("server stopped")
            return 0
        time.sleep(1)
    print("server still running after taskkill")
    return 5


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "up":
        return up()
    if cmd == "down":
        return down()
    print(f"running={running()} health={health()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
