# Milestone 1 Analysis Report: Backend API Implementation Strategy

## 1. Overview and Constraints
This report outlines the proposed backend architecture and implementation strategy for the BigQuery Release Notes RSS Aggregator. The goal is to design a Flask application that aggregates a live BigQuery release notes XML feed, parses it, applies cache-aside mechanics with stale-on-error fallback, and returns a JSON payload matching the contract.

### Constraints & Requirements
* **Feed Source**: `https://docs.cloud.google.com/feeds/bigquery-release-notes.xml`
* **Network Mode**: In production, the feed must be fetched from the live Google Cloud endpoint.
* **Interface Contract**: Expose `/api/releases` returning:
  ```json
  [
    {
      "title": "String",
      "link": "String",
      "description": "String",
      "pubDate": "String (ISO format or parsed date string)"
    }
  ]
  ```
* **Resiliency**: Implement caching with fallback capabilities when the feed is offline or invalid.
* **Write Permission**: Read-only explorer. No source code modifications are performed directly.

---

## 2. Feed Parsing Strategy
Google Cloud feeds are formatted as Atom XML documents. Standard RSS and Atom have distinct element vocabularies:

| Field | Atom Element | RSS Element | Target JSON Key |
|---|---|---|---|
| **Title** | `<title>` | `<title>` | `title` |
| **Link** | `<link href="..."/>` (attribute) | `<link>` (text content) | `link` |
| **Description** | `<content>` or `<summary>` | `<description>` | `description` |
| **Date** | `<published>` or `<updated>` | `<pubDate>` | `pubDate` (formatted to ISO) |

### Double-Layer Parser Design
To ensure ultimate reliability, we propose a two-tiered parser design:
1. **Primary Parser (`feedparser` library)**: A robust python feed aggregator parser that handles varying encodings, tags, relative URLs, namespaces, and sanitization automatically.
2. **Fallback Parser (`xml.etree.ElementTree`)**: Standard library XML parser. If `feedparser` fails or is not installed, the app falls back to this parser to maintain service without crashing.

### Normalizing pubDate
Atom feeds utilize ISO-8601 strings (e.g., `2026-06-18T00:00:00Z`). RSS feeds typically use RFC-2822 (e.g., `Thu, 18 Jun 2026 00:00:00 GMT`). We use `datetime.fromisoformat` and `email.utils.parsedate_to_datetime` to parse either style and convert to clean ISO-8601 strings.

---

## 3. Caching & Thread Safety Design
Since Flask is inherently multi-threaded, caching must be designed to withstand simultaneous requests.

### File-Based Persistence
Using an in-memory cache loses its state whenever the Flask server restarts or is recycled by the WSGI host (e.g., gunicorn). Thus, we use a file-based cache in `releases_cache.json`.

### Lifecycle Flowchart
```
                 [Request to /api/releases]
                            │
              Is there a valid cache file?
               /                        \
             Yes                         No
             /                             \
    Is cache < 10 mins old?               Fetch live feed
        /             \                     /            \
      Yes              No                Success        Fail
      /                 \                 /                \
[Serve Cache]     Fetch live feed    [Save Cache]   Does cache exist?
                   /          \      [Serve New]      /          \
                Success      Fail                   Yes           No
                 /              \                   /               \
           [Save Cache]    [Serve Stale Cache] [Serve Stale]   [Serve Error]
           [Serve New]     [Header Warning]    [Header Warning] [HTTP 503 + []]
```

### Thread Synchronization
We establish a threading lock (`threading.Lock()`) around read/write operations targeting `releases_cache.json` to prevent file corruption.

### Refresh Override
To support the UI's manual "Refresh" button, the endpoint accepts a query parameter: `/api/releases?refresh=true`. This forces a live fetch, bypassing the expiration check, but will still fall back to cached data if the remote fetch fails.

---

## 4. Proposed File Contents

### `requirements.txt`
```text
Flask>=2.0.0
requests>=2.25.0
feedparser>=6.0.0
```

