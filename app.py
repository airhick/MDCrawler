import asyncio
import hashlib
import re
from collections import Counter, deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Deque, Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urldefrag, urlparse

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, HttpUrl
import httpx
from bs4 import BeautifulSoup

# Playwright for JS-rendered sites (lazy import)
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    async_playwright = None


app = FastAPI(title="Voice AI Optimized Crawler", version="2.1.1")
@app.get("/")
async def root():
    return {"status": "ok"}



DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


class CrawlRequest(BaseModel):
    url: HttpUrl
    depth: int = 1
    max_pages: int = 10
    same_domain: bool = True
    timeout: float = 15.0
    max_chars_per_page: int = 15000
    rate_limit_delay: float = 0.0
    user_agent: Optional[str] = None
    exclude_patterns: Optional[List[str]] = None
    use_sitemap: bool = False
    sitemap_url: Optional[str] = None
    sitemap_max_urls: int = 100
    use_js_rendering: bool = True  # Auto-detect and use Playwright for JS sites
    max_concurrent: int = 10  # Maximum concurrent requests for parallel crawling


@dataclass
class PageContent:
    url: str
    title: str
    description: Optional[str]
    markdown: str
    crawled_at: str
    page_type: str
    lang: str
    canonical_url: Optional[str] = None
    contact_info: Dict[str, Any] = field(default_factory=dict)
    structured_data: Dict[str, Any] = field(default_factory=dict)
    content_hash: str = ""


def is_probably_html(response: httpx.Response) -> bool:
    content_type = response.headers.get("content-type", "").lower()
    return "text/html" in content_type or content_type.startswith("text/")


def same_registered_domain(url_a: str, url_b: str) -> bool:
    a = urlparse(url_a)
    b = urlparse(url_b)
    return a.hostname == b.hostname


def normalize_url(candidate: str, base: str) -> Optional[str]:
    if not candidate:
        return None
    absolute = urljoin(base, candidate)
    # remove fragments
    absolute, _ = urldefrag(absolute)
    parsed = urlparse(absolute)
    if parsed.scheme not in {"http", "https"}:
        return None
    if not parsed.netloc:
        return None
    return absolute


def extract_links(html: str, base_url: str) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    links: List[str] = []
    for a in soup.find_all("a", href=True):
        href = normalize_url(a.get("href"), base_url)
        if href:
            links.append(href)
    return links


# ============================================================================
# TEXT NORMALIZATION & CLEANING
# ============================================================================

def normalize_text(text: str) -> str:
    """Normalize text: fix spaces, quotes, currency, etc."""
    if not text:
        return text
    
    # Fix spacing issues
    text = re.sub(r'\s+', ' ', text)  # Multiple spaces to single
    text = re.sub(r'\s+([,;:!?.])', r'\1', text)  # Space before punctuation
    text = re.sub(r'([,;:!?.])\s*([,;:!?.])', r'\1\2', text)  # Double punctuation
    
    # Normalize quotes and apostrophes
    text = text.replace(''', "'").replace(''', "'")
    text = text.replace('"', '"').replace('"', '"')
    
    # Currency formatting
    text = re.sub(r'(\d)\s+([,.])\s*(\d)', r'\1\2\3', text)  # Fix "1 ,00" to "1,00"
    text = re.sub(r'(\d)\s+(CHF|EUR|USD|Fr\.)', r'\1 \2', text)  # Normalize currency spacing
    text = re.sub(r'\s+CHF', ' CHF', text)  # Consistent CHF spacing
    
    # Remove excessive line breaks already handled elsewhere
    return text.strip()


def normalize_city_name(city: str) -> str:
    """Normalize city names: proper capitalization."""
    if not city:
        return city
    
    # Simple title case for Swiss cities
    city = city.strip()
    # Special cases
    special_cases = {
        'genève': 'Genève',
        'neuchâtel': 'Neuchâtel',
        'zürich': 'Zürich',
        'bâle': 'Bâle',
        'lausanne': 'Lausanne',
        'cointrin': 'Cointrin',
        'conthey': 'Conthey',
        'crissier': 'Crissier',
    }
    
    city_lower = city.lower()
    if city_lower in special_cases:
        return special_cases[city_lower]
    
    return city.title()


def normalize_phone_e164(phone: str, default_country: str = "CH") -> Tuple[str, str]:
    """
    Normalize phone to E.164 format and human-readable format.
    Returns (e164_format, display_format)
    """
    if not phone:
        return "", ""
    
    # Remove all non-digit characters except +
    cleaned = re.sub(r'[^\d+]', '', phone)
    
    # Swiss phone number patterns
    if cleaned.startswith('+41'):
        e164 = cleaned
    elif cleaned.startswith('0041'):
        e164 = '+' + cleaned[2:]
    elif cleaned.startswith('0'):
        e164 = '+41' + cleaned[1:]
    elif cleaned.startswith('41'):
        e164 = '+' + cleaned
    else:
        e164 = '+41' + cleaned
    
    # Create display format: +41 XX XXX XX XX
    if e164.startswith('+41') and len(e164) >= 12:
        display = f"+41 {e164[3:5]} {e164[5:8]} {e164[8:10]} {e164[10:]}"
    else:
        display = phone
    
    return e164, display.strip()


