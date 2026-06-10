# Prática 06 — Uploads em modo S3 (Amazon)

> **Objetivo:** mandar o mesmo `/uploads` para um bucket **S3 de verdade** e
> baixar via **URL pré-assinada**.
>
> **Tempo:** 25 min.
>
> **Pré-req:**
> 1. Sessão do Learner Lab ativa (credenciais coladas em `~/.aws/credentials`).
> 2. AWS CLI funcionando: `aws sts get-caller-identity` retorna seu ARN.
> 3. Prática [05](05-uploads-modo-local.md) feita.
>
> **Aula:** 5 (Semana 3).

---

## 1. Confirmar credenciais

No terminal do devcontainer:

```bash
aws sts get-caller-identity
```

Saída deve ter `"Account"`, `"Arn"`. Se der `Unable to locate credentials`:

- Verifique se colou as credenciais em `~/.aws/credentials` no **host**
  (Windows: `C:\Users\seu-nome\.aws\credentials`).
- Veja [`00-setup-inicial-e-aws-academy.md`](00-setup-inicial-e-aws-academy.md), Parte 3.

> ⚠️ **Learner Lab expira:** as credenciais duram ~4 horas. Quando expirar,
> abra a sessão de novo no AWS Academy e cole as novas em
> `~/.aws/credentials`. O mount do devcontainer enxerga na hora — sem rebuild.

---

## 2. Criar bucket S3

Nomes de bucket são **globais** na AWS — escolha algo único:

```bash
export BUCKET=cloudtask-uploads-$(whoami)-$(date +%s)
echo $BUCKET

aws s3 mb s3://$BUCKET --region us-east-1
```

> 💡 **POR QUÊ `us-east-1`?** Região default do Learner Lab. Se mudar, edite
> também `AWS_REGION` no `.env`.

Confirmar:

```bash
aws s3 ls
# 2026-XX-XX HH:MM:SS cloudtask-uploads-seu-nome-1234567890
```

---

## 3. Configurar `.env` pra modo S3

Edite o `.env` na raiz do projeto:

```env
STORAGE_MODE=s3
AWS_REGION=us-east-1
S3_BUCKET_NAME=cloudtask-uploads-seu-nome-1234567890
S3_PRESIGNED_URL_EXPIRES=3600
```

Recriar o container pra carregar o novo `.env`:

```bash
docker compose down
docker compose up -d
```

> 💡 **`restart` NÃO basta** porque `.env` é lido na criação do container, não a
> cada start. `down`+`up` cria de novo.

---

## 4. Upload em S3

```bash
echo "olá nuvem" > nuvem.txt
curl -i -X POST -F "file=@nuvem.txt" http://localhost:8000/uploads
```

Resposta agora deve trazer `"storage_mode":"s3"` e uma URL **pré-assinada** longa:

```
HTTP/1.1 201 Created
{
  "filename": "9a4b...nuvem.txt",
  "url": "https://cloudtask-uploads-...s3.amazonaws.com/9a4b...nuvem.txt?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=...&X-Amz-Date=...&X-Amz-Expires=3600&X-Amz-SignedHeaders=host&X-Amz-Signature=...",
  "storage_mode": "s3"
}
```

> 💡 **URL pré-assinada:** um link **temporário** (expira em
> `S3_PRESIGNED_URL_EXPIRES` segundos = 1h) que dá acesso ao objeto SEM
> precisar de credenciais AWS no cliente. O backend assinou para você.

---

## 5. Conferir no bucket

```bash
aws s3 ls s3://$BUCKET/
# 2026-XX-XX HH:MM:SS  11  9a4b...nuvem.txt
```

Ou no Console AWS:

1. Abra `https://s3.console.aws.amazon.com/`.
2. Clique no seu bucket.
3. Veja o objeto.

---

## 6. Baixar via GET — três modos (`?via=`)

A rota `GET /uploads/{filename}` aceita o parâmetro `?via=` para você **ver na
prática** os padrões de entrega de arquivo na nuvem.

### 6.1 `via=redirect` (default) — padrão de produção

**Inspecionar** o redirect (só vê os headers, não baixa — note: **sem** `-L`):

```bash
curl -i "http://localhost:8000/uploads/9a4b...nuvem.txt?via=redirect"
```

```
HTTP/1.1 307 Temporary Redirect
Location: https://cloudtask-uploads-...s3.amazonaws.com/9a4b...?X-Amz-...
```

**Baixar** de fato — segue o redirect (`-L`) e salva (**sem** `-i`):

```bash
curl -L "http://localhost:8000/uploads/9a4b...nuvem.txt?via=redirect" -o saida.txt
```

A API devolve só um `307` com a URL pré-assinada — o cliente baixa **direto do
S3**. `-L` faz o curl seguir o redirect automaticamente.

