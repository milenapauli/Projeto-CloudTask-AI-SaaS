"""
Schemas Pydantic da entidade Task — formato de entrada/saída da API.

Um *schema* descreve **como o dado trafega pela API** (JSON). É diferente do
*model* (:mod:`app.db.models`), que descreve como o dado é guardado no banco.

POR QUÊ separar model de schema:
    * Segurança: nem todo campo do banco deve ser aceito do cliente (ex.: o
      cliente não define ``id`` nem ``created_at`` — quem faz isso é o banco).
    * Validação: o Pydantic recusa entradas inválidas (ex.: título vazio)
      ANTES de tocar no banco.
    * Documentação: os ``examples`` abaixo populam o "Try it out" do Swagger.

Tipos de schema desta entidade:
    * :class:`TaskCreate` — corpo do ``POST /tasks`` (criar).
    * :class:`TaskUpdate` — corpo do ``PUT /tasks/{id}`` (atualizar; tudo opcional).
    * :class:`TaskRead`   — resposta devolvida pela API (inclui id e datas).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import TaskPriority, TaskStatus


class TaskBase(BaseModel):
    """Campos comuns de entrada de uma tarefa (compartilhados por create/update)."""

    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Título curto e obrigatório da tarefa.",
        examples=["Configurar PostgreSQL no Docker Compose"],
    )
    description: str | None = Field(
        default=None,
        max_length=2000,
        description="Detalhes opcionais da tarefa.",
        examples=["Adicionar serviço db com postgres:16-alpine e volume."],
    )
    status: TaskStatus = Field(
        default=TaskStatus.pending,
        description="Estado da tarefa: pending | in_progress | done.",
        examples=[TaskStatus.pending],
    )
    priority: TaskPriority = Field(
        default=TaskPriority.medium,
        description="Prioridade da tarefa: low | medium | high.",
        examples=[TaskPriority.high],
    )


class TaskCreate(TaskBase):
    """Dados aceitos ao **criar** uma tarefa (``POST /tasks``).

    Note que NÃO há ``id``, ``created_at`` nem ``updated_at`` aqui: esses
    campos são preenchidos pelo banco, não pelo cliente.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "title": "Subir API no EKS",
                    "description": "Aplicar manifests em infra/k8s/aws.",
                    "status": "pending",
                    "priority": "high",
                }
            ]
        }
    )


class TaskUpdate(BaseModel):
    """Dados aceitos ao **atualizar** uma tarefa (``PUT /tasks/{id}``).

    Todos os campos são opcionais: o cliente envia apenas o que quer mudar.

    RISCO/CUIDADO: como tudo é opcional, um ``PUT`` com corpo vazio é válido e
    não altera nada. A rota trata isso retornando a tarefa inalterada.
    """

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    status: TaskStatus | None = Field(default=None)
    priority: TaskPriority | None = Field(default=None)

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"status": "in_progress", "priority": "medium"}]
        }
    )


class TaskRead(TaskBase):
    """Tarefa **retornada** pela API (inclui campos gerados pelo banco).

    ``from_attributes=True`` permite construir este schema diretamente a partir
    do objeto SQLAlchemy (ex.: ``TaskRead.model_validate(task_orm)``), sem
    conversão manual campo a campo.
    """

    id: int = Field(..., description="Identificador único da tarefa.", examples=[1])
    created_at: datetime = Field(..., description="Quando a tarefa foi criada.")
    updated_at: datetime = Field(..., description="Última alteração da tarefa.")

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Schemas de Evento (Aula 10) — eventos/logs gravados em NoSQL (DynamoDB) ou
# no fallback local JSON. Diferente de Task, NÃO há model SQLAlchemy: o evento
# vive no event store (ver :mod:`app.services.dynamodb_service`), não no Postgres.
# ---------------------------------------------------------------------------
class EventCreate(BaseModel):
    """Dados aceitos ao criar um evento manualmente (``POST /events``).

    ``id`` e ``created_at`` NÃO vêm do cliente — o event store os gera.
    """

    event_type: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Tipo do evento, ex.: task.created | task.updated | task.deleted.",
        examples=["task.created"],
    )
    task_id: int | None = Field(
        default=None,
        description="Id da tarefa relacionada (opcional para eventos avulsos).",
        examples=[1],
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Descrição legível do evento.",
        examples=["Tarefa 1 criada."],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"event_type": "task.created", "task_id": 1, "message": "Tarefa 1 criada."}
            ]
        }
    )


class EventRead(EventCreate):
    """Evento retornado pela API (inclui ``id`` e ``created_at`` gerados).

    ``created_at`` chega como string ISO 8601 do event store e o Pydantic a
    converte para :class:`datetime`.
    """

    id: str = Field(..., description="Identificador único do evento (uuid).", examples=["a1b2c3d4..."])
    created_at: datetime = Field(..., description="Quando o evento foi registrado (UTC).")

    model_config = ConfigDict(from_attributes=True)
