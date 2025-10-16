#!/bin/bash

echo "🚀 Monitoring Railway Deployment..."
echo "=================================="
echo ""

SERVICE_URL="https://n8n.goreview.fr/webhook/2309b53e-735f-4103-9988-dabb68366dab"
WAIT_TIME=30
MAX_ATTEMPTS=20

echo "📦 Latest commits:"
git log --oneline -3
echo ""

echo "⏳ Waiting ${WAIT_TIME}s for Railway to start rebuild..."
sleep $WAIT_TIME

for i in $(seq 1 $MAX_ATTEMPTS); do
    echo ""
    echo "🔍 Attempt $i/$MAX_ATTEMPTS ($(date +%H:%M:%S))"
    echo "-------------------"
    
    # Test health endpoint
    RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "$SERVICE_URL/" 2>&1)
    
    if [ "$RESPONSE" = "200" ]; then
        echo "✅ Service is UP! (HTTP $RESPONSE)"
        
        # Test actual crawl
        echo ""
        echo "🧪 Testing crawl functionality..."
        CRAWL_RESULT=$(curl -s "${SERVICE_URL}?url=https://example.com&max_pages=1&use_js_rendering=false" | head -c 200)
        
        if [ ! -z "$CRAWL_RESULT" ]; then
            echo "✅ Crawl works! Preview:"
            echo "$CRAWL_RESULT"
            echo ""
            echo "🎉 DEPLOYMENT SUCCESSFUL!"
            echo ""
            echo "🧪 Test with your n8n workflow now!"
            exit 0
        else
            echo "⚠️  Service responds but returns empty content"
        fi
    else
        echo "⏳ Service not ready yet (HTTP $RESPONSE)"
    fi
    
    # Wait before next attempt
    if [ $i -lt $MAX_ATTEMPTS ]; then
        echo "   Waiting 15s before next check..."
        sleep 15
    fi
done

echo ""
echo "❌ Deployment did not complete in time"
echo ""
echo "📊 Check Railway logs manually:"
echo "   https://railway.app/"
echo ""
echo "Or run: railway logs --tail 50"
exit 1

