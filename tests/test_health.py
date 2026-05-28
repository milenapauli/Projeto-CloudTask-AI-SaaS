"""
Testes de INTEGRAÇÃO dos endpoints básicos (/ e /health) e do readiness.

Usam o TestClient do FastAPI, que sobe a aplicação em memória e faz chamadas
HTTP reais contra ela (sem precisar do uvicorn rodando).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.db.database import get_db
from app.main import app


def test_root(client: TestClient) -> None:
    """GET / retorna metadados com a versão atual."""
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "CloudTask AI SaaS"
    assert body["docs"] == "/docs"
    assert "version" in body


def test_health_liveness(client: TestClient) -> None:
    """GET /health responde ok e NÃO depende do banco."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_ready_com_banco(client: TestClient) -> None:
    """GET /health/ready responde 200/ready quando o banco está acessível."""
    resp = client.get("/health/ready")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ready", "db": "ok"}


def test_ready_com_banco_fora() -> None:
    """GET /health/ready responde 503/not_ready quando o banco falha.

    Simulamos a falha substituindo a dependência get_db por uma sessão "fake"
    cujo .execute() levanta exceção — assim não precisamos derrubar o Postgres
    de verdade para exercitar o caminho de erro.
    """

    class _BrokenSession:
        def execute(self, *_args: object, **_kwargs: object) -> None:
            raise RuntimeError("banco indisponível (simulado)")

    def _broken_db():
        yield _BrokenSession()

    app.dependency_overrides[get_db] = _broken_db
    try:
        with TestClient(app) as c:
            resp = c.get("/health/ready")
        assert resp.status_code == 503
        assert resp.json() == {"status": "not_ready", "db": "down"}
    finally:
        app.dependency_overrides.clear()


def test_openapi_disponivel(client: TestClient) -> None:
    """A especificação OpenAPI é gerada e contém as rotas registradas."""
    spec = client.get("/openapi.json").json()
    paths = spec["paths"]
    assert "/health" in paths
    assert "/health/ready" in paths
    assert "/tasks" in paths
