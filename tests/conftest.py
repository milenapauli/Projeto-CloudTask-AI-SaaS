"""
Fixtures compartilhadas pelos testes (pytest).

Estratégia de banco para os testes de integração:
    * Usamos um banco DEDICADO de testes (``<nome>_test``), separado do banco
      de desenvolvimento. POR QUÊ: rodar os testes NÃO pode apagar/alterar os
      dados que você criou enquanto desenvolvia.
    * O banco de testes é criado automaticamente se não existir (a conftest
      conecta no banco administrativo ``postgres`` e roda ``CREATE DATABASE``).
    * As tabelas são criadas uma vez por sessão de testes.
    * Antes de CADA teste, limpamos a tabela ``tasks`` (estado limpo).

Como o teste alcança o banco:
    * No container de teste (docker-compose.test.yml), ``TEST_DATABASE_URL``
      aponta para ``cloudtask_test``.
    * No devcontainer (dev), não há ``TEST_DATABASE_URL``; derivamos o nome
      somando ``_test`` ao banco da ``DATABASE_URL`` (ex.: cloudtask ->
      cloudtask_test). Assim o banco ``cloudtask`` (dev) fica intocado.
"""

from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.database import Base, get_db
from app.main import app


def _test_database_url() -> str:
    """Resolve a URL do banco de TESTES.

    Prioridade:
        1. variável de ambiente ``TEST_DATABASE_URL`` (usada no container de teste);
        2. derivada da ``DATABASE_URL`` somando ``_test`` ao nome do banco.

    Returns:
        str: URL SQLAlchemy apontando para o banco de testes.
    """
    explicit = os.getenv("TEST_DATABASE_URL")
    if explicit:
        return explicit
    base = make_url(settings.database_url)
    return str(base.set(database=f"{base.database or 'cloudtask'}_test"))


def _ensure_database_exists(db_url: str) -> None:
    """Cria o banco de testes caso ele ainda não exista.

    Conecta no banco administrativo ``postgres`` (sempre presente) em modo
    AUTOCOMMIT — POR QUÊ: ``CREATE DATABASE`` não pode rodar dentro de uma
    transação. Se o banco já existe, não faz nada.

    Args:
        db_url: URL do banco de testes desejado.
    """
    url = make_url(db_url)
    admin_engine = create_engine(
        url.set(database="postgres"), isolation_level="AUTOCOMMIT"
    )
    try:
        with admin_engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": url.database},
            ).scalar()
            if not exists:
                # Nome entre aspas para aceitar nomes com caracteres especiais.
                conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    finally:
        admin_engine.dispose()


@pytest.fixture(scope="session")
def engine() -> Generator[Engine, None, None]:
    """Engine SQLAlchemy ligada ao banco de testes (escopo de sessão).

    Garante que o banco existe e cria todas as tabelas uma única vez.
    """
    db_url = _test_database_url()
    _ensure_database_exists(db_url)
    eng = create_engine(db_url, pool_pre_ping=True, future=True)
    Base.metadata.create_all(bind=eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db_session(engine: Engine) -> Generator[Session, None, None]:
    """Sessão de banco isolada por teste, com limpeza da tabela ``tasks``.

    Limpamos ANTES de entregar a sessão para o teste, garantindo um ponto de
    partida vazio independentemente do que outro teste deixou.
    """
    SessionTesting = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)
    session = SessionTesting()
    # TRUNCATE ... RESTART IDENTITY: zera a tabela e reinicia o contador de id.
    session.execute(text("TRUNCATE TABLE tasks RESTART IDENTITY CASCADE"))
    session.commit()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Cliente HTTP de teste do FastAPI, usando o banco de testes.

    Substitui a dependência ``get_db`` para que as rotas usem a sessão de
    testes (banco ``_test``), e não o banco de desenvolvimento.
    """

    def _override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
