# Prática 09 — Deploy manual na AWS (ECR → Fargate / EKS, RDS, Secrets)

> **Objetivo:** subir a aplicação CloudTask na AWS **manualmente** (sem
> Terraform/CDK), usando AWS CLI e Console. Cobre o caminho **mais simples**
> (ECS Fargate) e o **caminho oficial do curso** (EKS), além de:
> - linkar o código do GitHub ao build na AWS,
> - configurar `.env` em **Secrets Manager**,
> - subir o banco em **container** OU em **RDS**, comparando custo e
>   complexidade.
>
> **Conceito de base obrigatório:** [`../conceitos/infra-aws-minima-por-semana.md`](../conceitos/infra-aws-minima-por-semana.md).
>
> **Pré-req:** [`00-setup-inicial-e-aws-academy.md`](00-setup-inicial-e-aws-academy.md)
> concluído (AWS CLI funcionando, Learner Lab ativo, `kubectl`, `eksctl`).

---

## Mapa do que **cada semana** faz aqui

| Etapa | Quando | Seção |
| --- | :---: | --- |
| **A.** Criar bucket S3 (sanity check) | Semana 3 | [§1](#1-semana-3--bucket-s3-sanity-check) |
| **B.** Linkar repo GitHub → AWS (CodeBuild) | Semana 4 | [§2](#2-semana-4--linkar-github-na-aws-via-codebuild) |
| **C.** Push da imagem para ECR | Semana 4 | [§3](#3-semana-4--push-da-imagem-para-ecr) |
| **D.** Subir API em **ECS Fargate** (atalho simples) | Semana 4 (opcional) | [§4](#4-semana-4-opcional--ecs-fargate-deploy-simples) |
| **E.** Provisionar **EKS** com `eksctl` | Semana 5 | [§5](#5-semana-5--provisionar-eks-com-eksctl) |
| **F.** Subir API no EKS com Postgres em **container** | Semana 5 | [§6](#6-semana-5--subir-api-no-eks-com-postgres-em-container) |
| **G.** Trocar Postgres por **RDS** | Semana 6/8 | [§7](#7-semana-68--trocar-postgres-por-rds) |
| **H.** Configurar `.env` via **Secrets Manager** | Semana 6 | [§8](#8-semana-6--secrets-manager-para-env) |
| **I.** HPA + load test | Semana 6 | [§9](#9-semana-6--hpa--load-test) |
| **J.** Eventos em **DynamoDB** | Semana 6 | [§10](#10-semana-6--dynamodb-para-eventos) |
| **K.** **Cleanup obrigatório** ao fim de toda aula | Sempre | [§11](#11-sempre--cleanup-obrigatorio) |

> ⚠️ **Numeração de semana** segue [`ROADMAP.md`](../ROADMAP.md). A demo final
> em ALB + ACM + Route 53 + EKS roda na **conta pessoal do professor** (não
> no Learner Lab) — não está nesta prática (vira material do professor).

---

## 0. Antes de cada sessão

```bash
# 1. abrir Learner Lab no AWS Academy → Start Lab → AWS Details → AWS CLI
# 2. copiar o bloco e colar em ~/.aws/credentials no HOST (não no container)
# 3. validar dentro do devcontainer
aws sts get-caller-identity
# saída deve ter "Account" e "Arn"

# 4. region default
aws configure set region us-east-1
```

> ⚠️ Credenciais do Learner Lab expiram em ~4 h. Quando acabar, recole.

---

## 1. Semana 3 — Bucket S3 (sanity check)

> **Quando:** Aula 5. **Já coberto** na prática [`06-uploads-modo-s3.md`](06-uploads-modo-s3.md).
> Aqui só lembramos o resumo.

```bash
export BUCKET=cloudtask-uploads-$(whoami)-$(date +%s)
aws s3 mb s3://$BUCKET --region us-east-1
echo "Bucket: $BUCKET"
```

Aponta no `.env`:

```env
STORAGE_MODE=s3
AWS_REGION=us-east-1
S3_BUCKET_NAME=cloudtask-uploads-...
```

**Cleanup:** `aws s3 rb s3://$BUCKET --force`.

---

## 2. Semana 4 — Linkar GitHub na AWS (via CodeBuild)

> **Quando:** **Aula 7**. **Opcional** — também pode buildar localmente e dar
> `docker push`. Mas conectar o GitHub ensina **pipeline real**.

### Por que CodeBuild e não Actions/Jenkins?

CodeBuild é **serverless** (paga só por minuto rodando), nativo da AWS e
integra com ECR/EKS sem extra. Para esta disciplina, é o caminho mais
didático para **ver o pipeline acontecer dentro da AWS**.

> Limite Learner Lab: CodeBuild **funciona**, mas não consegue criar
> webhooks privados (não tem permissão `iam:PassRole` ampla). Vamos buildar
> **on-demand** (acionado manualmente).

### Passos

#### 2.1. Criar token GitHub (PAT)

1. GitHub → Settings → Developer Settings → Personal Access Tokens → Tokens (classic).
2. Permissões mínimas: `repo` (público) ou `repo` + `read:org` (privado).
3. Copie o token (`ghp_...`).

#### 2.2. Conectar no CodeBuild via CLI

```bash
aws codebuild import-source-credentials \
  --server-type GITHUB \
  --auth-type PERSONAL_ACCESS_TOKEN \
  --token "ghp_SEU_TOKEN_AQUI"
```

#### 2.3. Criar `buildspec.yml` na raiz do repo

```yaml
# buildspec.yml — usado pelo CodeBuild
version: 0.2
phases:
  pre_build:
    commands:
      - echo "Login no ECR..."
      - aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REPO_URI
      - IMAGE_TAG=v$(date +%Y%m%d-%H%M%S)
  build:
    commands:
      - echo "Build da imagem (target prod)..."
      - docker build --target prod -t cloudtask-api:$IMAGE_TAG .
      - docker tag cloudtask-api:$IMAGE_TAG $ECR_REPO_URI:$IMAGE_TAG
      - docker tag cloudtask-api:$IMAGE_TAG $ECR_REPO_URI:latest
  post_build:
    commands:
      - echo "Push para ECR..."
      - docker push $ECR_REPO_URI:$IMAGE_TAG
      - docker push $ECR_REPO_URI:latest
```

Commitar e empurrar.

#### 2.4. Criar o projeto CodeBuild

Via Console (Learner Lab não autoriza tudo via CLI):

1. Console → CodeBuild → Create build project.
2. **Source:** GitHub → seu repo → branch `semana-04-eks-aws`.
3. **Environment:**
   - Managed image, Ubuntu, Standard 7.0.
   - Privileged: **ON** (necessário para `docker build`).
   - Service role: **LabRole** (única disponível).
4. **Buildspec:** Use a buildspec file → `buildspec.yml`.
5. **Env vars:**
   - `AWS_REGION` = `us-east-1`
   - `ECR_REPO_URI` = (preencher depois de criar repo na §3)
6. Create build project → Start build (manual).

**Resultado:** CodeBuild puxa o código do GitHub, faz `docker build`, e dá
push pro ECR.

---

## 3. Semana 4 — Push da imagem para ECR

> **Quando:** Aula 7. **Caminho rápido** (sem CodeBuild) — build local +
> push direto.

```bash
# 1. criar repo
aws ecr create-repository \
  --repository-name cloudtask-api \
  --region us-east-1

# 2. capturar URI
export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export ECR=$ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/cloudtask-api
echo "ECR URI: $ECR"

# 3. login no ECR
aws ecr get-login-password --region us-east-1 \
  | docker login --username AWS --password-stdin $ECR

# 4. build prod
docker build --target prod -t cloudtask-api:v0.4.0 .

# 5. tag + push
docker tag cloudtask-api:v0.4.0 $ECR:v0.4.0
docker tag cloudtask-api:v0.4.0 $ECR:latest
docker push $ECR:v0.4.0
docker push $ECR:latest

# 6. listar
aws ecr list-images --repository-name cloudtask-api
```

> 💡 `target prod` garante imagem **sem dev tools** (menor superfície de
> ataque + imagem menor).

**Cleanup do ECR:** seção [§11](#11-sempre--cleanup-obrigatorio).

---

## 4. Semana 4 (opcional) — ECS Fargate (deploy simples)

> **Quando:** Aula 7, **antes** de partir para EKS. Serve como
> **comparação**: "olha como Fargate é simples; agora veja o poder do EKS".
> Quem preferir ECS para o restante do curso pode — mas o curso oficial é
> EKS.

### Por que Fargate primeiro?

- Sem cluster pra gerenciar.
- Sem nó EC2.
- Cobra só pelo tempo do container ligado.
- Suba em ~5 min.

### Passos (via Console — Learner Lab limita CLI)

1. Console → ECS → Clusters → Create cluster.
   - Cluster name: `cloudtask-fargate`.
   - Infrastructure: **AWS Fargate (serverless)**.
2. Task definitions → Create new.
   - Family: `cloudtask-api`.
   - Launch type: Fargate.
   - OS: Linux x86_64.
   - CPU: 0.25 vCPU, Memory: 0.5 GB.
   - Task role: **LabRole**, Task execution role: **LabRole**.
   - Container:
     - Name: `api`.
     - Image URI: `<ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/cloudtask-api:latest`.
     - Port mapping: 8000 TCP.
     - Env vars: cole `DATABASE_URL`, `SECRET_KEY`, etc.
3. Services → Create.
   - Cluster: `cloudtask-fargate`.
   - Task definition: `cloudtask-api:1`.
   - Desired tasks: 1.
   - Networking: VPC default, subnets públicas, Security Group permitindo 8000.
   - Public IP: ENABLED (para testar sem LB).
4. Aguardar `RUNNING` → pegar Public IP da task → `curl http://<IP>:8000/health`.

> ⚠️ **`Public IP: ENABLED` é didático**, NÃO usar em produção real. Em
> produção: Fargate atrás de ALB.

**Cleanup Fargate:**

```bash
aws ecs update-service --cluster cloudtask-fargate \
  --service cloudtask-api --desired-count 0
aws ecs delete-service --cluster cloudtask-fargate \
  --service cloudtask-api --force
aws ecs delete-cluster --cluster cloudtask-fargate
```

---

## 5. Semana 5 — Provisionar EKS com `eksctl`

> **Quando:** Aula 8.

```bash
# 1. criar cluster (demora ~15 min)
eksctl create cluster \
  --name cloudtask-eks \
  --region us-east-1 \
  --version 1.30 \
  --nodegroup-name std-nodes \
  --node-type t3.small \
  --nodes 2 \
  --nodes-min 1 \
  --nodes-max 3 \
  --managed

# 2. confirmar
kubectl get nodes
# 2 nós em Ready
```

> ⚠️ **CUSTO:** cluster cobra $0,10/h + 2 nós t3.small ($0,04/h). Total
> ~$0,14/h. Em 4 h de aula = $0,56. **Sempre destruir no fim.**

> 💡 **Sem permissão para criar cluster?** Learner Lab tem limites; se
> `eksctl` falhar com `iam:CreateRole`, use o **template já criado pelo
> professor** ou contate-o.

**Acesso:**

```bash
# kubeconfig já fica configurado pelo eksctl
kubectl cluster-info
kubectl get nodes -o wide
```

---

## 6. Semana 5 — Subir API no EKS com Postgres em container

> Caminho **mais barato e didático**. Postgres roda como Pod, dados **somem
> ao reiniciar** (sem PVC). Para persistência mínima, adicione PVC. Para
> produção, vá direto pra §7 (RDS).

### 6.1. Estrutura dos manifests

```text
infra/k8s/aws/
├── namespace.yaml
├── postgres-deployment.yaml      # NOVO — Pod do banco
├── postgres-service.yaml         # ClusterIP (DNS interno)
├── secret-app.yaml               # SECRET_KEY, DB password
├── configmap-app.yaml            # DATABASE_URL etc.
├── api-deployment.yaml           # Pod da API + image do ECR
├── api-service.yaml              # type=LoadBalancer (ELB)
└── README.md
```

### 6.2. Aplicar

```bash
# 1. namespace
kubectl create namespace cloudtask

# 2. secret (DB password)
kubectl create secret generic cloudtask-secrets \
  --namespace cloudtask \
  --from-literal=POSTGRES_PASSWORD=$(openssl rand -hex 16) \
  --from-literal=SECRET_KEY=$(openssl rand -hex 32)

# 3. configmap (config não-sensível)
kubectl create configmap cloudtask-config \
  --namespace cloudtask \
  --from-literal=APP_ENV=production \
  --from-literal=AWS_REGION=us-east-1

# 4. aplicar manifests
kubectl apply -f infra/k8s/aws/

# 5. acompanhar
kubectl get pods -n cloudtask -w
```

### 6.3. Pegar URL do LoadBalancer

```bash
kubectl get svc -n cloudtask api-service
# EXTERNAL-IP → endereço do ELB (demora 1–3 min para aparecer)

# testar
curl http://$ELB_DNS:8000/health
```

---

## 7. Semana 6/8 — Trocar Postgres por RDS

> **Quando:**
> - **Semana 6** se a aula focar em produção / persistência;
> - **Semana 8** (final, conta pessoal) com Multi-AZ.

### Por que mudar?

| Razão | Pod | RDS |
| --- | --- | --- |
| Persiste após restart | só com PVC | ✅ |
| Backup automático | manual | ✅ até 35 dias |
| Multi-AZ HA | não | ✅ opcional |
| Custo (4 h) | ~$0 | ~$0,15 |

### Passos

#### 7.1. Criar RDS via CLI

```bash
# Security Group permitindo 5432 só do EKS
export VPC_ID=$(aws eks describe-cluster --name cloudtask-eks \
  --query "cluster.resourcesVpcConfig.vpcId" --output text)

aws ec2 create-security-group \
  --group-name rds-sg \
  --description "RDS access from EKS" \
  --vpc-id $VPC_ID
export RDS_SG=$(aws ec2 describe-security-groups \
  --filters "Name=group-name,Values=rds-sg" \
  --query "SecurityGroups[0].GroupId" --output text)

# Liberar 5432 do CIDR do EKS
aws ec2 authorize-security-group-ingress \
  --group-id $RDS_SG \
  --protocol tcp --port 5432 \
  --cidr 10.0.0.0/8     # ajuste conforme VPC do EKS

# Criar instância RDS
aws rds create-db-instance \
  --db-instance-identifier cloudtask-db \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --engine-version 16.3 \
  --master-username cloudtask \
  --master-user-password "$(openssl rand -hex 16)" \
  --allocated-storage 20 \
  --vpc-security-group-ids $RDS_SG \
  --db-name cloudtask \
  --no-publicly-accessible

# aguardar (~8 min)
aws rds wait db-instance-available --db-instance-identifier cloudtask-db
```

#### 7.2. Capturar endpoint

```bash
export RDS_HOST=$(aws rds describe-db-instances \
  --db-instance-identifier cloudtask-db \
  --query "DBInstances[0].Endpoint.Address" --output text)
echo "RDS: $RDS_HOST"
```

#### 7.3. Atualizar Secret e ConfigMap no EKS

```bash
kubectl create secret generic cloudtask-secrets \
  --namespace cloudtask \
  --from-literal=DATABASE_URL=postgresql://cloudtask:SUA_SENHA@$RDS_HOST:5432/cloudtask \
  --dry-run=client -o yaml | kubectl apply -f -

# remover o Pod do Postgres (não precisa mais)
kubectl delete -f infra/k8s/aws/postgres-deployment.yaml
kubectl delete -f infra/k8s/aws/postgres-service.yaml

# reiniciar a API para pegar a nova DATABASE_URL
kubectl rollout restart deployment/api -n cloudtask
```

#### 7.4. Testar

```bash
curl http://$ELB_DNS:8000/health/ready
# {"database":"ok"} → conectou no RDS
```

---

## 8. Semana 6 — Secrets Manager para `.env`

> **Quando:** Aula 9. Substitui o `kubectl create secret` por algo gerenciado
> e auditável.

### 8.1. Criar segredo

```bash
aws secretsmanager create-secret \
  --name cloudtask/prod \
  --description "Credenciais e config CloudTask" \
  --secret-string '{
    "DATABASE_URL":"postgresql://cloudtask:SENHA@HOST:5432/cloudtask",
    "SECRET_KEY":"...",
    "AWS_REGION":"us-east-1",
    "S3_BUCKET_NAME":"cloudtask-uploads-..."
  }'
```

### 8.2. Consumir no EKS — duas formas

**A) External Secrets Operator (recomendado):**

```bash
# instalar
helm repo add external-secrets https://charts.external-secrets.io
helm install external-secrets external-secrets/external-secrets \
  --namespace external-secrets-system --create-namespace
```

E aplicar um `ExternalSecret` apontando para `cloudtask/prod` (manifest em
`infra/k8s/aws/external-secret.yaml`).

**B) Init container que injeta o segredo (mais simples):**

```yaml
# trecho do api-deployment.yaml
initContainers:
  - name: fetch-secrets
    image: amazon/aws-cli:latest
    command:
      - sh
      - -c
      - |
        aws secretsmanager get-secret-value \
          --secret-id cloudtask/prod \
          --query SecretString --output text > /env/.env
    volumeMounts:
      - name: env-vol
        mountPath: /env
```

> ⚠️ Em ambos os casos, o **pod precisa de IAM role** com permissão
> `secretsmanager:GetSecretValue`. No Learner Lab usa `LabRole`; em produção
> use **IRSA** (IAM Roles for Service Accounts).

### 8.3. Cleanup

```bash
aws secretsmanager delete-secret \
  --secret-id cloudtask/prod \
  --force-delete-without-recovery
```

---

## 9. Semana 6 — HPA + load test

```bash
# 1. instalar metrics-server (necessário para HPA)
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# 2. aplicar HPA
kubectl apply -f infra/k8s/hpa.yaml

# 3. ver status
kubectl get hpa -n cloudtask

# 4. teste de carga simples
python scripts/load-test-simple.py http://$ELB_DNS:8000

# 5. ver pods escalando
kubectl get pods -n cloudtask -w
```

> A escala é demonstrada — não deixe rodando para sempre, dispara custo.

---

## 10. Semana 6 — DynamoDB para eventos

```bash
# 1. criar tabela (PAY_PER_REQUEST = só paga por uso)
aws dynamodb create-table \
  --table-name cloudtask-events \
  --attribute-definitions \
    AttributeName=id,AttributeType=S \
  --key-schema AttributeName=id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST

# 2. esperar ativa
aws dynamodb wait table-exists --table-name cloudtask-events

# 3. configurar no Secrets Manager (ou ConfigMap)
# EVENT_STORE_MODE=dynamodb
# DYNAMODB_TABLE_NAME=cloudtask-events

# 4. testar POST /events
curl -X POST http://$ELB_DNS:8000/events \
  -H "Content-Type: application/json" \
  -d '{"event_type":"task.created","task_id":1,"message":"teste"}'

# 5. ver na tabela
aws dynamodb scan --table-name cloudtask-events --max-items 5
```

**Cleanup:**

```bash
aws dynamodb delete-table --table-name cloudtask-events
```

---

## 11. SEMPRE — cleanup obrigatório

> ⚠️ **NÃO PULE**. Cluster EKS sozinho gasta crédito 24/7 ($0,10/h).

```bash
# 1. derrubar Services LoadBalancer (libera ELBs)
kubectl delete svc --all -n cloudtask

# 2. derrubar pods
kubectl delete namespace cloudtask

# 3. destruir cluster EKS
eksctl delete cluster --name cloudtask-eks --region us-east-1
# (~10 min)

# 4. apagar RDS (se subiu)
aws rds delete-db-instance \
  --db-instance-identifier cloudtask-db \
  --skip-final-snapshot

# 5. apagar bucket S3
aws s3 rb s3://$BUCKET --force

# 6. apagar repo ECR
aws ecr delete-repository --repository-name cloudtask-api --force

# 7. apagar secret
aws secretsmanager delete-secret \
  --secret-id cloudtask/prod \
  --force-delete-without-recovery

# 8. apagar tabela DynamoDB
aws dynamodb delete-table --table-name cloudtask-events

# 9. ECS Fargate (se subiu)
aws ecs delete-cluster --cluster cloudtask-fargate

# 10. confirmar
aws ec2 describe-instances --filters "Name=instance-state-name,Values=running"
aws elbv2 describe-load-balancers
aws rds describe-db-instances
# tudo deve estar vazio
```

**Validação final via Cost Explorer:** abra o Cost Explorer 24 h depois — se
houver gasto, alguma coisa escapou.

---

## 12. Tabela de complexidade × momento

| O que | Complexidade | Quando tentar |
| --- | :---: | :---: |
| Criar bucket S3 | ⭐ | Aula 5 |
| Login + push ECR | ⭐⭐ | Aula 7 |
| ECS Fargate Console | ⭐⭐ | Aula 7 (opcional) |
| CodeBuild + GitHub | ⭐⭐⭐ | Aula 7 |
| EKS + manifests | ⭐⭐⭐⭐ | Aula 8 |
| Postgres como Pod | ⭐⭐ | Aula 8 |
| Postgres RDS + SG | ⭐⭐⭐⭐ | Aula 9 ou final |
| Secrets Manager + IRSA | ⭐⭐⭐⭐⭐ | Aula 9 |
| HPA + load test | ⭐⭐⭐ | Aula 9 |
| DynamoDB + POST /events | ⭐⭐ | Aula 10 |
| Cleanup completo | ⭐⭐ | Toda aula |
| ALB + ACM + Route 53 | ⭐⭐⭐⭐⭐ | só Aula 12 (conta pessoal) |

---

## Próximos passos

| Quero... | Vá em |
| --- | --- |
| Entender o que mora na AWS | [`../conceitos/infra-aws-minima-por-semana.md`](../conceitos/infra-aws-minima-por-semana.md) |
| Modelo de segurança | [`../conceitos/security-model.md`](../conceitos/security-model.md) |
| VPC / SG | [`../conceitos/aws-networking.md`](../conceitos/aws-networking.md) |
| HTTPS / ACM | [`../conceitos/https-tls.md`](../conceitos/https-tls.md) |
| Resolver erros AWS | [`99-troubleshooting.md`](99-troubleshooting.md) (seção AWS) |
