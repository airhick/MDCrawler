# Voice AI Optimized Crawler v2.1

Service FastAPI exposant un webhook `/crawl` qui prend une URL, explore en largeur (depth réglable), et renvoie un contenu ultra-simplifié et nettoyé en Markdown, optimisé pour la lecture par Voice AI.

## Version 2.1 - Voice AI Optimized 🎙️

**Conçu pour les agents vocaux** qui lisent le contenu à haute voix et l'utilisent comme contexte pour comprendre une entreprise.

### 🎭 **NEW: JavaScript Rendering Support**
- ✅ Crawls modern **React, Vue, Angular, Next.js** sites
- ✅ Auto-detects SPAs and uses **Playwright** (headless browser)
- ✅ Hybrid approach: fast httpx for static sites, browser for JS sites
- ✅ No configuration needed - works automatically

Tested on: eratos.ch (React), and other modern SPAs ✅

### 🧹 **NEW: Advanced Anti-Redundancy** (v2.1.1)
- ✅ **Detects and removes** navigation menu blocks (50+ patterns)
- ✅ **Eliminates** consecutive duplicate lines
- ✅ **Filters** language switchers (DE, FR, IT, EN)
- ✅ **Result**: 90%+ reduction in redundant content

Example: planzer.ch - from 11,613 lines → ~800 lines ✅

### Optimisations Voice AI

**✅ Supprimé (bruit pour la voix)**:
- ❌ En-têtes de rapport statistiques
- ❌ Blocs YAML front-matter
- ❌ Marqueurs de pages (PAGE 1, PAGE 2)
- ❌ Ancres HTML `<a id="...">`
- ❌ Liens Markdown complexes
- ❌ Menus de navigation répétés
- ❌ Titres marketing vides

**✅ Format simplifié**:
- ✅ Contact info en texte simple: `Téléphone: +41 79 136 36 38`
- ✅ Email simple: `Email: contact@example.com`
- ✅ Adresse simple: `Adresse: Route des Jeunes 4, 1227 Les Acacias`
- ✅ Horaires en liste claire
- ✅ Séparateurs simples (`---`) entre pages
- ✅ Déduplication automatique par hash de contenu

### Données Structurées
- ✅ Détection automatique du type de page (home, store, product, category, service, faq, contact, about)
- ✅ Détection de la langue (fr, de, it, en) via HTML, URL et contenu
- ✅ Extraction et normalisation des coordonnées:
  - Emails avec liens `mailto:`
  - Téléphones normalisés E.164 avec liens `tel:`
  - Adresses détectées et normalisées
- ✅ Horaires d'ouverture parsés en tableaux Markdown
- ✅ URLs canoniques extraites
- ✅ Hash de contenu pour déduplication

### Nettoyage & Normalisation
- ✅ Normalisation des espaces, quotes, apostrophes
- ✅ Formatage cohérent des devises (CHF, EUR, USD)
- ✅ Capitalisation correcte des noms de villes suisses
- ✅ Suppression des CTAs dupliqués et slogans isolés
- ✅ Fusion des phrases monosyllabiques isolées

### Rapport de Crawl Enrichi
- ✅ Statistiques complètes (pages, types, langues, doublons)
- ✅ Version du crawler et User-Agent utilisé
- ✅ Horodatage ISO 8601
- ✅ Compteurs par type (magasins, produits, catégories trouvés)
- ✅ Chaque page marquée clairement (PAGE 1, PAGE 2, etc.)
- ✅ URL source en pied de chaque page

## Installation

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Install Playwright browsers (for JS rendering)
python -m playwright install chromium
```

**Note**: Playwright browsers (~300MB) sont requis pour crawler les sites JavaScript modernes (React, Vue, etc.). Pour sites statiques uniquement, vous pouvez sauter cette étape et mettre `use_js_rendering=false`.

## Lancement

```bash
uvicorn app:app --host 0.0.0.0 --port 8080
```

### Docker (déploiement ou exécution serveur)

Build et run en exposant le port publiquement:

```bash
docker build -t crawler-webhook \
  -f "/Users/Eric.AELLEN/Documents/A - projets pro/crawler/1.0/Dockerfile" \
  "/Users/Eric.AELLEN/Documents/A - projets pro/crawler/1.0"

docker run --rm -p 8080:8080 --name crawler-webhook crawler-webhook
```

Vous pouvez ensuite appeler `http://<ip_serveur>:8080/crawl` depuis l'extérieur.

### Render (hébergement managé)

1. Poussez ce dossier dans un repo Git (GitHub/GitLab).
2. Sur Render, créez un nouveau Web Service, connectez le repo.
3. Render détectera `render.yaml` et provisionnera automatiquement.
4. Une URL publique sera fournie, ex: `https://simple-crawler-webhook.onrender.com/crawl`.

### Railway (hébergement managé)

1. Installez l'outil CLI Railway: `npm i -g @railway/cli`.
2. Depuis ce dossier: `railway init` (ou `railway up` pour créer le service).
3. Railway détectera `railway.toml`. Aucune config additionnelle requise.
4. Le service démarre avec: `uvicorn app:app --host 0.0.0.0 --port $PORT`.
5. Une URL publique sera fournie, ex: `https://<projet>-up.railway.app/crawl`.

## Utilisation

