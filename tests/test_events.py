"""
Testes de eventos/logs (`/events`) e da emissão automática no CRUD de tarefas.

POR QUÊ só o backend **local** (JSON): o backend DynamoDB exige credenciais e
tabela reais. Aqui cobrimos a lógica das rotas, o store local e a emissão
automática de eventos. A seleção do backend DynamoDB é checada sem chamar a AWS.

O event store já vem isolado em arquivo temporário pela fixture autouse
``_isolate_event_store`` (ver ``conftest.py``).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.services.dynamodb_service import (
    DynamoEventStore,
    EventStoreError,
    LocalEventStore,
    get_event_store,
)


# ---------------------------------------------------------------------------
# Rotas /events
# ---------------------------------------------------------------------------
def test_post_event_cria_e_retorna_id(client: TestClient) -> None:
    """POST /events grava e devolve o evento com id + created_at (201)."""
    resp = client.post(
        "/events",
        json={"event_type": "task.created", "task_id": 1, "message": "teste"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["event_type"] == "task.created"
    assert body["task_id"] == 1
    assert body["message"] == "teste"
    assert body["id"]  # uuid não vazio
    assert body["created_at"]  # timestamp preenchido


def test_get_events_mais_recentes_primeiro(client: TestClient) -> None:
    """GET /events lista os eventos com o mais recente primeiro."""
    client.post("/events", json={"event_type": "a", "message": "primeiro"})
    client.post("/events", json={"event_type": "b", "message": "segundo"})

    resp = client.get("/events")
    assert resp.status_code == 200, resp.text
    eventos = resp.json()
    assert len(eventos) == 2
    assert eventos[0]["message"] == "segundo"  # mais recente primeiro
    assert eventos[1]["message"] == "primeiro"


def test_get_events_respeita_limit(client: TestClient) -> None:
    """O parâmetro `limit` corta a quantidade retornada."""
    for i in range(5):
        client.post("/events", json={"event_type": "x", "message": f"e{i}"})
    resp = client.get("/events?limit=2")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_post_event_sem_message_422(client: TestClient) -> None:
    """`message` é obrigatório — sua ausência é rejeitada (422)."""
    resp = client.post("/events", json={"event_type": "task.created"})
    assert resp.status_code == 422


def test_post_event_event_type_vazio_422(client: TestClient) -> None:
    """`event_type` vazio fere o min_length e é rejeitado (422)."""
    resp = client.post("/events", json={"event_type": "", "message": "x"})
    assert resp.status_code == 422


def test_get_events_limit_invalido_422(client: TestClient) -> None:
    """`limit` fora da faixa (1–1000) é rejeitado (422)."""
    assert client.get("/events?limit=0").status_code == 422
    assert client.get("/events?limit=5000").status_code == 422


# ---------------------------------------------------------------------------
# Emissão automática no CRUD de tarefas
# ---------------------------------------------------------------------------
def test_criar_tarefa_emite_evento(client: TestClient) -> None:
    """POST /tasks gera um evento `task.created` com o task_id correto."""
    nova = client.post("/tasks", json={"title": "Tarefa com evento"})
    assert nova.status_code == 201, nova.text
    task_id = nova.json()["id"]

    eventos = client.get("/events").json()
    criados = [e for e in eventos if e["event_type"] == "task.created"]
    assert len(criados) == 1
    assert criados[0]["task_id"] == task_id


def test_atualizar_tarefa_emite_evento(client: TestClient) -> None:
    """PUT /tasks/{id} gera um evento `task.updated`."""
    task_id = client.post("/tasks", json={"title": "T"}).json()["id"]
    client.put(f"/tasks/{task_id}", json={"status": "done"})

    tipos = [e["event_type"] for e in client.get("/events").json()]
    assert "task.updated" in tipos


def test_remover_tarefa_emite_evento(client: TestClient) -> None:
    """DELETE /tasks/{id} gera um evento `task.deleted`."""
    task_id = client.post("/tasks", json={"title": "T"}).json()["id"]
    assert client.delete(f"/tasks/{task_id}").status_code == 204

    tipos = [e["event_type"] for e in client.get("/events").json()]
    assert "task.deleted" in tipos


def test_emissao_resiliente_nao_quebra_crud(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Se o event store falhar, o CRUD de tarefas continua funcionando.

    Forçamos o ``put`` do store a estourar e confirmamos que a criação da
    tarefa ainda retorna 201 (o evento é secundário).
    """
    from app.api import routes_tasks

    class _BrokenStore:
        def put(self, **_: object) -> dict:
            raise EventStoreError("simulando store fora do ar")

    monkeypatch.setattr(routes_tasks, "get_event_store", lambda: _BrokenStore())
    resp = client.post("/tasks", json={"title": "Mesmo com store quebrado"})
    assert resp.status_code == 201, resp.text


# ---------------------------------------------------------------------------
# Store local (JSON) — unidade
# ---------------------------------------------------------------------------
def test_local_store_persiste_no_arquivo(client: TestClient) -> None:
    """O evento criado pela rota aparece no arquivo JSON isolado do teste."""
    client.post("/events", json={"event_type": "t", "message": "no arquivo"})
    path = Path(settings.local_events_file)
    assert path.is_file()
    dados = json.loads(path.read_text(encoding="utf-8"))
    assert any(e["message"] == "no arquivo" for e in dados)


