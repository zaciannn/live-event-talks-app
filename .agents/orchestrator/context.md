# Context Document

## Overview
This file indexes the environment and context for the BigQuery Release Notes RSS aggregator web application.

## Working Directory
`/mnt/c/Users/Lenovo/Documents/agy-cli-projects/bq-releases-notes`

## Requirements Summary
- **R1. RSS Feed Aggregator Backend**: Fetch feed from `https://docs.cloud.google.com/feeds/bigquery-release-notes.xml`, expose `/api/releases`, implement caching/error handling.
- **R2. Responsive Vanilla Frontend**: Responsive UI using standard HTML5/CSS3/modern vanilla JS. Clean, scrollable timeline/list, manual refresh button, active spinner. High quality visual aesthetics (Google Fonts, themes).
- **R3. Update Selection and Tweeting**: Select a release note, share selected note text/link via Twitter web intent.
- **R4. Programmatic Verification Suite**: `test_app.py` script verifying `/api/releases` JSON format.

## Acceptance Criteria
- Running `python -m unittest test_app.py` passes.
- `/api/releases` returns 200 OK and valid parsed JSON.
- Frontend successfully displays notes, handles spinner, triggers Twitter sharing.
- Refresh button works.
- Selecting item and tweeting opens Twitter web intent page in a new window.
