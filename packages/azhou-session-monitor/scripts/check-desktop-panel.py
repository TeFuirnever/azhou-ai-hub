"""Run against a disposable Codex home, with two host-issued thread IDs and numeric fixtures."""
import argparse
import json
import os
from pathlib import Path
from queue import Queue
import subprocess
import tempfile
from threading import Thread

REPO = Path(__file__).resolve().parents[1]


def exercise(executable, home):
    env = dict(os.environ, CODEX_HOME=str(home))
    for args in (["plugin", "marketplace", "add", str(REPO)],
                 ["plugin", "add", "azhou-session-monitor@azhou-session-tools"]):
        subprocess.run([executable, *args], cwd=REPO, env=env, check=True, timeout=30)
    with tempfile.TemporaryFile() as log:
        proc = subprocess.Popen([executable, "app-server", "--listen", "stdio://"], env=env, cwd=REPO,
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log, text=True)
        messages = Queue()
        def drain():
            for line in proc.stdout:
                messages.put(json.loads(line))
            messages.put(None)
        reader = Thread(target=drain, daemon=True)
        reader.start()
        sequence = 0
        def send(msg):
            proc.stdin.write(json.dumps(msg) + "\n")
            proc.stdin.flush()
        def call(method, params):
            nonlocal sequence
            sequence += 1
            send({"id": sequence, "method": method, "params": params})
            while True:
                message = messages.get(timeout=30)
                if message is None:
                    raise RuntimeError("app-server closed the stream")
                if message.get("id") == sequence:
                    if "error" in message:
                        raise RuntimeError(message["error"])
                    return message["result"]
        try:
            call("initialize", {"clientInfo": {"name":"azhou-panel-test","version":"0.1"},
                                "capabilities":{"experimentalApi":True}})
            send({"method":"initialized"})
            ids = []
            fixture_dir = home / "sessions/2000/01/01"
            fixture_dir.mkdir(parents=True)
            for tokens in (24, 48):
                thread = call("thread/start", {"cwd":str(REPO), "sandbox":"read-only","approvalPolicy":"never"})
                sid = thread["thread"]["id"]
                ids.append(sid)
                records = [
                    ("session_meta", {"id":sid}),
                    ("event_msg", {"type":"task_started","turn_id":"example"}),
                    ("token_usage_record", {"turn_id":"example","response_id":"fixture","turn_token_usage":{"output_tokens":tokens}}),
                    ("event_msg", {"type":"task_complete","turn_id":"example","duration_ms":2000}),
                ]
                with (fixture_dir / f"rollout-example-{sid}.jsonl").open("x") as output:
                    for kind, payload in records:
                        print(json.dumps({"type":kind,"payload":payload}),file=output)
            for index in (0, 1, 0):
                result = call("mcpServer/tool/call", {"threadId":ids[index],"server":"azhou-session-monitor",
                                                       "tool":"session_performance","arguments":{}})
                if result["structuredContent"].get("effectiveTps") != (index+1)*12:
                    raise RuntimeError("Host thread binding failed")
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            reader.join(timeout=2)
    print("PASS: host-supplied thread identity selected A, B, A without model calls.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex", default="codex")
    with tempfile.TemporaryDirectory() as directory:
        exercise(parser.parse_args().codex, Path(directory).resolve())
