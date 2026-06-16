# Prática 15 — Eventos e logs com DynamoDB (fallback JSON) (Aula 10)

> **Objetivo:** registrar **eventos** (auditoria) das operações de tarefa em um
> banco **NoSQL** (Amazon DynamoDB), com **fallback local em JSON** para quem
> não tem AWS.
>
> **Pré-req:** CRUD de tarefas funcionando (Semana 2). Para o modo `dynamodb`,
> credenciais AWS ativas.
>
> **Versão da API:** `0.5.0`.

---

## Conceito em 1 minuto

- **NoSQL / DynamoDB:** banco chave-valor, gerenciado, escala automática. Ótimo
  para **eventos/logs** (muitos, append-only, acesso por chave).
- **Por que não no Postgres:** tarefas (relacionais, consultas variadas) ficam no
  SQL; eventos (alto volume, por chave) vão para o NoSQL. Cada banco no seu uso.
- **Mesmo padrão dos uploads:** a variável `EVENT_STORE_MODE` (`local` |
  `dynamodb`) troca o backend **sem mexer no código**.

Modelo do evento: `id` (uuid), `event_type`, `task_id`, `message`, `created_at`.

---

## Parte A — Modo local (JSON, sem AWS, $0)

No `.env`:

```env
EVENT_STORE_MODE=local
LOCAL_EVENTS_FILE=./local_events/events.json
```

### Testar

**Linux/macOS (bash):**
```bash
# evento manual
curl -X POST http://localhost:8000/events -H "Content-Type: application/json" \
  -d '{"event_type":"task.created","task_id":1,"message":"teste"}'
# listar (mais recentes primeiro)
curl http://localhost:8000/events
# emissão AUTOMÁTICA: criar uma tarefa gera um evento task.created
curl -X POST http://localhost:8000/tasks -H "Content-Type: application/json" \
  -d '{"title":"Tarefa que gera evento"}'
curl http://localhost:8000/events
cat local_events/events.json
```

**Windows (PowerShell):**
```powershell
curl.exe -X POST http://localhost:8000/events -H "Content-Type: application/json" `
  -d '{\"event_type\":\"task.created\",\"task_id\":1,\"message\":\"teste\"}'
curl.exe http://localhost:8000/events
curl.exe -X POST http://localhost:8000/tasks -H "Content-Type: application/json" `
  -d '{\"title\":\"Tarefa que gera evento\"}'
curl.exe http://localhost:8000/events
Get-Content local_events/events.json
```

✅ **Checkpoint A:** `GET /events` lista o evento manual **e** o `task.created`
emitido ao criar a tarefa. O arquivo `local_events/events.json` existe.

> 💡 **Emissão automática:** criar/atualizar/excluir tarefa gera, respectivamente,
> `task.created` / `task.updated` / `task.deleted`. Se o event store estiver fora,
> o CRUD **não quebra** (o evento é secundário; vira só um warning no log).

---

## Parte B — Modo DynamoDB (AWS, centavos)

### B1. Criar a tabela

**Linux/macOS (bash):**
```bash
aws dynamodb create-table --table-name cloudtask-events \
  --attribute-definitions AttributeName=id,AttributeType=S \
  --key-schema AttributeName=id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST --region us-east-1
aws dynamodb wait table-exists --table-name cloudtask-events
```

**Windows (PowerShell):**
```powershell
aws dynamodb create-table --table-name cloudtask-events `
  --attribute-definitions AttributeName=id,AttributeType=S `
  --key-schema AttributeName=id,KeyType=HASH `
  --billing-mode PAY_PER_REQUEST --region us-east-1
aws dynamodb wait table-exists --table-name cloudtask-events
```

> **`HASH` key:** é a chave de partição — como o DynamoDB localiza o item. Aqui é
> o `id` (uuid) do evento. **`PAY_PER_REQUEST`:** cobra por requisição (centavos
> para a aula), sem capacidade reservada parada.

### B2. Apontar a app para o DynamoDB

No `.env`:

```env
EVENT_STORE_MODE=dynamodb
DYNAMODB_TABLE_NAME=cloudtask-events
AWS_REGION=us-east-1
```

Reinicie a API e repita os `curl` da Parte A. Os eventos agora vão para a tabela.

### B3. Conferir na AWS

```bash
aws dynamodb scan --table-name cloudtask-events --output table
```
**Console:** DynamoDB → `cloudtask-events` → **Explore items**.

✅ **Checkpoint B:** os eventos aparecem no `scan`/Console. Trocar de modo
exigiu só o `.env` — o código é o mesmo.

### B4. 🔥 Cleanup (obrigatório)

```bash
aws dynamodb delete-table --table-name cloudtask-events --region us-east-1
```

> DynamoDB `PAY_PER_REQUEST` é barato, mas **apague a tabela** ao terminar.

---

## Ligação com o Data Lake (Aula 5)

Esses eventos poderiam ser exportados para o **S3** e alimentar analytics
(Data Lake) — o mesmo S3 dos uploads. Eventos hoje → insumo de BI amanhã.

## Se algo der errado

| Sintoma | Causa provável |
| --- | --- |
| `GET /events` 500 no modo local | sem permissão de escrita em `LOCAL_EVENTS_FILE` |
| `ResourceNotFoundException` | tabela não criada (B1) ou nome/região errados |
| `AccessDenied` no Academy | a role `voclabs` pode limitar DynamoDB — use o modo `local` |
| Evento não aparece ao criar tarefa | `EVENT_STORE_MODE` aponta p/ backend fora do ar (veja o log) |
