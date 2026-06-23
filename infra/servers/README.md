# `infra/servers/` — três servidores EC2 (API + Frontend + Grafana)

Sobe a aplicação como em produção, com cada peça num **EC2 separado** na AWS
(Academy/Learner Lab ou conta própria). Há **dois caminhos** para o mesmo
resultado — eles compartilham os scripts de `user-data` deste diretório:

* **Script CLI** → `launch-academy.sh` (aqui). Rápido, na VPC default.
* **IaC (CDK)** → a `ComputeStack` em [`../cdk/stacks/compute_stack.py`](../cdk/stacks/compute_stack.py),
  que lê estes mesmos `.sh` como `user-data`.

Tutorial passo a passo na [prática 19](../../docs/praticas/19-servidores-ec2-grafana.md).

## Arquivos

| Arquivo | Papel |
| --- | --- |
| `userdata-api.sh` | Boot da API: Docker + (Postgres local **ou** RDS) + a imagem `prod`. :8000 |
| `userdata-grafana.sh` | Boot do Grafana: datasource CloudWatch + dashboard provisionado. :3000 |
| `grafana-dashboard.json` | Dashboard (CPU/rede dos EC2, DynamoDB, RDS). Fonte única — embutido no boot. |
| `launch-academy.sh` | Cria o security group e sobe os 3 EC2 (frontend recebe a URL da API). |
| `destroy-academy.sh` | Termina os 3 EC2 (tag `project=cloudtask-demo`) e apaga o security group. |

> O `user-data` do **frontend** é gerado pelo `launch-academy.sh`: ele instala o
> nginx e injeta o `frontend/index.html` (comprimido em base64) já com a URL
> pública da API. Não há `.sh` separado para ele.

## Uso rápido

```bash
# subir (na raiz do repo, com o Learner Lab iniciado)
bash infra/servers/launch-academy.sh
# ...abra o link "Frontend" impresso no fim. Login: admin / admin#123

# derrubar (SEMPRE ao terminar)
bash infra/servers/destroy-academy.sh
```

## Variáveis úteis (todas têm default)

| Variável | Default | Onde |
| --- | --- | --- |
| `REGION` | `us-east-1` | launch/destroy |
| `KEY_NAME` | `vockey` | par de chaves SSH (o do Academy) |
| `PROFILE_NAME` | `LabInstanceProfile` | instance profile (role do lab) |
| `ADMIN_PASSWORD` | `admin#123` | senha do app/API e do Grafana |
| `DATABASE_URL` | *(vazio)* | se setada no `userdata-api.sh`, usa esse banco (ex.: RDS) e **não** sobe Postgres local |

> ⚠️ **Custo:** os EC2 são baratos e sem NAT. Se você usar o RDS (caminho CDK),
> ele cobra por hora — destrua ao terminar.
