# Prática 05 — Uploads em modo local

> **Objetivo:** testar `POST /uploads` e `GET /uploads/{filename}` usando o
> backend **local** (sem AWS). Os arquivos vão pra pasta `local_uploads/` dentro
> do container.
>
> **Tempo:** 10 min.
>
> **Pré-req:** API rodando (ver [01](01-rodar-api-devcontainer.md)).
>
> **Aula:** 5 (Semana 3).
>
> **Conceito por trás:** [`../conceitos/s3-efs-datalake.md`](../conceitos/s3-efs-datalake.md).

---

## 1. Confirmar que está em modo local

O `.env` precisa ter (ou nem ter — `local` é o default):

```env
STORAGE_MODE=local
LOCAL_UPLOADS_DIR=local_uploads
```

Reinicie a API se mudou o `.env`:

```bash
docker compose restart api
```

Confirma:

```bash
curl -s http://localhost:8000/openapi.json | grep -o '"storage_mode":"[^"]*"' | head -1
```

> Alternativa: faça um POST (passo 2) e veja o campo `storage_mode` na
> resposta.

---

## 2. Upload de um arquivo

```bash
echo "olá mundo" > teste.txt
curl -i -X POST -F "file=@teste.txt" http://localhost:8000/uploads
```

**Resposta esperada:**

```
HTTP/1.1 201 Created
{
  "filename": "9a4b3c1d-XXXXXXXX-teste.txt",
  "url": "/uploads/9a4b3c1d-XXXXXXXX-teste.txt",
  "storage_mode": "local"
}
```

> 💡 **Por que o nome muda?** O serviço gera um prefixo único (`secrets.token_hex(8) + uuid4()[:8]`)
> e mantém a extensão original. Evita: (1) colisão se 2 alunos enviarem `teste.txt`;
> (2) path traversal (nome sanitizado, sem `..`); (3) overwrite acidental.

---

## 3. Baixar de volta

```bash
curl -O http://localhost:8000/uploads/9a4b3c1d-XXXXXXXX-teste.txt
cat 9a4b3c1d-XXXXXXXX-teste.txt
# olá mundo
```

> O `GET` em modo local devolve o arquivo via `FileResponse` (200 OK + body
> binário).

---

## 4. Ver o arquivo dentro do container

```bash
docker compose exec api ls -la local_uploads/
```

Você verá o arquivo lá, com prefixo aleatório.

---

## 5. Provocar erro 404 (arquivo não existe)

```bash
curl -i http://localhost:8000/uploads/nao-existe.txt
# HTTP/1.1 404 Not Found
# {"detail":"Arquivo 'nao-existe.txt' não encontrado."}
```

---

## 6. Provocar erro 413 (arquivo grande demais)

Criar arquivo de 11 MB (limite é 10 MB):

```bash
dd if=/dev/zero of=grande.bin bs=1M count=11
curl -i -X POST -F "file=@grande.bin" http://localhost:8000/uploads
# HTTP/1.1 413 Request Entity Too Large
# {"detail":"Arquivo excede 10 MB."}
```

> 💡 **Por que 10 MB?** Limite didático em `app/api/routes_uploads.py`. Em
> produção, ALB e API Gateway também impõem limites próprios (1MB / 10MB / 6MB
> dependendo do serviço). Sempre validar **antes** do upload concluir.

---

## 7. Provocar erro 422 (sem arquivo)

```bash
curl -i -X POST http://localhost:8000/uploads
# 422 — campo "file" obrigatório
```

---

## 8. Limpeza

```bash
rm teste.txt grande.bin 9a4b3c1d-*.txt
docker compose exec api rm -rf local_uploads/*
```

---

## Erros comuns

| Erro | Causa | Fix |
| --- | --- | --- |
| `413` mesmo com arquivo pequeno | proxy/nginx no caminho | em dev não tem; verifique tamanho real |
| `500 Internal Server Error` no POST | pasta `local_uploads/` sem permissão | `docker compose exec api ls -la local_uploads` — owner deve ser `appuser` |
| `connection refused` no curl | API caiu | `docker compose logs -f api` |

---

## Próximo passo

→ [`06-uploads-modo-s3.md`](06-uploads-modo-s3.md): mesmas operações, mas
mandando pra um bucket S3 real (precisa de Learner Lab).