# ============================================================================
# LANGUAGE & PAGE TYPE DETECTION
# ============================================================================

def detect_language(soup: BeautifulSoup, url: str, text: str) -> str:
    """Detect page language from HTML attributes, URL, or content."""
    # Check HTML lang attribute
    html_tag = soup.find('html')
    if html_tag and html_tag.get('lang'):
        lang = html_tag.get('lang', '').lower()
        if lang.startswith('fr'):
            return 'fr'
        elif lang.startswith('de'):
            return 'de'
        elif lang.startswith('it'):
            return 'it'
        elif lang.startswith('en'):
            return 'en'
    
    # Check URL patterns
    if '/fr/' in url or '/fr-' in url:
        return 'fr'
    elif '/de/' in url or '/de-' in url:
        return 'de'
    elif '/it/' in url or '/it-' in url:
        return 'it'
    elif '/en/' in url or '/en-' in url:
        return 'en'
    
    # Simple heuristic based on common words
    text_lower = text[:1000].lower()
    fr_words = ['les', 'des', 'une', 'nous', 'vous', 'est', 'sont', 'avec', 'pour']
    de_words = ['der', 'die', 'das', 'und', 'ist', 'sind', 'mit', 'für', 'von']
    
    fr_count = sum(1 for w in fr_words if f' {w} ' in text_lower)
    de_count = sum(1 for w in de_words if f' {w} ' in text_lower)
    
    if fr_count > de_count:
        return 'fr'
    elif de_count > fr_count:
        return 'de'
    
    return 'unknown'


def detect_page_type(url: str, title: str, soup: BeautifulSoup) -> str:
    """Detect the type of page: home, store, product, category, service, faq, etc."""
    url_lower = url.lower()
    title_lower = title.lower()
    
    # Homepage detection
    parsed = urlparse(url)
    if parsed.path in ['/', '', '/fr', '/de', '/fr/', '/de/']:
        return 'home'
    
    # Store/Location page
    if any(x in url_lower for x in ['/magasin', '/store', '/location', '/cointrin', '/conthey', '/crissier', '/neuchatel']):
        return 'store'
    
    # Product page - specific product
    if any(x in url_lower for x in ['/product/', '/produit/', '/p/']):
        return 'product'
    
    # Category/Catalog page
    if any(x in url_lower for x in ['/category/', '/categorie/', '/c/', '/catalogue', '/velo-', '/vtt-', '/gravel']):
        return 'category'
    
    # Service page
    if any(x in url_lower for x in ['/service', '/prestation', '/nettoyage', '/menage']):
        return 'service'
    
    # FAQ page
    if 'faq' in url_lower or 'question' in url_lower:
        return 'faq'
    
    # Contact page
    if 'contact' in url_lower:
        return 'contact'
    
    # About page
    if any(x in url_lower for x in ['/about', '/a-propos', '/ueber-uns']):
        return 'about'
    
    # Default to generic page
    return 'page'


# ============================================================================
# CONTENT EXTRACTION & STRUCTURING
# ============================================================================

def extract_contact_info(soup: BeautifulSoup, text: str) -> Dict[str, Any]:
    """Extract and structure contact information."""
    contact = {}
    
    # Email detection
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(email_pattern, text)
    if emails:
        contact['emails'] = list(set(emails))
    
    # Phone detection
    phone_pattern = r'(?:\+41|0041|0)\s*\d{1,2}\s*\d{3}\s*\d{2}\s*\d{2}'
    phones = re.findall(phone_pattern, text)
    normalized_phones = []
    for phone in phones:
        e164, display = normalize_phone_e164(phone)
        if e164:
            normalized_phones.append({'e164': e164, 'display': display})
    if normalized_phones:
        contact['phones'] = normalized_phones
    
    # Address detection (Swiss addresses)
    address_patterns = [
        r'(?:Route|Rue|Avenue|Chemin|Place)\s+[^,\n]{3,50}(?:,\s*\d{4}\s+[A-ZÀ-ÿ][a-zà-ÿ]+)?',
        r'\d{4}\s+[A-ZÀ-ÿ][a-zà-ÿ]+(?:,\s*Suisse)?'
    ]
    addresses = []
    for pattern in address_patterns:
        found = re.findall(pattern, text)
        addresses.extend(found)
    if addresses:
        contact['addresses'] = [normalize_text(addr) for addr in set(addresses)]
    
    return contact


