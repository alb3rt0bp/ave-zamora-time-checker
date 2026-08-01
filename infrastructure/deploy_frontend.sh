#!/usr/bin/env bash
# deploy_frontend.sh — Compila el frontend y lo sincroniza al bucket S3 estático
# Requisitos: aws-cli v2, npm, y que ./infrastructure/deploy.sh ya se haya
# ejecutado para ese entorno (necesita los outputs TrainsApiBaseUrl y
# FrontendBucketName del stack).
# Uso: ./infrastructure/deploy_frontend.sh [dev|staging|prod]

set -euo pipefail

ENVIRONMENT="${1:-dev}"
STACK_NAME="zamora-train-observability-${ENVIRONMENT}"
AWS_REGION="${AWS_DEFAULT_REGION:-eu-south-2}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "════════════════════════════════════════════════════════"
echo " Zamora Train Observability — Deploy Frontend"
echo " Stack:      ${STACK_NAME}"
echo " Entorno:    ${ENVIRONMENT}"
echo "════════════════════════════════════════════════════════"

# ── 0. Prerrequisitos ─────────────────────────────────────────────────────────
command -v aws >/dev/null 2>&1 || { echo "Error: aws no encontrado. Instala AWS CLI v2."; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "Error: npm no encontrado. Instala Node.js."; exit 1; }

# ── 1. Leer outputs del stack (debe existir: ejecutar deploy.sh primero) ─────
echo ""
echo ">>> Paso 1: Leyendo outputs del stack ${STACK_NAME}..."

API_BASE_URL="$(aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --region "${AWS_REGION}" \
    --query "Stacks[0].Outputs[?OutputKey=='TrainsApiBaseUrl'].OutputValue" \
    --output text 2>/dev/null || true)"

FRONTEND_BUCKET_NAME="$(aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --region "${AWS_REGION}" \
    --query "Stacks[0].Outputs[?OutputKey=='FrontendBucketName'].OutputValue" \
    --output text 2>/dev/null || true)"

if [ -z "${API_BASE_URL}" ] || [ -z "${FRONTEND_BUCKET_NAME}" ]; then
    echo "Error: no se encontraron los outputs del stack '${STACK_NAME}'."
    echo "       Ejecuta primero ./infrastructure/deploy.sh ${ENVIRONMENT}"
    exit 1
fi

echo "    API base URL:      ${API_BASE_URL}"
echo "    Frontend bucket:   ${FRONTEND_BUCKET_NAME}"

# ── 2. Instalar dependencias ──────────────────────────────────────────────────
echo ""
echo ">>> Paso 2: npm ci..."
(cd "${REPO_ROOT}/frontend" && npm ci)

# ── 3. Build con la URL del API inyectada ────────────────────────────────────
echo ""
echo ">>> Paso 3: npm run build..."
(cd "${REPO_ROOT}/frontend" && VITE_API_BASE_URL="${API_BASE_URL}" npm run build)

# ── 4. Sincronizar a S3 ───────────────────────────────────────────────────────
echo ""
echo ">>> Paso 4: aws s3 sync..."
aws s3 sync "${REPO_ROOT}/frontend/dist/" "s3://${FRONTEND_BUCKET_NAME}/" --delete

# ── 5. Mostrar la URL del sitio ────────────────────────────────────────────────
echo ""
echo ">>> Paso 5: URL del frontend:"
aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --region "${AWS_REGION}" \
    --query "Stacks[0].Outputs[?OutputKey=='FrontendWebsiteUrl'].OutputValue" \
    --output text

echo ""
echo "✅ Frontend desplegado."
