"""
Rotas CRUD de tarefas (``/tasks``) do CloudTask AI SaaS.

CRUD = Create, Read, Update, Delete — as quatro operações básicas sobre um
recurso. Aqui o recurso é a tarefa (:class:`app.db.models.Task`).

PADRÃO desta camada (ver :mod:`app.api`):
    * A rota só orquestra HTTP: recebe dados, chama o banco, devolve resposta.
    * A sessão de banco vem por injeção de dependência (``Depends(get_db)``).
    * Entrada/saída sempre via schemas Pydantic (nunca o model ORM direto).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Task
from app.db.schemas import TaskCreate, TaskRead, TaskUpdate
from app.services.dynamodb_service import EventStoreError, get_event_store

router = APIRouter(prefix="/tasks", tags=["tasks"])

logger = logging.getLogger(__name__)


def _emit_event(event_type: str, task_id: int | None, message: str) -> None:
    """Registra um evento de auditoria no event store (Aula 10).

    Chamado em create/update/delete para deixar um rastro do que aconteceu.

    POR QUÊ engolir exceções aqui: o log de evento é **secundário**. Se o event
    store estiver fora (DynamoDB indisponível, disco cheio), a operação de tarefa
    NÃO deve falhar por causa disso — apenas registramos um aviso e seguimos.

    Args:
        event_type: Tipo do evento (ex.: ``task.created``).
        task_id: Id da tarefa relacionada.
        message: Descrição legível.
    """
    try:
        get_event_store().put(event_type=event_type, task_id=task_id, message=message)
    except EventStoreError as exc:  # store fora não pode derrubar o CRUD
        logger.warning("Falha ao emitir evento %s: %s", event_type, exc)


def _get_task_or_404(task_id: int, db: Session) -> Task:
    """Busca uma tarefa pelo id ou lança 404.

    Função auxiliar usada por GET-um, PUT e DELETE para não repetir o mesmo
    bloco de "buscar e checar se existe".

    Args:
        task_id: Identificador da tarefa.
        db: Sessão de banco.

    Returns:
        Task: a tarefa encontrada.

    Raises:
        HTTPException: 404 quando não existe tarefa com aquele id.
    """
    task = db.get(Task, task_id)
    if task is None:
        # POR QUÊ 404 e não 500: "não encontrado" é uma resposta esperada,
        # não um erro do servidor. Devolver o status certo ajuda o cliente
        # a tratar o caso corretamente.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tarefa com id={task_id} não encontrada.",
        )
    return task


CREATE_DESCRIPTION = """\
Cria uma nova tarefa.

O corpo aceita `title` (obrigatório), `description`, `status` e `priority`.
Os campos `id`, `created_at` e `updated_at` **não** são enviados pelo cliente —
o banco os preenche.

```bash
curl -X POST http://localhost:8000/tasks \\
  -H "Content-Type: application/json" \\
  -d '{"title":"Estudar Docker","priority":"high"}'
```
"""


@router.post(
    "",
    response_model=TaskRead,
    status_code=status.HTTP_201_CREATED,
    summary="Criar tarefa",
    description=CREATE_DESCRIPTION,
    response_description="Tarefa criada, já com id e datas.",
)
def create_task(payload: TaskCreate, db: Session = Depends(get_db)) -> Task:
    """Cria e persiste uma nova tarefa.

    Returns:
        Task: a tarefa recém-criada (o FastAPI converte para ``TaskRead``).
    """
    task = Task(**payload.model_dump())
    db.add(task)
    db.commit()       # grava de fato no banco
    db.refresh(task)  # recarrega id/created_at/updated_at gerados pelo banco
    _emit_event("task.created", task.id, f"Tarefa {task.id} criada: {task.title!r}.")
    return task


@router.get(
    "",
    response_model=list[TaskRead],
    summary="Listar tarefas",
    description="Retorna todas as tarefas. Use `skip`/`limit` para paginar.",
    response_description="Lista de tarefas.",
)
def list_tasks(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> list[Task]:
    """Lista tarefas com paginação simples.

    Args:
        skip: Quantos registros pular (offset). Default 0.
        limit: Máximo de registros a retornar. Default 100.

    Returns:
        list[Task]: tarefas encontradas, ordenadas por id.
    """
    # POR QUÊ paginar: sem limite, listar uma tabela enorme pode esgotar a
    # memória e travar a API. limit/skip mantêm a resposta sob controle.
    stmt = select(Task).order_by(Task.id).offset(skip).limit(limit)
    return list(db.scalars(stmt).all())


@router.get(
    "/{task_id}",
    response_model=TaskRead,
    summary="Obter tarefa por id",
    response_description="A tarefa solicitada.",
    responses={404: {"description": "Tarefa não encontrada."}},
)
def get_task(task_id: int, db: Session = Depends(get_db)) -> Task:
    """Retorna uma tarefa pelo id (404 se não existir)."""
    return _get_task_or_404(task_id, db)


@router.put(
    "/{task_id}",
    response_model=TaskRead,
    summary="Atualizar tarefa",
    response_description="A tarefa após a atualização.",
    responses={404: {"description": "Tarefa não encontrada."}},
)
def update_task(
    task_id: int,
    payload: TaskUpdate,
    db: Session = Depends(get_db),
) -> Task:
    """Atualiza campos de uma tarefa existente.

    Apenas os campos enviados no corpo são alterados (atualização parcial).
    Um corpo vazio é válido e retorna a tarefa sem mudanças.

    Returns:
        Task: a tarefa atualizada.
    """
    task = _get_task_or_404(task_id, db)

    # `exclude_unset=True`: pega só os campos que o cliente realmente enviou,
    # preservando os demais. RISCO de não usar: campos omitidos viriam como
    # None e apagariam dados existentes.
    changes = payload.model_dump(exclude_unset=True)
    for campo, valor in changes.items():
        setattr(task, campo, valor)

    db.commit()
    db.refresh(task)
    _emit_event("task.updated", task.id, f"Tarefa {task.id} atualizada.")
    return task


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remover tarefa",
    responses={404: {"description": "Tarefa não encontrada."}},
)
def delete_task(task_id: int, db: Session = Depends(get_db)) -> None:
    """Remove uma tarefa pelo id.

    Retorna ``204 No Content`` (sucesso sem corpo) — convenção REST para
    deleção bem-sucedida.
    """
    task = _get_task_or_404(task_id, db)
    db.delete(task)
    db.commit()
    _emit_event("task.deleted", task_id, f"Tarefa {task_id} removida.")
    # 204: não retornamos corpo. POR QUÊ: o recurso não existe mais, então não
    # há o que devolver. Retornar o objeto deletado confundiria o cliente.