### 6.2 `via=url` — JSON com a URL (ideal para frontend)

```bash
curl -i "http://localhost:8000/uploads/9a4b...nuvem.txt?via=url"
```

```json
{
  "url": "https://cloudtask-uploads-...s3.amazonaws.com/9a4b...?X-Amz-...",
  "expires_in": 3600,
  "storage_mode": "s3"
}
```

Um frontend baixaria com **um clique** do usuário:

```js
const { url } = await fetch(`/uploads/${name}?via=url`).then(r => r.json());
window.location = url;   // baixa direto do S3
```

### 6.3 `via=stream` — API faz proxy dos bytes (⚠️ anti-padrão)

```bash
curl "http://localhost:8000/uploads/9a4b...nuvem.txt?via=stream" -o saida.txt
```

A API baixa do S3 e **repassa** os bytes (`200 OK` com o conteúdo). Funciona em
qualquer cliente — inclusive o **Swagger**.

> ⚠️ **Não use `-i` junto com `-o`.** A flag `-i` grava os **cabeçalhos HTTP
> dentro do arquivo** — para texto fica feio, para binário (pptx, png, zip)
> **corrompe** o arquivo (os bytes do header entram na frente do conteúdo). Use
> `-i` só para inspecionar headers no terminal, sem `-o`. Para salvar com o nome
> original do header: `curl -OJ "…?via=stream"`.

---

> 💡 **Por que o GET "não funcionava" no Swagger?** O modo `redirect` devolve um
> `307` para o S3. O Swagger UI roda no **browser** (via `fetch`) e **não segue**
> esse redirect cross-origin até o S3 (o bucket não tem CORS) — então parece que
> nada baixa. Para testar download **pelo `/docs`**, use `?via=stream` (baixa
> direto) ou `?via=url` (mostra o link clicável).

### ⚠️ Proxy vs URL pré-assinada (a lição de nuvem)

`via=stream` é cômodo, mas em **produção é anti-padrão**. O arquivo trafega
`S3 → API → cliente`, o que:

- **dobra a banda** (egress ~2x) e satura a rede da API;
- **prende um worker** durante toda a transferência;
- **não escala barato** (cresce a API só para empurrar bytes);
- **perde CDN e _range requests_** (CloudFront, pausar/retomar).

> **Regra de ouro:** a **API autoriza** (gera a URL pré-assinada que expira) e o
> **S3/CDN entrega** os bytes. Mais contexto em
> [`../conceitos/s3-efs-datalake.md`](../conceitos/s3-efs-datalake.md).

---

## 7. Tornar público (NÃO recomendado) — só para entender ACL

> ⚠️ **NÃO faça isso em produção.** Buckets públicos são uma das principais
> causas de vazamento de dados em LGPD/GDPR. Aqui é só pra você ver na prática
> que **bucket privado + URL pré-assinada** é o padrão correto.

(Pulamos esse passo — fica como leitura conceitual em
[`../conceitos/s3-efs-datalake.md`](../conceitos/s3-efs-datalake.md).)

---

## 8. **LIMPEZA OBRIGATÓRIA** (custos!)

> ⚠️ **NÃO PULE.** Mesmo um bucket vazio gera custo de listagem se tiver muito
> tráfego. No Learner Lab há limite de crédito — não desperdice.

```bash
# 1. apagar objetos do bucket
aws s3 rm s3://$BUCKET --recursive

# 2. apagar o bucket
aws s3 rb s3://$BUCKET

# 3. confirmar
aws s3 ls
# (não deve listar o bucket apagado)
```

---

## 9. Voltar para modo local

Edite `.env`:

```env
STORAGE_MODE=local
```

```bash
docker compose down && docker compose up -d
```

---

## Erros comuns

| Erro | Causa | Fix |
| --- | --- | --- |
| `Unable to locate credentials` | sem `~/.aws/credentials` | colar credenciais (Parte 3 do setup-inicial) |
| `The AWS Access Key Id you provided does not exist in our records` | credenciais expiraram | nova sessão no Learner Lab |
| `BucketAlreadyExists` | nome de bucket já em uso no mundo | adicione sufixo único (timestamp + seu nome) |
| `Access Denied` ao criar | sua role não tem permissão (raro no Learner Lab) | confirme com `aws s3 ls` que tem leitura básica |
| `storage_mode` ainda diz `"local"` após mudar `.env` | container não foi recriado | `docker compose down && docker compose up -d` |
| `botocore.exceptions.NoRegionError` | `AWS_REGION` faltando no `.env` | adicione `AWS_REGION=us-east-1` |

---

## Próximo passo

→ [`07-rodar-testes.md`](07-rodar-testes.md): rodar `pytest` no devcontainer
e em container isolado.
