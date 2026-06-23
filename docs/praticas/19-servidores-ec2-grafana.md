# Prática 19 — Três servidores (API + Frontend + Grafana) na AWS (Aula 12)

> **Objetivo:** subir a aplicação completa como ela seria em produção: a **API**
> num servidor, o **frontend** (site) em outro e o **Grafana** (observabilidade)
> em um terceiro — cada um num EC2 separado. No fim você abre um **link externo
> real** no navegador, faz login e usa o app.
>
> **Quando:** Semana 6 / Aula 12.
>
> **Pré-req:** AWS Academy (Learner Lab) iniciado e credenciais no terminal
> (ver [`00-setup-inicial-e-aws-academy.md`](00-setup-inicial-e-aws-academy.md)).
> Conceitos por trás: [`../conceitos/aws-compute.md`](../conceitos/aws-compute.md),
> a IaC da [prática 18](18-cdk-iac.md) e os eventos/observabilidade da
> [prática 15](15-eventos-dynamodb.md).
>
> ⚠️ **Custo:** três EC2 pequenos (2× `t3.small` + 1× `t3.micro`) custam centavos
> por hora e **não usam NAT**. Se você também subir o RDS (caminho CDK), aí sim
> cobra mais — **destrua tudo ao terminar** (passo 6).

---

## 1. O desenho (por que três servidores)

Até agora a API, o banco e os anexos rodavam juntos (no devcontainer ou num
container só). Em produção a gente **separa responsabilidades** — cada peça
escala e falha de forma independente:

```text
   navegador  ─►  Frontend EC2 (nginx)  ──chama──►  API EC2 (FastAPI + banco)
   (você)          :80  serve o SPA                  :8000  /docs, /tasks, ...
                                                         │
   navegador  ─►  Grafana EC2  ──lê métricas──►  CloudWatch (da conta)
   (você)          :3000                          (CPU, rede, DynamoDB, RDS)
```

* **Frontend** — um `nginx` servindo o `frontend/index.html` (tela de login +
  kanban de tarefas + anexos). No boot ele recebe a **URL pública da API**.
* **API** — a mesma imagem Docker das aulas anteriores, agora com **login por
  token (JWT)**. Usuário `admin`, senha `admin#123`.
* **Grafana** — sobe já **provisionado**: um datasource **CloudWatch** (sem
  chave fixa — usa a *role* do próprio EC2) e um dashboard com gráficos úteis.

---

## 2. Segurança (o que mudou na API)

A API agora **exige token** nas rotas de dados. O fluxo:

1. `POST /auth/login` com `{"username":"admin","password":"admin#123"}` → devolve
   um `access_token`.
2. As chamadas a `/tasks`, `/uploads`, `/events` precisam do cabeçalho
   `Authorization: Bearer <token>` — sem ele, **401**.

A mesma senha `admin#123` é usada de propósito em tudo (banco, app, Grafana)
**só porque é uma demo**. Em produção: senhas diferentes, fortes e fora do
código (Secrets Manager, como o RDS já faz).

---

## 3. Caminho A — script CLI (rápido)

O jeito mais direto de ver tudo no ar. Na raiz do repositório:

```bash
bash infra/servers/launch-academy.sh
```

O script: acha a AMI Amazon Linux 2023 mais nova, cria um **security group**
(portas 22/80/3000/8000), e sobe os três EC2 — injetando a URL da API no
frontend. No fim ele imprime algo assim:

```text
  Frontend (abra este):  http://SEU_IP_FRONT/
  API (Swagger):         http://SEU_IP_API:8000/docs
  Grafana:               http://SEU_IP_GRAF:3000/   (admin / admin#123)
```

Espere **~3–5 min** (a API faz `docker build` no primeiro boot) e abra o link do
frontend. Login: `admin` / `admin#123`.

> Os servidores usam o **`LabInstanceProfile`** (a *role* do laboratório, já
> pronta) — por isso o Grafana lê o CloudWatch sem você configurar credencial.

---

## 4. Caminho B — IaC com CDK (a 7ª stack)

O mesmo resultado, agora **versionado**: a `ComputeStack` descreve os três EC2.
Ela reutiliza os **mesmos** scripts de `infra/servers/` como `user-data`, então
não há divergência entre o caminho A e o B.

```bash
cd infra/cdk
cat cdk.out/CloudTaskCompute.template.json   # (depois do synth) só p/ espiar
./cdk-academy.sh deploy                       # sobe TODAS as stacks, em ordem
```

Diferença importante do caminho B: como a `DatabaseStack` (RDS) sobe antes, a
API se conecta ao **RDS gerenciado** (lendo a senha do **Secrets Manager**), em
vez de um Postgres em container. É a versão "produção".

> Por que isso funciona no Academy sem `cdk bootstrap`: a stack **não cria IAM**
> (usa o `LabInstanceProfile` existente) e **não tem assets** (o HTML do
> frontend e o dashboard do Grafana vão embutidos em base64 no template). Mesmo
> truque da [prática 18](18-cdk-iac.md).

---

## 5. O que olhar no Grafana

Abra `http://SEU_IP_GRAF:3000/` (admin / admin#123) → dashboard
**“CloudTask — Infra (Academy)”**. Use o seletor **EC2 Instance** no topo para
filtrar. Painéis:

* **CPU dos EC2 (%)** e **Rede de saída** — saúde das três máquinas.
* **DynamoDB — capacidade consumida** — aparece quando a API grava eventos.
* **RDS — conexões ativas** — aparece se você subiu o RDS (caminho B).

As métricas levam alguns minutos para popular (o CloudWatch agrega de 1 em 1
min).

---

## 6. Limpeza (faça SEMPRE) 🔥

```bash
# Caminho A (script):
bash infra/servers/destroy-academy.sh

# Caminho B (CDK):
cd infra/cdk && ./cdk-academy.sh destroy
```

Confira no Console (EC2 → Instances; RDS → Databases) que **nada** ficou
`running`/`available`. O RDS é o que mais cobra — não deixe ligado.

---

## 7. Resumo

| Peça | Servidor | Porta | Login |
| --- | --- | --- | --- |
| Frontend (SPA) | `t3.micro` nginx | 80 | `admin` / `admin#123` |
| API (FastAPI) | `t3.small` Docker | 8000 | token via `/auth/login` |
| Grafana | `t3.small` | 3000 | `admin` / `admin#123` |

Você subiu uma arquitetura de **produção de verdade** — frontend, backend com
autenticação e observabilidade — pelos **dois** caminhos (script e IaC),
terminando a jornada **console → CLI → script → IaC** da disciplina.
