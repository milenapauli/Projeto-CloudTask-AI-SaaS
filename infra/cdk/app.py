#!/usr/bin/env python3
"""Ponto de entrada do app AWS CDK — CloudTask AI SaaS (Aula 11).

Este arquivo é o que o comando ``cdk`` executa (ver ``cdk.json``). Ele monta o
**app** e instancia as **stacks** (pilhas) que descrevem a infraestrutura como
código (IaC). Cada stack vira um CloudFormation template que o CDK sintetiza e
implanta.

POR QUÊ CDK (e não Console/CLI na mão):
    nas semanas anteriores criamos recursos clicando no Console (lento, não
    versionável) e por comandos avulsos (``aws ...``). O **CDK** descreve a
    infra em **Python versionado no git**: você revê em Pull Request, reproduz
    em qualquer conta com um comando e destrói tudo junto. É o passo final da
    evolução **console → CLI → script → IaC**.

POR QUÊ estas stacks (S3, ECR, VPC, DynamoDB, CloudWatch/SNS, RDS) e não o EKS:
    elas recriam, como código, a infra que construímos na mão ao longo do curso
    — mostrando que **toda a jornada cabe em IaC**. Ficam de fora os recursos que
    exigem assets/imagens (Lambda, container), para o app subir no AWS Academy
    **sem `cdk bootstrap`** (ver o synthesizer abaixo).

Comandos (rode dentro de ``infra/cdk/``):
    cdk synth      # gera o CloudFormation (NÃO cria nada) — ótimo p/ aula
    cdk diff       # mostra o que mudaria vs o que está implantado
    cdk deploy     # cria/atualiza os recursos na AWS (cobra!)
    cdk destroy    # apaga tudo que estas stacks criaram
"""

from __future__ import annotations

import os

import aws_cdk as cdk

from stacks.storage_stack import StorageStack
from stacks.ecr_stack import EcrStack
from stacks.network_stack import NetworkStack
from stacks.events_stack import EventsStack
from stacks.observability_stack import ObservabilityStack
from stacks.database_stack import DatabaseStack
from stacks.compute_stack import ComputeStack

app = cdk.App()

# ---------------------------------------------------------------------------
# Synthesizer — POR QUÊ CliCredentialsStackSynthesizer (e não o padrão):
#
#   O synthesizer PADRÃO do CDK exige `cdk bootstrap` antes do deploy — ele cria
#   roles/bucket/ECR do "CDKToolkit" e referencia um parâmetro SSM de versão. No
#   **AWS Academy (Learner Lab)** o bootstrap FALHA, porque criar essas IAM roles
#   é negado para a role da sessão (`voclabs`).
#
#   O CliCredentialsStackSynthesizer NÃO usa bootstrap: o deploy roda com as
#   **credenciais ativas** (as do `aws`/Learner Lab). Como nossas 3 stacks NÃO
#   têm assets (sem Lambda/imagem para publicar — ver nota nas stacks), isso
#   funciona direto. Combine com `cdk deploy --role-arn .../LabRole` para o
#   CloudFormation criar os recursos usando a LabRole (que confia em
#   cloudformation.amazonaws.com).
#
#   Em conta própria, este synthesizer também funciona (sem bootstrap) para
#   stacks sem assets — então o mesmo app serve nos dois ambientes.
# ---------------------------------------------------------------------------
synthesizer = cdk.CliCredentialsStackSynthesizer()

# ---------------------------------------------------------------------------
# Ambiente (conta + região).
#
# Lemos a conta/região das variáveis que o CDK injeta (CDK_DEFAULT_*), que
# vêm das credenciais ativas (mesmas do AWS CLI). Sem fixar conta no código:
# o MESMO app implanta na sua conta hoje e em outra amanhã, só trocando as
# credenciais — exatamente a vantagem de IaC.
# ---------------------------------------------------------------------------
env = cdk.Environment(
    account=os.getenv("CDK_DEFAULT_ACCOUNT"),
    region=os.getenv("CDK_DEFAULT_REGION", "us-east-1"),
)

