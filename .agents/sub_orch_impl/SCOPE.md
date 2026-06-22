# Scope: Implementation Track

## Architecture
- Backend: Flask web application (`app.py`), RSS feed parser logic.
- Frontend: Single-page application using vanilla HTML5, CSS3, JavaScript served from `static/` directory.
- Feed Source: `https://docs.cloud.google.com/feeds/bigquery-release-notes.xml`
- Caching/Error Handling: Cache feed data in-memory or on-disk, fall back to cached version if external feed fetch fails.
- External Network: Must use real HTTP requests to pull the XML feed in production (no mocking in production).

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Backend API | `/api/releases`, RSS parsing, caching/error handling | None | PLANNED |
| 2 | Responsive Frontend | HTML/CSS/JS, timeline, theme, refresh button, spinner | M1 | PLANNED |
| 3 | Tweet / Selection | Selection state, Twitter Web Intent integration | M2 | PLANNED |
| 4 | Programmatic Verification | Implement `test_app.py` and run E2E test suite from `TEST_READY.md` | M1, M3 | PLANNED |
| 5 | Adversarial Hardening | Phase 2 Adversarial coverage hardening (Tier 5) | M4 | PLANNED |

## Interface Contracts
### `/api/releases`
- Method: GET
- Response: `200 OK` on success, or cached/fallback JSON on feed failures.
- Payload: JSON array of release notes. Each item:
  ```json
  {
    "title": "String",
    "link": "String",
    "description": "String",
    "pubDate": "String (ISO format or parsed date string)"
  }
  ```
