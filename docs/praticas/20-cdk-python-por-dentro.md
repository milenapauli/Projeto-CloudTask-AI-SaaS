# Prática 20 — Como o AWS CDK em Python funciona (por dentro) (Aula 11/12)

> **Objetivo:** entender **como** o CDK transforma o seu código Python em
> infraestrutura — não só rodar os comandos, mas saber o que cada arquivo do
> projeto faz, como um *construct* vira um recurso e por que essa abordagem
> **escala melhor quanto mais complexa fica a infra**.
>
> **Quando:** Semana 6 / Aulas 11–12. Faça depois da [prática 18](18-cdk-iac.md)
> (que sobe as stacks) e da [prática 19](19-servidores-ec2-grafana.md) (os 3
> servidores).
>
> **Pré-req:** ter o `infra/cdk/` aberto no editor. Tudo aqui é **leitura +
> `cdk synth`** (não cria nada na AWS, é grátis).

---

## 1. A ideia central: Python **gera** CloudFormation

O CDK **não cria recursos diretamente**. Ele faz uma coisa só:

```text
   seu código Python   ──►   cdk synth   ──►   CloudFormation (JSON)   ──►   AWS
   (infra/cdk/*.py)          (gera arquivo)     (cdk.out/*.template.json)     (cria recursos)
```

* Você **descreve** o estado desejado em Python ("quero um bucket privado").
* `cdk synth` **sintetiza**: percorre seu código e cospe um **template
  CloudFormation** em `cdk.out/`.
* Quem **cria** os recursos é o CloudFormation (no nosso fluxo Academy, via
  `aws cloudformation deploy` — ver prática 18).

> 💡 Por isso `cdk synth` é seguro e offline: é só **geração de arquivo**. Abra
> um `cdk.out/CloudTaskStorage.template.json` depois e veja: é o mesmo JSON que
> você escreveria na mão — só que o Python escreveu por você, sem erro de
> vírgula.

---

## 2. Anatomia de um *construct* (o tijolo do CDK)

Todo recurso no CDK é um **construct**, e todo construct é criado com a **mesma
assinatura de 3 partes**:

```python
s3.Bucket(self, "UploadsBucket", versioned=True)
#         ^^^^  ^^^^^^^^^^^^^^^^  ^^^^^^^^^^^^^^^
#         (1)   (2)              (3)
```

1. **scope** (`self`) — *onde* na árvore esse construct vive. `self` = "dentro
   desta Stack". É assim que o CDK monta a hierarquia.
2. **id** (`"UploadsBucket"`) — um nome **único dentro do scope**. O CDK usa
   esse id para gerar o *Logical ID* do recurso no CloudFormation. (Não é o nome
   do bucket na AWS — é o "apelido" dentro do template.)
3. **props** (`versioned=True`, ...) — a configuração do recurso.

Esses tijolos vêm em **três níveis** (você vê os três no projeto):

| Nível | Como reconhecer | Exemplo no projeto |
| --- | --- | --- |
| **L1** (`Cfn*`) | classe começa com `Cfn`; espelha 1:1 o CloudFormation | `ec2.CfnInstance` (em `compute_stack.py`) |
| **L2** | API "amigável", com defaults sensatos e helpers | `s3.Bucket`, `ec2.Vpc`, `rds.DatabaseInstance` |
| **L3** (patterns) | junta vários recursos num padrão pronto | (não usamos — exigiria assets) |

> No dia a dia você usa **L2** (menos código, mais seguro). Caímos para **L1**
> (`CfnInstance`) só quando precisamos de controle fino — no nosso caso, para
> **não criar IAM** no Academy (ver §5).

---

## 3. A árvore: App → Stack → Construct → recurso

O `app.py` monta uma **árvore**. A raiz é o `App`; abaixo dela, as **Stacks**;
dentro de cada Stack, os **constructs**:

```text
App  (cdk.App())
├── CloudTaskStorage      (Stack)
│   └── UploadsBucket      (s3.Bucket)        → AWS::S3::Bucket
├── CloudTaskNetwork      (Stack)
│   └── CloudTaskVpc       (ec2.Vpc)          → AWS::EC2::VPC (+ subnets, route tables...)
├── CloudTaskDatabase     (Stack)
│   └── PostgresDb         (rds.DatabaseInstance)
└── CloudTaskCompute      (Stack)
    ├── DemoSg             (ec2.SecurityGroup)
    ├── cloudtask-api      (ec2.CfnInstance)
    ├── cloudtask-frontend (ec2.CfnInstance)
    └── cloudtask-grafana  (ec2.CfnInstance)
```

Cada **Stack** vira **um template** CloudFormation separado (e um "stack" no
Console). Por isso dá para subir/derrubar uma de cada vez.

---

## 4. Tour pelos arquivos (`infra/cdk/`)

Abra cada um enquanto lê — **os comentários no código explicam linha a linha**.

| Arquivo | O que ensina |
| --- | --- |
| `cdk.json` | Como o `cdk` roda seu app: `"app": "python3 app.py"`. É só isso que liga a CLI ao seu Python. |
| `app.py` | A **montagem**: cria o `App`, escolhe o *synthesizer*, lê conta/região, aplica *tags* e instancia as 7 stacks. Termina em `app.synth()`. |
| `stacks/storage_stack.py` | **L2** mínimo: um `s3.Bucket` seguro por padrão. Bom primeiro arquivo. |
| `stacks/ecr_stack.py` | Repositório ECR + *lifecycle*. Mostra por que **não fixar nomes**. |
| `stacks/network_stack.py` | `ec2.Vpc` — um construct que gera **dezenas** de recursos (subnets, rotas) a partir de poucas linhas. |
| `stacks/events_stack.py` | Tabela DynamoDB. Expõe `self.table` para **outra stack** usar. |
| `stacks/observability_stack.py` | **Referência entre stacks**: recebe `events_table` e cria alarme/dashboard em cima dela. |
| `stacks/database_stack.py` | `rds.DatabaseInstance` na VPC + senha no Secrets Manager (sem segredo no código). |
| `stacks/compute_stack.py` | **L1** (`CfnInstance`), **tokens** e `user_data` — a parte mais avançada. |

