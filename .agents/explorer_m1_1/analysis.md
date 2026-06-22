# Milestone 1 Analysis: Backend API Strategy

This document outlines the investigation findings, architectural details, caching/error handling designs, and proposed implementation files for Milestone 1 of the BigQuery Release Notes RSS Aggregator.

---

## 1. Problem and Feed Analysis

The backend API is responsible for fetching, parsing, and exposing the BigQuery release notes XML feed via a JSON endpoint `/api/releases`. 

### Feed Details
- **Source URL**: `https://docs.cloud.google.com/feeds/bigquery-release-notes.xml`
- **Format**: Typically an Atom feed (`xmlns="http://www.w3.org/2005/Atom"`), but the aggregator must be flexible enough to handle standard RSS formats (`<item>`, `<title>`, `<link>`, `<description>`, `<pubDate>`) to guarantee robust backward/forward compatibility.
- **Data Extracted**:
  - `title`: The title of the release note.
  - `link`: The permalink URL to the release note.
  - `description`: The main body text/HTML of the release note.
  - `pubDate`: The date of publication (either in ISO-8601 format for Atom or parsed date string for RSS).

---

## 2. Proposed Architecture & Design Decisions

### A. Dual-Layer Caching (In-Memory + File-Based)
Since external network requests are subject to latency, rate-limiting, and intermittent failures, the API must implement caching.
1. **In-Memory Cache**: Active requests within the TTL (default: 600 seconds / 10 minutes) will be served immediately from memory.
2. **File-Based Cache (`releases_cache.json`)**: Serves as persistent cache across application restarts and acts as a robust recovery fallback if the network/feed is offline.
3. **Stale-While-Revalidate Fallback**: If the cache expires and a live fetch fails, the app falls back to the expired cache (either from memory or from disk) instead of returning an error, appending an `X-Warning` response header to notify client-side components of stale data.

### B. Environment-Driven Configuration
To enable clean integration testing (e.g., E2E offline mock tests as described in `TEST_INFRA.md`), the application configurations will be environment-variable-driven:
- `RSS_FEED_URL`: Defaults to the live Google Cloud feed, but can be configured to point to a local file or local mock server URL (e.g., `/mnt/.../e2e_tests/mock_feed.xml` or `file:///...`) during testing.
- `CACHE_TIMEOUT`: Configurable cache duration in seconds.
- `CACHE_FILE`: File path for the persistent JSON cache.

### C. Separation of Concerns for HTML Stripping
The E2E test inventory requires the Twitter share feature to strip HTML tags from descriptions. To preserve formatting (bold text, lists, links) on the timeline, the backend will return raw description HTML as provided by the Google feed. The frontend will be responsible for stripping HTML tags prior to generating the Twitter Web Intent payload.

---

## 3. Proposed Implementation Files

### `requirements.txt`
```text
Flask>=3.0.0
requests>=2.31.0
```

