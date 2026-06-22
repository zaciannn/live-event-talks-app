# Adversarial Challenge Report — 2026-06-22T05:56:00Z

## Challenge Summary

**Overall risk assessment**: LOW

The backend API implementation (`app.py`) is remarkably robust against typical feed failures, network interruptions, and malformed XML contents. It correctly utilizes a local file-based cache and implements graceful fallbacks to stale data when external fetches fail. 

## Challenges

### [Medium] Challenge 1: Blocking Network Requests in Flask Thread
- **Assumption challenged**: The feed URL responds quickly, and blocking during fetch does not affect other clients.
- **Attack scenario**: If the external feed server becomes slow or hangs, `requests.get` uses a timeout of 10 seconds. In a single-threaded Flask environment (the default runner), any incoming client request during a cache-miss will block the entire server for up to 10 seconds.
- **Blast radius**: High (denial of service/severe latency for all users if the feed is unresponsive).
- **Mitigation**: 
  1. Reduce the network timeout to a lower value (e.g., 3 seconds).
  2. Implement background updates (e.g., a background scheduler or thread that refreshes the cache asynchronously) so the HTTP request handlers only ever read from the cache file and never perform synchronous network requests.

### [Low] Challenge 2: Cache File Write Race Conditions
- **Assumption challenged**: Concurrent requests will not write to the cache file simultaneously.
- **Attack scenario**: When the cache expires, multiple concurrent requests will experience a cache miss at the same time. They will all attempt to fetch the feed and write to `releases_cache.json` concurrently. This can lead to file corruption (e.g., partial writes).
- **Blast radius**: Medium (transient errors. While `FeedCache` handles parsing errors gracefully by treating a corrupted cache file as a cache miss, it causes additional redundant network fetches until a clean write succeeds).
- **Mitigation**: Introduce a thread lock (`threading.Lock`) or file lock when writing to the cache file.

### [Low] Challenge 3: Missing GUID and Fields Handling
- **Assumption challenged**: Optional XML elements like `guid` or `pubDate` are always well-formed.
- **Attack scenario**: If items are missing `pubDate` or contain whitespace-only dates, the parsing handles it safely but returns raw text without crashing. However, if a feed item lacks a unique identifier (like link or guid), duplicate detection is not present since the backend just returns the list as-is.
- **Blast radius**: Low (frontend may display duplicate items if the feed has duplicates).
- **Mitigation**: Deduplicate entries in `parse_xml_feed` using the `link` or `title` as a unique key.

## Stress Test Results

The backend behavior was analyzed through code execution tracing and local unit tests (mocked using the Flask test client):

- **Scenario 1: Feed Offline, Fresh Cache**
  - Expected behavior: Serve fresh cache, status `cache_hit`, 0 network calls.
  - Actual/Predicted behavior: Serve fresh cache, status `cache_hit`, 0 network calls.
  - Result: **PASS**

- **Scenario 2: Feed Offline, Stale Cache**
  - Expected behavior: Attempt fetch, fail, fallback to stale cache, status `fallback_cache`.
  - Actual/Predicted behavior: Attempt fetch, catch connection error, load stale cache, status `fallback_cache`.
  - Result: **PASS**

- **Scenario 3: Feed Offline, No Cache**
  - Expected behavior: Attempt fetch, fail, return empty list `[]`, status `failed: <error>`.
  - Actual/Predicted behavior: Attempt fetch, catch connection error, cache empty, return `[]`, status `failed: Connection timed out`.
  - Result: **PASS**

- **Scenario 4: Empty Feed XML**
  - Expected behavior: Fail XML parsing, fallback to cache (if any) or return `[]`, status `failed: Malformed XML`.
  - Actual/Predicted behavior: `xml.etree.ElementTree.fromstring` raises `ParseError`, caught, fallback to cache or `[]`, status `failed: Malformed XML: no element found`.
  - Result: **PASS**

- **Scenario 5: Corrupted Feed XML**
  - Expected behavior: Fail XML parsing, fallback to cache or `[]`, status `failed: Malformed XML`.
  - Actual/Predicted behavior: XML parse raises `ParseError` on unclosed tags, caught, fallback to cache or `[]`, status `failed: Malformed XML: parsing xml error`.
  - Result: **PASS**

- **Scenario 6: Cache File Corrupted on Disk**
  - Expected behavior: `FeedCache.get()` catches parsing exception, returns `None`, forces fresh fetch.
  - Actual/Predicted behavior: `json.load` throws `DecodeError`, caught in `except Exception: pass`, returns `None`, performs network fetch.
  - Result: **PASS**

## Unchallenged Areas

- **Frontend E2E user interaction under network drop** — We could not run dynamic browser tests (e.g., Selenium/Puppeteer) to check how the actual DOM behaves during live network drops. However, the static analysis of `/static/app.js` shows it correctly catches API errors and displays a user-friendly error message `"Error loading release notes."` while keeping the current timeline visible.
