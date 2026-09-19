import io
import json
import subprocess
from urllib.error import HTTPError

import pytest

from tools import project_advisor as advisor


@pytest.fixture
def repo(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "README.md").write_text("Build a preparation planner.")
    (tmp_path / ".gitignore").write_text("ignored.py\n")
    (tmp_path / "ignored.py").write_text("ignored content")
    (tmp_path / ".env").write_text("OPENAI_API_KEY=do-not-send")
    (tmp_path / "credentials.json").write_text("do-not-send")
    (tmp_path / "app.py").write_text("# Current implementation")
    (tmp_path / "linked.py").symlink_to(tmp_path / ".env")
    (tmp_path / ".ai").mkdir()
    (tmp_path / ".ai/next-step.md").write_text("Previous plan")
    return tmp_path


def test_context_includes_code_and_missing_evidence_but_excludes_private_files(repo):
    context = advisor.collect_context(repo)
    assert context["files"]["app.py"] == "# Current implementation"
    assert "Build a preparation planner." in context["files"]["README.md"]
    assert context["git_history"] == "No commits yet."
    assert "do-not-send" not in json.dumps(context)
    assert "ignored.py" not in context["files"]
    assert ".ai/next-step.md" not in context["files"]
    assert "docs/architecture.md: missing or symlink" in context["omitted_files"]


def response(plan, status="completed"):
    return io.BytesIO(
        json.dumps(
            {
                "status": status,
                "output": [
                    {"type": "reasoning"},
                    {
                        "type": "message",
                        "content": [
                            {"type": "output_text", "text": json.dumps(plan)},
                        ],
                    },
                ],
            }
        ).encode()
    )


def test_next_writes_all_sections_with_mocked_api(repo, monkeypatch):
    monkeypatch.setattr(advisor, "ROOT", repo)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    plan = {name: f"Details for {name}" for name in advisor.SECTIONS}

    def fake_open(request, timeout):
        payload = json.loads(request.data)
        assert payload["store"] is False
        assert payload["model"] == "test-model"
        assert payload["text"]["format"]["strict"] is True
        assert "app.py" in payload["input"]
        assert timeout == 120
        return response(plan)

    monkeypatch.setattr(advisor, "urlopen", fake_open)
    assert advisor.main(["next", "--model", "test-model"]) == 0
    text = (repo / ".ai/next-step.md").read_text()
    for index, name in enumerate(advisor.SECTIONS, 1):
        assert f"## {index}. {name}" in text
    assert (repo / "app.py").read_text() == "# Current implementation"


@pytest.mark.parametrize("kind", ["http", "incomplete", "empty", "malformed"])
def test_failure_preserves_previous_plan(repo, monkeypatch, kind):
    monkeypatch.setattr(advisor, "ROOT", repo)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def fake_open(*args, **kwargs):
        if kind == "http":
            raise HTTPError("https://api.openai.com", 401, "Unauthorized", {}, None)
        if kind == "malformed":
            return io.BytesIO(b"not json")
        return response({}, status="incomplete" if kind == "incomplete" else "completed")

    monkeypatch.setattr(advisor, "urlopen", fake_open)
    assert advisor.main(["next", "--model", "test-model"]) == 1
    assert (repo / ".ai/next-step.md").read_text() == "Previous plan"


def test_dry_run_requires_no_credentials_and_does_not_write(repo, monkeypatch, capsys):
    monkeypatch.setattr(advisor, "ROOT", repo)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert advisor.main(["next", "--dry-run"]) == 0
    assert "files" in json.loads(capsys.readouterr().out)
    assert (repo / ".ai/next-step.md").read_text() == "Previous plan"


def test_missing_credentials_is_actionable(repo, monkeypatch, capsys):
    monkeypatch.setattr(advisor, "ROOT", repo)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    (repo / ".env").write_text("OPENAI_API_KEY=\nADVISOR_MODEL=\n")
    assert advisor.main(["next"]) == 1
    assert "OPENAI_API_KEY" in capsys.readouterr().err


@pytest.mark.parametrize("override", ["none", "environment", "cli"])
def test_dotenv_configuration_and_precedence(repo, monkeypatch, override):
    monkeypatch.setattr(advisor, "ROOT", repo)
    monkeypatch.chdir(repo.parent)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ADVISOR_MODEL", raising=False)
    (repo / ".env").write_text('OPENAI_API_KEY="local-key"\nADVISOR_MODEL="local-model"\n')
    expected_key, expected_model = "local-key", "local-model"
    if override in {"environment", "cli"}:
        monkeypatch.setenv("OPENAI_API_KEY", "env-key")
        monkeypatch.setenv("ADVISOR_MODEL", "env-model")
        expected_key, expected_model = "env-key", "env-model"
    args = ["next"]
    if override == "cli":
        args += ["--model", "cli-model"]
        expected_model = "cli-model"

    def fake_llm(context, api_key, model):
        assert api_key == expected_key
        assert model == expected_model
        assert "local-key" not in json.dumps(context)
        return {name: "Plan details" for name in advisor.SECTIONS}

    monkeypatch.setattr(advisor, "ask_llm", fake_llm)
    assert advisor.main(args) == 0
