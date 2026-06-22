# Original User Request

## Initial Request — 2026-06-22T05:41:59Z

A web application built with Python Flask (backend) and vanilla HTML/JS/CSS (frontend) that fetches the BigQuery Release notes RSS feed, displays the updates with a refresh mechanism, and allows users to share/Tweet selected updates.

Working directory: /mnt/c/Users/Lenovo/Documents/agy-cli-projects/bq-releases-notes
Integrity mode: benchmark

## Requirements

### R1. RSS Feed Aggregator Backend
- Fetch release notes from the Google Cloud BigQuery RSS feed: `https://docs.cloud.google.com/feeds/bigquery-release-notes.xml`.
- Expose a Flask API endpoint `/api/releases` to serve the parsed release notes in JSON format.
- Implement server-side caching or error handling to gracefully handle feed fetch failures.
- Make sure external network access is used to pull the live XML.

### R2. Responsive Vanilla Frontend
- Build a responsive UI using standard HTML5, CSS3, and modern vanilla JavaScript.
- Display release notes in a clean, scrollable timeline/list.
- Include a manual refresh button with an active spinner animation while fetching.
- Prioritize high-quality visual aesthetics: modern typography (e.g. Google Fonts), subtle transitions, clear spacing, and modern colors (e.g. sleek dark/light theme).

### R3. Update Selection and Tweeting
- Allow the user to select/click a specific release note from the list.
- Enable sharing the selected note text/link via a Twitter web intent interface (`https://twitter.com/intent/tweet?text=...`) opened in a new browser tab/window.

### R4. Programmatic Verification Suite
- Provide a Python test script (`test_app.py`) to programmatically verify the backend API.
- The test suite must verify that the `/api/releases` endpoint returns valid JSON with keys like title, link, description/content, and publish date.

## Acceptance Criteria

### API Verification
- [ ] Running `python -m unittest test_app.py` passes all verification checks successfully.
- [ ] `/api/releases` returns 200 OK and valid JSON data parsed from the Google RSS feed.

### Frontend Usability
- [ ] Frontend successfully displays notes, handles loading spinner state, and triggers Twitter sharing flow.
- [ ] Clicking the refresh button fetches updated data.
- [ ] Selecting an item and clicking the "Tweet" button successfully opens a Twitter intent page in a new window with the text of the selected update.
