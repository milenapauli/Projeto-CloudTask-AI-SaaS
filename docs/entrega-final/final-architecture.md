# Arquitetura final — CloudTask AI SaaS

Visão consolidada do que a disciplina construiu, da máquina local à nuvem.

> Documento de **fechamento** (Aula 12). Resume as 6 semanas em um só lugar.

---

## Linha do tempo (o que cada semana somou)

| Semana | Camada adicionada | Tema |
| -----: | --- | --- |
| 1 | API FastAPI + Docker + devcontainer | base |
| 2 | PostgreSQL + CRUD + `.env` + HTTPS (conceito) | persistência + config |
| 3 | Uploads (S3 / local) + Kubernetes local (Kind) | storage + orquestração local |
| 4 | Imagem no ECR + deploy no EKS | nuvem (registry + cluster gerenciado) |
| 5 | HPA + custos + eventos (DynamoDB / JSON) | elasticidade + NoSQL |
| 6 | CDK (IaC, 7 stacks) + autenticação (JWT) + frontend SPA + 3 servidores EC2 (API/Front/Grafana) + entrega final | infra como código + segurança + consolidação |

---

## Arquitetura de produção (alvo final)

```text
                         Internet (HTTPS)
                              │
                       www.seu-dominio  ── Route 53 (DNS)
                              │
                         ┌────▼─────┐
                         │   ALB    │ ◄── ACM (certificado TLS)
                         └────┬─────┘
                  TLS termina aqui; HTTP interno
                              │
              ┌───────────────▼────────────────┐
              │        Amazon EKS (cluster)     │
              │   ┌──────────┐   HPA 2..5       │
              │   │ Pods API │ ◄── escala c/ CPU│
              │   └────┬─────┘                  │
              └────────┼───────────────────────┘
                       │
        ┌──────────────┼───────────────┬──────────────┐
        ▼              ▼               ▼              ▼
  RDS PostgreSQL   Amazon S3      DynamoDB        ECR (imagem)
  (tarefas)        (uploads)      (eventos/logs)  (origem do deploy)

  Infra descrita como código (CDK): S3, ECR, VPC  →  reprodutível e versionada.
```

> Esta é a topologia **alvo** (demonstrada na conta pessoal do professor, com
> domínio real). No Learner Lab, partes ficam simplificadas (sem Route53/ACM;
> Postgres pode rodar como Pod em vez de RDS).

### Topologia da Semana 6 — 3 servidores via CDK (o que de fato sobe no Lab)

Para mostrar IaC gerenciando uma infra **mais complexa**, a Aula 12 sobe **três
servidores separados** (a 7ª stack do CDK, `ComputeStack` — ver
[`infra/cdk/stacks/compute_stack.py`](../../infra/cdk/stacks/compute_stack.py)):

```text
        navegador
           │
   ┌───────▼────────┐      ┌──────────────────┐      ┌──────────────────┐
   │  Frontend EC2  │─────►│     API EC2      │─────►│  RDS PostgreSQL   │
   │  (nginx + SPA) │ HTTP │ (FastAPI + JWT)  │ 5432 │  (Secrets Manager)│
   │  :80           │      │  :8000           │      └──────────────────┘
   └────────────────┘      └────────┬─────────┘
                                    │ logs/métricas
   ┌────────────────┐               ▼
   │  Grafana EC2   │◄────── Amazon CloudWatch  (CPU, rede, DynamoDB, RDS)
   │  :3000         │  (role do EC2, sem chave fixa)
   └────────────────┘
```

> 🧩 **Por que um servidor só para o frontend?** Não era obrigatório para a app
> funcionar — foi adicionado **de propósito** para a infra ganhar mais uma peça
> (mais um EC2, mais um security group, mais uma URL externa). Quanto **mais
> complexa** a topologia, mais evidente fica o **ganho do CDK**: descrever 3
> servidores + RDS + VPC + observabilidade como código e subir/derrubar com **um
> comando** é muito mais rápido, seguro e gerenciável do que clicar/scriptar na
> mão.

> 🔐 **Autenticação — o ideal vs. o que o Lab permite.** Em produção de verdade,
> a autenticação **não** ficaria embutida no backend: usaríamos um **servidor de
> autenticação dedicado** (ex.: **Authentik**) num host próprio, falando
> OAuth2/OIDC. Isso **isola** a emissão de credenciais e, principalmente, o
> **gerenciamento dos certificados TLS** — assim o backend não precisa
> administrar certs (cada serviço que administra cert aumenta a **superfície de
> exposição**; um comprometimento do backend não deve levar junto o material de
> autenticação). Aqui, pelas **limitações do laboratório** (sessão curta, sem
> domínio/DNS, sem gestão de certificados própria), simplificamos: o JWT é
> emitido/validado **no mesmo container do backend**. Funciona para a demo, mas o
> caminho "produção" é o servidor de auth separado.

---

## Componentes e responsabilidades

| Componente | Papel | Onde nasceu |
| --- | --- | --- |
| **FastAPI** | API REST + Swagger | Semana 1 |
| **PostgreSQL / RDS** | dados relacionais (tarefas) | Semana 2 / 6 |
| **Amazon S3** | arquivos (uploads), base de Data Lake | Semana 3 |
| **Kubernetes (Kind→EKS)** | orquestração de containers | Semanas 3–4 |
| **Amazon ECR** | registry da imagem da API | Semana 4 |
| **HPA** | escala automática de réplicas | Semana 5 |
| **DynamoDB** | eventos/logs (NoSQL) | Semana 5 |
| **ALB + ACM + Route 53** | borda HTTPS + domínio | Semana 6 (demo) |
| **Frontend SPA (nginx)** | interface web (login + kanban + anexos), servida em EC2 próprio | Semana 6 |
| **Autenticação (JWT)** | login/token na API; em prod, servidor dedicado (Authentik) | Semana 6 |
| **Grafana + CloudWatch** | observabilidade (dashboards) em EC2 próprio | Semana 6 |
| **AWS CDK (7 stacks)** | infra como código: S3, ECR, VPC, DynamoDB, CloudWatch/SNS, RDS, **Compute (3 EC2)** | Semana 6 |

---

## Decisões de projeto (e por quê)

- **Fallback local em tudo que depende de nuvem** (S3→disco, DynamoDB→JSON):
  o aluno completa as aulas **sem AWS**.
- **Imagem `prod` embute o código** (`COPY`), `dev` usa volume: cluster precisa
  de imagem autossuficiente.
- **Cada banco para seu uso:** SQL (tarefas) + NoSQL (eventos). Não é "um
  substitui o outro".
- **Custo é cidadão de primeira classe:** todo recurso caro tem aviso + roteiro
  de destruição.
- **Frontend num servidor próprio (de propósito):** ele adiciona uma peça à
  infra para evidenciar que o **CDK gerencia complexidade crescente** com o mesmo
  esforço — quanto mais servidores/dependências, maior o ganho de IaC.
- **Autenticação no backend é simplificação do Lab:** o desenho de produção usa
  um **servidor de auth separado (Authentik)** para isolar credenciais e **não
  gerenciar certificados TLS dentro do backend** (menos superfície de exposição).
  No Lab, sem domínio/cert próprios, o JWT roda no mesmo container.

---

## Para a entrega

- Preencha o [`final-report-template.md`](final-report-template.md).
- Rode o [`deployment-checklist.md`](deployment-checklist.md) antes de demonstrar.
- Confirme o [`lgpd-checklist.md`](lgpd-checklist.md).
