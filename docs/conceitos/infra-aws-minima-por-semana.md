# Infra mínima na AWS — por semana

> **Para que serve este doc:** entender **o que precisa existir na AWS** para
> rodar a aplicação CloudTask em cada semana da disciplina. Não é tutorial de
> comandos (esses ficam em [`../praticas/09-deploy-manual-aws.md`](../praticas/09-deploy-manual-aws.md))
> — é o **mapa** de "do que feito?" antes de ir lá.
>
> **Quando ler:** antes de cada aula a partir da **Semana 4**, e sempre que
> precisar dimensionar custo / saber o que pode ser apagado depois.

---

## 1. Premissas

- A maior parte das semanas usa o **AWS Academy Learner Lab** (credenciais
  temporárias, ~4h de sessão, ~$100 de crédito).
- A última semana (Aula 12) é demonstrada na **conta pessoal do professor**,
  porque exige Route 53 + ACM + ALB + domínio real — coisas que o Learner Lab
  bloqueia.
- Toda infra fica em **`us-east-1`** (região default do Learner Lab).
- Usamos **somente a `LabRole`** (única role disponível no Learner Lab — não
  conseguimos criar roles novas).
- **Sempre destruir** a infra ao fim da aula. Crédito é finito.

---

## 2. Mapa "o que precisa por semana"

| Semana | AWS exige? | Recursos mínimos | Custo aprox. (4h) |
| :--- | :---: | :--- | :--- |
| **1** — FastAPI + Docker | ❌ | nada (tudo local) | $0 |
| **2** — PG + HTTPS docs | ❌ | nada (só conceito) | $0 |
| **3** — S3 uploads + Kind local | ⚠️ opcional | 1 bucket S3 | < $0,01 |
| **4** — ECR + push de imagem | ✅ | 1 repositório ECR | < $0,10 |
| **5** — EKS + Service LB | ✅ | EKS (2 nós t3.small) + ECR + ELB | ~$5 |
| **6** — HPA + DynamoDB + Custos | ✅ | tudo da 5 + DynamoDB table + load test | ~$8 |
| **7** — CDK (opcional) | ✅ | mesma da 5/6, mas provisionada por CDK | ~$5 |
| **8** — Final (conta do prof) | ✅✅ | EKS + ALB + ACM + Route53 + RDS | ~$15 |

> ⚠️ **Estimativas**. Real depende de tempo ligado, tráfego e instance type.
> Sempre conferir no **Cost Explorer** (Aula 9 ensina ativar).

> A numeração de semana acima é a **antiga** (sem retrabalho da Aula 12). Veja
> [`ROADMAP.md`](../ROADMAP.md) para mapeamento atualizado entre semanas e aulas.

---

## 3. Stack mínima por etapa

### Semana 3 — só S3

```text
          ┌──────────────┐
   POST   │   FastAPI    │
   ──────►│ (devcontainer│
          │   local)     │      ┌──────────────┐
          │              │─────►│  S3 bucket   │
          └──────────────┘      │ us-east-1    │
                                └──────────────┘
```

**O que existe na AWS:** 1 bucket. Nenhum compute, nenhum BD gerenciado.
**Para que serve:** validar `boto3` + URL pré-assinada com cloud real.

### Semana 4 — ECR

```text
   devcontainer ──docker push──► ECR repo (us-east-1)
                                  │
                                  └── imagem :v0.4.0 fica lá
```

**O que existe:** 1 repositório ECR. Nada roda na AWS ainda — apenas
**armazena** a imagem da API.

### Semana 5 — EKS (primeiro deploy real)

```text
┌─────────────┐   pull  ┌──────────┐
│   Pod API   │◄────────│   ECR    │
├─────────────┤         └──────────┘
│ Postgres   *│  ← container interno (semana 5/6) OU RDS (semana 8+)
│   Pod       │
└─────────────┘
       ▲
       │ Service (type=LoadBalancer)
       │
   ┌───┴───┐
   │  ELB  │ ← clássico (sem ACM por enquanto)
   └───────┘
       ▲
       │ HTTP
   internet
```