def extract_opening_hours(text: str) -> Optional[Dict[str, Any]]:
    """Extract and structure opening hours into a structured format."""
    # Detect special closures
    if 'fermeture hivernale' in text.lower():
        return {'status': 'winter_closure', 'note': 'Fermeture hivernale'}
    
    # Pattern for day: HH:MM - HH:MM format
    hours_pattern = r'(lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)\s*:?\s*([^:\n]+?)(?=(?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)|$)'
    matches = re.findall(hours_pattern, text.lower(), re.IGNORECASE)
    
    if not matches:
        return None
    
    schedule = {}
    day_map = {
        'lundi': 'monday', 'mardi': 'tuesday', 'mercredi': 'wednesday',
        'jeudi': 'thursday', 'vendredi': 'friday', 'samedi': 'saturday',
        'dimanche': 'sunday'
    }
    
    for day_fr, hours_text in matches:
        day_en = day_map.get(day_fr.lower(), day_fr)
        hours_text = hours_text.strip()
        
        if 'fermé' in hours_text.lower():
            schedule[day_en] = {'status': 'closed'}
        else:
            # Extract time ranges
            time_pattern = r'(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})'
            times = re.findall(time_pattern, hours_text)
            if times:
                schedule[day_en] = {
                    'status': 'open',
                    'slots': [{'open': t[0], 'close': t[1]} for t in times]
                }
    
    return schedule if schedule else None


def create_hours_table(hours: Optional[Dict[str, Any]]) -> str:
    """Convert hours dict to markdown table."""
    if not hours:
        return ""
    
    if hours.get('status') == 'winter_closure':
        return f"**Horaires**: {hours.get('note', 'Fermé')}\n"
    
    lines = ["**Horaires**:\n", "| Jour | Horaires |", "|------|----------|"]
    
    day_order = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    day_names_fr = {
        'monday': 'Lundi', 'tuesday': 'Mardi', 'wednesday': 'Mercredi',
        'thursday': 'Jeudi', 'friday': 'Vendredi', 'saturday': 'Samedi',
        'sunday': 'Dimanche'
    }
    
    for day in day_order:
        if day in hours:
            day_data = hours[day]
            day_name = day_names_fr.get(day, day.capitalize())
            
            if day_data.get('status') == 'closed':
                lines.append(f"| {day_name} | Fermé |")
            elif day_data.get('status') == 'open' and day_data.get('slots'):
                slots_str = ', '.join([f"{s['open']} - {s['close']}" for s in day_data['slots']])
                lines.append(f"| {day_name} | {slots_str} |")
    
    return '\n'.join(lines) + '\n'


def extract_product_data(text: str, html: str) -> List[Dict[str, Any]]:
    """Extract structured product data from text."""
    products = []
    
    # Pattern for price with optional discount
    price_pattern = r'(\d[\d\s,.]*)\s*CHF'
    
    # Look for product blocks (simplified - would need more context for real extraction)
    # This is a placeholder for more sophisticated extraction
    
    return products


# ============================================================================
# HEADING & STRUCTURE PROCESSING
# ============================================================================

# Marketing/empty headings to filter out
NOISE_HEADINGS = {
    'à la une', 'nos services', 'agenda', 'nos clients parlent de nous',
    'newsletter', 'rejoignez la communauté', 'rejoignez la communaute',
    'nos marques', 'inscrivez-vous', 'suivez-nous', 'nos partenaires',
    'velomania+', 'pack sérénité', 'bike fitting', 'conseils',
}

# Navigation/menu phrases to filter out (for voice AI clarity)
NAVIGATION_PATTERNS = [
    # French navigation
    r'^accueil$',
    r'^contact$',
    r'^à propos$',
    r'^nos services',
    r'^mentions légales$',
    r'^plan du site$',
    r'nos formules de déménagement',
    r'^nettoyage$',
    r'^garde-meubles$',
    r'^débarras$',
    r'^interventions? diverses?$',
    
    # German navigation
    r'^startseite$',
    r'^kontakt$',
    r'^über uns$',
    r'^unternehmen$',
    r'^karriere$',
    r'^jobs$',
    r'^standorte?$',
    r'^geschichte$',
    r'^blog$',
    r'^referenzen$',
    r'^medien$',
    r'^qualität$',
    r'^nachhaltigkeit$',
    r'^mobilität$',
    r'^sicherheit$',
    r'^technik$',
    
    # Generic service categories (often menus)
    r'^transport$',
    r'^lagerlogistik$',
    r'^lagerung$',
    r'^gesamtlösungen$',
    r'^national$',
    r'^international$',
    r'^stückgut$',
    r'^pharma$',
    r'^pakete$',
    r'^homeservice$',
    r'^nachtexpress$',
    r'^spezial$',
    r'^container$',
    r'^umzug$',
    r'^verzollungen$',
    r'^konfektionierung$',
    r'^kommissionierung$',
    r'^cross docking$',
    r'^e-commerce$',
    r'^ersatzteillogistik$',
    r'^eventlogistik$',
    r'^fitness$',
    r'^food$',
    r'^gefahrgut$',
    r'^outsourcing$',
    r'^city-logistik$',
    
    # Language switchers
    r'^de$',
    r'^en$',
    r'^fr$',
    r'^it$',
    r'^ch$',
    r'^de\s+ch\s+it\s+fr\s+en$',
    
    # Contact fragments
    r'^\d{3}\.\d{3}\.\d{2}\.\d{2}$',  # Phone numbers as menu items
    r'^\+41\s*\d{2}\s*\d{3}\s*\d{2}\s*\d{2}$',  # +41 format phones
    r'^info@',  # Email addresses as menu items
    r'^rte des jeunes',  # Address fragments
]

