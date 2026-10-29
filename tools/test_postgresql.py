"""Run migrations and pytest against a disposable local PostgreSQL + pgvector container."""

import os
import secrets
import shlex
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def main(args: list[str] | None = None) -> int:
    args = sys.argv[1:] if args is None else args
    environment = os.environ.copy()
    password = secrets.token_hex(24)
    environment["PREPBUDDY_TEST_PASSWORD"] = password
    compose = [
        "docker", "compose", "--project-name", f"prepbuddy-test-{uuid4().hex[:12]}",
        "--file", str(ROOT / "compose.test.yaml"),
    ]

    def run(command: list[str], *, quiet: bool = False) -> subprocess.CompletedProcess:
        result = subprocess.run(
            command, cwd=ROOT, env=environment, capture_output=True, text=True, check=False,
        )
        if not quiet or result.returncode:
            output = result.stdout + result.stderr
            print(output.replace(password, "[redacted]"), end="", flush=True)
        return result

    try:
        if run(["docker", "info"], quiet=True).returncode:
            print("Docker is unavailable. Start Docker Desktop and enable this WSL distro.")
            return 1
        if run(["docker", "compose", "version"], quiet=True).returncode:
            return 1
    except OSError:
        print("Docker with Compose is required. Start Docker Desktop and enable WSL integration.")
        return 1

    result_code = 1
    try:
        print("Starting an isolated PostgreSQL test database...", flush=True)
        if run([*compose, "up", "--detach", "--wait", "--wait-timeout", "60"]).returncode:
            return 1
        result = run([*compose, "port", "postgres", "5432"], quiet=True)
        if result.returncode:
            return 1
        host, port = result.stdout.strip().rsplit(":", 1)
        if host != "127.0.0.1" or not port.isdigit() or not 1 <= int(port) <= 65535:
            print("Docker did not publish the expected loopback database port.")
            return 1
        url = f"postgresql+psycopg://prepbuddy_test:{password}@127.0.0.1:{port}/prepbuddy_test"
        # Override both variables only in child processes; never read or modify the user's .env.
        environment["DATABASE_URL"] = url
        environment["PREPBUDDY_TEST_DATABASE_URL"] = url
        print("Applying migrations to the test database...", flush=True)
        if run([sys.executable, "-m", "alembic", "upgrade", "head"]).returncode:
            return 1
        print("Running tests with PostgreSQL enabled...", flush=True)
        result_code = run([sys.executable, "-m", "pytest", *(args or ["-q"])]).returncode
    except (OSError, ValueError):
        print("Test database setup failed; check Docker and its published port.")
        result_code = 1
    except KeyboardInterrupt:
        result_code = 130
    finally:
        print("Removing this run's test database...", flush=True)
        try:
            if run([*compose, "down", "--volumes"]).returncode:
                print("Cleanup failed. Retry: PREPBUDDY_TEST_PASSWORD=unused "
                      + shlex.join([*compose, "down", "--volumes"]))
                result_code = 1
        except OSError:
            print("Docker cleanup could not start for project " + compose[3])
            result_code = 1
    return result_code


if __name__ == "__main__":
    raise SystemExit(main())
