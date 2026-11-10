"""Run the locked project's checks in order; PG and browser checks are explicit opt-ins."""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def executable(name):
    path = shutil.which(name)
    if path is None:
        raise RuntimeError(f"Install {name} and make it available in this terminal.")
    return path


def npm_command():
    # Run npm's JS entry point on Windows, avoiding cmd/PowerShell shell quoting.
    if os.name == "nt":
        node = Path(executable("node"))
        entry = node.parent / "node_modules/npm/bin/npm-cli.js"
        if not entry.is_file():
            raise RuntimeError("Use scripts/use_node.ps1 or a Node installation containing npm.")
        return [str(node), str(entry)]
    return [executable("npm")]


def run_checks(*, integration=False, browser=False, output=None):
    uv, npm = [executable("uv"), "run"], npm_command()
    checks = [
        ("python lint", uv + ["ruff", "check", "."], ROOT),
        ("python format", uv + ["ruff", "format", "--check", "."], ROOT),
        (
            "backend tests",
            uv
            + ["pytest", *(["--integration"] if integration else ["-m", "not integration"]), "-q"],
            ROOT,
        ),
    ]
    if integration:
        checks.extend(
            [
                ("database capabilities", uv + ["python", "scripts/verify_environment.py"], ROOT),
                ("migration drift", uv + ["alembic", "check"], ROOT),
            ]
        )
    checks.extend(
        (name, npm + ["run", command], ROOT / "frontend")
        for name, command in [
            ("frontend lint", "lint"),
            ("frontend types", "typecheck"),
            ("frontend components", "test"),
            ("frontend build", "build"),
            ("frontend format", "format:check"),
        ]
    )
    if browser:
        checks.append(("real browser workflow", npm + ["run", "test:e2e"], ROOT / "frontend"))
    results = []
    try:
        for name, command, cwd in checks:
            print(f"Checking: {name}", flush=True)
            started = time.monotonic()
            result = subprocess.run(command, cwd=cwd, check=False)
            results.append(
                {
                    "check": name,
                    "exit_code": result.returncode,
                    "seconds": round(time.monotonic() - started, 2),
                }
            )
            if result.returncode:
                return False
        return True
    finally:
        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(
                json.dumps(
                    {
                        "integration_requested": integration,
                        "browser_requested": browser,
                        "checks": results,
                        "all_requested_passed": len(results) == len(checks)
                        and all(r["exit_code"] == 0 for r in results),
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--integration", action="store_true", help="Use the provisioned local cluster"
    )
    parser.add_argument(
        "--browser", action="store_true", help="Use real local API/PG browser tests"
    )
    parser.add_argument(
        "--output", type=Path, help="Optional JSON status artifact (no credentials)"
    )
    args = parser.parse_args()
    try:
        passed = run_checks(integration=args.integration, browser=args.browser, output=args.output)
    except (OSError, RuntimeError) as failure:
        print(str(failure), file=sys.stderr)
        raise SystemExit(1) from None
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
