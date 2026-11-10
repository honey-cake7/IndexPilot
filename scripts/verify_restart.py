"""Read one saved report across two actual, exclusively owned local API processes."""

import argparse
import hashlib
import json
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def read_once(identifier):
    with socket.socket() as available:
        available.bind(("127.0.0.1", 0))
        port = available.getsockname()[1]
    # Never stop a user's server: only this Popen instance is terminated below.
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "indexpilot.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{port}", timeout=2, trust_env=False
        ) as client:
            deadline = time.monotonic() + 15
            while True:
                if process.poll() is not None:
                    raise RuntimeError(
                        "Owned API process did not start; check local configuration."
                    )
                try:
                    ready = client.get("/health/ready")
                    if ready.status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                if time.monotonic() >= deadline:
                    raise RuntimeError("Owned API did not become ready within 15 seconds.")
                time.sleep(0.1)
            response = client.get(f"/api/v1/reports/{identifier}/download.json")
            if response.status_code != 200 or response.json().get("id") != str(identifier):
                raise RuntimeError("Saved report could not be retrieved after API startup.")
            return response.content
    finally:
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def verify(identifier):
    before, after = read_once(identifier), read_once(identifier)
    if before != after:
        raise RuntimeError("Saved report changed across API process restart.")
    return {
        "report_id": str(identifier),
        "api_process_starts": 2,
        "content_unchanged": True,
        "sha256": hashlib.sha256(after).hexdigest(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report_id", type=uuid.UUID)
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.report_id)))
    except (RuntimeError, OSError, httpx.HTTPError):
        raise SystemExit(
            "Report restart verification failed; check local API/database setup."
        ) from None


if __name__ == "__main__":
    main()