### `app.py`
```python
import os
import time
import json
import logging
import threading
import email.utils
from datetime import datetime
from flask import Flask, jsonify, request

# Initialize Flask application
app = Flask(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
FEED_URL = "https://docs.cloud.google.com/feeds/bigquery-release-notes.xml"
CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'releases_cache.json')
CACHE_TIMEOUT = 600  # 10 minutes (600 seconds)

# Threading lock for cache file access to prevent race conditions
cache_lock = threading.Lock()

def parse_date(date_str):
    """
    Normalizes feed date strings (ISO or RFC 2822) to a standardized ISO-8601 format.
    """
    if not date_str:
        return ""
    
    # Try parsing as ISO-8601 (standard for Atom feeds)
    try:
        cleaned = date_str.strip()
        if cleaned.endswith('Z'):
            cleaned = cleaned[:-1] + '+00:00'
        return datetime.fromisoformat(cleaned).isoformat()
    except Exception:
        pass

    # Try parsing as RFC 2822 (standard for RSS pubDate)
    try:
        dt = email.utils.parsedate_to_datetime(date_str)
        return dt.isoformat()
    except Exception:
        pass
        
    return date_str

def parse_xml_fallback(xml_content):
    """
    Parses Atom or RSS XML feed using standard library xml.etree.ElementTree.
    Used if feedparser is unavailable or raises an exception.
    """
    import xml.etree.ElementTree as ET
    root = ET.fromstring(xml_content)
    
    namespaces = {
        'atom': 'http://www.w3.org/2005/Atom'
    }
    
    releases = []
    
    # Check if Atom feed (root tag ends with 'feed' or has the Atom namespace)
    if 'feed' in root.tag or root.tag.endswith('feed'):
        entries = root.findall('.//atom:entry', namespaces) or root.findall('.//entry')
        for entry in entries:
            title_el = entry.find('atom:title', namespaces) or entry.find('title')
            title = title_el.text if title_el is not None else ""
            
            link_el = entry.find('atom:link', namespaces) or entry.find('link')
            link = ""
            if link_el is not None:
                link = link_el.attrib.get('href', '')
                if not link and link_el.text:
                    link = link_el.text.strip()
                    
            desc_el = (entry.find('atom:content', namespaces) or entry.find('content') or
                      entry.find('atom:summary', namespaces) or entry.find('summary'))
            description = desc_el.text if desc_el is not None else ""
            
            pub_el = (entry.find('atom:published', namespaces) or entry.find('published') or
                     entry.find('atom:updated', namespaces) or entry.find('updated'))
            pub_date_raw = pub_el.text if pub_el is not None else ""
            pub_date = parse_date(pub_date_raw)
            
            releases.append({
                "title": title.strip() if title else "",
                "link": link.strip() if link else "",
                "description": description.strip() if description else "",
                "pubDate": pub_date
            })
    else:
        # Standard RSS feed
        items = root.findall('.//item')
        for item in items:
            title_el = item.find('title')
            title = title_el.text if title_el is not None else ""
            
            link_el = item.find('link')
            link = link_el.text if link_el is not None else ""
            
            desc_el = item.find('description')
            description = desc_el.text if desc_el is not None else ""
            
            pub_el = item.find('pubDate')
            pub_date_raw = pub_el.text if pub_el is not None else ""
            pub_date = parse_date(pub_date_raw)
            
            releases.append({
                "title": title.strip() if title else "",
                "link": link.strip() if link else "",
                "description": description.strip() if description else "",
                "pubDate": pub_date
            })
            
    return releases

def fetch_and_parse_feed():
    """
    Fetches the live XML feed with a timeout, then parses it using
    feedparser (primary) or xml.etree.ElementTree (fallback).
    """
    import requests
    
    # 10s timeout ensures the app does not hang indefinitely on network failure
    response = requests.get(FEED_URL, timeout=10)
    response.raise_for_status()
    
    try:
        import feedparser
        feed = feedparser.parse(response.content)
        
        # Raise parse failure error if feed is completely invalid and has no elements
        if not feed.entries and feed.get('bozo', 0) == 1:
            exc = feed.get('bozo_exception')
            raise ValueError(f"Feed parsing error: {exc}")
            
        releases = []
        for entry in feed.entries:
            title = entry.get('title', '')
            link = entry.get('link', '')
            description = entry.get('summary', entry.get('description', ''))
            pub_date_raw = entry.get('published', entry.get('updated', ''))
            pub_date = parse_date(pub_date_raw)
            
            releases.append({
                "title": title.strip() if title else "",
                "link": link.strip() if link else "",
                "description": description.strip() if description else "",
                "pubDate": pub_date
            })
        return releases
        
    except ImportError:
        logger.warning("feedparser is not installed; falling back to xml.etree.ElementTree")
        return parse_xml_fallback(response.content)
    except Exception as e:
        logger.warning(f"feedparser failed to parse: {e}; falling back to xml.etree.ElementTree")
        return parse_xml_fallback(response.content)

def load_cache():
    """
    Thread-safe method to load cached releases from local JSON file.
    """
    with cache_lock:
        if not os.path.exists(CACHE_FILE):
            return None
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict) and 'timestamp' in data and 'releases' in data:
                    return data
        except Exception as e:
            logger.error(f"Error loading cache file: {e}")
        return None

def save_cache(releases):
    """
    Thread-safe method to save releases to local JSON cache file.
    """
    with cache_lock:
        try:
            data = {
                "timestamp": time.time(),
                "releases": releases
            }
            with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving to cache file: {e}")

@app.route('/')
def index():
    """Serves the main single-page UI index file."""
    try:
        return app.send_static_file('index.html')
    except Exception:
        return "Frontend file not found.", 404

@app.route('/api/releases', methods=['GET'])
def get_releases():
    """
    Exposes cached or live releases. Returns a JSON array.
    """
    force_refresh = request.args.get('refresh', 'false').lower() == 'true'
    
    # 1. Check cache state
    cache_data = load_cache()
    now = time.time()
    use_cache = False
    
    if cache_data is not None:
        cache_age = now - cache_data.get('timestamp', 0)
        if not force_refresh and cache_age < CACHE_TIMEOUT:
            use_cache = True
            
    # 2. Return cache hit immediately if valid
    if use_cache:
        logger.info("Serving from cache (cache age: %.1f seconds)", now - cache_data['timestamp'])
        response = jsonify(cache_data['releases'])
        response.headers['X-Cache-Status'] = 'HIT'
        return response
        
    # 3. Cache is cold, stale, or refresh is forced. Try live fetch.
    try:
        logger.info("Refreshing releases feed")
        releases = fetch_and_parse_feed()
        save_cache(releases)
        
        response = jsonify(releases)
        response.headers['X-Cache-Status'] = 'MISS'
        return response
    except Exception as e:
        logger.error(f"Feed retrieval failure: {e}")
        
        # 4. Fallback: serve stale cache if available
        if cache_data is not None:
            logger.warning("Serving stale cache data due to fetch failure")
            response = jsonify(cache_data['releases'])
            response.headers['X-Cache-Status'] = 'STALE'
            response.headers['X-Cache-Error'] = str(e)
            return response
            
        # 5. Severe failure: cache is empty and remote fetch failed.
        # Must return an empty JSON array [] to comply with the list contract.
        logger.error("No cache data available for fallback")
        response = jsonify([])
        response.headers['X-Cache-Status'] = 'ERROR'
        response.headers['X-Cache-Error'] = str(e)
        response.status_code = 503
        return response

if __name__ == '__main__':
    # Run the server on port 5000 with debug enabled
    app.run(host='0.0.0.0', port=5000, debug=True)
```

---

## 5. Verification Mapping (E2E Test Coverage)
The design resolves several key cases mapped in `TEST_INFRA.md`:

1. **`test_backend_returns_valid_json`**: Implemented by returning standard `jsonify` responses.
2. **`test_backend_releases_format`**: Implemented by transforming parsed elements to exact keys: `title`, `link`, `description`, and `pubDate`.
3. **`test_backend_caching_behavior`**: Serves from `releases_cache.json` under `CACHE_TIMEOUT` boundaries returning `X-Cache-Status: HIT`.
4. **`test_backend_feed_offline`**: Catches `requests.RequestException` and returns cached data or a fallback empty array `[]` (HTTP 503).
5. **`test_backend_invalid_rss_feed`**: Handles parsing exception gracefully with `xml.etree` fail-safes.