def is_navigation_item(text: str) -> bool:
    """Check if text is a navigation/menu item."""
    text_clean = text.lower().strip('- ').strip()
    for pattern in NAVIGATION_PATTERNS:
        if re.match(pattern, text_clean, re.IGNORECASE):
            return True
    return False

def is_noise_heading(text: str) -> bool:
    """Check if heading is marketing noise."""
    text_clean = text.lower().strip('# ').strip()
    # Remove markdown brackets
    text_clean = re.sub(r'\[|\]', '', text_clean)
    return text_clean in NOISE_HEADINGS or len(text_clean) < 3


def normalize_heading_hierarchy(lines: List[str]) -> List[str]:
    """Ensure coherent H1 > H2 > H3 hierarchy."""
    result = []
    current_level = 0
    
    for line in lines:
        if line.startswith('#'):
            # Count heading level
            level = len(line) - len(line.lstrip('#'))
            text = line.lstrip('#').strip()
            
            if is_noise_heading(text):
                continue
            
            # Enforce hierarchy: can't jump more than 1 level
            if current_level == 0:
                level = min(level, 1)  # First heading should be H1 or H2
            else:
                level = min(level, current_level + 1)
            
            current_level = level
            result.append('#' * level + ' ' + text)
        else:
            result.append(line)
    
    return result


def add_heading_anchors(lines: List[str]) -> List[str]:
    """Add anchor IDs to headings for internal linking - DISABLED for voice AI."""
    # Return lines as-is without anchors for cleaner voice AI output
    return lines


# ============================================================================
# DEDUPLICATION
# ============================================================================

def compute_content_hash(text: str) -> str:
    """Compute hash of content for deduplication."""
    normalized = re.sub(r'\s+', ' ', text.lower().strip())
    return hashlib.md5(normalized.encode()).hexdigest()


def deduplicate_blocks(lines: List[str], min_block_size: int = 50) -> List[str]:
    """Remove duplicate text blocks."""
    seen_hashes = set()
    result = []
    current_block = []
    
    for line in lines:
        if line.startswith('#') or line.startswith('---') or line.startswith('==='):
            # Process accumulated block
            if current_block:
                block_text = ' '.join(current_block)
                if len(block_text) >= min_block_size:
                    block_hash = compute_content_hash(block_text)
                    if block_hash not in seen_hashes:
                        result.extend(current_block)
                        seen_hashes.add(block_hash)
                else:
                    result.extend(current_block)
            
            current_block = []
            result.append(line)
        else:
            current_block.append(line)
    
    # Process final block
    if current_block:
        block_text = ' '.join(current_block)
        if len(block_text) >= min_block_size:
            block_hash = compute_content_hash(block_text)
            if block_hash not in seen_hashes:
                result.extend(current_block)
        else:
            result.extend(current_block)
    
    return result


def remove_consecutive_duplicates(lines: List[str]) -> List[str]:
    """Remove consecutive duplicate lines."""
    if not lines:
        return lines
    
    result = [lines[0]]
    for line in lines[1:]:
        # Skip if identical to previous line (case-insensitive for better matching)
        if line.strip().lower() != result[-1].strip().lower():
            result.append(line)
    
    return result


def remove_menu_list_blocks(lines: List[str]) -> List[str]:
    """Remove blocks that are purely navigation menu lists."""
    result = []
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Check if this starts a potential menu block (list of navigation items)
        if line.startswith('- '):
            # Look ahead to see if this is a menu block
            menu_items = []
            j = i
            
            # Collect consecutive list items
            while j < len(lines) and lines[j].startswith('- '):
                item_text = lines[j][2:].strip()
                menu_items.append(item_text)
                j += 1
            
            # If we have 5+ consecutive navigation items, it's likely a menu block
            if len(menu_items) >= 5:
                nav_count = sum(1 for item in menu_items if is_navigation_item(item))
                # If 70%+ are navigation items, skip the whole block
                if nav_count / len(menu_items) >= 0.7:
                    i = j  # Skip to after the menu block
                    continue
            
            # Not a menu block, keep the line
            result.append(line)
            i += 1
        else:
            result.append(line)
            i += 1
    
    return result


