import os
import json
import time
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import email.utils
from flask import Flask, jsonify, make_response, send_from_directory

app = Flask(__name__, static_folder='static', static_url_path='')

CACHE_FILE = "releases_cache.json"
CACHE_DURATION_SECONDS = 600  # 10 minutes
FEED_URL = os.environ.get("FEED_URL", "https://docs.cloud.google.com/feeds/bigquery-release-notes.xml")

class FeedCache:
    def __init__(self, cache_file=None, duration=None):
        self.cache_file = cache_file if cache_file is not None else CACHE_FILE
        self.duration = duration if duration is not None else CACHE_DURATION_SECONDS

    def get(self):
        """Returns the cached list of releases if fresh, else None."""
        if not os.path.exists(self.cache_file):
            return None
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            timestamp = data.get("timestamp", 0)
            if time.time() - timestamp < self.duration:
                return data.get("releases", [])
        except Exception:
            pass
        return None

    def get_any(self):
        """Returns cached data regardless of age, or empty list if none exists."""
        if not os.path.exists(self.cache_file):
            return []
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("releases", [])
        except Exception:
            return []

    def set(self, releases):
        """Saves releases to cache file with current timestamp."""
        try:
            data = {
                "timestamp": time.time(),
                "releases": releases
            }
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

def normalize_date(date_str):
    if not date_str:
        return ""
    # Try parsing as ISO format first (e.g., from Atom: 2026-06-22T05:44:22Z)
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            return dt.isoformat()
        except ValueError:
            pass
            
    # Try parsing as RFC 2822 / RFC 822 (e.g., RSS: Mon, 22 Jun 2026 05:44:22 GMT)
    try:
        dt = email.utils.parsedate_to_datetime(date_str)
        return dt.isoformat()
    except Exception:
        pass
        
    return date_str

def parse_xml_feed(xml_content):
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        raise ValueError(f"Malformed XML: {e}")
        
    releases = []
    
    def get_tag_name(element):
        tag = element.tag
        if '}' in tag:
            return tag.split('}', 1)[1]
        return tag
        
    root_tag = get_tag_name(root)
    
    if root_tag == 'feed':
        for entry in root.findall('.//{http://www.w3.org/2005/Atom}entry') or root.findall('.//entry'):
            title_el = entry.find('{http://www.w3.org/2005/Atom}title') or entry.find('title')
            link_el = entry.find('{http://www.w3.org/2005/Atom}link') or entry.find('link')
            content_el = (entry.find('{http://www.w3.org/2005/Atom}content') or 
                          entry.find('{http://www.w3.org/2005/Atom}summary') or 
                          entry.find('content') or 
                          entry.find('summary'))
            updated_el = (entry.find('{http://www.w3.org/2005/Atom}updated') or 
                          entry.find('{http://www.w3.org/2005/Atom}published') or 
                          entry.find('updated') or 
                          entry.find('published'))
            
            title = title_el.text if title_el is not None else ""
            link = ""
            if link_el is not None:
                link = link_el.attrib.get('href', '') or link_el.text or ""
            description = content_el.text if content_el is not None else ""
            pub_date = updated_el.text if updated_el is not None else ""
            
            releases.append({
                "title": title.strip() if title else "",
                "link": link.strip() if link else "",
                "description": description.strip() if description else "",
                "pubDate": normalize_date(pub_date)
            })
            
    elif root_tag == 'rss':
        for item in root.findall('.//item'):
            title_el = item.find('title')
            link_el = item.find('link')
            desc_el = item.find('description')
            pub_date_el = item.find('pubDate')
            
            title = title_el.text if title_el is not None else ""
            link = link_el.text if link_el is not None else ""
            description = desc_el.text if desc_el is not None else ""
            pub_date = pub_date_el.text if pub_date_el is not None else ""
            
            releases.append({
                "title": title.strip() if title else "",
                "link": link.strip() if link else "",
                "description": description.strip() if description else "",
                "pubDate": normalize_date(pub_date)
            })
    else:
        for item in (root.findall('.//entry') + root.findall('.//item')):
            title = item.findtext('title') or ""
            link_el = item.find('link')
            link = ""
            if link_el is not None:
                link = link_el.attrib.get('href', '') or link_el.text or ""
            description = item.findtext('content') or item.findtext('summary') or item.findtext('description') or ""
            pub_date = item.findtext('updated') or item.findtext('published') or item.findtext('pubDate') or ""
            
            releases.append({
                "title": title.strip() if title else "",
                "link": link.strip() if link else "",
                "description": description.strip() if description else "",
                "pubDate": normalize_date(pub_date)
            })
            
    return releases

def fetch_raw_feed(url):
    if url.startswith("http://") or url.startswith("https://"):
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.text
    else:
        local_path = url
        if url.startswith("file://"):
            local_path = url[7:]
        with open(local_path, 'r', encoding='utf-8') as f:
            return f.read()

def get_releases():
    cache = FeedCache()
    releases = cache.get()
    if releases is not None:
        return releases, "cache_hit"
        
    try:
        xml_content = fetch_raw_feed(FEED_URL)
        parsed_releases = parse_xml_feed(xml_content)
        cache.set(parsed_releases)
        return parsed_releases, "fetched"
    except Exception as e:
        releases = cache.get_any()
        if releases:
            return releases, "fallback_cache"
        return [], f"failed: {str(e)}"

@app.route('/api/releases', methods=['GET'])
def api_releases():
    releases, status = get_releases()
    response = make_response(jsonify(releases))
    response.headers['X-Cache-Status'] = status
    return response

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