# Prefixo comum nos nomes das stacks (facilita achar/apagar no Console).
PREFIX = "CloudTask"

# Tags aplicadas a TODOS os recursos das 3 stacks (rastreio de custo/limpeza).
common_tags = {
    "project": "cloudtask-ai-saas",
    "discipline": "computacao-em-nuvem-uninter",
    "managed-by": "cdk",
}

# ---------------------------------------------------------------------------
# Stacks. Cada uma é independente — você pode `cdk deploy CloudTaskStorage`
# isolada, por exemplo. São pequenas de propósito (didático).
#
# ANATOMIA de cada chamada abaixo (vale para TODO construct do CDK):
#     StorageStack(app, "CloudTaskStorage", env=..., tags=..., synthesizer=...)
#                  ^^^   ^^^^^^^^^^^^^^^^^   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#                  (1)   (2)                (3)
#   (1) scope  -> ONDE na árvore: `app` = filha direta do App (a raiz).
#   (2) id     -> nome ÚNICO no scope; vira o nome da stack no CloudFormation.
#   (3) props  -> configuração (conta/região, tags, synthesizer...).
# A árvore resultante é:  App -> [Storage, Ecr, Network, ...] -> recursos.
# Nada é criado AQUI: instanciar só MONTA o modelo em memória; o template só
# nasce no `app.synth()` lá embaixo.
# ---------------------------------------------------------------------------
storage = StorageStack(app, f"{PREFIX}Storage", env=env, tags=common_tags, synthesizer=synthesizer)
ecr = EcrStack(app, f"{PREFIX}Ecr", env=env, tags=common_tags, synthesizer=synthesizer)
network = NetworkStack(app, f"{PREFIX}Network", env=env, tags=common_tags, synthesizer=synthesizer)
events = EventsStack(app, f"{PREFIX}Events", env=env, tags=common_tags, synthesizer=synthesizer)

# Observability depende da tabela de eventos (alarme + dashboard sobre ela).
# Por isso é instanciada DEPOIS e recebe `events.table`. No deploy, suba a
# EventsStack antes da ObservabilityStack (o cdk-academy.sh já faz nessa ordem).
observability = ObservabilityStack(
    app,
    f"{PREFIX}Observability",
    env=env,
    tags=common_tags,
    synthesizer=synthesizer,
    events_table=events.table,
)

# DatabaseStack (RDS) depende da VPC da NetworkStack. É a stack mais pesada
# (cobra por hora, ~5–10 min). Suba a NetworkStack antes.
database = DatabaseStack(
    app,
    f"{PREFIX}Database",
    env=env,
    tags=common_tags,
    synthesizer=synthesizer,
    vpc=network.vpc,
)

# ComputeStack (7ª) — os 3 servidores (API, Frontend, Grafana). Depende da VPC
# (NetworkStack) e, no caminho de produção, do RDS (DatabaseStack): a API lê a
# credencial do RDS no Secrets Manager. ORDEM de deploy: Network -> Database ->
# Compute. Se preferir o caminho barato (sem RDS), troque por:
#     compute = ComputeStack(app, f"{PREFIX}Compute", env=env, tags=common_tags,
#                            synthesizer=synthesizer, vpc=network.vpc)
# e a API sobe um Postgres local em container (mesmo comportamento do
# launch-academy.sh).
compute = ComputeStack(
    app,
    f"{PREFIX}Compute",
    env=env,
    tags=common_tags,
    synthesizer=synthesizer,
    vpc=network.vpc,
    db=database.instance,
    db_secret_name=database.db_secret_name,
)

# Fecha a "montagem": percorre TODA a árvore (App -> stacks -> constructs) e
# escreve os templates CloudFormation em `cdk.out/` (um .template.json por
# stack). É AQUI que os tokens (nomes/ARNs/IDs que só existem no deploy) viram
# `Ref`/`Fn::GetAtt`, e que as referências entre stacks viram Export/ImportValue.
# Depois disso, é o CloudFormation (via `cdk deploy` ou `aws cloudformation
# deploy`) que de fato cria os recursos na AWS.
app.synth()
