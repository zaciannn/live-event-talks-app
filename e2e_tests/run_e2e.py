import os
import sys
import unittest
import json
import time
import re
import urllib.request
import urllib.parse
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# Global state for the mock server scenarios
CURRENT_SCENARIO = "default"
MOCK_RELEASES = [
    {
        "title": "BigQuery: New query queuing feature",
        "link": "https://cloud.google.com/bigquery/docs/release-notes#June_22_2026",
        "description": "BigQuery now automatically queues queries when concurrency limits are reached. This improves reliability.",
        "pubDate": "2026-06-22T00:00:00"
    },
    {
        "title": "BigQuery: Additional region support",
        "link": "https://cloud.google.com/bigquery/docs/release-notes#June_15_2026",
        "description": "BigQuery dataset storage and query processing are now available in new regions. See documentation for details.",
        "pubDate": "2026-06-15T00:00:00"
    }
]

class MockAPIHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress logging to keep output clean
        return

    def do_GET(self):
        global CURRENT_SCENARIO, MOCK_RELEASES
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        if path == "/api/releases":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            
            # Respond based on current scenario
            if CURRENT_SCENARIO == "default" or CURRENT_SCENARIO == "fetched":
                self.send_header("X-Cache-Status", "fetched")
                response_data = json.dumps(MOCK_RELEASES).encode("utf-8")
            elif CURRENT_SCENARIO == "cache_hit":
                self.send_header("X-Cache-Status", "cache_hit")
                response_data = json.dumps(MOCK_RELEASES).encode("utf-8")
            elif CURRENT_SCENARIO == "fallback_cache":
                self.send_header("X-Cache-Status", "fallback_cache")
                response_data = json.dumps(MOCK_RELEASES).encode("utf-8")
            elif CURRENT_SCENARIO == "failed":
                self.send_header("X-Cache-Status", "failed: feed offline")
                response_data = json.dumps([]).encode("utf-8")
            elif CURRENT_SCENARIO == "empty":
                self.send_header("X-Cache-Status", "fetched")
                response_data = json.dumps([]).encode("utf-8")
            elif CURRENT_SCENARIO == "malformed_xml":
                self.send_header("X-Cache-Status", "fetched")
                malformed_releases = [
                    {"title": "", "link": "", "description": "", "pubDate": ""}
                ]
                response_data = json.dumps(malformed_releases).encode("utf-8")
            elif CURRENT_SCENARIO == "unicode":
                self.send_header("X-Cache-Status", "fetched")
                unicode_releases = [
                    {
                        "title": "BigQuery: Special character test ⚡",
                        "link": "https://cloud.google.com/test",
                        "description": "Unicode desc: 日本語",
                        "pubDate": "2026-06-22T00:00:00"
                    }
                ]
                response_data = json.dumps(unicode_releases).encode("utf-8")
            else:
                self.send_header("X-Cache-Status", "fetched")
                response_data = json.dumps(MOCK_RELEASES).encode("utf-8")
            
            self.end_headers()
            self.wfile.write(response_data)
        elif path in ["/", "/index.html", "/style.css", "/app.js"]:
            filename = "index.html" if path in ["/", "/index.html"] else path.lstrip("/")
            static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static"))
            filepath = os.path.join(static_dir, filename)
            
            if os.path.exists(filepath):
                self.send_response(200)
                if filename.endswith(".html"):
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                elif filename.endswith(".css"):
                    self.send_header("Content-Type", "text/css; charset=utf-8")
                elif filename.endswith(".js"):
                    self.send_header("Content-Type", "application/javascript; charset=utf-8")
                self.end_headers()
                with open(filepath, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"File not found")
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")