def clean_html_to_markdown(html: str, url: str, max_chars: int) -> Dict[str, Any]:
    """Enhanced HTML to Markdown conversion with structured data extraction."""
    soup = BeautifulSoup(html, "html.parser")

    # Remove non-content elements
    for tag in soup(["script", "style", "noscript", "svg", "canvas", "form", "iframe"]):
        tag.decompose()

    # Extract canonical URL
    canonical = None
    canonical_tag = soup.find("link", attrs={"rel": "canonical"})
    if canonical_tag and canonical_tag.get("href"):
        canonical = canonical_tag.get("href")

    # Title and meta description
    title_tag = soup.find("title")
    title = (title_tag.get_text(strip=True) if title_tag else "") or "Untitled"
    title = normalize_text(title)
    
    meta_desc_tag = soup.find("meta", attrs={"name": "description"}) or soup.find(
        "meta", attrs={"property": "og:description"}
    )
    description = meta_desc_tag.get("content") if meta_desc_tag and meta_desc_tag.get("content") else None
    if description:
        description = normalize_text(description)

    # Detect language and page type
    raw_text = soup.get_text()
    lang = detect_language(soup, url, raw_text)
    page_type = detect_page_type(url, title, soup)

    # Simple content containers to prioritize
    main = soup.find("main") or soup.find("article") or soup.find("body") or soup

    # Convert headings, paragraphs, and lists into markdown-like text
    parts: List[str] = []
    for element in main.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "ul", "ol", "pre", "code", "blockquote"], recursive=True):
        # Skip if parent was already processed
        if element.find_parent(["pre", "code"]):
            continue
            
        name = element.name
        text = element.get_text(" ", strip=True)
        if not text:
            continue

        # Normalize text
        text = normalize_text(text)
        
        # Skip very short isolated phrases (likely CTAs)
        if name == "p" and len(text) < 25 and not any(c in text for c in '.,;:!?'):
            continue
        
        # Skip navigation items for voice AI
        if is_navigation_item(text):
            continue

        if name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            level = int(name[1])
            # Skip noise headings
            if not is_noise_heading(text):
                parts.append("#" * level + " " + text)
        elif name == "p":
            parts.append(text)
        elif name in {"ul", "ol"}:
            list_items = []
            for li in element.find_all("li", recursive=False):
                li_text = li.get_text(" ", strip=True)
                if li_text:
                    li_text = normalize_text(li_text)
                    # Filter out navigation items for voice AI
                    if not is_navigation_item(li_text):
                        list_items.append(li_text)
            
            if list_items:
                for item in list_items:
                    bullet = "- " if name == "ul" else "1. "
                    parts.append(bullet + item)
        elif name in {"pre", "code"}:
            parts.append("```\n" + text + "\n```")
        elif name == "blockquote":
            parts.append("> " + text)

    # Join and process content
    content = "\n\n".join(parts)
    content = re.sub(r"\n{3,}", "\n\n", content).strip()
    
    # Apply advanced processing
    lines = content.split('\n')
    lines = normalize_heading_hierarchy(lines)
    lines = remove_menu_list_blocks(lines)  # Remove navigation menu blocks
    lines = deduplicate_blocks(lines)
    lines = remove_consecutive_duplicates(lines)  # Remove consecutive identical lines
    lines = add_heading_anchors(lines)
    
    # Final cleanup: remove empty lines at start/end of sections
    cleaned_lines = []
    for i, line in enumerate(lines):
        # Skip multiple consecutive empty lines
        if line.strip() == '':
            if i == 0 or i == len(lines) - 1:
                continue
            if cleaned_lines and cleaned_lines[-1].strip() == '':
                continue
        cleaned_lines.append(line)
    
    content = '\n'.join(cleaned_lines)
    
    # Extract structured data
    contact_info = extract_contact_info(soup, raw_text)
    opening_hours = extract_opening_hours(raw_text)
    
    # Normalize contact info
    if 'addresses' in contact_info:
        normalized_addresses = []
        for addr in contact_info['addresses']:
            # Normalize city names in addresses
            addr_normalized = addr
            for city in ['cointrin', 'conthey', 'crissier', 'neuchâtel', 'genève']:
                pattern = re.compile(re.escape(city), re.IGNORECASE)
                addr_normalized = pattern.sub(normalize_city_name(city), addr_normalized)
            normalized_addresses.append(addr_normalized)
        contact_info['addresses'] = normalized_addresses
    
    structured_data = {}
    if opening_hours:
        structured_data['opening_hours'] = opening_hours
    
    # Truncate if needed
    if len(content) > max_chars:
        content = content[: max(0, max_chars - 50)].rsplit(" ", 1)[0] + " …"

    # Compute content hash
    content_hash = compute_content_hash(content)

    return {
        'title': title,
        'description': description,
        'markdown': content,
        'canonical_url': canonical,
        'lang': lang,
        'page_type': page_type,
        'contact_info': contact_info,
        'structured_data': structured_data,
        'content_hash': content_hash,
    }


async def fetch_html(client: httpx.AsyncClient, url: str, timeout: float) -> Optional[str]:
    try:
        resp = await client.get(url, timeout=timeout, follow_redirects=True)
        if resp.status_code >= 400:
            return None
        if not is_probably_html(resp):
            return None
        return resp.text
    except Exception:
        return None


async def fetch_text(client: httpx.AsyncClient, url: str, timeout: float) -> Optional[str]:
    try:
        resp = await client.get(url, timeout=timeout, follow_redirects=True)
        if resp.status_code >= 400:
            return None
        return resp.text
    except Exception:
        return None


