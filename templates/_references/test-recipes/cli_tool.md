# Test Recipe — cli_tool

> Test strategy reference for standalone command-line tools.
> Read by the discovery session (stage 01) and used to fill §Test Strategy in plan.md (stage 02).

## Required test types

| Type | What it tests | When to use |
|---|---|---|
| **Unit** | Parsing functions, transformation, core logic | All logic without I/O |
| **Integration** | CLI end-to-end via subprocess, stdin/stdout, files | Complete commands with real inputs |

## Recommended frameworks

| Language | Unit | Integration (subprocess) |
|---|---|---|
| Python | `pytest` | `subprocess.run` + `click.testing.CliRunner` |
| Node.js | `vitest` / `jest` | `execa` or `child_process.spawnSync` |
| Go | `testing` | `os/exec` or table-driven cases |
| Rust | `#[test]` | `assert_cmd` crate |

## Essential patterns

### Click — use CliRunner (no subprocess overhead)

```python
from click.testing import CliRunner
from myapp.cli import main

def test_convert_command_creates_output_file(tmp_path):
    runner = CliRunner()
    input_file = tmp_path / "input.csv"
    input_file.write_text("a,b\n1,2\n")
    output_file = tmp_path / "output.json"

    result = runner.invoke(main, ["convert", str(input_file), "--output", str(output_file)])

    assert result.exit_code == 0
    assert output_file.exists()
    assert json.loads(output_file.read_text()) == [{"a": "1", "b": "2"}]

def test_convert_command_fails_on_missing_file(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, ["convert", "nonexistent.csv"])
    assert result.exit_code != 0
    assert "not found" in result.output.lower()
```

### Direct subprocess (framework-agnostic)

```python
import subprocess, sys

def run_cli(*args: str, input_text: str = "") -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "myapp", *args],
        input=input_text,
        capture_output=True,
        text=True,
        timeout=10,
    )

def test_version_flag():
    result = run_cli("--version")
    assert result.returncode == 0
    assert "1.0" in result.stdout

def test_stdin_input():
    result = run_cli("process", "--stdin", input_text="hello world\n")
    assert result.returncode == 0
    assert "HELLO WORLD" in result.stdout
```

### Tempdir fixtures for I/O files

```python
@pytest.fixture
def workspace(tmp_path):
    """Clean directory per test — no shared state."""
    (tmp_path / "input").mkdir()
    (tmp_path / "output").mkdir()
    return tmp_path

def test_batch_process_all_files_in_dir(workspace):
    # Create inputs
    for i in range(3):
        (workspace / "input" / f"file{i}.txt").write_text(f"content {i}")

    result = run_cli("batch", str(workspace / "input"), "--output", str(workspace / "output"))

    assert result.returncode == 0
    output_files = list((workspace / "output").iterdir())
    assert len(output_files) == 3
```

## File structure

```
tests/
  unit/
    test_parser.py          # argument parsing, validation
    test_transform.py       # transformation logic
    test_formatter.py       # output formatting
  integration/
    test_cli_convert.py     # convert command end-to-end
    test_cli_batch.py       # batch command
    test_cli_errors.py      # all error exit codes
```

## Anti-patterns

- Testing shell behavior (pipes, redirects) — out of scope; test the CLI, not the shell.
- Hardcoded absolute paths in tests — always use pytest `tmp_path`.
- Not testing exit codes — exit code is part of a CLI's contract.
- Tests depending on current directory state (`os.getcwd()`) — isolate with `monkeypatch.chdir`.

## Quick checklist (auto-QA Akita support)

- [ ] Each subcommand has ≥1 integration test with real input
- [ ] Exit code 0 (success) and ≠0 (error) tested for each command
- [ ] All I/O files use `tmp_path` (no global state)
- [ ] Stdin/stdout tested if the command supports them
- [ ] `--help` and `--version` tested
- [ ] Timeout set in subprocess calls (prevents hanging tests)
