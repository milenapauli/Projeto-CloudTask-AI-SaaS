"""
Rotas de eventos/logs (``/events``) — Aula 10.

Endpoints:
    * ``POST /events`` — registra um evento manualmente.
    * ``GET  /events`` — lista os eventos (mais recentes primeiro).

O backend (NoSQL DynamoDB ou fallback local JSON) é escolhido por
:func:`app.services.dynamodb_service.get_event_store`, que lê
``settings.event_store_mode``. As rotas não sabem qual backend está ativo —
só conversam com a interface.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.db.schemas import EventCreate, EventRead
from app.services.dynamodb_service import EventStoreError, get_event_store

router = APIRouter(prefix="/events", tags=["events"])


CREATE_DESCRIPTION = """\
Registra um evento no event store configurado.

| Modo (`EVENT_STORE_MODE`) | Onde grava |
| --- | --- |
| `local` | arquivo JSON `LOCAL_EVENTS_FILE` |
| `dynamodb` | tabela `DYNAMODB_TABLE_NAME` no Amazon DynamoDB |

Os campos `id` (uuid) e `created_at` (UTC) são gerados pelo servidor.

```bash
curl -X POST http://localhost:8000/events -H "Content-Type: application/json" \\
  -d '{"event_type":"task.created","task_id":1,"message":"teste"}'
```
"""


@router.post(
    "",
    response_model=EventRead,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar evento",
    description=CREATE_DESCRIPTION,
    response_description="Evento criado, já com id e created_at.",
    responses={
        201: {"description": "Evento registrado."},
        500: {"description": "Falha ao gravar (I/O do JSON, DynamoDB indisponível, etc.)."},
    },
)
def create_event(payload: EventCreate) -> EventRead:
    """Persiste um evento no backend configurado.

    Args:
        payload: tipo, task_id (opcional) e mensagem do evento.

    Returns:
        EventRead: o evento gravado, com ``id`` e ``created_at``.

    Raises:
        HTTPException: 500 em falha de gravação.
    """
    store = get_event_store()
    try:
        event = store.put(
            event_type=payload.event_type,
            task_id=payload.task_id,
            message=payload.message,
        )
    except EventStoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc
    return EventRead.model_validate(event)


@router.get(
    "",
    response_model=list[EventRead],
    summary="Listar eventos",
    description=(
        "Retorna os eventos registrados, **mais recentes primeiro**. "
        "Use `limit` para limitar a quantidade."
    ),
    response_description="Lista de eventos.",
    responses={500: {"description": "Falha ao ler o event store."}},
)
def list_events(
    limit: int = Query(100, ge=1, le=1000, description="Máximo de eventos a retornar."),
) -> list[EventRead]:
    """Lista os eventos do backend configurado (mais recentes primeiro).

    Args:
        limit: Máximo de eventos a retornar (1–1000, default 100).

    Returns:
        list[EventRead]: eventos encontrados.

    Raises:
        HTTPException: 500 em falha de leitura.
    """
    store = get_event_store()
    try:
        events = store.list_events(limit=limit)
    except EventStoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc
    return [EventRead.model_validate(e) for e in events]
