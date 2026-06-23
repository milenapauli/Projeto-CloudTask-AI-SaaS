#!/usr/bin/env bash
# =============================================================================
# launch-academy.sh — sobe os 3 servidores (API, Frontend, Grafana) no AWS
# Academy/Learner Lab usando SOMENTE a AWS CLI (sem CDK, sem CloudFormation).
# -----------------------------------------------------------------------------
# É o caminho "rápido e didático": cada servidor é um EC2 na VPC default, com o
# LabInstanceProfile já existente (a role do laboratório) — por isso nada de
# criar IAM. O frontend recebe, no boot, a URL pública da API.
#
#   API      : EC2 t3.small  — Docker (Postgres + API)        porta 8000
#   Frontend : EC2 t3.micro  — nginx servindo o SPA           porta 80
#   Grafana  : EC2 t3.small  — Grafana + datasource CloudWatch porta 3000
#
# USO (com o Learner Lab "Start" e as credenciais já no ~/.aws):
#   bash infra/servers/launch-academy.sh
#
# Derrubar tudo depois:  bash infra/servers/destroy-academy.sh
#
# Pré-requisitos: aws cli, gzip e base64 no PATH (Git Bash no Windows já tem).
# =============================================================================
set -euo pipefail

REGION="${REGION:-us-east-1}"
KEY_NAME="${KEY_NAME:-vockey}"
PROFILE_NAME="${PROFILE_NAME:-LabInstanceProfile}"
SG_NAME="${SG_NAME:-cloudtask-demo-sg}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin#123}"
SECRET_KEY="${SECRET_KEY:-demo-troque-em-producao}"
TAG="cloudtask-demo"
HERE="$(cd "$(dirname "$0")" && pwd)"
FRONT_HTML="$HERE/../../frontend/index.html"

echo "==> Região: $REGION"

# --- AMI Amazon Linux 2023 (mais recente) ------------------------------------
AMI=$(aws ec2 describe-images --region "$REGION" --owners amazon \
  --filters "Name=name,Values=al2023-ami-2023.*-kernel-6.1-x86_64" "Name=state,Values=available" \
  --query 'reverse(sort_by(Images,&CreationDate))[0].ImageId' --output text)
echo "==> AMI AL2023: $AMI"

# --- VPC default + subnet pública --------------------------------------------
VPC=$(aws ec2 describe-vpcs --region "$REGION" --filters Name=isDefault,Values=true \
  --query 'Vpcs[0].VpcId' --output text)
SUBNET=$(aws ec2 describe-subnets --region "$REGION" \
  --filters Name=vpc-id,Values="$VPC" Name=default-for-az,Values=true \
  --query 'Subnets[0].SubnetId' --output text)
echo "==> VPC: $VPC  Subnet: $SUBNET"

# --- Security Group (reaproveita se já existir) ------------------------------
SG=$(aws ec2 describe-security-groups --region "$REGION" \
  --filters Name=group-name,Values="$SG_NAME" Name=vpc-id,Values="$VPC" \
  --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || echo "None")
if [ "$SG" = "None" ] || [ -z "$SG" ]; then
  SG=$(aws ec2 create-security-group --region "$REGION" --group-name "$SG_NAME" \
    --description "CloudTask demo (Aula 12)" --vpc-id "$VPC" --query 'GroupId' --output text)
  for p in 22 80 3000 8000; do
    aws ec2 authorize-security-group-ingress --region "$REGION" --group-id "$SG" \
      --protocol tcp --port "$p" --cidr 0.0.0.0/0 >/dev/null
  done
  echo "==> SG criado: $SG (22,80,3000,8000)"
else
  echo "==> SG reaproveitado: $SG"
fi

# file:// que a AWS CLI lê em qualquer SO. No Git Bash (Windows) a CLI é nativa
# e não entende paths MSYS (/tmp/...); o cygpath converte para F:/... .
udurl () {
  if command -v cygpath >/dev/null 2>&1; then echo "file://$(cygpath -m "$1")"; else echo "file://$1"; fi
}

