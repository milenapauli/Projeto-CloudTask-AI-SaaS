"""
Testes do endpoint de uploads (`/uploads`) no modo **local**.

POR QUÊ só local: o backend S3 depende de credenciais e de um bucket real (ou
LocalStack). Para a Aula 5, o modo local cobre a lógica das rotas, a sanitização
de nome e o caminho de erro 404. O backend S3 é coberto manualmente pelo aluno
quando ele liga `STORAGE_MODE=s3`.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _force_local_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Garante storage local + pasta temporária por teste.

    POR QUÊ monkeypatch: cada teste recebe uma `tmp_path` única do pytest;
    sobrescrevemos `settings.local_uploads_dir` para isolar uploads entre
    testes e não tocar em `./local_uploads`.
    """
    from app.core.config import settings

    monkeypatch.setattr(settings, "storage_mode", "local", raising=False)
    monkeypatch.setattr(settings, "local_uploads_dir", str(tmp_path), raising=False)


def test_upload_e_download_local(client: TestClient) -> None:
    """Fluxo feliz: envia arquivo, baixa de volta, conteúdo bate."""
    conteudo = b"conteudo de teste do CloudTask"
    resp = client.post(
        "/uploads",
        files={"file": ("nota.txt", io.BytesIO(conteudo), "text/plain")},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["storage_mode"] == "local"
    assert body["filename"].endswith(".txt")
    assert body["url"].startswith("/uploads/")

    # Baixa pelo nome retornado e confere o conteúdo.
    baixado = client.get(f"/uploads/{body['filename']}")
    assert baixado.status_code == 200
    assert baixado.content == conteudo


def test_download_inexistente_404(client: TestClient) -> None:
    resp = client.get("/uploads/nao-existe-99999.bin")
    assert resp.status_code == 404


def test_upload_extensao_preservada(client: TestClient) -> None:
    resp = client.post(
        "/uploads",
        files={"file": ("foto.png", io.BytesIO(b"\x89PNG\r\n"), "image/png")},
    )
    assert resp.status_code == 201
    assert resp.json()["filename"].endswith(".png")


def test_upload_grande_413(client: TestClient) -> None:
    """Arquivo maior que o limite (10 MB) é rejeitado com 413."""
    grande = b"\0" * (10 * 1024 * 1024 + 1)
    resp = client.post(
        "/uploads",
        files={"file": ("grande.bin", io.BytesIO(grande), "application/octet-stream")},
    )
    assert resp.status_code == 413


def test_upload_sem_arquivo_422(client: TestClient) -> None:
    """Requisição sem o campo `file` é rejeitada (validação do FastAPI)."""
    resp = client.post("/uploads", files={})
    assert resp.status_code == 422
