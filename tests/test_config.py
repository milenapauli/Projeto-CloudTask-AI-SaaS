"""
Testes UNITÁRIOS da configuração (app/core/config.py).

Verificam o parsing das variáveis de ambiente — em especial o caso que já nos
quebrou: TRUSTED_HOSTS como lista separada por vírgula (CSV), e não JSON.
"""

from __future__ import annotations

from app.core.config import Settings


def _make(**overrides: object) -> Settings:
    """Cria Settings ignorando o arquivo .env, só com os valores passados.

    `_env_file=None` garante que o teste não depende de um .env presente.
    """
    return Settings(_env_file=None, **overrides)  # type: ignore[arg-type]


class TestTrustedHosts:
    """TRUSTED_HOSTS deve aceitar CSV e virar lista."""

    def test_default_wildcard(self) -> None:
        assert _make().trusted_hosts == ["*"]

    def test_csv_vira_lista(self) -> None:
        s = _make(trusted_hosts="api.exemplo.com,localhost")
        assert s.trusted_hosts == ["api.exemplo.com", "localhost"]

    def test_csv_com_espacos(self) -> None:
        s = _make(trusted_hosts="a , b ,c")
        assert s.trusted_hosts == ["a", "b", "c"]

    def test_lista_passa_direto(self) -> None:
        s = _make(trusted_hosts=["x", "y"])
        assert s.trusted_hosts == ["x", "y"]


class TestFlags:
    """Conversões de tipo e atalhos."""

    def test_force_https_string_para_bool(self) -> None:
        assert _make(force_https="true").force_https is True
        assert _make(force_https="false").force_https is False

    def test_is_production(self) -> None:
        assert _make(app_env="production").is_production is True
        assert _make(app_env="development").is_production is False

    def test_app_port_int(self) -> None:
        assert _make(app_port="8001").app_port == 8001
