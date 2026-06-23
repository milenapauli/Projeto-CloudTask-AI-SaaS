# Prática 18 — Infraestrutura como Código com AWS CDK (Aula 11)

> **Objetivo:** descrever recursos da AWS em **Python versionado** (o AWS CDK) em
> vez de criar na mão pelo Console ou por comandos avulsos. Você vai **gerar** o
> template, **ver** o que seria criado e (opcionalmente, em conta própria)
> **implantar** e **destruir** — tudo com um comando.
>
> **Quando:** Semana 6 / Aula 11.
>
> **Pré-req:** Python e Node disponíveis (o devcontainer já tem; o `cdk` é
> instalado no `post-create.sh`). Conceitos que viram código aqui:
> [`../conceitos/aws-networking.md`](../conceitos/aws-networking.md),
> [`../conceitos/s3-efs-datalake.md`](../conceitos/s3-efs-datalake.md).
>
> ⚠️ **Custo:** `cdk synth` é **grátis** (só gera arquivo). `cdk deploy` cria
> recursos de verdade — S3/ECR são centavos; a VPC vem **sem NAT** (sem custo).
> Sempre `cdk destroy` ao terminar.
>
> 🔎 **Quer entender por dentro** (como Python vira CloudFormation, o que é um
> *construct*, tokens, L1 vs L2)? Veja a
> [prática 20 — CDK Python por dentro](20-cdk-python-por-dentro.md).

---

## 1. Por que IaC (a evolução da disciplina)

Você já criou os mesmos recursos de **4 formas**, da mais trabalhosa à melhor:

| Forma | Onde vimos | Problema |
| --- | --- | --- |
| **Console (cliques)** | prática 16 | lento, não versionável, erra fácil |
| **CLI (`aws ...`)** | prática 09 | melhor, mas comando solto, sem revisão |
| **Script (`.sh`)** | prática 11 | reproduzível, mas imperativo (passo a passo) |
| **IaC (CDK)** | **aqui** | **declarativo, versionado, revisável, destruível junto** |

Com CDK você **descreve o estado desejado** ("quero um bucket privado") e a
ferramenta descobre como chegar lá. O código fica no git → entra em Pull
Request → roda igual em qualquer conta.

---

## 2. Conhecer o app (`infra/cdk/`)

```text
infra/cdk/
├── app.py                      ← ponto de entrada (instancia as stacks)
├── cdk.json                    ← diz ao cdk: "rode python3 app.py"
├── cdk-academy.sh              ← sobe/derruba no Academy (sem bootstrap)
├── requirements.txt            ← aws-cdk-lib + constructs
└── stacks/
    ├── storage_stack.py        ← bucket S3 privado (uploads)
    ├── ecr_stack.py            ← repositório ECR
    ├── network_stack.py        ← VPC 2 AZs (sem NAT)
    ├── events_stack.py         ← tabela DynamoDB (eventos/logs)
    ├── observability_stack.py  ← CloudWatch Log Group + Dashboard + Alarme + SNS
    └── database_stack.py       ← RDS PostgreSQL + Secrets Manager (⚠️ cobra/lento)
```

São **6 stacks** que recriam, como código, a infra das 6 semanas. Todas **sem
assets** (sem Lambda) — por isso sobem no Academy sem `cdk bootstrap`.

Leia os comentários de cada `stack` — explicam **por que** cada propriedade
existe (segurança, custo, limpeza).

---

## 3. Instalar as dependências (uma vez)

```bash
cd infra/cdk
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cdk --version          # confirma que o cdk está no PATH
```

> 🪟 **PowerShell:** ative o venv com `.venv\Scripts\Activate.ps1`.

---

## 4. `cdk synth` — ver o CloudFormation SEM criar nada

Este é o passo mais importante da aula (e o que funciona até no Learner Lab):

```bash
cdk synth
```

Saída: o **template CloudFormation** (YAML) que o CDK gerou a partir do seu
Python. Repare que poucas linhas de Python viram **dezenas** de linhas de
CloudFormation — o CDK escreve o "muito chato" por você.

```bash
# ver só uma stack:
cdk synth CloudTaskStorage
# listar as stacks do app:
cdk ls
```

✅ **Checkpoint 1:** `cdk synth` imprime um template e `cdk ls` lista
`CloudTaskStorage`, `CloudTaskEcr`, `CloudTaskNetwork`.

---

## 5. Implantar de verdade

