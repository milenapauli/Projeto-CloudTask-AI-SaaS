<!-- Área do Banner -->
<div align="center" style="background-color: white; max-width: 70%;">
  <img alt="BANNER do repositório CloudTask AI SaaS — disciplina Computação em Nuvem" title="Banner_CloudTask_AI_SaaS" src=".readme_docs/Banner_Github_NCPU.png" width="100%" />
</div>

<!-- Título e breve descrição do repositório -->
<div align="center">
  <h1>CloudTask AI SaaS — Aula 4</h1>
  <p><b>Branch <code>semana-02-rds-vpc-seguranca</code> — estado pós Aula 4.</b></p>
  <p>API FastAPI + PostgreSQL + CRUD, agora com <b>config por <code>.env</code></b>, <b>readiness probe</b> e <b>HTTPS</b>.</p>
</div>

<p align="center">
  <a href="https://www.python.org/" title="Python"><img src="https://github.com/get-icon/geticon/raw/master/icons/python.svg" alt="Python" height="21px"></a>
  +
  <a href="https://fastapi.tiangolo.com/" title="FastAPI"><img src="https://github.com/get-icon/geticon/raw/master/icons/fastapi.svg" alt="FastAPI" height="21px"></a>
  +
  <a href="https://www.docker.com/" title="Docker"><img src="https://github.com/get-icon/geticon/raw/master/icons/docker-icon.svg" alt="Docker" height="21px"></a>
  +
  <a href="https://www.postgresql.org/" title="PostgreSQL"><img src="https://github.com/get-icon/geticon/raw/master/icons/postgresql.svg" alt="PostgreSQL" height="21px"></a>
  +
  <a href="https://www.sqlalchemy.org/" title="SQLAlchemy">SQLAlchemy</a>
</p>

## O que foi entregue nesta aula (Aula 4)

- `app/core/config.py` — configuração central com **pydantic-settings** (lê `.env` / variáveis de ambiente, valida tipos).
- `GET /health/ready` — **readiness probe** que faz `SELECT 1` no PostgreSQL (`200` pronto / `503` banco fora). `GET /health` permanece **liveness puro** (não toca no banco).
- **HTTPS / transporte:**
  - `uvicorn --proxy-headers` no `Dockerfile` (confia no `X-Forwarded-Proto` do ALB).
  - **HSTS** enviado quando `FORCE_HTTPS=true` e fora de `development` (sem `preload`).
  - `TrustedHostMiddleware` (hosts via `TRUSTED_HOSTS`).
  - `HTTPSRedirectMiddleware` só no caso sem proxy (`FORCE_HTTPS=true` e `BEHIND_PROXY=false`).
- Docs de segurança: `docs/https-tls.md`, `docs/aws-networking.md`, `docs/security-model.md`.
- `.env.example` cobre `FORCE_HTTPS`, `BEHIND_PROXY`, `TRUSTED_HOSTS`.
- Versão: **`0.2.0`** (mesma Semana 2).

### Já existia (Aula 3)
- Serviço `db` (PostgreSQL 16-alpine) no compose; camada `app/db/` (database, models, schemas); CRUD `/tasks`; tabelas criadas no startup.

> Tudo com **comentários didáticos** explicando motivo, impacto e risco de cada decisão.

## Endpoints

| Método | Caminho            | Descrição                              |
| ------ | ------------------ | -------------------------------------- |
| GET    | `/`                | Metadados da aplicação.                |
| GET    | `/health`          | Liveness probe (não toca no banco).    |
| GET    | `/health/ready`    | Readiness probe (checa o PostgreSQL).  |
| POST   | `/tasks`           | Criar tarefa (201).                    |
| GET    | `/tasks`           | Listar tarefas (paginação `skip`/`limit`). |
| GET    | `/tasks/{task_id}` | Obter tarefa por id (404 se não existe). |
| PUT    | `/tasks/{task_id}` | Atualizar tarefa (parcial).            |
| DELETE | `/tasks/{task_id}` | Remover tarefa (204).                  |
| GET    | `/docs`            | Swagger UI.                            |

### Modelo `Task`

```text
id           int        (gerado pelo banco)
title        str        (obrigatório, 1–200 chars)
description  str | null  (até 2000 chars)
status       enum        pending | in_progress | done   (default pending)
priority     enum        low | medium | high            (default medium)
created_at   datetime    (carimbado pelo banco)
updated_at   datetime    (atualizado pelo banco a cada PUT)
```

## Pré-requisitos

| Ferramenta              | Versão mínima | Para quê                       |
| ----------------------- | ------------- | ------------------------------ |
| Docker Desktop          | 4.30          | API + PostgreSQL em containers |
| VS Code + Dev Containers| 1.90 / 0.380  | Abrir o projeto no container   |

> Nunca usou terminal/Docker? Veja [`docs/aws-academy-setup.md`](docs/aws-academy-setup.md).

## Como rodar

### 1) Devcontainer no VS Code (recomendado)

```text
1. F1 → "Dev Containers: Rebuild and Reopen in Container".
   (Rebuild porque o compose agora tem o serviço `db`.)
2. O VS Code sobe API + PostgreSQL juntos.
3. Terminal integrado:  uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
4. Abra http://localhost:8000/docs
```

### 2) Docker Compose direto

```bash
docker compose up --build           # sobe API + PostgreSQL
curl http://localhost:8000/tasks    # deve responder []
docker compose down                 # para (mantém os dados)
docker compose down -v              # para e ZERA o banco
```

> ⚠️ Se a porta **5432** já estiver ocupada na sua máquina, defina
> `POSTGRES_PORT=5433` (ou outra livre) no seu `.env` antes de subir.

