"""
Serviço de armazenamento de objetos (uploads).

Dois backends acessíveis pela mesma interface:

* :class:`LocalStorage` — grava em disco (pasta ``settings.local_uploads_dir``).
  Útil quando o aluno não tem AWS configurada.
* :class:`S3Storage` — grava no Amazon S3 (bucket ``settings.s3_bucket_name``).
  Usado em produção e quando o Learner Lab estiver disponível.

A função :func:`get_storage` escolhe um ou outro a partir de
``settings.storage_mode`` (``local`` ou ``s3``). Trocar de modo NÃO exige
alterar o código das rotas — só a variável de ambiente.

POR QUÊ NÃO guardar arquivos dentro do container: container é EFÊMERO; ao
reiniciar/recriar, qualquer arquivo dentro dele some. Storage tem que ser
externo (disco montado em volume, S3, etc.).
"""

from __future__ import annotations

import io
import secrets
import uuid
from pathlib import Path
from typing import IO, Protocol

from app.core.config import settings


class StorageError(Exception):
    """Erro genérico do serviço de storage (problema de I/O, S3, etc.)."""


class StorageBackend(Protocol):
    """Contrato comum aos backends de storage.

    Métodos:
        save: persiste o arquivo recebido e devolve o "nome" gravado (id).
        get_download_url: devolve URL ou caminho para baixar o objeto.
        delete: remove o objeto (opcional para a aula, mas útil em testes).
        exists: indica se o objeto está presente.
    """

    def save(self, *, filename: str, content_type: str | None, file_obj: IO[bytes]) -> str:
        ...

    def get_download_url(self, stored_name: str) -> str:
        ...

    def delete(self, stored_name: str) -> None:
        ...

    def exists(self, stored_name: str) -> bool:
        ...


# ---------------------------------------------------------------------------
# Helpers compartilhados.
# ---------------------------------------------------------------------------
def _safe_unique_name(original: str) -> str:
    """Gera um nome seguro e único para o arquivo no storage.

    Estratégia: usa `secrets.token_hex(8)` (16 hex chars) + a extensão do
    arquivo original — evita colisões e impede *path traversal* do tipo
    ``../../etc/passwd`` (ignoramos qualquer caminho do nome).
    """
    suffix = Path(original).suffix.lower()
    return f"{secrets.token_hex(8)}-{uuid.uuid4().hex[:8]}{suffix}"


# ---------------------------------------------------------------------------
# Backend local.
# ---------------------------------------------------------------------------
class LocalStorage:
    """Armazena arquivos em pasta local (``settings.local_uploads_dir``)."""

    def __init__(self, base_dir: str | Path | None = None) -> None:
        self.base_dir = Path(base_dir or settings.local_uploads_dir).resolve()
        # `parents=True` para criar pastas pai; `exist_ok` evita erro em reinício.
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, name: str) -> Path:
        """Resolve o caminho dentro de ``base_dir`` rejeitando saída por ``..``."""
        candidate = (self.base_dir / name).resolve()
        if self.base_dir not in candidate.parents and candidate != self.base_dir:
            # Sanity: nome com ``..`` apontaria para fora do diretório base.
            raise StorageError(f"Nome de arquivo inválido: {name!r}")
        return candidate

    def save(
        self, *, filename: str, content_type: str | None, file_obj: IO[bytes]
    ) -> str:
        stored = _safe_unique_name(filename)
        path = self._path(stored)
        try:
            with path.open("wb") as out:
                # Lê em pedaços para não estourar memória com arquivos grandes.
                while chunk := file_obj.read(1024 * 1024):
                    out.write(chunk)
        except OSError as exc:
            raise StorageError(f"Falha ao salvar {filename!r}: {exc}") from exc
        return stored

    def get_download_url(self, stored_name: str) -> str:
        # No modo local, a "URL" é o endpoint da própria API (servida por
        # GET /uploads/{filename}). Apenas devolvemos o caminho relativo.
        return f"/uploads/{stored_name}"

    def delete(self, stored_name: str) -> None:
        try:
            self._path(stored_name).unlink(missing_ok=True)
        except OSError as exc:
            raise StorageError(f"Falha ao remover {stored_name!r}: {exc}") from exc

    def exists(self, stored_name: str) -> bool:
        return self._path(stored_name).is_file()

    def read(self, stored_name: str) -> bytes:
        """Lê o conteúdo (uso interno da rota GET /uploads no modo local)."""
        if not self.exists(stored_name):
            raise StorageError(f"Arquivo {stored_name!r} não encontrado.")
        return self._path(stored_name).read_bytes()


