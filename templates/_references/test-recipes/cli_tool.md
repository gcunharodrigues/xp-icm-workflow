# Test Recipe — cli_tool

> Referência de estratégia de teste para ferramentas de linha de comando standalone.
> Lido pela sessão de discovery (stage 01) e usado para preencher §Test Strategy no plan.md (stage 02).

## Tipos de teste obrigatórios

| Tipo | O que testa | Quando usar |
|---|---|---|
| **Unit** | Funções de parsing, transformação, lógica core | Toda lógica sem I/O |
| **Integration** | CLI end-to-end via subprocess, stdin/stdout, arquivos | Comandos completos com entradas reais |

## Frameworks recomendados

| Linguagem | Unit | Integration (subprocess) |
|---|---|---|
| Python | `pytest` | `subprocess.run` + `click.testing.CliRunner` |
| Node.js | `vitest` / `jest` | `execa` ou `child_process.spawnSync` |
| Go | `testing` | `os/exec` ou tabela de casos |
| Rust | `#[test]` | `assert_cmd` crate |

## Padrões essenciais

### Click — usar CliRunner (sem subprocess overhead)

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

### Subprocess direto (agnóstico de framework)

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

### Tempdir fixtures para arquivos de I/O

```python
@pytest.fixture
def workspace(tmp_path):
    """Diretório limpo por test — sem estado compartilhado."""
    (tmp_path / "input").mkdir()
    (tmp_path / "output").mkdir()
    return tmp_path

def test_batch_process_all_files_in_dir(workspace):
    # Criar inputs
    for i in range(3):
        (workspace / "input" / f"file{i}.txt").write_text(f"content {i}")

    result = run_cli("batch", str(workspace / "input"), "--output", str(workspace / "output"))

    assert result.returncode == 0
    output_files = list((workspace / "output").iterdir())
    assert len(output_files) == 3
```

## Estrutura de arquivos

```
tests/
  unit/
    test_parser.py          # parsing de argumentos, validação
    test_transform.py       # lógica de transformação
    test_formatter.py       # formatação de output
  integration/
    test_cli_convert.py     # comando convert end-to-end
    test_cli_batch.py       # comando batch
    test_cli_errors.py      # todos os exit codes de erro
```

## Anti-patterns

- Testar comportamento do shell (pipes, redirects) — fora de escopo; testar a CLI, não o shell.
- Hardcoded paths absolutos em testes — usar `tmp_path` do pytest sempre.
- Não testar exit codes — código de saída é parte do contrato de uma CLI.
- Testes que dependem de estado do diretório atual (`os.getcwd()`) — isolar com `monkeypatch.chdir`.

## Checklist rápido (auto-QA Akita suporte)

- [ ] Cada subcomando tem ≥1 integration test com input real
- [ ] Exit code 0 (sucesso) e ≠0 (erro) testados para cada comando
- [ ] Todos os arquivos de I/O usam `tmp_path` (sem estado global)
- [ ] Stdin/stdout testados se o comando os suportar
- [ ] `--help` e `--version` testados
- [ ] Timeout definido em subprocess calls (evita testes pendurados)
