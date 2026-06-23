"""StorageStack — bucket S3 para os uploads do CloudTask (Aula 11).

Descreve, como código, o mesmo bucket que na Semana 3 (Aula 5) criamos na mão
com ``aws s3 mb`` / pelo Console. Aqui ele nasce **seguro por padrão**:
privado, criptografado e versionado.

Mapa do que cada propriedade resolve:
    * ``block_public_access`` TOTAL  -> ninguém acessa o bucket pela internet
      direto (o app entrega via URL pré-assinada — ver app/services/s3_service.py).
    * ``encryption`` S3_MANAGED       -> objetos criptografados em repouso.
    * ``versioned``                   -> mantém versões antigas (proteção contra
      sobrescrita/exclusão acidental).
    * ``removal_policy=DESTROY`` -> DIDÁTICO: ao rodar ``cdk destroy`` o bucket é
      apagado, sem deixar recurso órfão cobrando. RISCO: em produção isso
      apagaria dados — lá se usa ``RETAIN``. Deixamos DESTROY porque é aula.

POR QUÊ NÃO usamos ``auto_delete_objects=True`` (que apagaria também o conteúdo):
    essa opção cria um **custom resource Lambda** (um "asset" de código). Assets
    exigem ``cdk bootstrap``, que é **bloqueado no AWS Academy**. Para o app
    subir sem bootstrap (ver ``app.py``), mantemos as stacks **sem assets**. Em
    troca, antes do ``cdk destroy`` o bucket precisa estar **vazio** (na demo ele
    costuma estar; se tiver objetos, rode ``aws s3 rm s3://<bucket> --recursive``).
"""

from __future__ import annotations

from aws_cdk import RemovalPolicy, Stack, CfnOutput
from aws_cdk import aws_s3 as s3
from constructs import Construct


class StorageStack(Stack):
    """Cria um bucket S3 privado para os uploads da aplicação."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ANATOMIA DE UM CONSTRUCT (modelo de TODO recurso no CDK):
        #   s3.Bucket(self, "UploadsBucket", **props)
        #            └ scope └ id            └ configuração
        #   * scope = `self` -> este bucket pertence a ESTA stack (entra na árvore
        #     abaixo dela).
        #   * id = "UploadsBucket" -> único DENTRO da stack; o CDK o usa para
        #     montar o "Logical ID" no template (NÃO é o nome do bucket na AWS).
        #   * props = as linhas abaixo -> cada uma vira uma propriedade do
        #     `AWS::S3::Bucket` no CloudFormation gerado.
        #   `s3.Bucket` é um construct de NÍVEL 2 (L2): API amigável, com defaults
        #   seguros e validação — você escreve pouco e ganha um recurso correto.
        #
        # POR QUÊ não definimos `bucket_name`: nomes de bucket são GLOBAIS na
        # AWS. Deixar o CDK gerar um nome único evita colisão "BucketAlreadyExists"
        # quando vários alunos implantam na mesma região.
        bucket = s3.Bucket(
            self,
            "UploadsBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,  # sem acesso público
            encryption=s3.BucketEncryption.S3_MANAGED,           # criptografia em repouso
            versioned=True,                                       # guarda versões antigas
            enforce_ssl=True,                                     # nega requisições não-HTTPS
            removal_policy=RemovalPolicy.DESTROY,                 # destroy apaga o bucket (didático)
        )

        # Saída exibida no fim do `cdk deploy` e consultável depois. Útil para
        # colar no `.env` da app (S3_BUCKET_NAME=...).
        CfnOutput(
            self,
            "UploadsBucketName",
            value=bucket.bucket_name,
            description="Nome do bucket S3 de uploads (use em S3_BUCKET_NAME)",
        )
