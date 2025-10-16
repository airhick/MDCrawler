#!/bin/bash
# Script pour vérifier le déploiement Railway

echo "🚂 Vérification du déploiement Railway"
echo "========================================"
echo ""

WEBHOOK_URL="https://n8n.goreview.fr/webhook/2309b53e-735f-4103-9988-dabb68366dab"
TEST_URL="https://www.eratos.ch/"

echo "📊 Derniers commits pushés:"
git log --oneline -3
echo ""

echo "🔍 Test du webhook Railway..."
echo "URL: ${WEBHOOK_URL}?url=${TEST_URL}"
echo ""

# Test simple d'abord (health check via redirect)
echo "1️⃣ Test de connectivité..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${WEBHOOK_URL}")
echo "   Status code: ${HTTP_CODE}"

if [ "$HTTP_CODE" = "000" ]; then
    echo "   ❌ Serveur inaccessible - Railway est peut-être en train de redéployer"
    echo ""
    echo "💡 Vérifiez le dashboard Railway:"
    echo "   https://railway.app/"
    echo ""
    exit 1
fi

echo ""
echo "2️⃣ Test du crawler (cela peut prendre 15-30 secondes)..."
echo ""

# Test complet avec timeout
RESPONSE=$(curl -s --max-time 60 "${WEBHOOK_URL}?url=${TEST_URL}")

# Compter le nombre de caractères
CHAR_COUNT=$(echo "$RESPONSE" | wc -c | tr -d ' ')

echo "📊 Résultat:"
echo "   Caractères: $CHAR_COUNT"
echo ""

if [ "$CHAR_COUNT" -lt 100 ]; then
    echo "❌ ÉCHEC: Contenu trop court (< 100 chars)"
    echo ""
    echo "Contenu reçu:"
    echo "---"
    echo "$RESPONSE"
    echo "---"
    echo ""
    echo "🔍 Problèmes possibles:"
    echo "   - Build Railway encore en cours"
    echo "   - Playwright non installé correctement"
    echo "   - Timeout du serveur"
    echo ""
    echo "💡 Actions:"
    echo "   1. Vérifiez les logs Railway: railway logs"
    echo "   2. Attendez la fin du build (3-5 min)"
    echo "   3. Relancez ce script"
    exit 1
elif [ "$CHAR_COUNT" -lt 5000 ]; then
    echo "⚠️  PARTIEL: Contenu présent mais incomplet"
    echo "   Attendu: ~8,915 chars"
    echo "   Reçu: $CHAR_COUNT chars"
    echo ""
    echo "Preview (100 premiers chars):"
    echo "$RESPONSE" | head -c 100
    echo ""
    echo "..."
else
    echo "✅ SUCCÈS: Contenu complet récupéré!"
    echo ""
    echo "Preview (200 premiers chars):"
    echo "---"
    echo "$RESPONSE" | head -c 200
    echo "..."
    echo "---"
    echo ""
    echo "📁 Sauvegarder le résultat complet?"
    read -p "   (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        OUTPUT_FILE="railway_test_$(date +%Y%m%d_%H%M%S).md"
        echo "$RESPONSE" > "$OUTPUT_FILE"
        echo "   ✅ Sauvegardé dans: $OUTPUT_FILE"
        echo "   Taille: $(wc -c < "$OUTPUT_FILE") bytes"
    fi
fi

echo ""
echo "================================"
echo "🎉 Railway Crawler v2.1.1 opérationnel!"
echo ""
echo "🔗 Votre webhook:"
echo "   ${WEBHOOK_URL}?url=<URL_A_CRAWLER>"
echo ""
echo "📝 Exemples d'utilisation:"
echo ""
echo "GET simple:"
echo "   curl '${WEBHOOK_URL}?url=https://example.com&max_pages=3'"
echo ""
echo "POST avec options:"
echo "   curl -X POST ${WEBHOOK_URL%\?*} \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"url\": \"https://example.com\", \"depth\": 1, \"max_pages\": 5}'"

