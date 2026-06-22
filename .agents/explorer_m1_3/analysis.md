# Backend API Implementation Strategy — Milestone 1

## Overview
This document analyzes the requirements and outlines the implementation strategy for the BigQuery Release Notes RSS Aggregator backend API. 
The backend will fetch, parse, cache, and serve release notes from the Google Cloud BigQuery RSS feed at `https://docs.cloud.google.com/feeds/bigquery-release-notes.xml`.

---

## 1. Feed Fetching & Parsing Strategy

### 1.1 Feed Format
Google Cloud release feeds are typical Atom feeds using namespace `http://www.w3.org/2005/Atom` (root tag `<feed>`, entries under `<entry>`). However, to make the system robust and resistant to schema changes or different Google RSS formats, the parser is designed to handle:
* **Atom Feeds**: `<feed>` root, `<entry>` items, `<title>`, `<link href="...">`, `<content>` or `<summary>`, and `<updated>` or `<published>`.
* **RSS Feeds**: `<rss>` root, `<item>` items, `<title>`, `<link>`, `<description>`, and `<pubDate>`.
* **Generic XML Feeds**: Uses elements directly if namespace patterns fail or are absent.

### 1.2 Parsing Logic
Using Python's standard `xml.etree.ElementTree` avoids external parsing library dependencies (like `feedparser` which has many transitive dependencies and potential security vulnerabilities).
- We look for namespaced tags first (e.g. `{http://www.w3.org/2005/Atom}entry`), and fall back to local name lookup if namespaces are missing.
- When extracting `<link>` from an Atom entry, the `href` attribute is checked. If it is empty, we fall back to the element text.
- If optional elements like `<description>` or `<link>` are missing, they default to an empty string `""` to satisfy the API contract.

### 1.3 Date Parsing and Normalization
To ensure the UI can display dates consistently, dates from both Atom (ISO 8601 strings like `2026-06-20T12:00:00Z`) and RSS (RFC 2822 dates like `Sat, 20 Jun 2026 12:00:00 GMT`) are normalized into standard ISO 8601 format:
* We first try parsing using standard ISO format formats (`strptime`).
* We fall back to `email.utils.parsedate_to_datetime()` which is built into Python's standard library and parses standard RSS date structures flawlessly.
* If all parsing attempts fail, the raw string is returned.

---

## 2. Caching Strategy

To ensure high performance and prevent rate limiting or slow initial loads, we implement a **File-Based Cache** rather than an in-memory cache.

### 2.1 Benefits of File-Based Cache
1. **Persistence Across Restarts**: If the Flask process crashes or is restarted (e.g., during deployments), the cache persists. 
2. **Offline Mode & Test Support**: If the server starts up offline (or during offline E2E tests), it can immediately read the cache file to serve responses, preventing startup errors.

### 2.2 Cache Lifecycle & Workflow
1. A request hits `/api/releases`.
2. The server checks if `releases_cache.json` exists and if the difference between the current time and the cached timestamp is less than `CACHE_DURATION_SECONDS` (10 minutes).
3. If the cache is **fresh**:
   * Return the cached JSON directly.
   * Add HTTP header `X-Cache-Status: cache_hit`.
4. If the cache is **stale** or **missing**:
   * Attempt to fetch the live XML feed from the network.
   * If the fetch succeeds:
     * Parse the XML content.
     * Write the new timestamp and JSON content to `releases_cache.json`.
     * Return the fresh JSON.
     * Add HTTP header `X-Cache-Status: fetched`.
   * If the fetch fails (due to network timeout, HTTP 404/500, or DNS failure):
     * Check if `releases_cache.json` has *any* data (even if stale).
     * If yes, return the stale cached data.
     * Add HTTP header `X-Cache-Status: fallback_cache`.
     * If no cache exists, return an empty array `[]`.
     * Add HTTP header `X-Cache-Status: failed: <error_message>`.

---

## 3. Offline Testing & Configurations

To support programmatic E2E testing (Tier 1 & Tier 2 tests in `TEST_INFRA.md`), the feed source is configured via the environment variable `FEED_URL`:
- **Production/Default**: `https://docs.cloud.google.com/feeds/bigquery-release-notes.xml`
- **Testing**: Can be set to a local file path (e.g., `file://e2e_tests/mock_feed.xml` or simply `e2e_tests/mock_feed.xml`).
The server's fetcher resolves both standard HTTP/HTTPS URLs and local file system paths. This eliminates the need to mock network requests using third-party libraries like `responses` or `mock`, keeping the testing setup robust.

---

## 4. API Interface Contract

### Endpoint: `/api/releases`
* **Method**: GET
* **Headers**: `X-Cache-Status: [cache_hit | fetched | fallback_cache | failed: <reason>]`
* **Response Status**: `200 OK` (Always, unless routing issues arise. Feed failures return cached/fallback JSON structure).
* **Payload Structure**:
  ```json
  [
    {
      "title": "BigQuery release notes - June 20, 2026",
      "link": "https://cloud.google.com/bigquery/docs/release-notes#June_20_2026",
      "description": "<p>Description with Unicode like 🚀 or HTML tags.</p>",
      "pubDate": "2026-06-20T12:00:00"
    }
  ]
  ```

---

## 5. File Inventory

The following proposed files are written in the agent's folder for deployment:
1. `proposed_app.py` — Complete Flask backend with Atom/RSS parsing, normalization, file caching, and error handling.
2. `proposed_requirements.txt` — Minimal python dependencies.
3. `proposed_mock_feed.xml` — A mock Atom XML for tests, verifying unicode and entry formats.