> Há **dois caminhos**. No **AWS Academy** use o **5A** (funciona sem bootstrap).
> Em **conta própria** dá para usar o 5A também, ou o `cdk deploy` clássico (5B).

### 5A. 🟢 AWS Academy / Learner Lab — SEM `cdk bootstrap`

No Learner Lab o `cdk bootstrap`/`cdk deploy` **falham** (criar as IAM roles do
CDKToolkit é negado para a role `voclabs`). A solução, **testada e funcionando**:
o CDK só **gera** o template (`cdk synth`) e o **CloudFormation implanta** usando
a **LabRole** (que confia em `cloudformation.amazonaws.com`). Como nossas stacks
**não têm assets** (sem Lambda), o template vai inline — nada de bootstrap.

Tem um script que faz tudo:

```bash
cd infra/cdk
pip install -r requirements.txt        # uma vez
./cdk-academy.sh deploy                 # synth + cloudformation deploy (LabRole)
# ... use os recursos ...
./cdk-academy.sh destroy                # 🔥 apaga as 3 stacks
```

Ou, **manualmente** (o que o script faz por dentro):

```bash
cdk synth                               # gera cdk.out/*.template.json
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
for s in CloudTaskStorage CloudTaskEcr CloudTaskNetwork; do
  aws cloudformation deploy \
    --template-file cdk.out/$s.template.json \
    --stack-name $s \
    --role-arn arn:aws:iam::$ACCOUNT:role/LabRole \
    --capabilities CAPABILITY_IAM --region us-east-1
done
```

### 5B. 🔵 Conta própria — `cdk deploy` clássico

```bash
cdk bootstrap                 # uma vez por conta/região
cdk deploy --all              # cria S3 + ECR + VPC (sem NAT = sem custo)
```
> O `cdk-academy.sh` também funciona em conta própria (ele só usa a LabRole se
> ela existir).

### 5.3. Conferir

- Console → CloudFormation → as stacks `CloudTask*` criadas.
- Console → S3 / ECR / VPC → os recursos lá.
- Os **Outputs** trazem o nome do bucket e a URI do ECR (cole no `.env` da app).

✅ **Checkpoint 2:** as stacks aparecem no CloudFormation e os recursos no S3/ECR/VPC.

---

## 6. `cdk diff` — o que mudaria

Edite algo (ex.: em `ecr_stack.py` troque `max_image_count=10` para `5`) e:

```bash
cdk diff
```
Mostra exatamente o que seria alterado **antes** de aplicar. É a revisão que o
Console não te dá.

---

## 7. 🔥 Destruir (obrigatório)

```bash
# Academy (ou conta própria) — via script:
./cdk-academy.sh destroy

# OU, em conta própria com bootstrap:
cdk destroy --all
```

Tudo tem `removal_policy=DESTROY`, então as stacks somem sem órfão cobrando.

> ⚠️ As stacks são **sem assets** (não usam Lambda de auto-limpeza, para
> funcionar no Academy). Por isso o **bucket S3 precisa estar VAZIO** para ser
> deletado. Na demo ele costuma estar; se você subiu arquivos, esvazie antes:
> `aws s3 rm s3://<bucket> --recursive`. Idem ECR se tiver imagens.

✅ **Checkpoint 3:** o destroy remove as stacks; CloudFormation fica sem as
`CloudTask*`.

---

## Se algo der errado

| Sintoma | Causa provável | Fix |
| --- | --- | --- |
| `cdk: command not found` | cdk não instalado | `sudo npm install -g aws-cdk` (ou rode `post-create.sh`) |
| `This stack uses assets... run cdk bootstrap` | conta sem bootstrap | `cdk bootstrap` (conta própria) |
| `AccessDenied`/`not authorized` no bootstrap/deploy | Learner Lab bloqueia | use só `cdk synth` (Academy) |
| `BucketAlreadyExists` | nome de bucket fixo colidiu | não fixamos nome — se editou, remova `bucket_name` |
| `ExpiredToken` | credenciais venceram | renove (Learner Lab) / `aws sso login` |

---

## Próximos passos

| Quero... | Vá em |
| --- | --- |
| Comparar IaC com fazer na mão | [`16-console-vs-script.md`](16-console-vs-script.md) |
| Entender a rede que virou código | [`../conceitos/aws-networking.md`](../conceitos/aws-networking.md) |
| Fechar a disciplina (entrega final) | `docs/entrega-final/` (Aula 12) |