- GET:
```bash
curl --get \
  --data-urlencode "url=https://example.com" \
  --data-urlencode "depth=1" \
  --data-urlencode "max_pages=5" \
  --data-urlencode "same_domain=true" \
  --data-urlencode "use_sitemap=true" \
  --data-urlencode "timeout=15" \
  --data-urlencode "max_chars_per_page=15000" \
  --data-urlencode "rate_limit_delay=0.2" \
  http://localhost:8080/crawl
```

- POST (JSON):
```bash
curl -X POST http://localhost:8080/crawl \
  -H 'Content-Type: application/json' \
  -d '{
    "url": "https://example.com",
    "depth": 1,
    "max_pages": 5,
    "same_domain": true,
    "use_sitemap": true,
    "sitemap_url": null,
    "sitemap_max_urls": 200,
    "timeout": 15,
    "max_chars_per_page": 15000,
    "rate_limit_delay": 0.2,
    "exclude_patterns": ["/login", "\\.pdf$"]
  }'
```

Réponse: `text/markdown`.

## Paramètres

- `url` (obligatoire): URL de départ.
- `depth` (0-5): profondeur BFS (0 = seulement la page de départ).
- `max_pages` (1-200): nombre maximum de pages à extraire.
- `same_domain` (bool): restreindre au même domaine.
- `timeout` (1-60s): timeout HTTP par requête.
- `max_chars_per_page` (1000-200000): limite de caractères extraits par page.
- `rate_limit_delay` (0-5s): délai entre les requêtes.
- `exclude_patterns` (liste de regex): URLs à ignorer.
- `user_agent` (POST): UA custom.
- `use_sitemap` (bool): activer la découverte via sitemap.
- `sitemap_url` (str|null): URL sitemap explicite (sinon robots.txt + /sitemap.xml).
- `sitemap_max_urls` (int): limite d'URLs importées depuis les sitemaps.
- `use_js_rendering` (bool): activer le rendu JavaScript pour les SPAs (défaut: true).

## Format de Sortie Voice AI

Format ultra-simple pour lecture vocale:

```markdown
# ERZA Déménagement Genève – Experts du déménagement

URL: https://erza.ch/

Chez ERZA Déménagement, nous accompagnons particuliers et professionnels dans toutes les étapes de leur déménagement à Genève et alentours.

Email: info@erza.ch

Téléphone: +41 79 136 36 38

Adresse: Rte des Jeunes 4 Bis, 1227 Les Acacias

Horaires:
- Lundi: Fermé
- Mardi: 09:00-12:30, 13:30-18:30
- Mercredi: 09:00-12:30, 13:30-18:30
- Jeudi: 09:00-12:30, 13:30-18:30
- Vendredi: 09:00-12:30, 13:30-18:30
- Samedi: 09:00-17:00
- Dimanche: Fermé

# Des services de déménagement professionnels à Genève

Chez ERZA Déménagement, nous accompagnons particuliers et professionnels dans toutes les étapes de leur déménagement à Genève et alentours. Du nettoyage au garde-meubles, en passant par le débarras ou les interventions techniques, nous proposons des solutions complètes, sur mesure et clé en main.

## Nos 3 formules de déménagements

### Formule Économique – L'essentiel à prix malin

Idéal pour les petits budgets ou les clients autonomes...

---

# Nettoyage de logement

URL: https://erza.ch/nos-services/nettoyage/

Un logement impeccable, prêt à être rendu ou habité...

[Contenu de la page suivante...]
```

## Types de Pages Détectés

Le crawler identifie automatiquement les types suivants:
- **home**: Page d'accueil
- **store**: Page de magasin/point de vente
- **product**: Fiche produit individuelle
- **category**: Page de catégorie/catalogue
- **service**: Page de service/prestation
- **faq**: Page FAQ
- **contact**: Page de contact
- **about**: Page "À propos"
- **page**: Page générique

## Langues Détectées

Détection automatique via:
1. Attribut HTML `lang`
2. Patterns dans l'URL (`/fr/`, `/de/`, etc.)
3. Analyse heuristique du contenu

Langues supportées: `fr`, `de`, `it`, `en`, `unknown`

## Notes Techniques

- Extraction intelligente: titres, paragraphes, listes, blocs code, citations
- Nettoyage avancé: suppression scripts, styles, nav, footer, iframe, formulaires
- Normalisation hiérarchique des titres (évite les sauts de niveaux)
- Déduplication basée sur hash MD5 du contenu normalisé
- Support des caractères spéciaux et accents français/allemand
- Normalisation téléphone E.164 pour Suisse (+41)
- Parsing intelligent des horaires en français

## Cas d'Usage

### Sites E-commerce (ex: Velomania)
- Extraction automatique des fiches magasins avec horaires
- Détection des pages de catégories de produits
- Normalisation des coordonnées de contact

### Sites de Services (ex: ERZA Nettoyage)
- Extraction des prestations en listes à puces
- Structuration des FAQs
- Centralisation des coordonnées

### Analyse Multi-sites
- Comparaison de contenus via hash
- Statistiques par langue et type de page
- Export Markdown compatible LLM (Claude, GPT, etc.)

## Développement

Version actuelle: **2.0.0**

Technologies:
- FastAPI 0.100+
- BeautifulSoup4 4.12+
- httpx (async HTTP client)
- Python 3.11+
# MDCrawler
