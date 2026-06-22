# E2E Test Infra: BigQuery Release Notes RSS Aggregator

## Test Philosophy
- Opaque-box, requirement-driven. No dependency on implementation details.
- Methodology: Category-Partition + BVA + Pairwise + Workload Testing.

## Feature Inventory
| # | Feature | Source (requirement) | Tier 1 | Tier 2 | Tier 3 |
|---|---------|---------------------|:------:|:------:|:------:|
| 1 | RSS Aggregator Backend | ORIGINAL_REQUEST §1 | 5      | 5      | ✓      |
| 2 | Responsive Frontend | ORIGINAL_REQUEST §2 | 5      | 5      | ✓      |
| 3 | Tweet / Selection | ORIGINAL_REQUEST §3 | 5      | 5      | ✓      |

## Test Architecture
- Test runner: `e2e_tests/run_e2e.py`
- Test case format: Python unittest format, outputting standard status codes.
- Directory layout:
  - `e2e_tests/`
    - `run_e2e.py` - runner and test case definitions
    - `mock_feed.xml` - mock RSS feed content for testing backend offline / corner cases

## Test Cases Inventory

### Tier 1 - Feature Coverage (15 cases)
- **F1: RSS Feed Aggregator Backend**
  1. `test_backend_returns_valid_json`: Checks `/api/releases` returns 200 OK and valid JSON format.
  2. `test_backend_releases_format`: Checks the returned releases have the expected keys: `title`, `link`, `description`, `pubDate`.
  3. `test_backend_releases_list_not_empty`: Checks the backend returns a list (which should contain items if feed is fetched).
  4. `test_backend_caching_behavior`: Checks that subsequent calls to `/api/releases` are fast/cached (or verifies caching header if applicable).
  5. `test_backend_rss_parsing_correctness`: Verifies that elements from the RSS XML feed are correctly transformed to the JSON fields.
- **F2: Responsive Vanilla Frontend**
  6. `test_frontend_html_structure`: Checks that `/static/index.html` (or root `/`) contains a timeline container element.
  7. `test_frontend_refresh_button`: Checks that frontend has a manual refresh button.
  8. `test_frontend_loading_spinner`: Checks that frontend has a loading spinner element.
  9. `test_frontend_responsive_styling`: Parses `/static/style.css` to verify media queries or responsive styling rules.
  10. `test_frontend_theme_styles`: Parses `/static/style.css` to check for light/dark theme color variable definitions or classes.
- **F3: Selection and Twitter Sharing**
  11. `test_frontend_item_selectable`: Checks JavaScript or HTML structure has a class or click handler for selection.
  12. `test_frontend_twitter_share_button`: Checks that a Twitter sharing button exists or is generated.
  13. `test_frontend_twitter_web_intent_url`: Checks JS code generates a valid `https://twitter.com/intent/tweet` URL.
  14. `test_frontend_twitter_web_intent_params`: Checks JS code includes the selected item's title and link in the Twitter intent URL.
  15. `test_frontend_share_new_tab`: Checks that Twitter share link/button has `target="_blank"` or JS triggers window.open with new tab.

### Tier 2 - Boundary & Corner Cases (15 cases)
- **F1: RSS Feed Aggregator Backend**
  16. `test_backend_invalid_rss_feed`: Checks backend behavior (graceful fallback or cached data) when the RSS feed XML is invalid or corrupted.
  17. `test_backend_feed_offline`: Checks backend behavior when the RSS feed URL returns 404/500 or is completely unreachable.
  18. `test_backend_empty_rss_feed`: Checks backend returns empty list (or fallback) when RSS feed has 0 items.
  19. `test_backend_malformed_xml_elements`: Checks backend handles RSS items with missing optional tags (e.g., missing description or link).
  20. `test_backend_unicode_characters`: Checks backend handles RSS feed containing non-ASCII/unicode characters in title/description.
- **F2: Responsive Vanilla Frontend**
  21. `test_frontend_spinner_active_during_fetch`: Verifies that JS show/hide spinner logic is called during feed fetch.
  22. `test_frontend_refresh_rate_limiting`: Checks that clicking refresh multiple times rapidly does not trigger excessive API calls (e.g., debounce/throttle).
  23. `test_frontend_theme_toggle_persistence`: Checks JS code utilizes localStorage/cookies to persist theme selection across refreshes.
  24. `test_frontend_long_descriptions`: Checks CSS rules for text truncation or layout management for very long release descriptions.
  25. `test_frontend_no_releases_message`: Checks frontend shows a user-friendly "no releases found" message when backend API returns empty.
- **F3: Selection and Twitter Sharing**
  26. `test_frontend_share_no_selection`: Checks that the share button is disabled or handles click gracefully when no item is selected.
  27. `test_frontend_share_extreme_length`: Checks handling when release title/link is extremely long (verifying Twitter's 280 char limit handling or URL truncation/encoding safety).
  28. `test_frontend_selection_toggle`: Checks that selecting a different item updates the active selection and deselects the previous one.
  29. `test_frontend_selection_clear`: Checks that clicking the selected item again deselects it, clearing the selection state.
  30. `test_frontend_share_html_tags_in_description`: Checks that if description contains HTML tags, they are stripped or properly handled before being passed to Twitter Web Intent.

### Tier 3 - Cross-Feature Combinations (3 cases)
  31. `test_integration_api_refresh_updates_ui`: Verifies that clicking refresh triggers an API fetch and correctly updates the timeline elements.
  32. `test_integration_selection_state_preserved_during_refresh`: Checks if the selection is handled correctly (either cleared or preserved) during a manual refresh.
  33. `test_integration_theme_affects_timeline_elements`: Verifies that changing theme updates style classes on the timeline items.

### Tier 4 - Real-World Application Scenarios (5 cases)
  34. `test_workload_typical_session`: Simulates a user landing on the page, viewing the timeline, toggling theme, selecting a release note, and clicking share.
  35. `test_workload_recovery_from_network_drop`: Simulates loading the page while offline (relying on cache/fallback), then network restoring and performing a manual refresh.
  36. `test_workload_rapid_theme_toggle`: Simulates rapid toggling of theme to verify no layout glitches or stylesheet loading issues.
  37. `test_workload_multiple_feed_updates`: Simulates feed updating with new content over time, verifying that the frontend refreshes to show new items.
  38. `test_workload_handling_faulty_backend_during_session`: Simulates user loading page with working backend, backend then failing, and user trying to refresh (verifying UI shows error message but keeps existing cached items displayed).

## Coverage Thresholds
- Tier 1: 15 / 15
- Tier 2: 15 / 15
- Tier 3: 3 / 3
- Tier 4: 5 / 5
- **Total minimum: 38 test cases**
