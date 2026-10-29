"""Database runner isolation and cleanup without requiring Docker."""

from subprocess import CompletedProcess

import pytest

from tools import test_postgresql as runner


@pytest.mark.parametrize("failure", [None, "startup", "migration", "tests", "cleanup"])
def test_runner_isolates_database_and_cleans_up(monkeypatch, capsys, failure):
    monkeypatch.setenv("DATABASE_URL", "development-database-must-not-be-used")
    monkeypatch.setenv("PREPBUDDY_TEST_DATABASE_URL", "old-test-database-must-not-be-used")
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs["env"].copy()))
        if "port" in command:
            return CompletedProcess(command, 0, "127.0.0.1:55432\n", "")
        stage = (
            "startup" if "up" in command else "migration" if "alembic" in command
            else "tests" if "pytest" in command else "cleanup" if "down" in command else None
        )
        failed = failure is not None and stage == failure
        return CompletedProcess(
            command, int(failed), "", kwargs["env"]["PREPBUDDY_TEST_PASSWORD"] if failed else "",
        )

    monkeypatch.setattr(runner.subprocess, "run", run)
    assert runner.main(["-q", "tests/test_api_postgresql.py"]) == (1 if failure else 0)
    assert "down" in calls[-1][0]
    assert "--volumes" in calls[-1][0]
    output = capsys.readouterr().out
    password = calls[0][1]["PREPBUDDY_TEST_PASSWORD"]
    assert password not in output
    compose_commands = [cmd for cmd, _ in calls if "--project-name" in cmd]
    assert len({cmd[3] for cmd in compose_commands}) == 1
    assert compose_commands[0][3].startswith("prepbuddy-test-")
    for command, environment in calls:
        if "alembic" in command or "pytest" in command:
            url = environment["DATABASE_URL"]
            assert url == environment["PREPBUDDY_TEST_DATABASE_URL"]
            assert url.endswith("@127.0.0.1:55432/prepbuddy_test")
            assert "development-database" not in url
        if "pytest" in command:
            assert command[-2:] == ["-q", "tests/test_api_postgresql.py"]
    if failure == "startup":
        assert not any("alembic" in cmd or "pytest" in cmd for cmd, _ in calls)
    if failure == "migration":
        assert not any("pytest" in cmd for cmd, _ in calls)


def test_unavailable_docker_does_not_attempt_database_changes(monkeypatch, capsys):
    calls = []

    def unavailable(command, **kwargs):
        calls.append(command)
        raise FileNotFoundError()

    monkeypatch.setattr(runner.subprocess, "run", unavailable)
    assert runner.main([]) == 1
    assert calls == [["docker", "info"]]
    assert "Docker with Compose is required" in capsys.readouterr().out