def test_local_store_arquivo_inexistente_lista_vazia(tmp_path: Path) -> None:
    """Listar quando o arquivo ainda não existe devolve lista vazia."""
    store = LocalEventStore(path=tmp_path / "ainda-nao-existe.json")
    assert store.list_events() == []


def test_local_store_json_invalido_erro(tmp_path: Path) -> None:
    """Arquivo com JSON corrompido vira EventStoreError ao ler."""
    bad = tmp_path / "bad.json"
    bad.write_text("isto não é json", encoding="utf-8")
    store = LocalEventStore(path=bad)
    with pytest.raises(EventStoreError):
        store.list_events()


def test_local_store_put_e_list_direto(tmp_path: Path) -> None:
    """put seguido de list_events devolve o evento (uso direto do store)."""
    store = LocalEventStore(path=tmp_path / "ev.json")
    ev = store.put(event_type="x", task_id=7, message="direto")
    assert ev["id"] and ev["created_at"]
    listados = store.list_events()
    assert listados[0]["task_id"] == 7


# ---------------------------------------------------------------------------
# Fábrica get_event_store
# ---------------------------------------------------------------------------
def test_factory_local_por_padrao() -> None:
    """Com EVENT_STORE_MODE=local (default nos testes), retorna LocalEventStore."""
    assert isinstance(get_event_store(), LocalEventStore)


def test_factory_dynamodb_quando_configurado(monkeypatch: pytest.MonkeyPatch) -> None:
    """Com EVENT_STORE_MODE=dynamodb, retorna DynamoEventStore (sem chamar AWS)."""
    monkeypatch.setattr(settings, "event_store_mode", "dynamodb", raising=False)
    assert isinstance(get_event_store(), DynamoEventStore)


# ---------------------------------------------------------------------------
# Caminhos de erro das rotas (event store fora do ar -> 500)
# ---------------------------------------------------------------------------
class _BrokenStore:
    """Store que sempre falha — para exercitar os handlers 500."""

    def put(self, **_: object) -> dict:
        raise EventStoreError("store fora do ar")

    def list_events(self, **_: object) -> list[dict]:
        raise EventStoreError("store fora do ar")


def test_post_event_erro_500(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Falha de gravação no store vira HTTP 500."""
    from app.api import routes_events

    monkeypatch.setattr(routes_events, "get_event_store", lambda: _BrokenStore())
    resp = client.post("/events", json={"event_type": "x", "message": "m"})
    assert resp.status_code == 500


def test_get_events_erro_500(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Falha de leitura no store vira HTTP 500."""
    from app.api import routes_events

    monkeypatch.setattr(routes_events, "get_event_store", lambda: _BrokenStore())
    resp = client.get("/events")
    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# Backend DynamoDB (com tabela fake — sem rede/AWS)
# ---------------------------------------------------------------------------
class _FakeTable:
    """Imitação mínima de uma tabela DynamoDB (boto3) para testes."""

    name = "cloudtask-events"

    def __init__(self) -> None:
        self.items: list[dict] = []

    def put_item(self, *, Item: dict) -> None:  # noqa: N803 (assinatura boto3)
        self.items.append(Item)

    def scan(self, *, Limit: int = 100) -> dict:  # noqa: N803
        return {"Items": self.items[:Limit]}


class _BoomTable:
    """Tabela que estoura em qualquer chamada (simula AWS fora)."""

    def put_item(self, **_: object) -> None:
        raise RuntimeError("sem AWS")

    def scan(self, **_: object) -> dict:
        raise RuntimeError("sem AWS")


def test_dynamo_put_e_list(monkeypatch: pytest.MonkeyPatch) -> None:
    """put grava e list_events devolve (mais recente primeiro) via tabela fake."""
    store = DynamoEventStore(table_name="t")
    fake = _FakeTable()
    monkeypatch.setattr(store, "_table", lambda: fake)
    store.put(event_type="task.created", task_id=1, message="a")
    store.put(event_type="task.updated", task_id=1, message="b")
    listados = store.list_events()
    assert [e["message"] for e in listados] == ["b", "a"]


def test_dynamo_erros_viram_eventstoreerror(monkeypatch: pytest.MonkeyPatch) -> None:
    """Falha do boto3 é encapsulada como EventStoreError (put e list)."""
    store = DynamoEventStore(table_name="t")
    monkeypatch.setattr(store, "_table", lambda: _BoomTable())
    with pytest.raises(EventStoreError):
        store.put(event_type="x", task_id=None, message="m")
    with pytest.raises(EventStoreError):
        store.list_events()


def test_dynamo_table_cria_recurso_boto3(monkeypatch: pytest.MonkeyPatch) -> None:
    """_table monta o recurso boto3 (lazy) sem conectar à rede.

    Usa um endpoint_url fake: boto3 só CRIA o objeto, não faz chamada até usar.
    """
    monkeypatch.setattr(
        settings, "dynamodb_endpoint_url", "http://localhost:9999", raising=False
    )
    store = DynamoEventStore(table_name="cloudtask-events")
    table = store._table()
    assert table.name == "cloudtask-events"
