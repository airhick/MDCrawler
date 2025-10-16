#!/bin/bash

SERVICE_URL="https://n8n.goreview.fr/webhook/2309b53e-735f-4103-9988-dabb68366dab"

echo "🚀 Waiting for Railway Dockerfile Build"
echo "========================================"
echo ""
echo "⏳ Initial wait: 3 minutes for Docker build to start..."
sleep 180

echo ""
echo "🔍 Starting health checks..."
echo ""

for i in {1..15}; do
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Attempt $i/15 - $(date +%H:%M:%S)"
    echo ""
    
    # Test 1: Health endpoint
    echo "1️⃣  Testing health endpoint..."
    HEALTH=$(curl -s "$SERVICE_URL/")
    
    if [ ! -z "$HEALTH" ]; then
        echo "✅ Health: $HEALTH"
        
        # Test 2: Simple crawl
        echo ""
        echo "2️⃣  Testing simple crawl (example.com)..."
        SIMPLE_RESULT=$(curl -s "${SERVICE_URL}?url=https://example.com&max_pages=1&use_js_rendering=false")
        SIMPLE_LEN=${#SIMPLE_RESULT}
        
        if [ $SIMPLE_LEN -gt 100 ]; then
            echo "✅ Simple crawl works! ($SIMPLE_LEN chars)"
            echo ""
            echo "Preview:"
            echo "$SIMPLE_RESULT" | head -c 300
            echo ""
            echo "..."
            
            # Test 3: JavaScript crawl
            echo ""
            echo "3️⃣  Testing JavaScript crawl (eratos.ch)..."
            JS_RESULT=$(curl -s "${SERVICE_URL}?url=https://www.eratos.ch/&max_pages=3&timeout=30")
            JS_LEN=${#JS_RESULT}
            
            echo "JS crawl result: $JS_LEN chars"
            
            if [ $JS_LEN -gt 1000 ]; then
                echo "✅ JavaScript crawl works! ($JS_LEN chars)"
                echo ""
                echo "Preview:"
                echo "$JS_RESULT" | head -c 400
                echo ""
                echo ""
                echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                echo "🎉 ALL TESTS PASSED!"
                echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                echo ""
                echo "✅ Health endpoint: Working"
                echo "✅ Simple crawl: Working ($SIMPLE_LEN chars)"
                echo "✅ JavaScript crawl: Working ($JS_LEN chars)"
                echo ""
                echo "🚀 Ready to use with n8n!"
                exit 0
            else
                echo "⚠️  JS crawl returned short content ($JS_LEN chars)"
                echo "Preview: $JS_RESULT" | head -c 200
                echo ""
                echo "This might mean:"
                echo "  - Chromium not installed yet"
                echo "  - Still building"
                echo "  - Timeout (try increasing)"
            fi
        else
            echo "⚠️  Simple crawl failed or returned short content ($SIMPLE_LEN chars)"
        fi
    else
        echo "⏳ Service not ready (empty response)"
    fi
    
    echo ""
    if [ $i -lt 15 ]; then
        echo "Waiting 30s before next attempt..."
        echo ""
        sleep 30
    fi
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "⏱️  Timeout after 15 attempts"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "The build might still be in progress."
echo ""
echo "Check Railway logs:"
echo "  railway logs --tail 50"
echo ""
echo "Or check Railway dashboard:"
echo "  https://railway.app/"
echo ""
echo "Look for:"
echo "  ✅ 'Using Detected Dockerfile'"
echo "  ✅ 'Installing Chromium'"
echo "  ✅ 'Deployment live'"