# ---------------------------------------------------------------------------
# Backend S3.
# ---------------------------------------------------------------------------
class S3Storage:
    """Armazena arquivos no Amazon S3.

    O cliente boto3 é criado preguiçosamente para não exigir credenciais quando
    rodamos no modo ``local`` (testes, alunos sem AWS).
    """

    def __init__(
        self,
        *,
        bucket: str | None = None,
        region: str | None = None,
        endpoint_url: str | None = None,
    ) -> None:
        self.bucket = bucket or settings.s3_bucket_name
        self.region = region or settings.aws_region
        # endpoint_url vazio -> AWS real; preenchido -> ex.: LocalStack.
        self.endpoint_url = endpoint_url if endpoint_url is not None else settings.s3_endpoint_url

    def _client(self):  # type: ignore[no-untyped-def]
        # Import dentro do método para que LocalStorage não puxe boto3 à toa.
        import boto3

        kwargs: dict = {"region_name": self.region}
        if self.endpoint_url:
            kwargs["endpoint_url"] = self.endpoint_url
        return boto3.client("s3", **kwargs)

    def save(
        self, *, filename: str, content_type: str | None, file_obj: IO[bytes]
    ) -> str:
        stored = _safe_unique_name(filename)
        try:
            extra: dict = {}
            if content_type:
                extra["ContentType"] = content_type
            # upload_fileobj envia em pedaços (streamado), seguro p/ arquivos grandes.
            self._client().upload_fileobj(file_obj, self.bucket, stored, ExtraArgs=extra)
        except Exception as exc:  # noqa: BLE001
            raise StorageError(f"Falha ao enviar para S3: {exc}") from exc
        return stored

    def get_download_url(self, stored_name: str) -> str:
        """Gera uma URL pré-assinada (temporária) para download.

        POR QUÊ pré-assinada: o bucket pode ser PRIVADO (recomendado). A URL
        permite o download SEM tornar o bucket público — e expira depois de
        ``settings.s3_presigned_url_expires`` segundos.
        """
        try:
            return self._client().generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": stored_name},
                ExpiresIn=settings.s3_presigned_url_expires,
            )
        except Exception as exc:  # noqa: BLE001
            raise StorageError(f"Falha ao gerar URL pré-assinada: {exc}") from exc

    def open_stream(self, stored_name: str) -> tuple[IO[bytes], dict]:
        """Abre o objeto no S3 e devolve um fluxo de bytes + metadados.

        Usado pela rota ``GET /uploads/{filename}?via=stream`` para fazer
        *proxy* do download: a API baixa do S3 e repassa os bytes ao cliente.

        POR QUÊ ISTO É UM ANTI-PADRÃO EM PRODUÇÃO: o arquivo trafega
        ``S3 -> API -> cliente`` (banda dobrada, ~2x de custo de egress), e
        cada download segura um worker da API enquanto a transferência dura.
        O padrão recomendado é a **URL pré-assinada** (ver
        :meth:`get_download_url`), em que o S3/CDN entrega direto ao cliente e
        a API só autoriza. Mantemos ``open_stream`` por ser o único modo que
        funciona dentro do Swagger UI (que não segue o redirect 307).

        Args:
            stored_name: Nome (key) do objeto no bucket.

        Returns:
            tuple[IO[bytes], dict]: o corpo do objeto (``StreamingBody``, que é
            file-like e expõe ``iter_chunks``) e um dicionário com
            ``content_type`` (str | None) e ``content_length`` (int | None).

        Raises:
            StorageError: se o objeto não existir ou a leitura falhar.
        """
        try:
            obj = self._client().get_object(Bucket=self.bucket, Key=stored_name)
        except Exception as exc:  # noqa: BLE001
            raise StorageError(f"Falha ao ler do S3: {exc}") from exc
        meta = {
            "content_type": obj.get("ContentType"),
            "content_length": obj.get("ContentLength"),
        }
        return obj["Body"], meta

    def delete(self, stored_name: str) -> None:
        try:
            self._client().delete_object(Bucket=self.bucket, Key=stored_name)
        except Exception as exc:  # noqa: BLE001
            raise StorageError(f"Falha ao remover do S3: {exc}") from exc

    def exists(self, stored_name: str) -> bool:
        try:
            self._client().head_object(Bucket=self.bucket, Key=stored_name)
            return True
        except Exception:  # noqa: BLE001
            return False


# ---------------------------------------------------------------------------
# Fábrica que escolhe o backend conforme settings.storage_mode.
# ---------------------------------------------------------------------------
def get_storage() -> StorageBackend:
    """Retorna a implementação correta de storage conforme ``settings.storage_mode``.

    POR QUÊ não cachear: queremos que testes que monkeypatcham ``settings`` ou
    a pasta local consigam recriar a instância limpa sem mexer em singletons.

    Returns:
        StorageBackend: instância de :class:`LocalStorage` ou :class:`S3Storage`.
    """
    if settings.storage_mode == "s3":
        return S3Storage()
    return LocalStorage()


__all__ = [
    "LocalStorage",
    "S3Storage",
    "StorageBackend",
    "StorageError",
    "get_storage",
]