**O que existe:**

- 1 cluster EKS (2 nós `t3.small`, criado via `eksctl`).
- 1 Service `LoadBalancer` → cria ELB clássico automaticamente.
- A imagem da API vem do ECR (semana 4).
- Postgres roda como **container** dentro do mesmo cluster (mais barato).

> ⚠️ **Postgres em container no EKS** é didático — funciona, mas **perde
> dados** se o pod cair sem volume persistente. Em produção real seria RDS.
> Veja a seção [Postgres: container vs RDS](#5-postgres-container-vs-rds).

### Semana 6 — adiciona HPA + DynamoDB

```text
   tudo da semana 5
        +
   ┌──────────────┐
   │ HPA          │ → scale 1..5 réplicas conforme CPU
   ├──────────────┤
   │ DynamoDB     │ → logs de eventos (insert-only)
   │  table       │
   └──────────────┘
```

**O que adiciona:** 1 tabela DynamoDB (PAY_PER_REQUEST → cobra só por uso).
HPA é objeto Kubernetes — não custa nada extra.

### Semana 8 — final (conta pessoal do professor)

```text
            internet (HTTPS)
                  │
              www.dominio.com
                  │
              Route 53
                  │
              ┌───▼────┐
              │  ALB   │  ◄── ACM (certificado TLS)
              └───┬────┘
                  │  TLS termina aqui; HTTP interno
                  ▼
              EKS pods (API)
                  │
                  ▼
              RDS PostgreSQL (Multi-AZ opcional)
                  │
                  ▼
              S3 (uploads) + DynamoDB (logs)
```

**O que adiciona em relação à semana 6:**

- RDS PostgreSQL (substitui o container Postgres).
- ALB (Application Load Balancer) em vez de ELB clássico.
- ACM (certificado TLS gratuito para o domínio).
- Route 53 (DNS) apontando para o ALB.

> Esta stack **só roda na conta pessoal**. O Learner Lab não autoriza criar
> certificados ACM nem usar Route 53.

---

## 4. Recursos AWS usados — referência rápida

| Recurso | Para quê | Semana | Custo |
| --- | --- | :---: | --- |
| **S3** | uploads `/uploads` em modo `s3` | 3+ | quase zero por sessão |
| **ECR** | armazenar imagem Docker | 4+ | quase zero |
| **EKS** | rodar a API em pods | 5+ | **~$0,10/h por cluster** + nós EC2 |
| **EC2** (nós EKS) | máquinas que rodam os pods | 5+ | $0,02/h cada `t3.small` |
| **ELB clássico** | Service `LoadBalancer` (auto) | 5+ | $0,025/h + tráfego |
| **DynamoDB** | tabela de eventos/logs | 6+ | $0 se PAY_PER_REQUEST e baixo uso |
| **CloudWatch** | logs e métricas do EKS | 5+ | quase zero |
| **RDS** | banco gerenciado (final) | 8 | $0,02/h `db.t3.micro` + storage |
| **ALB** | LB v2 (HTTP/HTTPS) | 8 | $0,025/h + LCU |
| **ACM** | certificado TLS gratuito | 8 | $0 |
| **Route 53** | DNS para domínio | 8 | $0,50/mês por hosted zone |

> 💡 **Diferença EKS × pod custo:** o cluster cobra ~$0,10/h só por existir
> (control plane). É o item mais caro. **NUNCA esqueça ele ligado** depois da
> aula — em 24 h são ~$2,40 sem você usar.

---

## 5. Postgres: container vs RDS

| Critério | Postgres em container (no EKS) | RDS PostgreSQL |
| --- | --- | --- |
| **Custo** | só EC2 do nó | $0,02/h + storage + IOPS |
| **Backup automático** | ❌ | ✅ (até 35 dias) |
| **Multi-AZ / HA** | ❌ | ✅ opcional |
| **Restart preserva dados** | ❌ sem PVC; ✅ com PVC | ✅ |
| **Tem painel de métricas** | manual | ✅ Performance Insights |
| **Complexidade pra subir** | baixa (1 manifest) | média (CLI / Console) |
| **Quando usar didaticamente** | **Semanas 5–7** (foco em K8s) | **Semana 8** (deploy real) |

**Resumo decisor:**

- Quer ensinar Kubernetes? Pod Postgres serve.
- Quer ensinar "produção"? RDS é o caminho.
- Quer ensinar "sem perder dados"? PVC ou RDS.
- Tem $0 de crédito? Pod (mas sem PVC, dados somem).

A prática [`09-deploy-manual-aws.md`](../praticas/09-deploy-manual-aws.md)
ensina **ambos**.

---

## 6. Onde ficam as credenciais e secrets

| Onde mora | Quando | Forma | Risco |
| --- | --- | --- | --- |
| `.env` local | dev no devcontainer | texto plano | só sua máquina |
| `~/.aws/credentials` | Learner Lab | texto plano (montado) | só sua máquina; expira em 4 h |
| ConfigMap (K8s) | config não-sensível em EKS | YAML | aceitável |
| Secret (K8s) | senha do banco / SECRET_KEY | base64 em YAML | médio — não commitar |
| **AWS Secrets Manager** | senhas/chaves para EKS/Fargate | criptografado, IAM gate | baixo (recomendado) |
| **AWS Systems Manager Parameter Store** | mesma ideia, mais barato | criptografado opcional | baixo |

Na prática:

- **Semanas 5–7 (Learner Lab):** Secret K8s já basta (apaga tudo no fim).
- **Semana 8 (conta pessoal):** **Secrets Manager** + IRSA (IAM role for
  service account). Cobre boas práticas reais.

---

## 7. ECS Fargate × EKS — qual usar?

| Critério | ECS Fargate | EKS |
| --- | --- | --- |
| Complexidade | baixa | alta |
| Vendor lock-in | alto (só AWS) | baixo (K8s padrão) |
| Cobra quando | ligado | cluster ($0,10/h) **+** nós |
| Encaixa no curso | "deploy rápido pra testar" | tema central das aulas 5+ |
| Quando ensinar | atalho em aulas que **não são** de K8s | aulas oficiais de K8s |

**No CloudTask, o tema oficial do curso é Kubernetes.** Mas:

- A prática `09-deploy-manual-aws.md` mostra **ECS Fargate primeiro** como
  comparação ("olha como é simples, agora vamos para EKS").
- Aluno que quiser hospedar **fora do contexto K8s** pode usar Fargate; é mais
  barato pra ligar/desligar.

---

## 8. Cuidados de segurança didática

1. **NUNCA commitar `.env`, `~/.aws/credentials`, kubeconfig.** Já está no
   `.gitignore`.
2. **Buckets S3 SEMPRE privados.** Acesso via URL pré-assinada
   ([`s3-efs-datalake.md`](s3-efs-datalake.md)).
3. **Não expor o RDS via Public IP**. Mantenha em subnet privada;
   acesse via bastion ou só de dentro do EKS.
4. **Apagar tudo no fim**. Use o **script de cleanup** que está em
   [`../praticas/09-deploy-manual-aws.md`](../praticas/09-deploy-manual-aws.md).
5. **Cost Explorer ligado**. Mesmo no Learner Lab. Confere se algo escapou.

---

## 9. Próximos passos

| Quero... | Vá em |
| --- | --- |
| Rodar os comandos | [`../praticas/09-deploy-manual-aws.md`](../praticas/09-deploy-manual-aws.md) |
| Entender VPC/SG/subnet | [`aws-networking.md`](aws-networking.md) |
| Entender IAM/LGPD | [`security-model.md`](security-model.md) |
| Entender ACM/HTTPS | [`https-tls.md`](https-tls.md) |
| Entender S3 / Data Lake | [`s3-efs-datalake.md`](s3-efs-datalake.md) |
| Setup inicial AWS Academy | [`../praticas/00-setup-inicial-e-aws-academy.md`](../praticas/00-setup-inicial-e-aws-academy.md) |
