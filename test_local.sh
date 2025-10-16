#!/bin/bash
# Script pour tester le crawler localement

echo "🚀 Test Local du Crawler v2.1.1"
echo "================================"
echo ""

# Vérifier si le serveur tourne déjà
if lsof -Pi :8080 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "✅ Serveur déjà en cours sur le port 8080"
    echo ""
else
    echo "⚠️  Serveur non démarré. Lancez-le dans un autre terminal avec:"
    echo "   uvicorn app:app --host 0.0.0.0 --port 8080"
    echo ""
    read -p "Voulez-vous le démarrer maintenant en arrière-plan? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🚀 Démarrage du serveur..."
        uvicorn app:app --host 0.0.0.0 --port 8080 > /tmp/crawler_server.log 2>&1 &
        SERVER_PID=$!
        echo "✅ Serveur démarré (PID: $SERVER_PID)"
        echo "📝 Logs: /tmp/crawler_server.log"
        sleep 3
    else
        exit 1
    fi
fi

echo "🧪 Tests disponibles:"
echo ""
echo "1. Test simple (GET) - Site statique"
echo "2. Test complet (POST) - Site JavaScript (eratos.ch)"
echo "3. Test anti-redondance - Site allemand (planzer.ch)"
echo "4. Custom URL"
echo ""
read -p "Choisissez un test (1-4): " choice

case $choice in
    1)
        echo ""
        echo "📡 Test GET sur example.com..."
        echo ""
        curl -s "http://localhost:8080/crawl?url=https://example.com&depth=0&max_pages=1" | head -50
        ;;
    2)
        echo ""
        echo "📡 Test POST sur eratos.ch (JavaScript rendering)..."
        echo ""
        curl -X POST http://localhost:8080/crawl \
          -H 'Content-Type: application/json' \
          -d '{
            "url": "https://www.eratos.ch",
            "depth": 1,
            "max_pages": 3,
            "timeout": 25.0,
            "use_js_rendering": true
          }' | head -100
        ;;
    3)
        echo ""
        echo "📡 Test POST sur planzer.ch (Anti-redondance)..."
        echo ""
        curl -X POST http://localhost:8080/crawl \
          -H 'Content-Type: application/json' \
          -d '{
            "url": "https://www.planzer.ch",
            "depth": 1,
            "max_pages": 2,
            "timeout": 20.0
          }' | head -100
        ;;
    4)
        echo ""
        read -p "Entrez l'URL à crawler: " url
        read -p "Nombre de pages max (défaut: 3): " max_pages
        max_pages=${max_pages:-3}
        
        echo ""
        echo "📡 Test POST sur $url..."
        echo ""
        curl -X POST http://localhost:8080/crawl \
          -H 'Content-Type: application/json' \
          -d "{
            \"url\": \"$url\",
            \"depth\": 1,
            \"max_pages\": $max_pages,
            \"timeout\": 20.0,
            \"use_js_rendering\": true
          }" | head -100
        ;;
    *)
        echo "❌ Choix invalide"
        exit 1
        ;;
esac

echo ""
echo ""
echo "================================"
echo "✅ Test terminé!"
echo ""
echo "💡 Pour arrêter le serveur:"
echo "   kill \$(lsof -t -i:8080)"

