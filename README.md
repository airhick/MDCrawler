# Advanced Crawler Webhook v2.0

Service FastAPI exposant un webhook `/crawl` qui prend une URL, explore en largeur (depth réglable), et renvoie un contenu structuré et nettoyé en Markdown avec métadonnées enrichies, optimisé pour les LLM et l'analyse de données.

## Nouveautés v2.0 🚀

### Structure Globale
- ✅ YAML front-matter par page (url, crawled_at, page_type, lang, content_hash)
- ✅ Hiérarchie de titres normalisée (H1 > H2 > H3 cohérente)
- ✅ Déduplication automatique des blocs de contenu répétés
- ✅ Ancres automatiques sur tous les titres
- ✅ Filtrage des titres marketing vides ("À LA UNE", "NOS SERVICES", etc.)

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
```

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

## Format de Sortie

Chaque page crawlée inclut:

```markdown
================================================================================
PAGE 1
================================================================================

​```yaml
---
url: https://example.com/page
canonical_url: https://example.com/canonical
crawled_at: 2025-10-15T12:34:56Z
page_type: store
lang: fr
content_hash: abc123def456...
---
​```

## Titre de la Page

**URL**: [https://example.com/page](https://example.com/page)

**Description**: Description meta de la page

### Contact Information

**Email**:
- [contact@example.com](mailto:contact@example.com)

**Téléphone**:
- [+41 22 788 00 22](tel:+41227880022)

**Adresse**:
- Route de Pré-Bois 14, 1216 Cointrin

**Horaires**:

| Jour | Horaires |
|------|----------|
| Lundi | Fermé |
| Mardi | 09:00 - 12:30, 13:30 - 18:30 |
| Mercredi | 09:00 - 12:30, 13:30 - 18:30 |
...

### Content

[Contenu nettoyé et structuré de la page...]

---
*Source: https://example.com/page*
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