run_instance () {  # $1=name $2=type $3=userdata-file
  aws ec2 run-instances --region "$REGION" \
    --image-id "$AMI" --instance-type "$2" --key-name "$KEY_NAME" \
    --iam-instance-profile "Name=$PROFILE_NAME" \
    --security-group-ids "$SG" --subnet-id "$SUBNET" --associate-public-ip-address \
    --user-data "$(udurl "$3")" \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$1},{Key=project,Value=$TAG}]" \
    --query 'Instances[0].InstanceId' --output text
}

# --- API ---------------------------------------------------------------------
UD_API="$(mktemp)"
{
  echo '#!/bin/bash'
  echo "export ADMIN_PASSWORD='$ADMIN_PASSWORD'"
  echo "export SECRET_KEY='$SECRET_KEY'"
  tail -n +2 "$HERE/userdata-api.sh"
} > "$UD_API"
API_ID=$(run_instance cloudtask-api t3.small "$UD_API")
echo "==> API instance: $API_ID (aguardando IP público...)"
aws ec2 wait instance-running --region "$REGION" --instance-ids "$API_ID"
API_DNS=$(aws ec2 describe-instances --region "$REGION" --instance-ids "$API_ID" \
  --query 'Reservations[0].Instances[0].PublicDnsName' --output text)
echo "==> API DNS: $API_DNS"

# --- Frontend (recebe a URL da API e o HTML embutido) ------------------------
HTML_B64=$(gzip -c "$FRONT_HTML" | base64 -w0)
UD_FRONT="$(mktemp)"
cat > "$UD_FRONT" <<FRONT
#!/bin/bash
set -xe
dnf install -y nginx
cat > /tmp/site.gz.b64 <<'B64'
$HTML_B64
B64
base64 -d /tmp/site.gz.b64 | gunzip > /usr/share/nginx/html/index.html
sed -i 's#__API_BASE__#http://$API_DNS:8000#' /usr/share/nginx/html/index.html
systemctl enable --now nginx
echo "frontend up on :80"
FRONT
FRONT_ID=$(run_instance cloudtask-frontend t3.micro "$UD_FRONT")
echo "==> Frontend instance: $FRONT_ID"

# --- Grafana -----------------------------------------------------------------
DASH_B64=$(base64 -w0 "$HERE/grafana-dashboard.json")
UD_GRAF="$(mktemp)"
{
  echo '#!/bin/bash'
  echo "export ADMIN_PASSWORD='$ADMIN_PASSWORD'"
  echo "export REGION='$REGION'"
  echo "export DASH_B64='$DASH_B64'"
  tail -n +2 "$HERE/userdata-grafana.sh"
} > "$UD_GRAF"
GRAF_ID=$(run_instance cloudtask-grafana t3.small "$UD_GRAF")
echo "==> Grafana instance: $GRAF_ID"

# --- IPs públicos finais -----------------------------------------------------
aws ec2 wait instance-running --region "$REGION" --instance-ids "$FRONT_ID" "$GRAF_ID"
get_ip () { aws ec2 describe-instances --region "$REGION" --instance-ids "$1" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' --output text; }
API_IP=$(get_ip "$API_ID"); FRONT_IP=$(get_ip "$FRONT_ID"); GRAF_IP=$(get_ip "$GRAF_ID")

rm -f "$UD_API" "$UD_FRONT" "$UD_GRAF"

cat <<EOF

============================================================
  CloudTask AI SaaS — servidores no ar (leva ~3-5 min p/ bootar)
------------------------------------------------------------
  Frontend (abra este):  http://$FRONT_IP/
  API (Swagger):         http://$API_IP:8000/docs
  Grafana:               http://$GRAF_IP:3000/   (admin / $ADMIN_PASSWORD)

  Login do app:          admin / $ADMIN_PASSWORD
============================================================
EOF
