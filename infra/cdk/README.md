# `infra/cdk/` — Infraestrutura como Código (AWS CDK) — Aula 11

Descreve parte da infra do CloudTask **como código Python versionado**, em vez
de criar na mão pelo Console/CLI. É o passo final da disciplina:
**console → CLI → script → IaC**.

> **Roteiro passo a passo (aluno):** [`../../docs/praticas/18-cdk-iac.md`](../../docs/praticas/18-cdk-iac.md).
> Este README é o índice + comandos rápidos.

---

## Arquivos

| Arquivo | O que faz |
| --- | --- |
| `app.py` | Ponto de entrada do CDK; instancia as 7 stacks. |
| `cdk.json` | Diz ao `cdk` como rodar o app (`python3 app.py`). |
| `requirements.txt` | `aws-cdk-lib` + `constructs`. |
| `stacks/storage_stack.py` | Bucket **S3** privado para uploads (seguro por padrão). |
| `stacks/ecr_stack.py` | Repositório **ECR** (scan + lifecycle 10 imgs). |
| `stacks/network_stack.py` | **VPC** 2 AZs (`nat_gateways=0` = sem custo de NAT). |
| `stacks/events_stack.py` | Tabela **DynamoDB** de eventos/logs (PAY_PER_REQUEST). |
| `stacks/observability_stack.py` | **CloudWatch** Log Group + Dashboard + Alarme + **SNS**. |
| `stacks/database_stack.py` | **RDS PostgreSQL** db.t3.micro + **Secrets Manager** (⚠️ cobra/lento). |
| `stacks/compute_stack.py` | **3 EC2** (API + Frontend + Grafana) — usa o `LabInstanceProfile` (zero IAM). |

---

## As 7 stacks (a infra das 6 semanas, como código)

Cada stack reproduz, em código, algo que construímos na mão ao longo do curso —
mostrando que **toda a jornada cabe em IaC**:

- **S3** (Semana 3) → bucket privado + criptografado + versionado.
- **ECR** (Semana 4) → repositório com scan e limpeza automática.
- **VPC** (Semana 4) → topologia pública/privada (`nat_gateways=0` = sem custo).
- **DynamoDB** (Semana 5) → tabela de eventos/logs (NoSQL).
- **CloudWatch + SNS** (Semana 5) → Log Group + **Dashboard** + Alarme + canal de alerta.
- **RDS PostgreSQL + Secrets Manager** (Semana 6) → banco gerenciado com senha
  gerada no cofre. ⚠️ É o único que **cobra por hora** e leva ~5–10 min.
- **Compute: 3 EC2** (Semana 6) → API + Frontend + Grafana, cada um num servidor
  (ver [`../servers/README.md`](../servers/README.md) e a
  [prática 19](../../docs/praticas/19-servidores-ec2-grafana.md)). Usa o
  `LabInstanceProfile` existente, então **não cria IAM**; o HTML do front e o
  dashboard do Grafana vão **embutidos** no template (sem assets).

> Todas **sem assets** (sem Lambda), para subir no Academy sem `cdk bootstrap`.

---

## Comandos rápidos (dentro de `infra/cdk/`)

```bash
# 1. dependências (no devcontainer/CloudShell já tem Python)
pip install -r requirements.txt

# 2. VER o CloudFormation gerado — NÃO cria nada
cdk synth
```

### 🟢 AWS Academy (Learner Lab) — sobe SEM `cdk bootstrap`  ✅ testado

```bash
./cdk-academy.sh deploy     # synth + cloudformation deploy usando a LabRole
./cdk-academy.sh destroy    # 🔥 apaga todas as stacks
```

POR QUÊ funciona: o `cdk bootstrap`/`cdk deploy` falham no Learner Lab (criar as
IAM roles do CDKToolkit é negado). O script contorna: o CDK só **gera** o
template e o **CloudFormation implanta** com a **LabRole** (que confia em
`cloudformation.amazonaws.com`). As stacks são **sem assets**, então o template
vai inline — nada de bootstrap.

### 🔵 Conta própria — `cdk deploy` clássico

```bash
cdk bootstrap         # uma vez por conta/região
cdk deploy --all      # cria S3 + ECR + VPC
cdk diff              # o que mudaria
cdk destroy --all     # 🔥 apaga tudo
```

> ⚠️ **Custo:** S3/ECR são centavos. A `NetworkStack` vem com `nat_gateways=0`
> (sem NAT) para não cobrar. Sempre **destrua depois**.

> ℹ️ As stacks são **sem assets** de propósito (sem Lambda de auto-limpeza), para
> rodar no Academy. Logo, **esvazie o bucket/ECR** antes do destroy se tiver
> conteúdo (`aws s3 rm s3://<bucket> --recursive`).