### `app.py`
```python
import os
import time
import json
import logging
from datetime import datetime
import xml.etree.ElementTree as ET
import requests
from flask import Flask, jsonify, send_from_directory

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='static', static_url_path='')

# Configuration via environment variables
FEED_URL = os.environ.get('RSS_FEED_URL', 'https://docs.cloud.google.com/feeds/bigquery-release-notes.xml')
CACHE_TIMEOUT = int(os.environ.get('CACHE_TIMEOUT', 600))
CACHE_FILE = os.environ.get('CACHE_FILE', 'releases_cache.json')

# In-memory cache state
_cached_releases = None
_last_fetched = 0.0

def parse_xml_feed(xml_content):
    """
    Parses Atom or RSS XML content and returns a list of release dictionaries.
    """
    root = ET.fromstring(xml_content)
    
    # Namespace definitions for Atom
    namespaces = {
        'atom': 'http://www.w3.org/2005/Atom'
    }
    
    releases = []
    
    # 1. Attempt parsing as Atom Feed
    entries = root.findall('.//atom:entry', namespaces)
    if entries:
        for entry in entries:
            title_node = entry.find('atom:title', namespaces)
            links = entry.findall('atom:link', namespaces)
            
            # Resolve link: favor rel="alternate", fallback to first link
            link = ""
            for l in links:
                if l.attrib.get('rel', 'alternate') == 'alternate':
                    link = l.attrib.get('href', '')
                    break
            if not link and links:
                link = links[0].attrib.get('href', '')
            
            # Resolve description: content (preferred) or summary
            desc_node = entry.find('atom:content', namespaces)
            if desc_node is None:
                desc_node = entry.find('atom:summary', namespaces)
            
            # Resolve publish date: updated or published
            pub_date_node = entry.find('atom:updated', namespaces)
            if pub_date_node is None:
                pub_date_node = entry.find('atom:published', namespaces)
                
            title = title_node.text.strip() if title_node is not None and title_node.text else ""
            description = desc_node.text.strip() if desc_node is not None and desc_node.text else ""
            pub_date = pub_date_node.text.strip() if pub_date_node is not None and pub_date_node.text else ""
            
            releases.append({
                "title": title,
                "link": link,
                "description": description,
                "pubDate": pub_date
            })
            
    # 2. Fallback to RSS Feed parsing if no Atom entries found
    else:
        items = root.findall('.//item')
        for item in items:
            title_node = item.find('title')
            link_node = item.find('link')
            desc_node = item.find('description')
            pub_date_node = item.find('pubDate')
            
            title = title_node.text.strip() if title_node is not None and title_node.text else ""
            link = link_node.text.strip() if link_node is not None and link_node.text else ""
            description = desc_node.text.strip() if desc_node is not None and desc_node.text else ""
            pub_date = pub_date_node.text.strip() if pub_date_node is not None and pub_date_node.text else ""
            
            releases.append({
                "title": title,
                "link": link,
                "description": description,
                "pubDate": pub_date
            })
            
    return releases

def load_cache_from_disk():
    """Loads cached data from CACHE_FILE if it exists."""
    global _cached_releases, _last_fetched
    if os.path.exists(CACHE_FILE):
        try:
            mtime = os.path.getmtime(CACHE_FILE)
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                _cached_releases = data
                _last_fetched = mtime
                logger.info(f"Loaded disk cache: {len(data)} items (mtime: {datetime.fromtimestamp(mtime).isoformat()})")
                return True
        except Exception as e:
            logger.error(f"Error loading disk cache file: {e}")
    return False

def save_cache_to_disk(data):
    """Saves data to CACHE_FILE."""
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved cache to disk: {len(data)} items")
    except Exception as e:
        logger.error(f"Error saving cache to disk: {e}")

def get_releases():
    """
    Retrieves release data using cache-first flow with online refresh and stale-recovery fallback.
    """
    global _cached_releases, _last_fetched
    
    current_time = time.time()
    
    # Step A: Check active in-memory cache
    if _cached_releases is not None and (current_time - _last_fetched < CACHE_TIMEOUT):
        logger.info("Serving from active in-memory cache")
        return _cached_releases, None
        
    # Step B: Check active disk cache if in-memory is empty
    if _cached_releases is None:
        load_cache_from_disk()
        if _cached_releases is not None and (current_time - _last_fetched < CACHE_TIMEOUT):
            logger.info("Serving from active disk cache")
            return _cached_releases, None
            
    # Step C: Revalidate cache (fetch live XML feed)
    logger.info(f"Fetching XML feed from: {FEED_URL}")
    try:
        # Check if FEED_URL is a local file (useful for offline/E2E testing)
        if FEED_URL.startswith('/') or FEED_URL.startswith('file://') or os.path.exists(FEED_URL):
            file_path = FEED_URL.replace('file://', '')
            with open(file_path, 'r', encoding='utf-8') as f:
                xml_content = f.read()
        else:
            response = requests.get(FEED_URL, timeout=10)
            response.raise_for_status()
            xml_content = response.text
            
        releases = parse_xml_feed(xml_content)
        
        # Update cache values
        _cached_releases = releases
        _last_fetched = current_time
        save_cache_to_disk(releases)
        
        return releases, None
        
    except Exception as e:
        logger.error(f"Fetch/parsing failed: {e}")
        
        # Stale fallback 1: Expired in-memory cache
        if _cached_releases is not None:
            logger.warning("Returning expired in-memory cache as fallback.")
            return _cached_releases, f"Feed offline. Stale data timestamp: {datetime.fromtimestamp(_last_fetched).isoformat()}"
            
        # Stale fallback 2: Expired disk cache
        if load_cache_from_disk():
            logger.warning("Returning expired disk cache as fallback.")
            return _cached_releases, f"Feed offline. Stale data timestamp: {datetime.fromtimestamp(_last_fetched).isoformat()}"
            
        # Empty fallback: No cache available
        logger.error("No cached data available to fall back to.")
        return [], "Feed offline and no cached data is available."

@app.route('/api/releases', methods=['GET'])
def api_releases():
    releases, warning = get_releases()
    response_data = jsonify(releases)
    if warning:
        response_data.headers['X-Warning'] = warning
    return response_data

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
```