---

## 5. Quatro conceitos que o projeto demonstra

### a) **Tokens** — valores que só existem no deploy

Quando você escreve `bucket.bucket_name` ou `api.attr_public_dns_name`, o valor
**ainda não existe** (o recurso nem foi criado). O CDK devolve um **token**: um
marcador que, no `synth`, vira a referência certa no CloudFormation
(`Ref`/`Fn::GetAtt`).

No `compute_stack.py` usamos isso para injetar a URL da API no frontend:

```python
f"sed -i 's#__API_BASE__#http://{api.attr_public_dns_name}:8000#' ..."
```

Mesmo dentro de uma f-string, o token "sobrevive" e o CDK o resolve na hora do
synth. É como o frontend descobre o endereço da API **sem você digitar IP**.

### b) **CfnOutput** — as saídas

`CfnOutput(self, "ApiRepositoryUri", value=repo.repository_uri)` cria uma
**saída** que aparece no fim do deploy e fica consultável. É como o código te
"devolve" os valores gerados (nome do bucket, URL do repo, link do frontend).

### c) **Referência entre stacks** (vira Export/ImportValue)

`ObservabilityStack` recebe `events.table` da `EventsStack`. O CDK percebe a
dependência e, no template, cria um **Export** numa stack e um **ImportValue** na
outra — e garante a **ordem** de deploy. Você só passou um objeto Python; o CDK
cuidou do encanamento.

### d) **Synthesizer sem bootstrap** (o truque do Academy)

No `app.py`:

```python
synthesizer = cdk.CliCredentialsStackSynthesizer()
```

O synthesizer **padrão** exige `cdk bootstrap` (cria IAM roles do CDKToolkit) —
**negado no Learner Lab**. Este aqui não precisa: como nossas stacks são **sem
assets** (sem Lambda/imagem para publicar), o template vai inline e o
CloudFormation cria tudo com a **LabRole**. Foi o que destravou subir CDK no
Academy.

> É também por isso que `compute_stack.py` usa `CfnInstance` (L1) com o
> `LabInstanceProfile` **existente**: o `ec2.Instance` (L2) criaria uma IAM Role
> nova → `iam:Create*` é negado no Academy. Às vezes o nível mais baixo é o que
> faz caber na limitação.

---

## 6. Mão na massa (sem gastar nada)

```bash
cd infra/cdk
source .venv/Scripts/activate      # ou: source .venv/bin/activate (Linux/Mac)

# 1. sintetizar TODAS as stacks
cdk synth >/dev/null && ls cdk.out/*.template.json

# 2. abrir um template e achar o recurso
#    (procure por "AWS::S3::Bucket" no CloudTaskStorage.template.json)

# 3. listar as stacks que o app define
cdk ls

# 4. mude algo pequeno no Python (ex.: max_image_count=5 no ecr_stack.py)
#    e veja a diferença SEM aplicar:
cdk diff CloudTaskEcr
```

`cdk diff` compara o que **mudaria** vs o que está implantado — o melhor amigo
do *code review* de infra.

---

## 7. Por que IaC ganha quando a infra **cresce**

Repare na evolução desta disciplina: **console → CLI → script → IaC**. Com uma
VM só, qualquer abordagem serve. Mas a infra final tem **7 stacks** e **3
servidores** (API, Frontend, Grafana) — e aí a diferença aparece:

* **Um comando** sobe/derruba tudo, na ordem certa, com as dependências
  resolvidas. Na mão, seriam dezenas de cliques/comandos sem garantia de ordem.
* **Versionado no git** → entra em Pull Request, alguém **revisa** a mudança de
  infra como revisa código.
* **Reproduzível** → roda igual na sua conta, na do colega e amanhã de novo.
* **Destrói junto** → sem recurso órfão esquecido cobrando.

> 🧩 **Por que adicionamos o frontend num servidor próprio?** Não era estritamente
> necessário para a aplicação funcionar — adicionamos de propósito para a infra
> ter **mais uma peça** (mais um EC2, mais um security group, mais uma URL). É
> assim que se enxerga o **ganho do CDK**: quanto **mais complexa** a topologia,
> mais valor tem descrevê-la como código em vez de clicar. Gerenciar 3 servidores
> + RDS + VPC + observabilidade na mão é frágil; em CDK é um `deploy`/`destroy`.

---

## 8. Resumo

* CDK = **Python que gera CloudFormation**; quem cria é o CloudFormation.
* Todo recurso é um **construct** `(scope, id, props)`, em níveis **L1/L2/L3**.
* `app.py` monta a **árvore** App → Stacks → constructs e chama `app.synth()`.
* **Tokens**, **CfnOutput** e **referências entre stacks** são o que torna o
  código declarativo e "auto-encanado".
* O `CliCredentialsStackSynthesizer` + stacks **sem assets** = sobe no Academy
  **sem bootstrap**.
* Quanto **maior** a infra, **maior** o ganho de fazê-la como código.
