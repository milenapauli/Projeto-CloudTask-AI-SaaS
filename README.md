<!-- Área do Banner -->
<div align="center" style="background-color: white; max-width: 70%;">
  <img alt="BANNER do repositório CloudTask AI SaaS — disciplina Computação em Nuvem" title="Banner_CloudTask_AI_SaaS" src=".readme_docs/Banner_Github_NCPU.png" width="100%" />
</div>

<!-- Título e breve descrição do repositório -->
<div align="center">
  <h1>CloudTask AI SaaS — Semana 4 (Aulas 7 e 8) — combinada com a Semana 3</h1>
  <p><b>Branch <code>semana-04-eks-aws</code> — cobre as Aulas 7 e 8 (e revisa as Aulas 5 e 6 da Semana 3, que não teve aula).</b></p>
  <p>API FastAPI + PostgreSQL + CRUD com <b>uploads S3/local</b> e <b>Kubernetes local com Kind</b> (vindos da Semana 3), agora também <b>publicada no Amazon ECR</b> (Aula 7) e <b>deployada no Amazon EKS</b> (Aula 8).</p>
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
  +
  <a href="https://aws.amazon.com/ecr/" title="Amazon ECR">Amazon ECR</a>
  +
  <a href="https://aws.amazon.com/eks/" title="Amazon EKS">Amazon EKS</a>
</p>

## O que foi feito nesta semana

> 📌 **Aula combinada Semanas 3 + 4.** A Semana 3 não teve aula presencial, então
> esta branch revisita as entregas das Aulas 5 e 6 (S3/uploads e Kind local) e
> adiciona as Aulas 7 e 8 (ECR e EKS na nuvem).

### Aula 7 — Publicar imagem no Amazon ECR

- `scripts/build-and-push-ecr.sh` — script idempotente que cria o repo, faz login,
  builda a imagem `--target prod`, taggea e dá `push` no ECR.
- `buildspec.yml` — equivalente para o AWS CodeBuild (alternativa ao build local).
- Doc completo: [`docs/praticas/11-ecr-push.md`](docs/praticas/11-ecr-push.md)
  (caminho fácil via script + caminho manual com bash e PowerShell + troubleshooting).
- A imagem fica em `<ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/cloudtask-api:latest`
  pronta para o EKS puxar.

### Aula 8 — Deploy no Amazon EKS

- `infra/k8s/aws/` — manifests para o cluster EKS:
  - `namespace.yaml`, `configmap.yaml`, `secret.example.yaml`.
  - `postgres-deployment.yaml` + `postgres-service.yaml` — Postgres como Pod (didático).
  - `deployment-eks.yaml` — API com imagem vinda do ECR, 2 réplicas, probes HTTP.
  - `service-loadbalancer.yaml` — `type: LoadBalancer` (ELB público real).
  - `ingress-optional.yaml` — alternativa ALB Ingress (Aula 12 / conta pessoal).
  - `kustomization.yaml` — `kubectl apply -k infra/k8s/aws/` aplica tudo.
- Doc completo: [`docs/praticas/12-eks-deploy.md`](docs/praticas/12-eks-deploy.md)
  (cluster via `eksctl`, deploy, pegar URL do ELB, demo perda de dados, **cleanup obrigatório**).

### Aula 5 (revisão) — Upload de arquivos (Amazon S3 + fallback local)

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
- `docs/conceitos/s3-efs-datalake.md` — guia didático S3 × EFS × Data Lake.

### Aula 6 (revisão) — Kubernetes local com Kind

- `infra/k8s/` — manifests:
  - `kind-config.yaml` — cluster Kind de 1 nó com porta `30080` mapeada para o host.
  - `namespace.yaml` — namespace `cloudtask`.
  - `configmap.yaml` — config não-sensível (hostname Postgres, STORAGE_MODE).
  - `secret.example.yaml` — TEMPLATE; copie para `secret.yaml` (gitignored) e preencha.
  - `postgres-deployment.yaml` + `postgres-service.yaml` — Postgres como Pod (sem volume — didático).
  - `api-deployment.yaml` — 2 réplicas da API, init container espera Postgres, probes HTTP.
  - `api-service.yaml` — NodePort `30080`.
  - `kustomization.yaml` — `kubectl apply -k infra/k8s/` aplica tudo.
- Roteiro passo a passo: [`docs/praticas/10-kubernetes-kind-local.md`](docs/praticas/10-kubernetes-kind-local.md).
- **Kind roda no HOST** (não no devcontainer). `kubectl` funciona dos dois lados.

Versão da API ao fim da semana: **`0.4.0`**.

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

