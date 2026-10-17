#!/usr/bin/env bash
# ==============================================================================
# FlytBase Asset Intelligence Copilot - DigitalOcean Production Deployment Script
# ==============================================================================
set -euo pipefail

echo "========================================================================"
echo " FlytBase Asset Intelligence Copilot - DigitalOcean Deployment"
echo "========================================================================"

APP_NAME="flytbase-asset-intelligence-copilot"
SPEC_FILE=".do/app.yaml"

# 1. Check for doctl installation
if ! command -v doctl &> /dev/null; then
    echo "⚠️  'doctl' is not installed or not in PATH."
    echo "    To install doctl: brew install doctl (macOS) or see https://docs.digitalocean.com/reference/doctl/how-to/install/"
    echo "    Alternatively, deploy directly from GitHub via the DigitalOcean Cloud Console."
    exit 1
fi

# 2. Check doctl authentication
echo "🔍 Checking DigitalOcean authentication..."
if ! doctl auth init --check &> /dev/null; then
    echo "❌ doctl is not authenticated. Run: doctl auth init"
    exit 1
fi

echo "✅ Authenticated with DigitalOcean."

# 3. Check if app already exists
echo "🔍 Checking for existing App Platform app: ${APP_NAME}..."
APP_ID=$(doctl apps list --format ID,Spec.Name --no-header | awk -v name="$APP_NAME" '$2 == name {print $1}' || true)

if [ -n "$APP_ID" ]; then
    echo "🔄 Existing app found with ID: ${APP_ID}. Updating application spec..."
    doctl apps update "$APP_ID" --spec "$SPEC_FILE"
    echo "🚀 App update initiated for ID: ${APP_ID}"
else
    echo "✨ Creating new App Platform deployment using ${SPEC_FILE}..."
    APP_ID=$(doctl apps create --spec "$SPEC_FILE" --format ID --no-header)
    echo "🎉 New application created with ID: ${APP_ID}"
fi

# 4. Monitor deployment
echo "⏳ Monitoring deployment progress..."
doctl apps get "$APP_ID" --format ID,DefaultIngress,ActiveDeployment.Phase

echo "========================================================================"
echo " Deployment submitted to DigitalOcean App Platform!"
echo " Monitor live logs via: doctl apps logs ${APP_ID} --follow"
echo "========================================================================"
