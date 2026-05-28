"""
Testes de INTEGRAÇÃO do CRUD de tarefas (/tasks) contra o PostgreSQL de testes.

Cobrem o ciclo completo: criar, listar, obter, atualizar, remover — além dos
casos de erro (404) e de validação (422). Cada teste começa com a tabela
``tasks`` vazia (ver a fixture ``db_session`` em conftest.py).
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def _criar(client: TestClient, **campos: object) -> dict:
    """Helper: cria uma tarefa e devolve o JSON da resposta (já validando 201)."""
    payload = {"title": "Tarefa de teste", **campos}
    resp = client.post("/tasks", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestCreate:
    def test_cria_com_defaults(self, client: TestClient) -> None:
        body = _criar(client)
        assert body["id"] == 1                 # tabela começa vazia (id reinicia)
        assert body["status"] == "pending"
        assert body["priority"] == "medium"
        assert body["created_at"] is not None
        assert body["updated_at"] is not None

    def test_cria_com_campos(self, client: TestClient) -> None:
        body = _criar(client, title="Subir EKS", priority="high", status="in_progress")
        assert body["title"] == "Subir EKS"
        assert body["priority"] == "high"
        assert body["status"] == "in_progress"

    def test_titulo_vazio_422(self, client: TestClient) -> None:
        resp = client.post("/tasks", json={"title": ""})
        assert resp.status_code == 422


class TestRead:
    def test_lista_vazia(self, client: TestClient) -> None:
        assert client.get("/tasks").json() == []

    def test_lista_apos_criar(self, client: TestClient) -> None:
        _criar(client, title="A")
        _criar(client, title="B")
        body = client.get("/tasks").json()
        assert len(body) == 2
        assert {t["title"] for t in body} == {"A", "B"}

    def test_obter_por_id(self, client: TestClient) -> None:
        criada = _criar(client, title="X")
        resp = client.get(f"/tasks/{criada['id']}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "X"

    def test_obter_inexistente_404(self, client: TestClient) -> None:
        resp = client.get("/tasks/999")
        assert resp.status_code == 404


class TestUpdate:
    def test_atualiza_status(self, client: TestClient) -> None:
        criada = _criar(client, title="Y")
        resp = client.put(f"/tasks/{criada['id']}", json={"status": "done"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "done"

    def test_atualizacao_parcial_preserva_outros_campos(self, client: TestClient) -> None:
        criada = _criar(client, title="Original", priority="high")
        resp = client.put(f"/tasks/{criada['id']}", json={"status": "in_progress"})
        body = resp.json()
        assert body["title"] == "Original"     # não foi enviado -> preservado
        assert body["priority"] == "high"       # não foi enviado -> preservado
        assert body["status"] == "in_progress"

    def test_atualizar_inexistente_404(self, client: TestClient) -> None:
        resp = client.put("/tasks/999", json={"status": "done"})
        assert resp.status_code == 404


class TestDelete:
    def test_remove(self, client: TestClient) -> None:
        criada = _criar(client, title="Z")
        resp = client.delete(f"/tasks/{criada['id']}")
        assert resp.status_code == 204
        # confirma que sumiu
        assert client.get(f"/tasks/{criada['id']}").status_code == 404

    def test_remover_inexistente_404(self, client: TestClient) -> None:
        resp = client.delete("/tasks/999")
        assert resp.status_code == 404


def test_persiste_entre_requisicoes(client: TestClient) -> None:
    """Uma tarefa criada numa requisição é visível em outra (persistência)."""
    criada = _criar(client, title="Persistente")
    listada = client.get("/tasks").json()
    assert any(t["id"] == criada["id"] for t in listada)