def is_js_rendered_site(html: str) -> bool:
    """Detect if a site is JavaScript-rendered (SPA) with minimal content."""
    soup = BeautifulSoup(html, "html.parser")
    
    # Remove script and style tags
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    
    # Check if body has minimal text content
    body = soup.find("body")
    if not body:
        return True
    
    text = body.get_text(strip=True)
    
    # If body has very little text (< 100 chars), likely JS-rendered
    if len(text) < 100:
        return True
    
    # Check for common SPA indicators
    spa_indicators = [
        'id="root"',
        'id="app"',
        'id="__next"',
        'data-reactroot',
        'data-vite-theme',
        'ng-app',
        'v-app'
    ]
    
    html_lower = html.lower()
    if any(indicator.lower() in html_lower for indicator in spa_indicators):
        # Has SPA indicator, check if there's actual content
        if len(text) < 500:  # Very little rendered content
            return True
    
    return False


async def fetch_html_with_js(url: str, timeout: float, user_agent: str) -> Optional[str]:
    """Fetch HTML using Playwright for JavaScript-rendered sites."""
    if not PLAYWRIGHT_AVAILABLE:
        print("WARNING: Playwright not available, skipping JS rendering")
        return None
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',  # Required for Docker/Railway
                    '--disable-dev-shm-usage'  # Overcome limited resource problems
                ]
            )
            context = await browser.new_context(
                user_agent=user_agent,
                viewport={'width': 1920, 'height': 1080},
                ignore_https_errors=True
            )
            page = await context.new_page()
            
            # Try different loading strategies
            try:
                # First try: wait for DOM content loaded (faster, more reliable for SPAs)
                await page.goto(url, wait_until='domcontentloaded', timeout=timeout * 1000)
            except Exception:
                # Fallback: just navigate without waiting
                await page.goto(url, wait_until='commit', timeout=timeout * 1000)
            
            # Wait for content to render (dynamic wait)
            try:
                # Wait for body to have some content
                await page.wait_for_function(
                    "document.body && document.body.innerText.length > 100",
                    timeout=5000
                )
            except Exception:
                # If that fails, just wait a fixed time
                await page.wait_for_timeout(3000)
            
            # Scroll to trigger lazy loading
            try:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(1000)
            except Exception:
                pass
            
            # Get the rendered HTML
            html = await page.content()
            
            await browser.close()
            return html
    except Exception as e:
        print(f"Playwright error for {url}: {e}")
        return None


async def discover_sitemap_urls(
    client: httpx.AsyncClient,
    start_url: str,
    explicit_sitemap_url: Optional[str],
    timeout: float,
    same_domain_only: bool,
    max_urls: int,
) -> List[str]:
    from urllib.parse import urlunparse
    import xml.etree.ElementTree as ET

    parsed = urlparse(start_url)
    base_root = f"{parsed.scheme}://{parsed.netloc}"

    candidates: List[str] = []
    if explicit_sitemap_url:
        candidates.append(explicit_sitemap_url)
    # robots.txt discovery
    robots_url = base_root + "/robots.txt"
    robots = await fetch_text(client, robots_url, timeout)
    if robots:
        for line in robots.splitlines():
            line = line.strip()
            if line.lower().startswith("sitemap:"):
                sm = line.split(":", 1)[1].strip()
                sm_norm = normalize_url(sm, base_root)
                if sm_norm:
                    candidates.append(sm_norm)
    # default location
    candidates.append(base_root + "/sitemap.xml")

    seen: Set[str] = set()
    discovered: List[str] = []

    async def parse_sitemap(sitemap_url: str) -> None:
        nonlocal discovered
        xml_text = await fetch_text(client, sitemap_url, timeout)
        if not xml_text:
            return
        try:
            root = ET.fromstring(xml_text)
        except Exception:
            return
        tag = root.tag.lower()
        # Handle namespaces by stripping them
        def strip_ns(t: str) -> str:
            return t.split('}', 1)[-1] if '}' in t else t
        root_name = strip_ns(root.tag).lower()
        if root_name == "sitemapindex":
            for sm in root:
                if strip_ns(sm.tag).lower() == "sitemap":
                    loc_el = next((c for c in sm if strip_ns(c.tag).lower() == "loc"), None)
                    if loc_el is not None and loc_el.text:
                        sm_url = normalize_url(loc_el.text.strip(), sitemap_url)
                        if sm_url and sm_url not in seen:
                            seen.add(sm_url)
                            if len(discovered) < max_urls:
                                await parse_sitemap(sm_url)
        elif root_name == "urlset":
            for url_el in root:
                if strip_ns(url_el.tag).lower() == "url":
                    loc_el = next((c for c in url_el if strip_ns(c.tag).lower() == "loc"), None)
                    if loc_el is not None and loc_el.text:
                        page_url = normalize_url(loc_el.text.strip(), sitemap_url)
                        if not page_url:
                            continue
                        if same_domain_only and not same_registered_domain(start_url, page_url):
                            continue
                        if page_url not in discovered:
                            discovered.append(page_url)
                            if len(discovered) >= max_urls:
                                return

    for cand in candidates:
        if cand in seen:
            continue
        seen.add(cand)
        if len(discovered) >= max_urls:
            break
        await parse_sitemap(cand)

    return discovered[:max_urls]


