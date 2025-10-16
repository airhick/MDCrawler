#!/bin/bash
# Quick deployment script for Railway

echo "🚂 Deploying Crawler v2.1.1 to Railway"
echo "========================================"
echo ""

# Check if we're in the right directory
if [ ! -f "app.py" ]; then
    echo "❌ Error: app.py not found. Are you in the crawler directory?"
    exit 1
fi

echo "📦 Files to deploy:"
echo "  - app.py (crawler)"
echo "  - Dockerfile (with Playwright support)"
echo "  - requirements.txt (all dependencies)"
echo ""

echo "🔍 Checking git status..."
git status --short

echo ""
echo "📝 Adding files to git..."
git add Dockerfile requirements.txt app.py .dockerignore

echo ""
echo "💾 Committing changes..."
git commit -m "feat: Add Playwright support for production JS rendering

- Updated Dockerfile with Chromium dependencies
- Added anti-redundancy system (v2.1.1)
- Improved navigation filtering (50+ patterns)
- Ready for Railway deployment"

echo ""
echo "🚀 Pushing to Railway..."
git push origin main

echo ""
echo "✅ Deployment initiated!"
echo ""
echo "⏱️  Build will take 3-5 minutes (Chromium installation)"
echo ""
echo "📊 Monitor deployment:"
echo "  - Railway Dashboard: https://railway.app/"
echo "  - Build logs: railway logs"
echo ""
echo "🧪 Test after deployment:"
echo "  curl 'https://n8n.goreview.fr/webhook/2309b53e-735f-4103-9988-dabb68366dab?url=https://www.eratos.ch/'"
echo ""
echo "Expected: ~8,915 characters with full content ✅"