> ⚠️ **Ao mudar de semana (branch), faça REBUILD do devcontainer.**
> A imagem do container é um snapshot congelado das dependências da branch em que
> foi construída. Cada semana acrescenta libs novas em `requirements.txt` (ex.:
> `boto3` na Semana 3, `kubernetes` na Semana 6, etc.). Sem rebuild, o `uvicorn`
> vai quebrar com `ModuleNotFoundError` ao tentar importar uma lib que ainda não
> foi instalada e o Swagger sai do ar.
>
> No VS Code: `F1` → **Dev Containers: Rebuild and Reopen in Container**.
>
> Para saber se precisa rebuild antes de trocar de branch:
> ```bash
> git diff <branch-atual> <branch-destino> -- requirements.txt requirements-dev.txt requirements-test.txt Dockerfile docker-compose.yml
> ```
> Se mostrar diff → rebuild. Entre **aulas da mesma semana**, geralmente código
> apenas — não precisa rebuild.

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

## Como subir na AWS (resumo)

```bash
# 1. credenciais Learner Lab no host (~/.aws/credentials)
aws sts get-caller-identity

# 2. Aula 7 — publicar imagem no ECR
./scripts/build-and-push-ecr.sh

# 3. Aula 8 — cluster EKS (~15 min) + deploy
eksctl create cluster --name cloudtask-eks --region us-east-1 \
  --node-type t3.small --nodes 2 --managed
kubectl apply -k infra/k8s/aws/
kubectl get svc -n cloudtask api -w   # esperar o ELB ficar pronto
```

> ⚠️ **Custo:** EKS cobra ~$0,10/h + 2 nós EC2 + ELB. **Sempre destrua ao fim:**
> ```bash
> kubectl delete -k infra/k8s/aws/
> eksctl delete cluster --name cloudtask-eks --region us-east-1
> ```

Roteiros mastigados: [`docs/praticas/11-ecr-push.md`](docs/praticas/11-ecr-push.md) → [`docs/praticas/12-eks-deploy.md`](docs/praticas/12-eks-deploy.md).

## O que vem na próxima semana

- **Semana 5 (`semana-05-custos-nosql-logs`):** Aulas 9 e 10 — **HPA + teste de carga + Cost Explorer** e **eventos com DynamoDB**.

## Referências

- Issues da semana: [#7 — Aula 7](https://github.com/N-CPUninter/Computa-o-em-Nuvem---Projeto-exemplo-CloudTask-AI-SaaS/issues/7) · [#8 — Aula 8](https://github.com/N-CPUninter/Computa-o-em-Nuvem---Projeto-exemplo-CloudTask-AI-SaaS/issues/8) · [#5 — Aula 5](https://github.com/N-CPUninter/Computa-o-em-Nuvem---Projeto-exemplo-CloudTask-AI-SaaS/issues/5) · [#6 — Aula 6](https://github.com/N-CPUninter/Computa-o-em-Nuvem---Projeto-exemplo-CloudTask-AI-SaaS/issues/6)
- Lista de tarefas: [`docs/TAREFAS.md`](docs/TAREFAS.md)
- Setup do zero: [`docs/praticas/00-setup-inicial-e-aws-academy.md`](docs/praticas/00-setup-inicial-e-aws-academy.md)
- **ECR**: [`docs/praticas/11-ecr-push.md`](docs/praticas/11-ecr-push.md) + `scripts/build-and-push-ecr.sh` + `buildspec.yml`
- **EKS**: [`docs/praticas/12-eks-deploy.md`](docs/praticas/12-eks-deploy.md) + manifests em `infra/k8s/aws/`
- **Kubernetes Kind (Aula 6)**: [`docs/praticas/10-kubernetes-kind-local.md`](docs/praticas/10-kubernetes-kind-local.md) + manifests em `infra/k8s/`
- **S3 (Aula 5)**: [`docs/conceitos/s3-efs-datalake.md`](docs/conceitos/s3-efs-datalake.md)
- **Roteiro Aula 3+4 (semanas combinadas)**: [`docs/praticas/13-roteiro-aula-3-e-4.md`](docs/praticas/13-roteiro-aula-3-e-4.md)
- **Stack AWS por semana** (custos, Postgres container × RDS, ECS × EKS): [`docs/conceitos/infra-aws-minima-por-semana.md`](docs/conceitos/infra-aws-minima-por-semana.md)
- **Deploy manual AWS** (ECR, Fargate, EKS, RDS, Secrets Manager, CodeBuild): [`docs/praticas/09-deploy-manual-aws.md`](docs/praticas/09-deploy-manual-aws.md)
- Segurança: [`docs/conceitos/security-model.md`](docs/conceitos/security-model.md) · [`docs/conceitos/aws-networking.md`](docs/conceitos/aws-networking.md) · [`docs/conceitos/https-tls.md`](docs/conceitos/https-tls.md)
- Docker: [`docs/conceitos/docker-explained.md`](docs/conceitos/docker-explained.md)

## Licença

[GNU General Public License v3.0](LICENSE).
