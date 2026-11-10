import platform
import subprocess
import time
from pathlib import Path

from indexpilot.config import Settings
from indexpilot.errors import DomainError

ROOT = Path(__file__).resolve().parents[3]
AUTH = (
    'export PGPASSWORD="$(cat /run/secrets/bench_password)"; export PGAPPNAME="$1"; '
    'export PGOPTIONS="-c statement_timeout=5000 -c lock_timeout=1000 '
    '-c idle_in_transaction_session_timeout=10000 -c search_path=pg_catalog"; shift; exec "$@"'
)


class ContainerClient:
    """Fixed local Compose transport. No credential appears in argv, scripts or returned errors."""

    def __init__(self, job_id, check, *, settings=None):
        settings = settings or Settings()
        self.job_id, self.check = job_id, check
        self.folder = "/tmp/indexpilot_bench_" + job_id.hex
        self.application = "indexpilot-bench-" + job_id.hex
        self.prefix = (["wsl", "--exec"] if platform.system() == "Windows" else []) + [
            "docker",
            "compose",
            "--project-name",
            settings.compose_project,
            "exec",
            "-T",
            "postgres",
        ]

    def call(self, arguments, *, data=None, timeout=15):
        self.check()
        try:
            process = subprocess.Popen(
                self.prefix + arguments,
                cwd=ROOT,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
            deadline = time.monotonic() + timeout
            # communicate drains both pipes; cancellation is checked between short waits.
            supplied = data
            while True:
                try:
                    stdout, _ = process.communicate(input=supplied, timeout=0.2)
                    break
                except subprocess.TimeoutExpired:
                    supplied = None
                    self.check()
                    if time.monotonic() >= deadline:
                        raise DomainError(
                            "pgbench_timeout", "Container operation exceeded its deadline.", 504
                        ) from None
            if process.returncode:
                raise DomainError(
                    "pgbench_failed",
                    "Container benchmark operation failed; no success was inferred.",
                    503,
                )
            return stdout
        except (OSError, UnicodeError):
            raise DomainError(
                "pgbench_unavailable",
                "The configured local Docker pgbench transport is unavailable.",
                503,
            ) from None
        finally:
            if "process" in locals() and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)

    def setup(self):
        self.call(["sh", "-c", 'umask 077; mkdir "$1"', "sh", self.folder])
        return self.call(["pgbench", "--version"]).strip()

    def verify_nonce(self, name):
        value = self.call(
            [
                "sh",
                "-c",
                AUTH,
                "sh",
                self.application + "-probe",
                "psql",
                "-XAt",
                "-v",
                "ON_ERROR_STOP=1",
                "-U",
                "indexpilot_bench_owner",
                "-d",
                "indexpilot_bench",
                "-c",
                f'SELECT token FROM "{name}".ip_guard',
            ]
        )
        if value.strip() != str(self.job_id):
            raise DomainError(
                "benchmark_transport_mismatch",
                "pgbench and guarded connection do not identify the same database.",
                409,
            )

    def execute(self, scripts, *, clients, transactions, seed, label):
        files = []
        for number, (script, weight) in enumerate(scripts):
            filename = f"{self.folder}/{label}_{number}.sql"
            self.call(["sh", "-c", 'umask 077; cat > "$1"', "sh", filename], data=script)
            files.extend(["-f", filename + "@" + str(weight)])
        logfile = f"{self.folder}/{label}_log"
        output = self.call(
            [
                "sh",
                "-c",
                AUTH,
                "sh",
                self.application,
                "timeout",
                "--signal=TERM",
                "--kill-after=2s",
                "60s",
                "pgbench",
                "--random-seed=" + str(seed),
                "-n",
                "-M",
                "simple",
                "--exit-on-abort",
                "-c",
                str(clients),
                "-j",
                "1",
                "-t",
                str(transactions),
                "-l",
                "--log-prefix=" + logfile,
                "-U",
                "indexpilot_bench_owner",
                "-d",
                "indexpilot_bench",
                *files,
            ],
            timeout=65,
        )
        logs = self.call(["sh", "-c", 'cat "$1".*', "sh", logfile])
        return output, logs

    def cleanup(self):
        # No recursive deletion; only files in this UUID-owned scratch directory are removed.
        self.call(
            [
                "sh",
                "-c",
                'if [ -d "$1" ]; then find "$1" -maxdepth 1 -type f -delete && rmdir "$1"; fi',
                "sh",
                self.folder,
            ]
        )


def read_script(sql):
    if any(char in sql for char in ("\n", "\r", "\\")):
        raise DomainError(
            "unsupported_benchmark_query", "pgbench input must be a validated single-line SELECT."
        )
    return "BEGIN READ ONLY;\n" + sql.rstrip(";") + ";\nCOMMIT;\n"


def write_script(name, operation, orders):
    table = '"' + name + '".orders'
    sequence = "'" + name + ".write_ids'::regclass"
    if operation == "insert":
        body = (
            f"INSERT INTO {table} VALUES (-pg_catalog.nextval({sequence}),"
            "1,TIMESTAMPTZ '2026-01-01 UTC','paid',100) RETURNING id \\gset"
        )
    elif operation == "update":
        body = (
            f"\\set target random(1,{orders})\nUPDATE {table} "
            "SET user_id=CASE WHEN user_id=1 THEN 2 ELSE 1 END WHERE id=:target "
            "RETURNING id \\gset"
        )
    elif operation == "delete":
        body = (
            f"SELECT pg_catalog.nextval({sequence}) AS victim \\gset\n"
            f"DELETE FROM {table} WHERE id=-:victim RETURNING id \\gset"
        )
    else:
        raise ValueError("Unknown controlled write operation")
    return "BEGIN;\n" + body + "\nCOMMIT;\n"
