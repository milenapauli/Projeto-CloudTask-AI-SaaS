# Entendendo o Docker do projeto (Dockerfile, Compose e imagens)

Guia didático para o aluno entender **como o Docker está organizado** neste
projeto: o que é cada arquivo, o que significam `cloudtask-api:dev` /
`:prod` / `:test`, e como tudo se conecta.

---

## 1. Conceitos rápidos

| Termo | O que é (analogia) |
| --- | --- |
| **Imagem** | uma "fôrma" congelada com tudo que a app precisa (Python, libs, código). Read-only. |
| **Container** | uma "instância viva" criada a partir de uma imagem (a app rodando). |
| **Dockerfile** | a *receita* de como construir a imagem. |
| **docker compose** | orquestra VÁRIOS containers juntos (ex.: API + banco) com um comando. |
| **tag** | um "apelido" para uma imagem, no formato `nome:tag` (ex.: `cloudtask-api:dev`). |

---

## 2. O que são `cloudtask-api:dev`, `:prod` e `:test`

São **três imagens diferentes** geradas a partir do **mesmo Dockerfile**, cada
uma para um momento do ciclo de vida. O texto depois dos dois-pontos (`dev`,
`prod`, `test`) é a **tag** — só um apelido para diferenciá-las.

| Imagem | Para quê | Contém | Onde aparece |
| --- | --- | --- | --- |
| `cloudtask-api:dev` | desenvolver | app + libs de **prod + test + dev** (debugpy, ruff, pytest...) | devcontainer, `docker-compose.yml` |
| `cloudtask-api:test` | rodar testes | app + `tests/` + libs de **prod + test** (pytest) | `docker-compose.test.yml`, CI |
| `cloudtask-api:prod` | produção (EKS) | **só** app + libs de prod (enxuta, sem dev/test) | `docker-compose.prod.yml`, ECR/EKS |

> A imagem **prod** é a que vai para a nuvem (Aula 7/8). Ela é a menor e mais
> segura: não tem pytest, ruff, debugpy nem o código de testes.

---

## 3. O Dockerfile (multi-stage)

O Dockerfile usa **multi-stage build**: vários "estágios" (`FROM ... AS nome`)
no mesmo arquivo. Cada estágio pode aproveitar o anterior. No final, escolhemos
**qual estágio** vira a imagem com `--target`.

```text
            ┌─────────┐
            │  base   │  Python 3.11 + tini + usuário não-root (appuser)
            └────┬────┘
                 │
        ┌────────▼────────┐
        │  builder-prod   │  instala requirements.txt        (libs de produção)
        └────────┬────────┘
                 │
        ┌────────▼────────┐
        │  builder-test   │  + requirements-test.txt          (pytest, httpx)
        └────────┬────────┘
                 │
        ┌────────▼────────┐
        │  builder-dev    │  + requirements-dev.txt           (debugpy, ruff...)
        └─────────────────┘

   Alvos finais (cada um copia as libs do builder correspondente):
        prod  ← builder-prod   (CMD: uvicorn)                  imagem enxuta
        test  ← builder-test   (CMD: pytest)  + copia tests/
        dev   ← builder-dev    (CMD: uvicorn --reload) + sudo + Node (apt)
```

**Por que separar `builder` de alvo final?** Os `builder-*` têm ferramentas de
compilação e caches; os alvos finais só **copiam** as bibliotecas já prontas
(`/root/.local`), ficando mais limpos.

**Por que cache em camadas?** Cada estágio copia o `requirements*.txt`
**antes** do código e instala. Enquanto o requirements não muda, o Docker
**reaproveita** a camada de instalação → builds muito mais rápidos.

Construir manualmente uma imagem específica:

```bash
docker build --target prod -t cloudtask-api:prod .
docker build --target dev  -t cloudtask-api:dev  .
docker build --target test -t cloudtask-api:test .
```

---

## 4. Os três arquivos de Compose

O Compose usa um arquivo **base** + **overrides** (sobreposições). Você combina
arquivos com `-f`; os de baixo sobrescrevem os de cima.

### `docker-compose.yml` (base / desenvolvimento)
Sobe **dois serviços**: `api` (target `dev`) + `db` (PostgreSQL 16). É o estado
padrão do dev e o que o **devcontainer** consome.

```bash
docker compose up --build           # sobe api + db
docker compose logs -f api          # logs da API
docker compose down                 # para (mantém o volume do banco)
```

### `docker-compose.prod.yml` (override de produção — simulação local)
Aplicado SOBRE o base, troca o `api` para o target `prod` e remove o que é de
dev (bind mount do código, porta de debug). Serve só para testar localmente que
a imagem de produção sobe limpa.

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build
```

> Usa as tags `!override` / `!reset` do Compose v2.24+ para SUBSTITUIR (e não
> mesclar) listas como `ports`/`volumes` herdadas do base.

### `docker-compose.test.yml` (override de testes)
Aplicado SOBRE o base, troca o `api` para o target `test` (com pytest) e usa um
banco **efêmero** (`cloudtask_test`, sem volume, sem porta no host). Rode SEMPRE
com um project name separado (`-p cloudtask-test`) para não colidir com seu dev:

```bash
docker compose -p cloudtask-test \
  -f docker-compose.yml -f docker-compose.test.yml \
  run --rm api
```

---

## 5. Como o devcontainer se encaixa

O `.devcontainer/devcontainer.json` aponta para o `docker-compose.yml` e diz ao
VS Code: "abra meu editor **dentro** do serviço `api`". Resultado:

- O VS Code constrói/usa a imagem `dev` e sobe `api` + `db`.
- O terminal integrado já é o Linux do container.
- As **features** adicionam AWS CLI, kubectl, Node, docker (ver
  `aws-academy-setup.md`).
- Com `overrideCommand: false`, o `uvicorn --reload` **sobe sozinho** →
  acesse `http://localhost:8000/docs`.

---

## 6. Fluxo geral (do código ao deploy)

```text
  escreve código  ──►  cloudtask-api:dev   (devcontainer, hot-reload)
        │
        ▼
   git push        ──►  cloudtask-api:test  (pytest passa?)         [CI futuro]
        │
        ▼
   testes passam   ──►  cloudtask-api:prod  ──► push ECR ──► EKS    [Aulas 7-8]
```

---

## 7. Cola de comandos

```bash
# Dev (compose)
docker compose up --build
docker compose exec api sh                 # shell no container da API
docker compose exec db psql -U cloudtask cloudtask

# Testes (projeto isolado)
docker compose -p cloudtask-test -f docker-compose.yml -f docker-compose.test.yml run --rm api
docker compose -p cloudtask-test -f docker-compose.yml -f docker-compose.test.yml down -v

# Produção local (smoke test)
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build

# Imagens / containers
docker images cloudtask-api                 # lista as tags dev/test/prod
docker ps                                   # containers rodando
```

## Referências

- [`HOW_TO_USE.md`](HOW_TO_USE.md) · [`aws-academy-setup.md`](aws-academy-setup.md)
- Multi-stage builds: <https://docs.docker.com/build/building/multi-stage/>
- Compose merge/override: <https://docs.docker.com/compose/multiple-compose-files/>
