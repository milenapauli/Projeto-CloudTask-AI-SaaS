"""
Serviço de eventos/logs — backend NoSQL com fallback local em JSON.

Mesma ideia do :mod:`app.services.s3_service`: dois backends atrás de uma única
interface, escolhidos por variável de ambiente
(``settings.event_store_mode`` = ``local`` ou ``dynamodb``).

* :class:`LocalEventStore`  — grava num arquivo JSON (``settings.local_events_file``).
  Permite completar a Aula 10 SEM AWS.
* :class:`DynamoEventStore` — grava no Amazon DynamoDB (tabela
  ``settings.dynamodb_table_name``).

POR QUÊ eventos em NoSQL (e não no Postgres junto das tarefas):
    eventos/logs são **muitos, append-only e acessados por chave** — um caso
    natural para chave-valor (DynamoDB). As tarefas, com relações e consultas
    variadas, seguem no SQL. Cada banco para o seu uso.

Modelo do evento (dict simples, igual nos dois backends)::

    {
      "id": "<uuid hex>",          # chave de partição (HASH) no DynamoDB
      "event_type": "task.created",
      "task_id": 1,                 # pode ser None p/ eventos avulsos
      "message": "Tarefa criada",
      "created_at": "2026-06-16T12:00:00+00:00"  # ISO 8601 (UTC)
    }
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from app.core.config import settings


class EventStoreError(Exception):
    """Erro genérico do serviço de eventos (I/O do JSON, DynamoDB, etc.)."""


class EventStore(Protocol):
    """Contrato comum aos backends de eventos.

    Métodos:
        put: cria e persiste um evento; devolve o dict completo (com id/data).
        list_events: devolve os eventos mais recentes primeiro.
    """

    def put(self, *, event_type: str, task_id: int | None, message: str) -> dict:
        ...

    def list_events(self, limit: int = 100) -> list[dict]:
        ...


# ---------------------------------------------------------------------------
# Helper compartilhado: monta o dict do evento (id + timestamp num só lugar).
# ---------------------------------------------------------------------------
def _build_event(event_type: str, task_id: int | None, message: str) -> dict:
    """Cria o dict do evento com ``id`` (uuid) e ``created_at`` (UTC ISO 8601).

    Centralizar aqui garante que os dois backends gerem eventos idênticos.
    """
    return {
        "id": uuid.uuid4().hex,
        "event_type": event_type,
        "task_id": task_id,
        "message": message,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Backend local (arquivo JSON).
# ---------------------------------------------------------------------------
class LocalEventStore:
    """Armazena eventos num arquivo JSON (lista de objetos).

    RISCO/CUIDADO: a escrita é *read-modify-write* (lê a lista inteira, anexa e
    regrava). Não é seguro para alta concorrência — mas é simples e suficiente
    para a aula. Em produção, é exatamente por isso que se usa um banco como o
    DynamoDB.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path or settings.local_events_file).resolve()
        # Cria a pasta-pai na 1ª escrita; `exist_ok` evita erro em reinício.
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read_all(self) -> list[dict]:
        """Lê a lista de eventos do arquivo (``[]`` se não existir/estiver vazio)."""
        if not self.path.is_file():
            return []
        try:
            content = self.path.read_text(encoding="utf-8").strip()
            return json.loads(content) if content else []
        except (OSError, json.JSONDecodeError) as exc:
            raise EventStoreError(f"Falha ao ler eventos de {self.path}: {exc}") from exc

    def put(self, *, event_type: str, task_id: int | None, message: str) -> dict:
        event = _build_event(event_type, task_id, message)
        events = self._read_all()
        events.append(event)
        try:
            self.path.write_text(
                json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except OSError as exc:
            raise EventStoreError(f"Falha ao gravar evento em {self.path}: {exc}") from exc
        return event

    def list_events(self, limit: int = 100) -> list[dict]:
        # Mais recentes primeiro (o arquivo guarda em ordem de inserção).
        return list(reversed(self._read_all()))[:limit]


# ---------------------------------------------------------------------------
# Backend DynamoDB.
# ---------------------------------------------------------------------------
class DynamoEventStore:
    """Armazena eventos no Amazon DynamoDB.

    O recurso boto3 é criado preguiçosamente para não exigir credenciais no
    modo ``local`` (testes, alunos sem AWS).
    """

    def __init__(
        self,
        *,
        table_name: str | None = None,
        region: str | None = None,
        endpoint_url: str | None = None,
    ) -> None:
        self.table_name = table_name or settings.dynamodb_table_name
        self.region = region or settings.aws_region
        self.endpoint_url = (
            endpoint_url if endpoint_url is not None else settings.dynamodb_endpoint_url
        )

    def _table(self):  # type: ignore[no-untyped-def]
        # Import dentro do método para não puxar boto3 no modo local.
        import boto3

        kwargs: dict = {"region_name": self.region}
        if self.endpoint_url:
            kwargs["endpoint_url"] = self.endpoint_url
        return boto3.resource("dynamodb", **kwargs).Table(self.table_name)

    def put(self, *, event_type: str, task_id: int | None, message: str) -> dict:
        event = _build_event(event_type, task_id, message)
        try:
            self._table().put_item(Item=event)
        except Exception as exc:  # noqa: BLE001
            raise EventStoreError(f"Falha ao gravar no DynamoDB: {exc}") from exc
        return event

    def list_events(self, limit: int = 100) -> list[dict]:
        try:
            # scan lê a tabela inteira (didático). Em produção, com volume alto,
            # prefira query por chave/índice + paginação — scan fica caro/lento.
            resp = self._table().scan(Limit=limit)
        except Exception as exc:  # noqa: BLE001
            raise EventStoreError(f"Falha ao ler do DynamoDB: {exc}") from exc
        items = resp.get("Items", [])
        # Ordena por created_at desc (scan não garante ordem).
        return sorted(items, key=lambda e: e.get("created_at", ""), reverse=True)[:limit]


# ---------------------------------------------------------------------------
# Fábrica que escolhe o backend conforme settings.event_store_mode.
# ---------------------------------------------------------------------------
def get_event_store() -> EventStore:
    """Retorna o backend de eventos conforme ``settings.event_store_mode``.

    POR QUÊ não cachear: testes que monkeypatcham ``settings`` precisam recriar
    a instância limpa (mesmo motivo de :func:`app.services.s3_service.get_storage`).

    Returns:
        EventStore: :class:`LocalEventStore` ou :class:`DynamoEventStore`.
    """
    if settings.event_store_mode == "dynamodb":
        return DynamoEventStore()
    return LocalEventStore()


__all__ = [
    "DynamoEventStore",
    "EventStore",
    "EventStoreError",
    "LocalEventStore",
    "get_event_store",
]
