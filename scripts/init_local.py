"""Generate local credentials without overwriting existing values."""

import os
import secrets
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    secret_dir = root / ".secrets"
    secret_dir.mkdir(mode=0o700, exist_ok=True)
    for name in ("admin", "meta", "demo", "analyzer", "bench"):
        path = secret_dir / f"{name}_password"
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            continue
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as output:
            output.write(secrets.token_hex(24) + "\n")
    env = root / ".env"
    if not env.exists():
        env.write_text((root / ".env.example").read_text(encoding="utf-8"), encoding="utf-8")
    print("Local configuration ready; existing credentials preserved. No secrets displayed.")


if __name__ == "__main__":
    main()