### Testando o CRUD pelo terminal

```bash
# criar
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"title":"Minha primeira tarefa","priority":"high"}'

# listar
curl http://localhost:8000/tasks

# atualizar (id 1)
curl -X PUT http://localhost:8000/tasks/1 \
  -H "Content-Type: application/json" -d '{"status":"done"}'

# remover (id 1)
curl -X DELETE http://localhost:8000/tasks/1
```

## Conexão com o banco

`DATABASE_URL` (lida do ambiente; default no compose):

```text
postgresql+psycopg2://cloudtask:cloudtask@db:5432/cloudtask
```

O host `db` é o nome do serviço no Compose. Esta **mesma URL** servirá para o
Amazon RDS na nuvem — só muda o host/usuário/senha (via Secret). Por isso
usamos PostgreSQL 16 local, igual ao RDS.

## Testes (unitários + integração)

A suíte de testes cobre schemas, configuração, endpoints de saúde e o CRUD
completo contra um PostgreSQL. Os arquivos ficam em [`tests/`](tests/) e estão
disponíveis tanto no container de **dev** quanto no de **test**.

### Opção A — dentro do devcontainer (mais simples)

O devcontainer já traz o `pytest`. No terminal integrado do VS Code:

```bash
pytest                 # roda todos os testes
pytest -v              # modo verboso (lista cada teste)
pytest tests/test_tasks_crud.py     # só um arquivo
pytest -k crud         # só testes cujo nome casa com "crud"
pytest --cov=app       # com relatório de cobertura
```

> Os testes usam um banco **separado** (`cloudtask_test`), criado
> automaticamente. Seus dados de desenvolvimento (`cloudtask`) **não** são
> tocados.

### Opção B — container de testes isolado (igual ao CI)

Sobe uma imagem `test` + um PostgreSQL efêmero, roda a suíte e sai. Use um
*project name* separado (`-p cloudtask-test`) para **não colidir** com o seu
devcontainer:

```bash
# rodar a suíte
docker compose -p cloudtask-test \
  -f docker-compose.yml -f docker-compose.test.yml \
  run --rm api

# limpar tudo depois
docker compose -p cloudtask-test \
  -f docker-compose.yml -f docker-compose.test.yml down -v
```

### O que cada arquivo de teste cobre

| Arquivo | Tipo | Cobre |
| --- | --- | --- |
| `tests/test_schemas.py` | unitário | validação dos schemas Pydantic (defaults, título vazio, enums) |
| `tests/test_config.py` | unitário | parsing do `.env` (TRUSTED_HOSTS CSV, `FORCE_HTTPS` bool) |
| `tests/test_health.py` | integração | `/`, `/health` (liveness) e `/health/ready` (200 e 503) |
| `tests/test_tasks_crud.py` | integração | CRUD completo de `/tasks` + erros 404/422 |

## Entendendo o Docker do projeto

Quer saber o que são `cloudtask-api:dev` / `:prod` / `:test`, como o
`Dockerfile` multi-stage funciona e a diferença entre os três arquivos de
Compose? Veja o guia: [`docs/docker-explained.md`](docs/docker-explained.md).

Resumo rápido:

| Imagem | Para quê | Onde aparece |
| --- | --- | --- |
| `cloudtask-api:dev` | desenvolver (hot-reload, debug) | devcontainer, `docker-compose.yml` |
| `cloudtask-api:test` | rodar `pytest` | `docker-compose.test.yml`, CI |
| `cloudtask-api:prod` | produção enxuta | `docker-compose.prod.yml`, ECR/EKS |

## Conhecendo a aplicação (passo a passo)

1. Abra o devcontainer (`F1 → Dev Containers: Reopen in Container`). A API sobe
   sozinha.
2. Acesse o **Swagger**: <http://localhost:8000/docs> — clique em **Try it out**
   em qualquer rota para chamá-la pelo navegador.
3. Veja os metadados: <http://localhost:8000/> e a saúde:
   <http://localhost:8000/health> e <http://localhost:8000/health/ready>.
4. Crie tarefas pelo Swagger (`POST /tasks`) ou pelo `curl` (seção acima).
5. Veja os logs da API: `docker compose logs -f api`.
6. Entre no banco: `docker compose exec db psql -U cloudtask cloudtask` e rode
   `SELECT * FROM tasks;`.
7. Rode os testes: `pytest -v`.

## O que vem na próxima aula

- **Semana 3 (branch `semana-03-s3-kubernetes`):** upload de arquivos com Amazon S3
  (com fallback local) e Kubernetes local com Kind. Versão sobe para `0.3.0`.

## Referências

- Issue da aula: [#4 — Aula 4](https://github.com/N-CPUninter/Computa-o-em-Nuvem---Projeto-exemplo-CloudTask-AI-SaaS/issues/4)
- Lista de tarefas: [`docs/TAREFAS.md`](docs/TAREFAS.md)
- Guia geral: [`docs/HOW_TO_USE.md`](docs/HOW_TO_USE.md)
- Setup do zero: [`docs/aws-academy-setup.md`](docs/aws-academy-setup.md)
- Segurança: [`docs/security-model.md`](docs/security-model.md) · [`docs/aws-networking.md`](docs/aws-networking.md) · [`docs/https-tls.md`](docs/https-tls.md)
- Docker explicado: [`docs/docker-explained.md`](docs/docker-explained.md)
- SQLAlchemy 2.0: <https://docs.sqlalchemy.org/en/20/>

## Licença

[GNU General Public License v3.0](LICENSE).
