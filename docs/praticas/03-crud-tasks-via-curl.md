# Prática 03 — CRUD de tarefas via curl

> **Objetivo:** fazer o CRUD completo (Create / Read / Update / Delete) na
> rota `/tasks` usando **curl** no terminal. Útil pra entender HTTP "puro".
>
> **Tempo:** 15 min.
>
> **Pré-req:** API rodando (ver [01](01-rodar-api-devcontainer.md)).
>
> Rode os comandos no **terminal do devcontainer** (ou no host — `curl` existe
> em todo lugar).

---

## 0. Sintaxe básica de curl

| Flag | Significa |
| --- | --- |
| `-X MÉTODO` | método HTTP (GET, POST, PUT, DELETE) |
| `-H "Header: valor"` | adicionar cabeçalho |
| `-d '...'` | body (string) |
| `-i` | mostrar response headers + body |
| `-s` | silenciar barra de progresso |
| `-o arq` | salvar em arquivo |

---

## 1. C — **Create** uma tarefa

```bash
curl -i -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Aprender curl",
    "description": "Prática 03",
    "status": "pending",
    "priority": "high"
  }'
```

**Resposta esperada:**

```
HTTP/1.1 201 Created
content-type: application/json

{"id":1,"title":"Aprender curl",...,"created_at":"2026-..."}
```

Guarde o `id` retornado — usaremos nos passos seguintes.

> 💡 **POR QUÊ `201` e não `200`?** `201 Created` é o status correto pra recurso
> criado. Pydantic + FastAPI já devolvem o objeto criado no body (com `id`).

---

## 2. R — **Read** (listar e obter)

**Listar todas (com paginação):**

```bash
curl -s http://localhost:8000/tasks | jq
```

> `jq` formata JSON bonito. Se não tiver: `curl -s ... | python -m json.tool`.

**Listar 5 primeiras:**

```bash
curl -s "http://localhost:8000/tasks?skip=0&limit=5" | jq
```

**Obter por id (substitua `1`):**

```bash
curl -s http://localhost:8000/tasks/1 | jq
```

**Tentar id inexistente:**

```bash
curl -i http://localhost:8000/tasks/999999
# HTTP/1.1 404 Not Found
# {"detail":"Tarefa com id=999999 não encontrada."}
```

---

## 3. U — **Update** (parcial — PATCH-style via PUT)

```bash
curl -i -X PUT http://localhost:8000/tasks/1 \
  -H "Content-Type: application/json" \
  -d '{
    "status": "done"
  }'
```

**Resposta:**

```
HTTP/1.1 200 OK
{"id":1,...,"status":"done","updated_at":"2026-..."}
```

> 💡 Mesmo sendo `PUT`, nesta API o payload é **parcial** (campos não enviados
> ficam como estavam). É um esquema simplificado; em REST estrito, PUT é total
> e PATCH é parcial. Decisão didática.

---

## 4. D — **Delete**

```bash
curl -i -X DELETE http://localhost:8000/tasks/1
# HTTP/1.1 204 No Content
```

> 💡 `204` = "OK, fiz o que pediu, sem body para devolver". Padrão pra DELETE.

**Confirmar que sumiu:**

```bash
curl -i http://localhost:8000/tasks/1
# 404 Not Found
```

---

## 5. Validação — disparar 422

Title vazio:

```bash
curl -i -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"title":""}'
# HTTP/1.1 422 Unprocessable Entity
# {"detail":[{"type":"string_too_short",...}]}
```

JSON inválido:

```bash
curl -i -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{title: bug}'
# HTTP/1.1 422 (JSONDecodeError)
```

> 💡 **Erros de validação NUNCA viram 500.** São `422 Unprocessable Entity`
> com detalhamento por campo.

---

## 6. Verificar no banco (peek rápido)

Em outro terminal do devcontainer:

```bash
docker compose exec db psql -U cloudtask cloudtask -c "SELECT id, title, status FROM tasks ORDER BY id;"
```

(Veja mais em [`04-explorar-banco-psql.md`](04-explorar-banco-psql.md).)

---

## Script de CRUD em loop (bônus)

```bash
# cria 5 tarefas de exemplo
for i in $(seq 1 5); do
  curl -s -X POST http://localhost:8000/tasks \
    -H "Content-Type: application/json" \
    -d "{\"title\":\"Tarefa $i\",\"priority\":\"medium\"}" | jq -r '"Criada id=\(.id)"'
done

# lista todas
curl -s http://localhost:8000/tasks | jq 'length'

# apaga todas (cuidado: deleta TUDO)
for id in $(curl -s http://localhost:8000/tasks | jq '.[].id'); do
  curl -s -X DELETE http://localhost:8000/tasks/$id
done
```

---

## Próximo passo

→ [`04-explorar-banco-psql.md`](04-explorar-banco-psql.md): ver as tarefas
direto no Postgres.
