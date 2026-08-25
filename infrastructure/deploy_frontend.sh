#!/usr/bin/env bash
# deploy_frontend.sh — Compila el frontend y lo sincroniza al bucket S3 estático
# Requisitos: aws-cli v2, npm, y que ./infrastructure/deploy.sh ya se haya
# ejecutado para ese entorno (necesita los outputs ApiBaseUrl,
# FrontendBucketName y FrontendDistributionId del stack).
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
    --query "Stacks[0].Outputs[?OutputKey=='ApiBaseUrl'].OutputValue" \
    --output text 2>/dev/null || true)"

FRONTEND_BUCKET_NAME="$(aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --region "${AWS_REGION}" \
    --query "Stacks[0].Outputs[?OutputKey=='FrontendBucketName'].OutputValue" \
    --output text 2>/dev/null || true)"

FRONTEND_DISTRIBUTION_ID="$(aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --region "${AWS_REGION}" \
    --query "Stacks[0].Outputs[?OutputKey=='FrontendDistributionId'].OutputValue" \
    --output text 2>/dev/null || true)"

if [ -z "${API_BASE_URL}" ] || [ -z "${FRONTEND_BUCKET_NAME}" ] || [ -z "${FRONTEND_DISTRIBUTION_ID}" ]; then
    echo "Error: no se encontraron los outputs del stack '${STACK_NAME}'."
    echo "       Ejecuta primero ./infrastructure/deploy.sh ${ENVIRONMENT}"
    exit 1
fi

echo "    API base URL:      ${API_BASE_URL}"
echo "    Frontend bucket:   ${FRONTEND_BUCKET_NAME}"
echo "    CloudFront dist.:  ${FRONTEND_DISTRIBUTION_ID}"

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

# ── 5. Invalidar caché de CloudFront ─────────────────────────────────────────
# Necesario porque el bucket ahora es privado y se sirve vía CloudFront: sin
# invalidar, los visitantes seguirían viendo los ficheros cacheados del
# deploy anterior hasta que expire el TTL de CachingOptimized.
echo ""
echo ">>> Paso 5: Invalidando caché de CloudFront..."
aws cloudfront create-invalidation \
    --distribution-id "${FRONTEND_DISTRIBUTION_ID}" \
    --paths "/*" \
    --query "Invalidation.Id" \
    --output text

# ── 6. Mostrar la URL del sitio ────────────────────────────────────────────────
echo ""
echo ">>> Paso 6: URL del frontend:"
aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --region "${AWS_REGION}" \
    --query "Stacks[0].Outputs[?OutputKey=='FrontendCustomDomainUrl' || OutputKey=='FrontendDistributionDomainName'].OutputValue" \
    --output text

echo ""
echo "✅ Frontend desplegado."