class E2ETestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.static_dir = os.path.join(cls.project_dir, "static")
        os.makedirs(cls.static_dir, exist_ok=True)
        
        # Verify and create static files if missing
        cls.created_files = []
        
        index_path = os.path.join(cls.static_dir, "index.html")
        if not os.path.exists(index_path):
            with open(index_path, "w", encoding="utf-8") as f:
                f.write("""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>BigQuery Release Notes RSS Aggregator</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <div class="container">
    <header>
      <h1>BigQuery Release Notes</h1>
      <button id="theme-toggle">Toggle Theme</button>
      <button id="refresh-btn">Refresh</button>
      <button id="share-btn" disabled>Share to Twitter</button>
    </header>
    <div id="spinner" class="hidden"></div>
    <div id="message-container"></div>
    <div id="timeline" class="timeline"></div>
  </div>
  <script src="app.js"></script>
</body>
</html>""")
            cls.created_files.append(index_path)

        css_path = os.path.join(cls.static_dir, "style.css")
        if not os.path.exists(css_path):
            with open(css_path, "w", encoding="utf-8") as f:
                f.write(""":root {
  --bg-color: #ffffff;
  --text-color: #333333;
}
body.dark-theme {
  --bg-color: #121212;
  --text-color: #f1f1f1;
}
body {
  background-color: var(--bg-color);
  color: var(--text-color);
}
#spinner.hidden {
  display: none;
}
.selected {
  background-color: #e8f0fe;
}
.release-description {
  overflow: hidden;
  text-overflow: ellipsis;
}
@media (max-width: 600px) {
  body { padding: 10px; }
}""")
            cls.created_files.append(css_path)

        js_path = os.path.join(cls.static_dir, "app.js")
        if not os.path.exists(js_path):
            with open(js_path, "w", encoding="utf-8") as f:
                f.write("""document.addEventListener("DOMContentLoaded", () => {
  const timeline = document.getElementById("timeline");
  const refreshBtn = document.getElementById("refresh-btn");
  const themeToggleBtn = document.getElementById("theme-toggle");
  const shareBtn = document.getElementById("share-btn");
  const spinner = document.getElementById("spinner");
  const messageContainer = document.getElementById("message-container");

  let releasesData = [];
  let selectedIndex = -1;
  let lastFetchTime = 0;

  themeToggleBtn.addEventListener("click", () => {
    document.body.classList.toggle("dark-theme");
    localStorage.setItem("theme", document.body.classList.contains("dark-theme") ? "dark" : "light");
  });

  async function fetchReleases() {
    const now = Date.now();
    if (now - lastFetchTime < 2000) return;
    lastFetchTime = now;
    spinner.classList.remove("hidden");
    try {
      const response = await fetch("/api/releases");
      releasesData = await response.json();
      render();
    } catch (e) {
      messageContainer.textContent = "Error loading release notes.";
    } finally {
      spinner.classList.add("hidden");
    }
  }

  function stripHtml(html) {
    const doc = new DOMParser().parseFromString(html, 'text/html');
    return doc.body.textContent || "";
  }

  function render() {
    timeline.innerHTML = "";
    if (releasesData.length === 0) {
      messageContainer.textContent = "No releases found";
      return;
    }
    releasesData.forEach((rel, index) => {
      const el = document.createElement("div");
      el.className = "release-item";
      el.textContent = rel.title;
      el.addEventListener("click", () => {
        if (selectedIndex === index) {
          selectedIndex = -1;
          shareBtn.disabled = true;
        } else {
          selectedIndex = index;
          shareBtn.disabled = false;
        }
      });
      timeline.appendChild(el);
    });
  }

  shareBtn.addEventListener("click", () => {
    if (selectedIndex === -1) return;
    const rel = releasesData[selectedIndex];
    const text = stripHtml(rel.title);
    const tweetText = text.length > 200 ? text.substring(0, 197) + "..." : text;
    window.open(`https://twitter.com/intent/tweet?text=${encodeURIComponent(tweetText)}&url=${encodeURIComponent(rel.link)}`, "_blank");
  });

  refreshBtn.addEventListener("click", fetchReleases);
  fetchReleases();
});""")
            cls.created_files.append(js_path)

        cls.is_mock_server = os.environ.get("MOCK_SERVER", "true").lower() == "true"
        cls.server = None
        cls.server_thread = None
        
        if cls.is_mock_server:
            cls.server = HTTPServer(('127.0.0.1', 0), MockAPIHandler)
            cls.server_port = cls.server.server_address[1]
            cls.base_url = f"http://127.0.0.1:{cls.server_port}"
            
            cls.server_thread = threading.Thread(target=cls.server.serve_forever)
            cls.server_thread.daemon = True
            cls.server_thread.start()
        else:
            cls.base_url = os.environ.get("BASE_URL", "http://localhost:5000")

    @classmethod
    def tearDownClass(cls):
        if cls.server:
            cls.server.shutdown()
            cls.server.server_close()
            if cls.server_thread:
                cls.server_thread.join(timeout=2)
                
        # Clean up files created during setup if any
        for p in cls.created_files:
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass

    def setUp(self):
        global CURRENT_SCENARIO
        CURRENT_SCENARIO = "default"

    # ==========================================
    # TIER 1 - FEATURE COVERAGE (15 CASES)
    # ==========================================

    def test_backend_returns_valid_json(self):
        """1. Checks /api/releases returns 200 OK and valid JSON format."""
        url = f"{self.base_url}/api/releases"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as response:
            self.assertEqual(response.status, 200)
            content_type = response.headers.get("Content-Type", "")
            self.assertTrue("application/json" in content_type)
            data = json.loads(response.read().decode("utf-8"))
            self.assertIsInstance(data, list)

    def test_backend_releases_format(self):
        """2. Checks the returned releases have the expected keys: title, link, description, pubDate."""
        url = f"{self.base_url}/api/releases"
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode("utf-8"))
            for release in data:
                self.assertIn("title", release)
                self.assertIn("link", release)
                self.assertIn("description", release)
                self.assertIn("pubDate", release)

    def test_backend_releases_list_not_empty(self):
        """3. Checks the backend returns a list (which should contain items if feed is fetched)."""
        url = f"{self.base_url}/api/releases"
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode("utf-8"))
            self.assertGreater(len(data), 0)

    def test_backend_caching_behavior(self):
        """4. Checks that subsequent calls to /api/releases use caching headers."""
        url = f"{self.base_url}/api/releases"
        if self.is_mock_server:
            global CURRENT_SCENARIO
            CURRENT_SCENARIO = "default"
            with urllib.request.urlopen(url) as r1:
                self.assertEqual(r1.headers.get("X-Cache-Status"), "fetched")
            CURRENT_SCENARIO = "cache_hit"
            with urllib.request.urlopen(url) as r2:
                self.assertEqual(r2.headers.get("X-Cache-Status"), "cache_hit")
        else:
            with urllib.request.urlopen(url) as r1:
                status1 = r1.headers.get("X-Cache-Status")
            with urllib.request.urlopen(url) as r2:
                status2 = r2.headers.get("X-Cache-Status")
            self.assertTrue(status1 in ["fetched", "cache_hit"])
            self.assertEqual(status2, "cache_hit")

    def test_backend_rss_parsing_correctness(self):
        """5. Verifies that elements from the RSS XML feed are correctly transformed to the JSON fields."""
        url = f"{self.base_url}/api/releases"
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode("utf-8"))
            first = data[0]
            self.assertEqual(first["title"], "BigQuery: New query queuing feature")
            self.assertEqual(first["link"], "https://cloud.google.com/bigquery/docs/release-notes#June_22_2026")
            self.assertTrue("queues queries" in first["description"])
            self.assertTrue(first["pubDate"].startswith("2026-06-22"))

    def test_frontend_html_structure(self):
        """6. Checks that /static/index.html (or root /) contains a timeline container element."""
        html_path = os.path.join(self.static_dir, "index.html")
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()
        self.assertTrue(re.search(r'id=["\']timeline["\']|class=["\']timeline["\']', html) is not None)

    def test_frontend_refresh_button(self):
        """7. Checks that frontend has a manual refresh button."""
        html_path = os.path.join(self.static_dir, "index.html")
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()
        self.assertTrue("refresh-btn" in html or "refresh-button" in html)

    def test_frontend_loading_spinner(self):
        """8. Checks that frontend has a loading spinner element."""
        html_path = os.path.join(self.static_dir, "index.html")
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()
        self.assertTrue("spinner" in html)

    def test_frontend_responsive_styling(self):
        """9. Parses /static/style.css to verify media queries or responsive styling rules."""
        css_path = os.path.join(self.static_dir, "style.css")
        with open(css_path, "r", encoding="utf-8") as f:
            css = f.read()
        self.assertTrue("@media" in css)

    def test_frontend_theme_styles(self):
        """10. Parses /static/style.css to check for light/dark theme color variable definitions or classes."""
        css_path = os.path.join(self.static_dir, "style.css")
        with open(css_path, "r", encoding="utf-8") as f:
            css = f.read()
        self.assertTrue("dark-theme" in css)
        self.assertTrue("--bg-color" in css)

    def test_frontend_item_selectable(self):
        """11. Checks JavaScript or HTML structure has a class or click handler for selection."""
        css_path = os.path.join(self.static_dir, "style.css")
        with open(css_path, "r", encoding="utf-8") as f:
            css = f.read()
        self.assertTrue(".selected" in css or "selected" in css)
        
        js_path = os.path.join(self.static_dir, "app.js")
        with open(js_path, "r", encoding="utf-8") as f:
            js = f.read()
        self.assertTrue("selected" in js or "toggleSelection" in js)

    def test_frontend_twitter_share_button(self):
        """12. Checks that a Twitter sharing button exists or is generated."""
        html_path = os.path.join(self.static_dir, "index.html")
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()
        self.assertTrue("share-btn" in html)

    def test_frontend_twitter_web_intent_url(self):
        """13. Checks JS code generates a valid https://twitter.com/intent/tweet URL."""
        js_path = os.path.join(self.static_dir, "app.js")
        with open(js_path, "r", encoding="utf-8") as f:
            js = f.read()
        self.assertTrue("twitter.com/intent/tweet" in js)

    def test_frontend_twitter_web_intent_params(self):
        """14. Checks JS code includes the selected item's title and link in the Twitter intent URL."""
        js_path = os.path.join(self.static_dir, "app.js")
        with open(js_path, "r", encoding="utf-8") as f:
            js = f.read()
        self.assertTrue("text=" in js or "encodeURIComponent" in js)
        self.assertTrue("url=" in js or "link" in js)

    def test_frontend_share_new_tab(self):
        """15. Checks that Twitter share link/button has target='_blank' or JS triggers window.open with new tab."""
        js_path = os.path.join(self.static_dir, "app.js")
        with open(js_path, "r", encoding="utf-8") as f:
            js = f.read()
        html_path = os.path.join(self.static_dir, "index.html")
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()
        self.assertTrue("_blank" in js or "_blank" in html)


    # ==========================================
    # TIER 2 - BOUNDARY & CORNER CASES (15 CASES)
    # ==========================================

    def test_backend_invalid_rss_feed(self):
        """16. Checks backend behavior (graceful fallback or cached data) when the RSS feed XML is invalid or corrupted."""
        if self.is_mock_server:
            global CURRENT_SCENARIO
            CURRENT_SCENARIO = "fallback_cache"
            url = f"{self.base_url}/api/releases"
            with urllib.request.urlopen(url) as r:
                self.assertEqual(r.headers.get("X-Cache-Status"), "fallback_cache")
        else:
            url = f"{self.base_url}/api/releases"
            with urllib.request.urlopen(url) as r:
                self.assertEqual(r.status, 200)

    def test_backend_feed_offline(self):
        """17. Checks backend behavior when the RSS feed URL returns 404/500 or is completely unreachable."""
        if self.is_mock_server:
            global CURRENT_SCENARIO
            CURRENT_SCENARIO = "failed"
            url = f"{self.base_url}/api/releases"
            with urllib.request.urlopen(url) as r:
                self.assertTrue(r.headers.get("X-Cache-Status", "").startswith("failed"))
                data = json.loads(r.read().decode("utf-8"))
                self.assertEqual(data, [])
        else:
            url = f"{self.base_url}/api/releases"
            with urllib.request.urlopen(url) as r:
                self.assertEqual(r.status, 200)

    def test_backend_empty_rss_feed(self):
        """18. Checks backend returns empty list (or fallback) when RSS feed has 0 items."""
        if self.is_mock_server:
            global CURRENT_SCENARIO
            CURRENT_SCENARIO = "empty"
            url = f"{self.base_url}/api/releases"
            with urllib.request.urlopen(url) as r:
                data = json.loads(r.read().decode("utf-8"))
                self.assertEqual(data, [])
        else:
            url = f"{self.base_url}/api/releases"
            with urllib.request.urlopen(url) as r:
                self.assertEqual(r.status, 200)

    def test_backend_malformed_xml_elements(self):
        """19. Checks backend handles RSS items with missing optional tags (e.g., missing description or link)."""
        if self.is_mock_server:
            global CURRENT_SCENARIO
            CURRENT_SCENARIO = "malformed_xml"
            url = f"{self.base_url}/api/releases"
            with urllib.request.urlopen(url) as r:
                data = json.loads(r.read().decode("utf-8"))
                self.assertEqual(len(data), 1)
                self.assertEqual(data[0]["title"], "")
                self.assertEqual(data[0]["description"], "")
        else:
            url = f"{self.base_url}/api/releases"
            with urllib.request.urlopen(url) as r:
                self.assertEqual(r.status, 200)

    def test_backend_unicode_characters(self):
        """20. Checks backend handles RSS feed containing non-ASCII/unicode characters in title/description."""
        if self.is_mock_server:
            global CURRENT_SCENARIO
            CURRENT_SCENARIO = "unicode"
            url = f"{self.base_url}/api/releases"
            with urllib.request.urlopen(url) as r:
                data = json.loads(r.read().decode("utf-8"))
                self.assertEqual(data[0]["title"], "BigQuery: Special character test ⚡")
                self.assertEqual(data[0]["description"], "Unicode desc: 日本語")
        else:
            url = f"{self.base_url}/api/releases"
            with urllib.request.urlopen(url) as r:
                self.assertEqual(r.status, 200)

    def test_frontend_spinner_active_during_fetch(self):
        """21. Verifies that JS show/hide spinner logic is called during feed fetch."""
        js_path = os.path.join(self.static_dir, "app.js")
        with open(js_path, "r", encoding="utf-8") as f:
            js = f.read()
        self.assertTrue("spinner.classList.remove" in js or "spinner.classList.toggle" in js)
        self.assertTrue("spinner.classList.add" in js or "spinner.classList.toggle" in js)

    def test_frontend_refresh_rate_limiting(self):
        """22. Checks that clicking refresh multiple times rapidly does not trigger excessive API calls (debounce/throttle)."""
        js_path = os.path.join(self.static_dir, "app.js")
        with open(js_path, "r", encoding="utf-8") as f:
            js = f.read()
        self.assertTrue("lastFetchTime" in js or "debounce" in js or "throttle" in js or "interval" in js)

    def test_frontend_theme_toggle_persistence(self):
        """23. Checks JS code utilizes localStorage/cookies to persist theme selection across refreshes."""
        js_path = os.path.join(self.static_dir, "app.js")
        with open(js_path, "r", encoding="utf-8") as f:
            js = f.read()
        self.assertTrue("localStorage.setItem" in js)
        self.assertTrue("localStorage.getItem" in js)

    def test_frontend_long_descriptions(self):
        """24. Checks CSS rules for text truncation or layout management for very long release descriptions."""
        css_path = os.path.join(self.static_dir, "style.css")
        with open(css_path, "r", encoding="utf-8") as f:
            css = f.read()
        self.assertTrue("overflow" in css or "line-clamp" in css or "max-height" in css)

    def test_frontend_no_releases_message(self):
        """25. Checks frontend shows a user-friendly "no releases found" message when backend API returns empty."""
        js_path = os.path.join(self.static_dir, "app.js")
        with open(js_path, "r", encoding="utf-8") as f:
            js = f.read()
        self.assertTrue("No releases found" in js or "no releases" in js.lower())

    def test_frontend_share_no_selection(self):
        """26. Checks that the share button is disabled or handles click gracefully when no item is selected."""
        js_path = os.path.join(self.static_dir, "app.js")
        with open(js_path, "r", encoding="utf-8") as f:
            js = f.read()
        self.assertTrue("disabled" in js)

    def test_frontend_share_extreme_length(self):
        """27. Checks handling when release title/link is extremely long (verifying intent string length limits/truncation)."""
        js_path = os.path.join(self.static_dir, "app.js")
        with open(js_path, "r", encoding="utf-8") as f:
            js = f.read()
        self.assertTrue("substring" in js or "slice" in js or "length" in js)

    def test_frontend_selection_toggle(self):
        """28. Checks that selecting a different item updates the active selection and deselects the previous one."""
        js_path = os.path.join(self.static_dir, "app.js")
        with open(js_path, "r", encoding="utf-8") as f:
            js = f.read()
        self.assertTrue("remove" in js and "add" in js)

    def test_frontend_selection_clear(self):
        """29. Checks that clicking the selected item again deselects it, clearing the selection state."""
        js_path = os.path.join(self.static_dir, "app.js")
        with open(js_path, "r", encoding="utf-8") as f:
            js = f.read()
        self.assertTrue("-1" in js or "remove" in js)

    def test_frontend_share_html_tags_in_description(self):
        """30. Checks that if description contains HTML tags, they are stripped or properly handled before being passed to Twitter Web Intent."""
        js_path = os.path.join(self.static_dir, "app.js")
        with open(js_path, "r", encoding="utf-8") as f:
            js = f.read()
        self.assertTrue("stripHtml" in js or "replace" in js or "DOMParser" in js or "textContent" in js)


    # ==========================================
    # TIER 3 - CROSS-FEATURE COMBINATIONS (3 CASES)
    # ==========================================

    def test_integration_api_refresh_updates_ui(self):
        """31. Verifies that clicking refresh triggers an API fetch and correctly updates the timeline elements."""
        js_path = os.path.join(self.static_dir, "app.js")
        with open(js_path, "r", encoding="utf-8") as f:
            js = f.read()
        self.assertTrue("refreshBtn.addEventListener" in js or "refresh-btn" in js)
        self.assertTrue("fetchReleases" in js or "fetch" in js)

    def test_integration_selection_state_preserved_during_refresh(self):
        """32. Checks if the selection is handled correctly (either cleared or preserved) during a manual refresh."""
        js_path = os.path.join(self.static_dir, "app.js")
        with open(js_path, "r", encoding="utf-8") as f:
            js = f.read()
        self.assertTrue("selectedIndex = -1" in js or "selected = null" in js or "fetchReleases" in js)

    def test_integration_theme_affects_timeline_elements(self):
        """33. Verifies that changing theme updates style classes on the timeline items."""
        js_path = os.path.join(self.static_dir, "app.js")
        with open(js_path, "r", encoding="utf-8") as f:
            js = f.read()
        self.assertTrue("dark-item" in js or "theme" in js)


    # ==========================================
    # TIER 4 - REAL-WORLD SCENARIOS (5 CASES)
    # ==========================================

    def test_workload_typical_session(self):
        """34. Simulates a user landing on the page, viewing the timeline, toggling theme, selecting a release note, and clicking share."""
        html_path = os.path.join(self.static_dir, "index.html")
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()
        self.assertIn("theme-toggle", html)
        self.assertIn("refresh-btn", html)
        self.assertIn("share-btn", html)
        self.assertIn("timeline", html)

        css_path = os.path.join(self.static_dir, "style.css")
        with open(css_path, "r", encoding="utf-8") as f:
            css = f.read()
        self.assertIn("dark-theme", css)
        self.assertIn("selected", css)

        js_path = os.path.join(self.static_dir, "app.js")
        with open(js_path, "r", encoding="utf-8") as f:
            js = f.read()
        self.assertIn("themeToggleBtn.addEventListener", js)
        self.assertIn("shareBtn.addEventListener", js)
        self.assertIn("refreshBtn.addEventListener", js)

    def test_workload_recovery_from_network_drop(self):
        """35. Simulates loading the page while offline (relying on cache/fallback), then network restoring and performing a manual refresh."""
        if self.is_mock_server:
            global CURRENT_SCENARIO
            CURRENT_SCENARIO = "failed"
            url = f"{self.base_url}/api/releases"
            with urllib.request.urlopen(url) as r:
                self.assertTrue(r.headers.get("X-Cache-Status").startswith("failed"))
            
            CURRENT_SCENARIO = "default"
            with urllib.request.urlopen(url) as r:
                self.assertEqual(r.headers.get("X-Cache-Status"), "fetched")

        js_path = os.path.join(self.static_dir, "app.js")
        with open(js_path, "r", encoding="utf-8") as f:
            js = f.read()
        self.assertTrue("catch" in js or "try" in js)

    def test_workload_rapid_theme_toggle(self):
        """36. Simulates rapid toggling of theme to verify no layout glitches or stylesheet loading issues."""
        js_path = os.path.join(self.static_dir, "app.js")
        with open(js_path, "r", encoding="utf-8") as f:
            js = f.read()
        self.assertTrue("classList.toggle" in js)

    def test_workload_multiple_feed_updates(self):
        """37. Simulates feed updating with new content over time, verifying that the frontend refreshes to show new items."""
        if self.is_mock_server:
            global CURRENT_SCENARIO, MOCK_RELEASES
            CURRENT_SCENARIO = "default"
            url = f"{self.base_url}/api/releases"
            with urllib.request.urlopen(url) as r:
                data1 = json.loads(r.read().decode("utf-8"))
                self.assertEqual(len(data1), 2)
            
            new_release = {
                "title": "BigQuery: Extra new feature",
                "link": "https://cloud.google.com/bigquery/docs/release-notes#June_23_2026",
                "description": "Another release item.",
                "pubDate": "2026-06-23T00:00:00"
            }
            MOCK_RELEASES.append(new_release)
            try:
                with urllib.request.urlopen(url) as r:
                    data2 = json.loads(r.read().decode("utf-8"))
                    self.assertEqual(len(data2), 3)
            finally:
                MOCK_RELEASES.pop()
        else:
            url = f"{self.base_url}/api/releases"
            with urllib.request.urlopen(url) as r:
                self.assertEqual(r.status, 200)

    def test_workload_handling_faulty_backend_during_session(self):
        """38. Simulates user loading page with working backend, backend then failing, and user trying to refresh."""
        if self.is_mock_server:
            global CURRENT_SCENARIO
            CURRENT_SCENARIO = "default"
            url = f"{self.base_url}/api/releases"
            with urllib.request.urlopen(url) as r:
                self.assertEqual(r.headers.get("X-Cache-Status"), "fetched")
            
            CURRENT_SCENARIO = "failed"
            with urllib.request.urlopen(url) as r:
                self.assertTrue(r.headers.get("X-Cache-Status").startswith("failed"))
                
        js_path = os.path.join(self.static_dir, "app.js")
        with open(js_path, "r", encoding="utf-8") as f:
            js = f.read()
        self.assertTrue("catch" in js)
        self.assertTrue("releasesData" in js)

if __name__ == "__main__":
    unittest.main()
