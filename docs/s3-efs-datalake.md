# Armazenamento na AWS — S3, EFS e Data Lake

Guia didático para entender **onde colocar arquivos** na nuvem AWS, por que NÃO
guardar dentro do container, e como o S3 vira a base de um **Data Lake**.

---

## 1. Por que não guardar arquivos dentro do container

Container é **efêmero**: ao reiniciar, recriar ou subir uma nova versão, tudo
que estiver dentro **some**. Mesmo com volumes locais (Docker), o arquivo fica
preso àquela máquina. Em produção (Kubernetes, várias réplicas), cada pod tem
seu próprio "disco" — o upload feito por uma réplica não estaria visível para
outra.

**Regra:** arquivos vivem **fora** do container — em um storage externo.

---

## 2. Três tipos de storage na AWS

| Tipo | Serviço AWS | Analogia | Quando usar |
| --- | --- | --- | --- |
| **Block** | **EBS** (Elastic Block Store) | "HD" colado em uma máquina | banco de dados, máquinas que precisam de disco rápido |
| **File** | **EFS** (Elastic File System) | "pasta de rede" (NFS) | várias máquinas que precisam **compartilhar** a mesma pasta |
| **Object** | **S3** (Simple Storage Service) | "balde de arquivos" com URL | uploads de app, backups, sites estáticos, **Data Lake** |

### Por que escolhemos S3 para uploads

- **Escala infinita.** Não precisamos dimensionar disco.
- **Pago por uso.** Centavos por GB/mês.
- **Acesso por URL.** Qualquer cliente pode baixar (controlado por IAM/URL).
- **Integra com tudo.** Lambda, Glue, Athena, CloudFront, EKS via IAM Roles.

Não usamos **EBS** porque ele é "do disco de uma máquina" — não escala
horizontalmente.

Não usamos **EFS** porque exige montagem (NFS) em cada pod e tem custo maior.
EFS é ótimo para apps legadas que precisam de uma pasta compartilhada; nossa
app fala direto com o S3.

---

## 3. Anatomia do S3

```text
s3://cloudtask-ai-saas-uploads/                ← BUCKET (nome único no mundo)
    ├── 2026/05/abc123-ddee.pdf                ← objeto (chave/key)
    ├── 2026/05/foto-perfil-xyz.jpg
    └── relatorios/2026-Q2.csv
```

- **Bucket:** o "balde". Nome **global** (`cloudtask-ai-saas-uploads` precisa
  ser único em TODO o S3 mundial).
- **Key:** o "caminho" dentro do bucket. NÃO há pastas reais; a barra é só
  parte do nome — mas o Console mostra como árvore.
- **Region:** o bucket vive em **uma região** (ex.: `us-east-1`). Acesso
  cross-region custa mais e é mais lento.

### Storage classes (preço × tempo de acesso)

| Classe | Preço (GB/mês) | Tempo de acesso | Para quê |
| --- | --- | --- | --- |
| **Standard** | ~ US$ 0,023 | imediato | acesso frequente (default) |
| **Standard-IA** (Infrequent Access) | ~ US$ 0,0125 | imediato | arquivos pouco acessados |
| **Glacier Flexible / Deep Archive** | ~ US$ 0,004 / 0,00099 | minutos a horas | arquivamento de longo prazo |

Para o curso, usamos **Standard** (default).

---

## 4. Segurança do bucket

- **Buckets são PRIVADOS por padrão** (e devem continuar assim).
- Para deixar usuários baixarem sem expor o bucket, usamos **URLs pré-assinadas**:
  link com assinatura que expira (ex.: 15 minutos).
- A aplicação assina a URL com sua credencial IAM e devolve para o cliente.
- Nunca commitar `AWS_ACCESS_KEY_ID` em código (ver `security-model.md`).
  Em produção, usamos **IAM Roles** atribuídas ao pod (no EKS, via IRSA).

> 🔴 **Bucket público acidental** é uma das maiores causas de vazamento na AWS.
> Sempre confirme em `Permissions → Block public access`.

---

## 5. Como nosso projeto usa

| Variável | Modo `local` | Modo `s3` |
| --- | --- | --- |
| `STORAGE_MODE` | `local` | `s3` |
| `LOCAL_UPLOADS_DIR` | `./local_uploads` | (ignorado) |
| `S3_BUCKET_NAME` | (ignorado) | nome do bucket |
| `AWS_REGION` | (ignorado) | ex.: `us-east-1` |

O arquivo `app/services/s3_service.py` tem duas implementações com a mesma
interface (`LocalStorage` e `S3Storage`). A função `get_storage()` escolhe uma
ou outra conforme `settings.storage_mode`. **Trocar de modo NÃO exige editar
código** — só a variável de ambiente.

### POST /uploads (multipart/form-data)

```bash
curl -F "file=@minha-foto.png" http://localhost:8000/uploads
```

Responde com o nome final e a URL de download. No modo `local`, a URL é da
própria API; no modo `s3`, é uma URL pré-assinada.

### GET /uploads/{filename}

- Modo `local`: serve o arquivo do disco.
- Modo `s3`: redireciona (`307`) para a URL pré-assinada — cliente baixa direto
  do S3, sem passar pela API (mais rápido e barato).

---

## 6. S3 como base do Data Lake

Um **Data Lake** é um repositório central que armazena dados brutos (logs,
eventos, arquivos) em escala enorme. Padrão na AWS:

```text
        ┌──────────┐  uploads e
producers │  apps    │  eventos
        └────┬─────┘
             ▼
        ┌──────────┐  particiona por
        │  S3      │  ano/mês/dia (parquet)
        └────┬─────┘
             ▼
   ┌─────────┼─────────┐
   ▼         ▼         ▼
  Glue   Athena      QuickSight
  (ETL)  (SQL)      (BI)
```

Na **Aula 10**, vamos gravar eventos (criação/edição de tarefas) no
**DynamoDB**. Esses eventos poderiam ser exportados periodicamente para o S3 e
analisados via Athena. Esse pipeline (DynamoDB → S3 → Athena) é o início de um
Data Lake.

---

## 7. Custos no Learner Lab

- Armazenamento: centavos para o que a aula usa.
- Requisições (`PUT`, `GET`): centavos.
- Transferência de saída: pequena.
- **Apague o bucket no fim da aula:**

```bash
aws s3 rm s3://cloudtask-ai-saas-uploads --recursive
aws s3 rb s3://cloudtask-ai-saas-uploads
```

## Referências

- [`aws-networking.md`](aws-networking.md) · [`security-model.md`](security-model.md)
- S3 docs: <https://docs.aws.amazon.com/AmazonS3/latest/userguide/>
- Pricing: <https://aws.amazon.com/s3/pricing/>
