"""DatabaseStack — RDS PostgreSQL + Secrets Manager (Aula 11).

Descreve como código o banco gerenciado (RDS) que substitui o Postgres-em-Pod —
a evolução "produção real" da Semana 8/6. A senha é **gerada e guardada no
AWS Secrets Manager** (sem segredo no código).

    * ``DatabaseInstance`` PostgreSQL ``db.t3.micro`` (menor classe).
    * Dentro da VPC da :class:`NetworkStack`, em subnets **isoladas** (sem
      acesso público — boa prática; só de dentro da VPC se conecta).
    * Credenciais via ``Credentials.from_generated_secret`` -> cria um segredo
      no Secrets Manager com usuário ``cloudtask`` e senha aleatória.
    * ``removal_policy=DESTROY`` + ``delete_automated_backups`` -> ``destroy``
      apaga o banco e os backups (sem órfão cobrando). RISCO: apagaria dados em
      produção — lá se usa ``RETAIN`` + snapshot final.

⚠️ CUSTO/TEMPO: RDS cobra por hora (~US$0,02/h a `db.t3.micro`) e leva ~5–10 min
   para criar/apagar. É o recurso mais "pesado" da demo — **destrua ao terminar**.

Sem assets (sem Lambda) -> sobe no Academy sem ``cdk bootstrap``.
"""

from __future__ import annotations

from aws_cdk import RemovalPolicy, Stack, CfnOutput
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_rds as rds
from constructs import Construct


class DatabaseStack(Stack):
    """Cria um RDS PostgreSQL db.t3.micro na VPC, com senha no Secrets Manager."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        vpc: ec2.Vpc,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        db = rds.DatabaseInstance(
            self,
            "PostgresDb",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_16,
            ),
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.BURSTABLE3, ec2.InstanceSize.MICRO
            ),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
            ),
            credentials=rds.Credentials.from_generated_secret(
                "cloudtask", secret_name="cloudtask/rds"
            ),
            database_name="cloudtask",
            allocated_storage=20,
            publicly_accessible=False,
            multi_az=False,                 # 1 AZ (didático/barato)
            removal_policy=RemovalPolicy.DESTROY,
            delete_automated_backups=True,
            deletion_protection=False,
        )

        # Exposto para a ComputeStack (libera o SG da API no banco) e para o
        # nome do segredo que a API lê em produção.
        self.instance = db
        self.db_secret_name = "cloudtask/rds"

        # ARN do segredo com a senha (a app leria daqui em produção).
        CfnOutput(
            self,
            "DbSecretArn",
            value=db.secret.secret_arn if db.secret else "(sem segredo)",
            description="ARN do segredo (Secrets Manager) com a credencial do RDS",
        )
        CfnOutput(
            self,
            "DbEndpoint",
            value=db.db_instance_endpoint_address,
            description="Endpoint do RDS (host para DATABASE_URL)",
        )
