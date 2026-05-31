<!-- Área do Banner -->
<div align="center" style="background-color: white; max-width: 70%;">
  <img alt="BANNER do repositório CloudTask AI SaaS — disciplina Computação em Nuvem" title="Banner_CloudTask_AI_SaaS" src=".readme_docs/Banner_Github_NCPU.png" width="100%" />
</div>

<!-- Título e breve descrição do repositório -->
<div align="center">
  <h1>CloudTask AI SaaS — Semana 3 (Aulas 5 e 6)</h1>
  <p><b>Branch <code>semana-03-s3-kubernetes</code> — cobre as Aulas 5 e 6.</b></p>
  <p>API FastAPI + PostgreSQL + CRUD agora com <b>upload de arquivos (S3 ou local)</b> (Aula 5) e <b>Kubernetes local com Kind</b> (Aula 6, a vir).</p>
</div>

<p align="center">
  <a href="https://www.python.org/" title="Python"><img src="https://github.com/get-icon/geticon/raw/master/icons/python.svg" alt="Python" height="21px"></a>
  +
  <a href="https://fastapi.tiangolo.com/" title="FastAPI"><img src="https://icon.icepanel.io/Technology/svg/FastAPI.svg" alt="FastAPI" height="21px"></a>
  +
  <a href="https://www.docker.com/" title="Docker"><img src="https://github.com/get-icon/geticon/raw/master/icons/docker-icon.svg" alt="Docker" height="21px"></a>
  +
  <a href="https://www.postgresql.org/" title="PostgreSQL"><img src="https://github.com/get-icon/geticon/raw/master/icons/postgresql.svg" alt="PostgreSQL" height="21px"></a>
  +
  <a href="https://aws.amazon.com/s3/" title="Amazon S3">Amazon S3</a>
  +
  <a href="https://kubernetes.io/" title="Kubernetes">Kubernetes</a>
</p>

## O que foi feito nesta semana

Esta branch contém **as duas aulas da Semana 3**. Abaixo, o que cada aula entregou.

### Aula 5 — Upload de arquivos (Amazon S3 + fallback local)

- `app/services/s3_service.py` — dois backends com a **mesma interface**:
  - `LocalStorage` (default): grava em `LOCAL_UPLOADS_DIR` no container.
  - `S3Storage`: envia para o bucket `S3_BUCKET_NAME` (boto3).
  - `get_storage()` escolhe um ou outro a partir de `STORAGE_MODE`.
- `app/api/routes_uploads.py`:
  - `POST /uploads` — recebe `multipart/form-data`, devolve nome + URL.
  - `GET /uploads/{filename}` — local serve do disco; S3 redireciona para URL pré-assinada.
- Limite de **10 MB** por arquivo (config didática).
- Nome de arquivo armazenado é **sanitizado** (sem `..`, com sufixo único) — evita path traversal.
- `app/schemas.py` ganhou `UploadResponse` com exemplos no Swagger.
- `app/core/config.py` ganhou `STORAGE_MODE`, `LOCAL_UPLOADS_DIR`, `AWS_REGION`, `S3_BUCKET_NAME`, `S3_ENDPOINT_URL` (opcional), `S3_PRESIGNED_URL_EXPIRES`.
- Testes (`tests/test_uploads.py`): fluxo feliz, 404, 413, 422, extensão preservada.
- `docs/s3-efs-datalake.md` — guia didático S3 × EFS × Data Lake.

### Aula 6 — Kubernetes local com Kind (a vir)

Manifests em `infra/k8s/` (namespace, deployment, service, configmap, secret.example).
Rodar local com **Kind** ou **Minikube** no host (não no devcontainer).

Versão da API ao fim da semana: **`0.3.0`**.

### Base herdada das semanas anteriores
FastAPI + PostgreSQL + CRUD, config `.env`, HTTPS preparado, readiness probe,
testes (transação + savepoint), docker-compose dev/prod/test, devcontainer com
zsh + sticky scroll + transient prompt + AWS CLI, kubectl, eksctl, Node+CDK,
docker-outside-of-docker.

> Todo o código vem com **comentários didáticos** explicando motivo, impacto e
> risco de cada decisão.

## Endpoints

| Método | Caminho               | Descrição |
| ------ | --------------------- | --------- |
| GET    | `/`                   | Metadados da aplicação. |
| GET    | `/health`             | Liveness probe. |
| GET    | `/health/ready`       | Readiness (checa o PostgreSQL). |
| POST   | `/tasks`              | Criar tarefa (201). |
| GET    | `/tasks`              | Listar (paginação `skip`/`limit`). |
| GET    | `/tasks/{task_id}`    | Obter por id (404). |
| PUT    | `/tasks/{task_id}`    | Atualizar parcial. |
| DELETE | `/tasks/{task_id}`    | Remover (204). |
| **POST** | **`/uploads`**          | **Enviar arquivo (multipart, 201)** |
| **GET**  | **`/uploads/{filename}`** | **Baixar (200) ou redirect S3 (307)** |
| GET    | `/docs`               | Swagger UI. |

## Como rodar

### Devcontainer (recomendado)
`F1` → "Dev Containers: Reopen in Container". A API sobe sozinha em
`http://localhost:8000/docs`.

### Modo local (default — sem AWS)
```bash
# upload (qualquer arquivo)
curl -F "file=@README.md" http://localhost:8000/uploads
# resposta: {"filename":"abcd1234-...md","url":"/uploads/abcd...md","storage_mode":"local"}

# download
curl -O http://localhost:8000/uploads/abcd1234-...md
```

### Modo S3 (precisa de credenciais AWS)
```bash
# 1. criar bucket (uma vez)
aws s3 mb s3://cloudtask-ai-saas-uploads-SEU-NOME --region us-east-1

# 2. configurar .env
echo "STORAGE_MODE=s3" >> .env
echo "S3_BUCKET_NAME=cloudtask-ai-saas-uploads-SEU-NOME" >> .env

# 3. recriar container e testar
docker compose down && docker compose up -d
curl -F "file=@README.md" http://localhost:8000/uploads
# resposta agora traz URL pré-assinada do S3
```

## Testes

```bash
pytest -v
```
41 testes (5 novos de upload). Mode S3 não tem teste automatizado (depende de
credenciais reais ou LocalStack); validar manualmente.

## O que vem na próxima aula

- **Aula 6 (mesma branch):** Kubernetes local com **Kind**. Manifests `namespace.yaml`, `deployment.yaml`, `service.yaml`, `configmap.yaml`, `secret.example.yaml`. Cluster e `kubectl` rodam **no HOST**, não no devcontainer.

## Referências

- Issue da aula: [#5 — Aula 5](https://github.com/N-CPUninter/Computa-o-em-Nuvem---Projeto-exemplo-CloudTask-AI-SaaS/issues/5)
- Lista de tarefas: [`docs/TAREFAS.md`](docs/TAREFAS.md)
- Setup do zero: [`docs/aws-academy-setup.md`](docs/aws-academy-setup.md)
- **S3 explicado**: [`docs/s3-efs-datalake.md`](docs/s3-efs-datalake.md)
- Segurança: [`docs/security-model.md`](docs/security-model.md) · [`docs/aws-networking.md`](docs/aws-networking.md) · [`docs/https-tls.md`](docs/https-tls.md)
- Docker: [`docs/docker-explained.md`](docs/docker-explained.md)

## Licença

[GNU General Public License v3.0](LICENSE).