async def crawl(request: CrawlRequest) -> List[PageContent]:
    headers = dict(DEFAULT_HEADERS)
    if request.user_agent:
        headers["User-Agent"] = request.user_agent

    exclude_patterns: List[re.Pattern] = []
    if request.exclude_patterns:
        exclude_patterns = [re.compile(p, re.IGNORECASE) for p in request.exclude_patterns]

    start_url = str(request.url)
    visited: Set[str] = set()
    seeds: List[str] = [start_url]
    results: List[PageContent] = []
    
    # Semaphore to limit concurrent requests
    semaphore = asyncio.Semaphore(request.max_concurrent)
    # Lock for thread-safe visited set operations
    visited_lock = asyncio.Lock()
    user_agent = request.user_agent or DEFAULT_HEADERS["User-Agent"]

    async def process_page(
        client: httpx.AsyncClient,
        url: str,
        depth: int,
        visited_set: Set[str],
        results_list: List[PageContent],
        queue: Deque[Tuple[str, int]],
    ) -> Optional[PageContent]:
        """Process a single page - can be called in parallel."""
        async with semaphore:
            # Check and mark as visited atomically
            async with visited_lock:
                if url in visited_set:
                    return None
                visited_set.add(url)
            
            # Validate URL
            if request.same_domain and not same_registered_domain(start_url, url):
                return None
            
            if any(p.search(url) for p in exclude_patterns):
                return None
            
            # Try static HTML first (fast)
            html = await fetch_html(client, url, request.timeout)
            
            # Check if JS rendering is needed
            if html and request.use_js_rendering and is_js_rendered_site(html):
                # Retry with Playwright for JS-rendered content
                html_js = await fetch_html_with_js(url, request.timeout, user_agent)
                if html_js:
                    html = html_js
            
            if not html:
                return None

            # Extract enhanced data (CPU-bound, but fast)
            page_data = clean_html_to_markdown(html, url, request.max_chars_per_page)
            
            # Create PageContent with all metadata
            page_content = PageContent(
                url=url,
                title=page_data['title'],
                description=page_data['description'],
                markdown=page_data['markdown'],
                crawled_at=datetime.utcnow().isoformat() + 'Z',
                page_type=page_data['page_type'],
                lang=page_data['lang'],
                canonical_url=page_data.get('canonical_url'),
                contact_info=page_data.get('contact_info', {}),
                structured_data=page_data.get('structured_data', {}),
                content_hash=page_data.get('content_hash', ''),
            )
            
            # Add links to queue for next depth level (thread-safe)
            if depth < request.depth:
                links = extract_links(html, url)
                async with visited_lock:
                    for link in links:
                        if link not in visited_set:
                            queue.append((link, depth + 1))
            
            # Rate limiting delay
            if request.rate_limit_delay > 0:
                await asyncio.sleep(request.rate_limit_delay)
            
            return page_content

    async with httpx.AsyncClient(headers=headers, limits=httpx.Limits(max_connections=request.max_concurrent * 2, max_keepalive_connections=request.max_concurrent)) as client:
        # Optional sitemap discovery to broaden initial queue
        if request.use_sitemap:
            try:
                sitemap_urls = await discover_sitemap_urls(
                    client=client,
                    start_url=start_url,
                    explicit_sitemap_url=request.sitemap_url,
                    timeout=request.timeout,
                    same_domain_only=request.same_domain,
                    max_urls=min(request.max_pages * 5, request.sitemap_max_urls),
                )
                # prioritize homepage first
                for u in sitemap_urls:
                    if u not in seeds:
                        seeds.append(u)
            except Exception:
                pass

        queue: Deque[Tuple[str, int]] = deque((u, 0) for u in seeds)
        
        # Process pages in parallel batches
        while queue and len(results) < request.max_pages:
            # Collect a batch of URLs to process in parallel
            batch: List[Tuple[str, int]] = []
            while queue and len(batch) < request.max_concurrent and len(results) + len(batch) < request.max_pages:
                url, depth = queue.popleft()
                if url not in visited:
                    batch.append((url, depth))
            
            if not batch:
                break
            
            # Process batch in parallel
            tasks = [
                process_page(client, url, depth, visited, results, queue)
                for url, depth in batch
            ]
            
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Collect successful results
            for result in batch_results:
                if isinstance(result, PageContent):
                    results.append(result)
                elif isinstance(result, Exception):
                    # Log but continue
                    print(f"Error processing page: {result}")

    return results


