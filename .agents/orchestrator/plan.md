# Project: BigQuery Release Notes RSS Aggregator

## Architecture
The application is a standard Flask web server serving a single-page frontend.
- **Backend (`app.py`)**: A Flask application that handles fetching the Google Cloud BigQuery RSS feed, parsing the XML data, caching the parsed results, and exposing `/api/releases`.
- **Frontend (`static/`)**: A responsive UI built using vanilla HTML5, CSS3, and JavaScript. Communicates with `/api/releases` to render the timeline and trigger the Twitter web intent.
- **Verification (`test_app.py` & `e2e_tests/`)**: A unit/integration test suite for checking backend structure, and an independent E2E test track running black-box scenarios.

## Code Layout
- `app.py` - Core Flask application and RSS feed parser logic.
- `requirements.txt` - Project dependencies (Flask, requests, feedparser or xml.etree, etc.).
- `static/index.html` - HTML structure for the timeline.
- `static/style.css` - CSS styling for dark/light themes and layout.
- `static/app.js` - JS frontend logic (fetch, spinner, selection, sharing).
- `test_app.py` - Programmatic verification suite for `/api/releases`.
- `e2e_tests/` - E2E tests folder.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Backend API | Implement `/api/releases`, RSS parsing, feed caching, error handling | None | PLANNED |
| 2 | Responsive Frontend | Implement HTML/CSS/JS, timeline, theme, manual refresh, loading spinner | M1 | PLANNED |
| 3 | Tweet / Selection | Implement selection state on UI, Twitter Web Intent integration | M2 | PLANNED |
| 4 | Programmatic Verification | Provide `test_app.py`, verify API structure under unittest | M1, M3 | PLANNED |
| 5 | Adversarial Hardening | Implement Tier 5 tests, white-box coverage check | M4 | PLANNED |

## Interface Contracts
### `/api/releases`
- **Method**: GET
- **Response**: `200 OK` on success, or cached/fallback JSON on feed failures.
- **Payload**: JSON array of release notes. Each item:
  ```json
  {
    "title": "String",
    "link": "String",
    "description": "String",
    "pubDate": "String (ISO format or parsed date string)"
  }
  ```
