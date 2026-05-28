"""
Testes UNITÁRIOS dos schemas Pydantic (não tocam no banco).

Validam o "contrato" de entrada/saída da API: defaults, limites e rejeição de
dados inválidos — tudo ANTES de qualquer acesso ao PostgreSQL.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.db.models import TaskPriority, TaskStatus
from app.db.schemas import TaskCreate, TaskRead, TaskUpdate
from app.schemas import HealthResponse, ReadyResponse, RootResponse


class TestTaskCreate:
    """Schema usado ao criar tarefas (POST /tasks)."""

    def test_defaults(self) -> None:
        """Sem status/priority, assume pending/medium."""
        task = TaskCreate(title="Minha tarefa")
        assert task.title == "Minha tarefa"
        assert task.description is None
        assert task.status == TaskStatus.pending
        assert task.priority == TaskPriority.medium

    def test_title_obrigatorio(self) -> None:
        """Título ausente é rejeitado."""
        with pytest.raises(ValidationError):
            TaskCreate()  # type: ignore[call-arg]

    def test_title_vazio_rejeitado(self) -> None:
        """Título vazio viola min_length=1."""
        with pytest.raises(ValidationError):
            TaskCreate(title="")

    def test_status_invalido_rejeitado(self) -> None:
        """Status fora do enum é rejeitado."""
        with pytest.raises(ValidationError):
            TaskCreate(title="x", status="concluida")  # type: ignore[arg-type]


class TestTaskUpdate:
    """Schema de atualização parcial (PUT /tasks/{id})."""

    def test_tudo_opcional(self) -> None:
        """Um update vazio é válido (não muda nada)."""
        update = TaskUpdate()
        assert update.model_dump(exclude_unset=True) == {}

    def test_atualizacao_parcial(self) -> None:
        """Só os campos enviados aparecem em exclude_unset."""
        update = TaskUpdate(status=TaskStatus.done)
        assert update.model_dump(exclude_unset=True) == {"status": TaskStatus.done}


class TestResponses:
    """Schemas de resposta (health, ready, root)."""

    def test_health_default(self) -> None:
        assert HealthResponse().status == "ok"

    def test_ready_fields(self) -> None:
        ready = ReadyResponse(status="ready", db="ok")
        assert ready.model_dump() == {"status": "ready", "db": "ok"}

    def test_ready_status_invalido(self) -> None:
        with pytest.raises(ValidationError):
            ReadyResponse(status="talvez", db="ok")  # type: ignore[arg-type]

    def test_root_fields(self) -> None:
        root = RootResponse(name="CloudTask AI SaaS", version="0.2.0", docs="/docs")
        assert root.version == "0.2.0"

    def test_taskread_from_attributes(self) -> None:
        """TaskRead consegue ser construído a partir de um objeto com atributos."""

        class _Fake:
            id = 1
            title = "t"
            description = None
            status = TaskStatus.pending
            priority = TaskPriority.low
            created_at = "2026-01-01T00:00:00Z"
            updated_at = "2026-01-01T00:00:00Z"

        read = TaskRead.model_validate(_Fake())
        assert read.id == 1
        assert read.priority == TaskPriority.low