def aggregate_markdown(start_url: str, req: CrawlRequest, pages: List[PageContent], user_agent: str) -> str:
    """Generate clean, simple output optimized for voice AI reading."""
    
    # Deduplicate pages by content hash
    seen_hashes = set()
    unique_pages = []
    for page in pages:
        if page.content_hash not in seen_hashes:
            seen_hashes.add(page.content_hash)
            unique_pages.append(page)
    
    # Build simple page sections
    sections: List[str] = []
    
    for i, page in enumerate(unique_pages, start=1):
        sec: List[str] = []
        page_title = page.title or f"Page {i}"
        
        # Simple separator
        if i > 1:
            sec.append("")
            sec.append("---")
            sec.append("")
        
        # Page title as main heading
        sec.append(f"# {page_title}")
        sec.append("")
        
        # Simple URL
        sec.append(f"URL: {page.url}")
        sec.append("")
        
        # Description if available
        if page.description:
            sec.append(page.description)
            sec.append("")
        
        # Contact Information - SIMPLE FORMAT for voice AI
        if page.contact_info:
            contact = page.contact_info
            
            if contact.get('emails'):
                for email in contact['emails']:
                    sec.append(f"Email: {email}")
                sec.append("")
            
            if contact.get('phones'):
                for phone in contact['phones']:
                    # Use display format, not e164
                    display = phone.get('display', phone.get('e164', ''))
                    sec.append(f"Téléphone: {display}")
                sec.append("")
            
            if contact.get('addresses'):
                for addr in contact['addresses']:
                    sec.append(f"Adresse: {addr}")
                sec.append("")
        
        # Opening Hours - simple text format
        if page.structured_data.get('opening_hours'):
            hours = page.structured_data['opening_hours']
            
            if hours.get('status') == 'winter_closure':
                sec.append(f"Horaires: {hours.get('note', 'Fermé')}")
                sec.append("")
            else:
                sec.append("Horaires:")
                day_order = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
                day_names_fr = {
                    'monday': 'Lundi', 'tuesday': 'Mardi', 'wednesday': 'Mercredi',
                    'thursday': 'Jeudi', 'friday': 'Vendredi', 'saturday': 'Samedi',
                    'sunday': 'Dimanche'
                }
                
                for day in day_order:
                    if day in hours:
                        day_data = hours[day]
                        day_name = day_names_fr.get(day, day.capitalize())
                        
                        if day_data.get('status') == 'closed':
                            sec.append(f"- {day_name}: Fermé")
                        elif day_data.get('status') == 'open' and day_data.get('slots'):
                            slots_str = ', '.join([f"{s['open']}-{s['close']}" for s in day_data['slots']])
                            sec.append(f"- {day_name}: {slots_str}")
                
        sec.append("")
        
        # Main content
        sec.append(page.markdown)
        sec.append("")
        
        sections.append("\n".join(sec))

    if not sections:
        sections.append("_No content extracted._")

    return "\n".join(sections)


@app.get("/crawl", response_class=PlainTextResponse)
async def crawl_get(
    url: HttpUrl = Query(..., description="URL à crawler"),
    depth: int = Query(1, ge=0, le=5),
    max_pages: int = Query(10, ge=1, le=200),
    same_domain: bool = Query(True),
    timeout: float = Query(15.0, ge=1.0, le=60.0),
    max_chars_per_page: int = Query(15000, ge=1000, le=200000),
    rate_limit_delay: float = Query(0.0, ge=0.0, le=5.0),
    use_sitemap: bool = Query(False),
    sitemap_url: Optional[str] = Query(None),
    sitemap_max_urls: int = Query(100, ge=1, le=5000),
    use_js_rendering: bool = Query(True, description="Enable JavaScript rendering for SPAs"),
    max_concurrent: int = Query(10, ge=1, le=50, description="Maximum concurrent requests for parallel crawling"),
):
    try:
        req = CrawlRequest(
            url=url,
            depth=depth,
            max_pages=max_pages,
            same_domain=same_domain,
            timeout=timeout,
            max_chars_per_page=max_chars_per_page,
            rate_limit_delay=rate_limit_delay,
            use_sitemap=use_sitemap,
            sitemap_url=sitemap_url,
            sitemap_max_urls=sitemap_max_urls,
            use_js_rendering=use_js_rendering,
            max_concurrent=max_concurrent,
        )

        pages = await crawl(req)
        user_agent = req.user_agent or DEFAULT_HEADERS["User-Agent"]
        md = aggregate_markdown(str(url), req, pages, user_agent)
        return PlainTextResponse(content=md, media_type="text/markdown; charset=utf-8")
    except Exception as e:
        import traceback
        error_msg = f"Crawl error: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        print(error_msg)  # Log to console
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@app.post("/crawl", response_class=PlainTextResponse)
async def crawl_post(payload: CrawlRequest):
    try:
        if payload.depth < 0 or payload.max_pages < 1:
            raise HTTPException(status_code=400, detail="Invalid crawl parameters")
        pages = await crawl(payload)
        user_agent = payload.user_agent or DEFAULT_HEADERS["User-Agent"]
        md = aggregate_markdown(str(payload.url), payload, pages, user_agent)
        return PlainTextResponse(content=md, media_type="text/markdown; charset=utf-8")
    except Exception as e:
        import traceback
        error_msg = f"Crawl error: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        print(error_msg)  # Log to console
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


if __name__ == "__main__":
    import os
    import uvicorn

    port = int(os.getenv("PORT", "8080"))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)


