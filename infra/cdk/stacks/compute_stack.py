"""ComputeStack — 3 servidores EC2 (API, Frontend, Grafana) — Aula 12.

A **7ª stack**: descreve como IaC os três servidores que, no caminho "CLI", o
``infra/servers/launch-academy.sh`` cria na mão. Mesma ideia, agora versionada
e reproduzível com ``cdk deploy``.

    * **API**      (t3.small) — Docker: a API + (RDS ou Postgres local). :8000
    * **Frontend** (t3.micro) — nginx servindo o SPA; recebe a URL da API. :80
    * **Grafana**  (t3.small) — Grafana + datasource CloudWatch.          :3000

POR QUÊ ``CfnInstance`` (L1) e não o ``ec2.Instance`` (L2):
    o construct L2 cria uma **IAM Role + InstanceProfile** novos para a máquina.
    No **AWS Academy** criar IAM é negado. Aqui reaproveitamos o
    ``LabInstanceProfile`` (a role do laboratório, com leitura de CloudWatch /
    Secrets) — por isso usamos o recurso de baixo nível, que aceita um profile
    **já existente** pelo nome. Zero IAM criado => sobe no Academy.

Sem assets (o HTML do front vai embutido, comprimido em base64 no user-data) =>
nada de ``cdk bootstrap``.

POR QUÊ o user-data é lido dos mesmos ``.sh`` de ``infra/servers``:
    uma única fonte de verdade. O script CLI e esta stack instalam EXATAMENTE a
    mesma coisa — o aluno compara os dois caminhos sem divergência.
"""

from __future__ import annotations

import base64
import gzip
from pathlib import Path

from aws_cdk import CfnOutput, CfnTag, Fn, Stack
from aws_cdk import aws_ec2 as ec2
from constructs import Construct

# AMI Amazon Linux 2023 x86_64 (us-east-1). É o id mais recente no momento da
# escrita; troque com `ami_id=` se sua região/data diferir (o launch-academy.sh
# resolve isso dinamicamente via describe-images).
DEFAULT_AMI = "ami-00948338a4aeec604"

_HERE = Path(__file__).resolve()
_INFRA = _HERE.parents[2]                 # .../infra
_REPO = _HERE.parents[3]                  # raiz do repositório
_SERVERS = _INFRA / "servers"
_FRONT_HTML = _REPO / "frontend" / "index.html"


def _body(path: Path) -> str:
    """Conteúdo de um user-data ``.sh`` SEM a linha do shebang (vamos prefixar
    nossas próprias linhas de ``export`` antes do corpo)."""
    return path.read_text(encoding="utf-8").split("\n", 1)[1]


class ComputeStack(Stack):
    """Três EC2 (API, Frontend, Grafana) na VPC da NetworkStack."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        vpc: ec2.IVpc,
        ami_id: str = DEFAULT_AMI,
        admin_password: str = "admin#123",
        secret_key: str = "demo-troque-em-producao",
        db: object | None = None,
        db_secret_name: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # --- Security group único: 22 (ssh), 80 (front), 3000 (grafana),
        #     8000 (api). Demo => aberto à internet. Criar SG é permitido no
        #     Academy (não é IAM). ----------------------------------------------
        sg = ec2.SecurityGroup(
            self,
            "DemoSg",
            vpc=vpc,
            allow_all_outbound=True,
            description="CloudTask demo (Aula 12): ssh/front/grafana/api",
        )
        for port in (22, 80, 3000, 8000):
            sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(port))

        subnet_id = vpc.public_subnets[0].subnet_id

        def make(name: str, itype: str, script: str) -> ec2.CfnInstance:
            return ec2.CfnInstance(
                self,
                name,
                image_id=ami_id,
                instance_type=itype,
                key_name="vockey",
                iam_instance_profile="LabInstanceProfile",
                subnet_id=subnet_id,
                security_group_ids=[sg.security_group_id],
                user_data=Fn.base64(script),
                tags=[
                    CfnTag(key="Name", value=name),
                    CfnTag(key="project", value="cloudtask-demo"),
                ],
            )

        # --- API ------------------------------------------------------------
        api_head = (
            "#!/bin/bash\n"
            f"export ADMIN_PASSWORD='{admin_password}'\n"
            f"export SECRET_KEY='{secret_key}'\n"
        )
        if db_secret_name:
            # Produção: pega a credencial do RDS no Secrets Manager (a instância
            # usa a LabRole, que tem secretsmanager:GetSecretValue) e monta a
            # DATABASE_URL. Com ela setada, o userdata-api.sh NÃO sobe Postgres
            # local — conecta no RDS.
            api_head += (
                "dnf install -y jq\n"
                f"SEC=$(aws secretsmanager get-secret-value --secret-id {db_secret_name} "
                "--query SecretString --output text)\n"
                'export DATABASE_URL="postgresql+psycopg2://'
                '$(echo "$SEC"|jq -r .username):$(echo "$SEC"|jq -r .password)@'
                '$(echo "$SEC"|jq -r .host):$(echo "$SEC"|jq -r .port)/'
                '$(echo "$SEC"|jq -r .dbname)"\n'
            )
        api = make("cloudtask-api", "t3.small", api_head + _body(_SERVERS / "userdata-api.sh"))

        # Se há RDS, libera o acesso da API ao banco (porta 5432 no SG do RDS).
        if db is not None and hasattr(db, "connections"):
            db.connections.allow_default_port_from(sg, "API EC2 -> RDS")

        # --- Frontend (HTML embutido + URL da API por token) ----------------
        html_b64 = base64.b64encode(
            gzip.compress(_FRONT_HTML.read_bytes(), mtime=0)  # mtime=0 => synth estável
        ).decode()
        front_script = (
            "#!/bin/bash\n"
            "set -xe\n"
            "dnf install -y nginx\n"
            "cat > /tmp/site.gz.b64 <<'B64'\n"
            f"{html_b64}\n"
            "B64\n"
            "base64 -d /tmp/site.gz.b64 | gunzip > /usr/share/nginx/html/index.html\n"
            f"sed -i 's#__API_BASE__#http://{api.attr_public_dns_name}:8000#' "
            "/usr/share/nginx/html/index.html\n"
            "systemctl enable --now nginx\n"
        )
        front = make("cloudtask-frontend", "t3.micro", front_script)

        # --- Grafana (dashboard embutido em base64) -------------------------
        dash_b64 = base64.b64encode(
            (_SERVERS / "grafana-dashboard.json").read_bytes()
        ).decode()
        graf_head = (
            "#!/bin/bash\n"
            f"export ADMIN_PASSWORD='{admin_password}'\n"
            f"export REGION='{self.region}'\n"
            f"export DASH_B64='{dash_b64}'\n"
        )
        graf = make(
            "cloudtask-grafana", "t3.small",
            graf_head + _body(_SERVERS / "userdata-grafana.sh"),
        )

        # --- Saídas (links prontos) -----------------------------------------
        CfnOutput(self, "FrontendUrl", value=f"http://{front.attr_public_ip}/",
                  description="Abra este link (SPA). Login: admin / admin#123")
        CfnOutput(self, "ApiUrl", value=f"http://{api.attr_public_ip}:8000/docs",
                  description="Swagger da API")
        CfnOutput(self, "GrafanaUrl", value=f"http://{graf.attr_public_ip}:3000/",
                  description="Grafana (admin / admin#123)")
