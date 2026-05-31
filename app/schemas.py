"""
Schemas Pydantic compartilhados por toda a aplicação.

Modelos definidos aqui são usados como ``response_model`` nas rotas
FastAPI; os ``examples`` declarados via :class:`pydantic.Field` aparecem
automaticamente no Swagger (``GET /docs``), permitindo que o usuário
clique em **Try it out** e veja a estrutura esperada.

Em aulas futuras criaremos schemas específicos em ``app/db/schemas.py``
para os modelos do banco (Task, Event, etc.). Por enquanto, este módulo
concentra apenas os schemas de uso geral (health, root).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    """Resposta padrão do endpoint :func:`app.api.routes_health.health`.

    Atributos:
        status: Sempre ``"ok"`` quando o processo da API está vivo.
            Em aulas futuras (Aula 3+) criaremos um ``/health/ready`` que
            poderá retornar outros valores quando o banco estiver fora.

    Example:
        >>> HealthResponse(status="ok").model_dump()
        {'status': 'ok'}
    """

    status: Literal["ok"] = Field(
        default="ok",
        description="Estado da aplicação. `ok` indica que o processo está vivo.",
        examples=["ok"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"status": "ok"},
            ]
        }
    )


class UploadResponse(BaseModel):
    """Resposta do endpoint :func:`app.api.routes_uploads.create_upload`.

    Atributos:
        filename: Nome do arquivo armazenado (gerado pelo backend, único).
        url: Caminho/URL para baixar o arquivo. No modo local é uma rota da
            própria API (``/uploads/<filename>``); no modo S3 é uma URL
            pré-assinada com tempo de expiração.
        storage_mode: Backend que recebeu o arquivo (``local`` ou ``s3``).

    Example:
        >>> UploadResponse(
        ...     filename="abcd1234-deadbeef.txt",
        ...     url="/uploads/abcd1234-deadbeef.txt",
        ...     storage_mode="local",
        ... ).model_dump()
        {'filename': 'abcd1234-deadbeef.txt', 'url': '/uploads/abcd1234-deadbeef.txt', 'storage_mode': 'local'}
    """

    filename: str = Field(..., examples=["abcd1234-deadbeef.txt"])
    url: str = Field(..., examples=["/uploads/abcd1234-deadbeef.txt"])
    storage_mode: Literal["local", "s3"] = Field(..., examples=["local"])

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "filename": "abcd1234-deadbeef.txt",
                    "url": "/uploads/abcd1234-deadbeef.txt",
                    "storage_mode": "local",
                }
            ]
        }
    )


class ReadyResponse(BaseModel):
    """Resposta do endpoint :func:`app.api.routes_health.ready` (readiness).

    Diferente do liveness (``/health``), este endpoint **verifica dependências
    externas** — nesta aula, a conexão com o PostgreSQL.

    Atributos:
        status: ``"ready"`` quando tudo OK; ``"not_ready"`` quando alguma
            dependência falhou.
        db: estado da conexão com o banco (``"ok"`` ou ``"down"``).

    Example:
        >>> ReadyResponse(status="ready", db="ok").model_dump()
        {'status': 'ready', 'db': 'ok'}
    """

    status: Literal["ready", "not_ready"] = Field(
        ...,
        description="`ready` se a app pode receber tráfego; senão `not_ready`.",
        examples=["ready"],
    )
    db: Literal["ok", "down"] = Field(
        ...,
        description="Estado da conexão com o PostgreSQL.",
        examples=["ok"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"status": "ready", "db": "ok"},
                {"status": "not_ready", "db": "down"},
            ]
        }
    )


class RootResponse(BaseModel):
    """Resposta do endpoint raiz :func:`app.main.root`.

    Devolve metadados básicos da aplicação para que clientes (humanos ou
    máquinas) identifiquem o serviço e encontrem rapidamente a documentação
    interativa.

    Atributos:
        name: Nome legível do serviço.
        version: Versão semântica corrente (vem de :data:`app.__version__`).
        docs: Caminho relativo do Swagger UI.

    Example:
        >>> RootResponse(
        ...     name="CloudTask AI SaaS", version="0.1.0", docs="/docs"
        ... ).model_dump()
        {'name': 'CloudTask AI SaaS', 'version': '0.1.0', 'docs': '/docs'}
    """

    name: str = Field(
        ...,
        description="Nome legível do serviço.",
        examples=["CloudTask AI SaaS"],
    )
    version: str = Field(
        ...,
        description="Versão semântica corrente da aplicação.",
        examples=["0.1.0"],
    )
    docs: str = Field(
        ...,
        description="Caminho relativo da interface Swagger UI.",
        examples=["/docs"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "CloudTask AI SaaS",
                    "version": "0.1.0",
                    "docs": "/docs",
                }
            ]
        }
    )
