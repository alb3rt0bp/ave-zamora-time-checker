#!/usr/bin/env bash
# deploy.sh — Despliega el stack completo con AWS SAM
# Requisitos: aws-cli v2, sam-cli, Python 3.12, permisos de despliegue en AWS
# Uso: ./infrastructure/deploy.sh [dev|staging|prod] [--alert-email tu@email.com]
#        [--domain zamorave.com --hosted-zone-id Z... --certificate-arn arn:aws:acm:us-east-1:...]
# Los tres flags de dominio son opcionales pero van juntos (ver
# infrastructure/DOMAIN_SETUP.md para obtener hosted-zone-id y certificate-arn,
# ninguno de los dos automatizable desde este script).

set -euo pipefail

ENVIRONMENT="dev"
ALERT_EMAIL=""
DOMAIN_NAME=""
HOSTED_ZONE_ID=""
CERTIFICATE_ARN=""

while [ $# -gt 0 ]; do
    case "$1" in
        --alert-email)
            ALERT_EMAIL="${2:-}"
            shift 2
            ;;
        --domain)
            DOMAIN_NAME="${2:-}"
            shift 2
            ;;
        --hosted-zone-id)
            HOSTED_ZONE_ID="${2:-}"
            shift 2
            ;;
        --certificate-arn)
            CERTIFICATE_ARN="${2:-}"
            shift 2
            ;;
        *)
            ENVIRONMENT="$1"
            shift
            ;;
    esac
done

if [ -n "${DOMAIN_NAME}" ] && { [ -z "${HOSTED_ZONE_ID}" ] || [ -z "${CERTIFICATE_ARN}" ]; }; then
    echo "Error: --domain requiere también --hosted-zone-id y --certificate-arn."
    echo "  Ver infrastructure/DOMAIN_SETUP.md para obtenerlos (registro del"
    echo "  dominio + despliegue de infrastructure/certificate-us-east-1.yaml,"
    echo "  ninguno de los dos automatizable desde este script)."
    exit 1
fi

STACK_NAME="zamora-train-observability-${ENVIRONMENT}"
AWS_REGION="${AWS_DEFAULT_REGION:-eu-south-2}"   # España (Zaragoza)
SAM_S3_BUCKET="sam-deployment-$(aws sts get-caller-identity --query Account --output text)-${AWS_REGION}"

echo "════════════════════════════════════════════════════════"
echo " Zamora Train Observability — Deploy"
echo " Stack:      ${STACK_NAME}"
echo " Región:     ${AWS_REGION}"
echo " Entorno:    ${ENVIRONMENT}"
echo "════════════════════════════════════════════════════════"

# ── 0. Prerrequisitos ─────────────────────────────────────────────────────────
command -v sam  >/dev/null 2>&1 || { echo "Error: sam no encontrado. Instala AWS SAM CLI."; exit 1; }
command -v aws  >/dev/null 2>&1 || { echo "Error: aws no encontrado. Instala AWS CLI v2.";  exit 1; }

# ── 1. Compilar horarios desde CSVs ──────────────────────────────────────────
echo ""
echo ">>> Paso 1: Compilando horarios desde CSVs..."
python3 scripts/compile_schedules.py

# Copiar el JSON compilado a la Lambda para que se empaquete
cp config/train_schedules.json lambdas/train_tracker/train_schedules.json

# ── 2. Crear bucket S3 para artefactos SAM si no existe ──────────────────────
echo ""
echo ">>> Paso 2: Verificando bucket SAM deployment..."
aws s3api head-bucket --bucket "${SAM_S3_BUCKET}" 2>/dev/null || \
    aws s3api create-bucket \
        --bucket "${SAM_S3_BUCKET}" \
        --region "${AWS_REGION}" \
        --create-bucket-configuration LocationConstraint="${AWS_REGION}"

# ── 3. Build SAM ──────────────────────────────────────────────────────────────
echo ""
echo ">>> Paso 3: SAM build..."
sam build \
    --template-file infrastructure/template.yaml \
    --use-container \
    --parallel

# ── 4. Deploy SAM ─────────────────────────────────────────────────────────────
echo ""
echo ">>> Paso 4: SAM deploy..."

PARAMS="Environment=${ENVIRONMENT} AwsRegion=${AWS_REGION} ZamoraStationCode=30200 PollingWindowMinutes=30"
if [ -n "${ALERT_EMAIL}" ]; then
    PARAMS="${PARAMS} AlertEmailAddress=${ALERT_EMAIL}"
fi
if [ -n "${DOMAIN_NAME}" ]; then
    PARAMS="${PARAMS} DomainName=${DOMAIN_NAME} HostedZoneId=${HOSTED_ZONE_ID} FrontendCertificateArn=${CERTIFICATE_ARN}"
fi

sam deploy \
    --template-file .aws-sam/build/template.yaml \
    --stack-name "${STACK_NAME}" \
    --s3-bucket "${SAM_S3_BUCKET}" \
    --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
    --region "${AWS_REGION}" \
    --parameter-overrides ${PARAMS} \
    --no-confirm-changeset \
    --no-fail-on-empty-changeset

# ── 5. Mostrar outputs ────────────────────────────────────────────────────────
echo ""
echo ">>> Paso 5: Outputs del stack:"
aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --query "Stacks[0].Outputs[*].[OutputKey,OutputValue]" \
    --output table

echo ""
echo "✅ Despliegue completado. Dashboard disponible en CloudWatch."
echo "   Para consultar datos: aws athena start-query-execution \\"
echo "     --query-string \"SELECT * FROM zamora_trains LIMIT 10\" \\"
echo "     --work-group zamora-trains-${ENVIRONMENT}"
