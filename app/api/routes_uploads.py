"""
Rotas de upload de arquivos (``/uploads``) — Aula 5.

Endpoints:
    * ``POST /uploads``              — recebe um arquivo, persiste e devolve
      ``UploadResponse`` com o nome final e a URL de download.
    * ``GET  /uploads/{filename}``  — baixa o arquivo (modo local) ou redireciona
      para a URL pré-assinada (modo S3).

A escolha entre backend local e S3 é feita por
:func:`app.services.s3_service.get_storage`, que lê ``settings.storage_mode``.
"""

from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse, Response

from app.core.config import settings
from app.schemas import UploadResponse
from app.services.s3_service import (
    LocalStorage,
    StorageError,
    get_storage,
)

router = APIRouter(prefix="/uploads", tags=["uploads"])


# Limite de tamanho por arquivo (10 MB). POR QUÊ: evitar que um upload enorme
# trave o processo. Ajustável em produção via env, se necessário.
_MAX_BYTES = 10 * 1024 * 1024


CREATE_DESCRIPTION = """\
Recebe um arquivo via `multipart/form-data` e o salva no storage configurado.

| Modo (`STORAGE_MODE`) | Onde grava | URL devolvida |
| --- | --- | --- |
| `local` | pasta `LOCAL_UPLOADS_DIR` no container | `/uploads/<nome>` (servido pela própria API) |
| `s3` | bucket `S3_BUCKET_NAME` | URL **pré-assinada** com expiração |

Trocar de modo NÃO exige mexer no código — só mudar a variável de ambiente.

> <kbd>Limite</kbd> arquivos acima de **10 MB** são rejeitados (`413`).

### Exemplo de chamada

```bash
curl -F "file=@./tarefa.pdf" http://localhost:8000/uploads
```
"""


@router.post(
    "",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Enviar arquivo (multipart/form-data)",
    description=CREATE_DESCRIPTION,
    responses={
        201: {"description": "Arquivo salvo com sucesso."},
        413: {"description": "Arquivo excede o limite (10 MB)."},
        500: {"description": "Falha ao salvar (disco cheio, S3 indisponível, etc.)."},
    },
)
async def create_upload(file: UploadFile = File(...)) -> UploadResponse:
    """Persiste o arquivo recebido no backend configurado.

    Args:
        file: Arquivo enviado pelo cliente (multipart).

    Returns:
        UploadResponse: nome final, URL de download e backend usado.

    Raises:
        HTTPException: 413 se o tamanho ultrapassar o limite; 500 em falhas de I/O.
    """
    # Lê em pedaços para controlar o tamanho total e não estourar memória.
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > _MAX_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Arquivo excede {_MAX_BYTES // (1024 * 1024)} MB.",
            )
        chunks.append(chunk)
    await file.close()

    # Repassa o conteúdo já lido como bytes para o backend.
    import io

    buffer = io.BytesIO(b"".join(chunks))
    storage = get_storage()
    try:
        stored_name = storage.save(
            filename=file.filename or "anexo.bin",
            content_type=file.content_type,
            file_obj=buffer,
        )
    except StorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc

    return UploadResponse(
        filename=stored_name,
        url=storage.get_download_url(stored_name),
        storage_mode=settings.storage_mode,
    )


GET_DESCRIPTION = """\
Baixa o arquivo previamente enviado.

* Modo `local`: a API serve o arquivo direto do disco.
* Modo `s3`: a API responde com **redirect 307** para a URL pré-assinada do S3
  (o cliente baixa direto do S3, sem passar pelo nosso servidor).
"""


@router.get(
    "/{filename}",
    summary="Baixar arquivo",
    description=GET_DESCRIPTION,
    responses={
        200: {"description": "Conteúdo do arquivo (modo local)."},
        307: {"description": "Redirect para URL pré-assinada do S3 (modo S3)."},
        404: {"description": "Arquivo não encontrado."},
    },
)
async def get_upload(filename: str) -> Response:
    """Devolve o arquivo ou redireciona para o S3.

    Args:
        filename: Nome armazenado (devolvido pelo `POST /uploads`).
    """
    storage = get_storage()
    if not storage.exists(filename):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Arquivo {filename!r} não encontrado.",
        )

    if settings.storage_mode == "s3":
        # Em S3, devolvemos um redirect para a URL pré-assinada — o cliente
        # baixa direto do bucket (mais rápido + nosso server não carrega bytes).
        url = storage.get_download_url(filename)
        return RedirectResponse(url=url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    # Local: serve direto. FileResponse cuida do streaming e dos headers.
    assert isinstance(storage, LocalStorage)
    path = storage.base_dir / filename
    return FileResponse(path=str(path), filename=filename)
