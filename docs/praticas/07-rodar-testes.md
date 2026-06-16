# Prática 07 — Rodar a suite de testes

> **Objetivo:** rodar `pytest` de duas formas:
> 1. Dentro do devcontainer (rápido, dia-a-dia).
> 2. Container isolado (igual ao CI futuro).
>
> **Tempo:** 10 min.
>
> **Pré-req:** API rodando (ver [01](01-rodar-api-devcontainer.md)) e prática
> [04](04-explorar-banco-psql.md) (entender transação/rollback ajuda).

---

## 1. No devcontainer — modo rápido

```bash
pytest
```

> 💡 **Por que funciona sem flag?** A configuração está no `pyproject.toml`:
> ```toml
> [tool.pytest.ini_options]
> addopts = "-ra -q -p no:warnings"
> testpaths = ["tests"]
> ```
> Isso silencia warnings, mostra resumo dos não-passados (`-ra`) e usa output curto (`-q`).

Saída esperada:

```
.........................................                   [100%]
41 passed in 1.23s
```

---

## 2. Modo verbose (ver cada teste)

```bash
pytest -v
```

Saída:

```
tests/test_config.py::test_settings_default_values PASSED
tests/test_health.py::test_health_endpoint PASSED
tests/test_tasks_crud.py::test_criar_tarefa PASSED
...
```

---

## 3. Filtrar por padrão de nome

```bash
pytest -k "upload"
pytest -k "crud and not delete"
pytest tests/test_uploads.py
pytest tests/test_uploads.py::test_upload_local
```

---

## 4. Cobertura de código

```bash
pytest --cov=app --cov-report=term-missing
```

> Mostra % de linhas cobertas, e quais NÃO foram exercitadas. Útil pra
> direcionar onde escrever mais testes.

HTML interativo:

```bash
pytest --cov=app --cov-report=html
# abra htmlcov/index.html no navegador
```

---

## 5. Como os testes NÃO sujam o banco de dev?

Olhe `tests/conftest.py` → fixture `db_session`:

```python
# 1. Abre uma conexão
# 2. Begin transaction
# 3. TRUNCATE TABLE tasks RESTART IDENTITY CASCADE  ← limpa dados de dev DENTRO da transação
# 4. Sessão usa savepoint (join_transaction_mode="create_savepoint")
# 5. Teste roda...
# 6. ROLLBACK no finally → tudo desfeito, dados de dev voltam
```

**Resultado:**

- Testes veem **tabela limpa** (não tem dados de dev "vazando").
- Dados que você criou via Swagger/curl **continuam intactos** após pytest
  (foram preservados pelo rollback).

> 💡 Esse é o motivo de não precisarmos de banco separado pra teste.

Para verificar: crie tarefas via curl, rode `pytest`, liste de novo — elas
estão lá.

---

## 6. Container isolado (modo CI)

Quando quiser **garantir** que os testes passam sem depender do seu ambiente:

```bash
docker compose -p cloudtask-test \
  -f docker-compose.yml \
  -f docker-compose.test.yml \
  run --build --rm api
```

> 💡 Decompondo:
> - `-p cloudtask-test` — outro **project name** → containers e volumes separados.
> - `-f docker-compose.yml -f docker-compose.test.yml` — merge dos dois.
> - `docker-compose.test.yml` muda `target: test` e usa banco efêmero.
> - `--build` — **reconstrói a imagem antes de rodar** (ver aviso abaixo).
> - `run --rm api` — sobe `db` (depends_on) + executa o CMD do target `test`
>   (que é `pytest`) e remove no fim.

> ⚠️ **SEMPRE `--build` aqui.** Diferente do caminho rápido (`pytest`/`tv`
> dentro do devcontainer, que usa o código por **volume** e enxerga suas edições
> na hora), o target `test` **embute o código na imagem** via `COPY` (sem bind
> mount). Sem `--build`, o Compose reaproveita a imagem em cache com o código
> **antigo** → você roda uma versão **fóssil**: a correção que acabou de fazer
> "não faz efeito", ou um teste que você quebrou continua passando. Com
> `--build`, a imagem é reconstruída e reflete o código atual do disco.

Limpar:

```bash
docker compose -p cloudtask-test -f docker-compose.yml -f docker-compose.test.yml down -v
```

> `-v` remove os volumes do projeto de teste (banco efêmero).

---

## 7. Debug de teste que falhou

```bash
pytest -v --tb=short        # traceback curto
pytest -v --tb=long         # traceback longo (default)
pytest -v --pdb             # cai no debugger Python ao falhar
pytest -v -x                # para no primeiro fail
pytest -v --lf              # roda só os que falharam da última vez
```

---

## Erros comuns

| Erro | Causa | Fix |
| --- | --- | --- |
| `psycopg2.OperationalError: could not connect` | banco `db` não subiu | `docker compose up -d db` |
| `ModuleNotFoundError: No module named 'pytest'` | está no target `prod` (sem pytest) | troque para `dev` ou `test` |
| Testes passam local mas falham no isolado | dependência implícita de dados | confira fixture e seed do isolado |
| `address already in use` na porta 5432 | banco do projeto principal de pé | use `-p cloudtask-test` (isola portas se tiver `ports: !override`) |
| `41 passed in 0.01s` (suspeito) | só rodou os marcados/skipped | confira filtros (`-k`, `-m`) ativos |

---

## Próximo passo

→ [`08-debug-vscode.md`](08-debug-vscode.md): usar breakpoints no VS Code.
