# BigQuery Release Notes RSS Aggregator

A responsive web application built with **Python Flask** (backend) and **Vanilla HTML/JS/CSS** (frontend) that aggregates, caches, parses, and visualizes the Google Cloud BigQuery Release Notes RSS feed, allowing users to browse updates on a clean timeline and share them to Twitter.

---

## 🚀 Key Features

*   **Dual RSS & Atom Feed Parser**: Dynamically supports parsing standard RSS feeds (`<rss>` formats) and Atom feeds (`<feed>` formats), extracting titles, links, HTML descriptions, and publishing dates.
*   **Resilient Server-Side Caching**: Uses a disk-backed cache mechanism with a 10-minute validity window. Under offline or network failure scenarios, it gracefully serves stale cached notes as fallback data rather than returning an error.
*   **Modern Theme-Aware Timeline**: A clean, scrollable timeline UI styled with modern CSS variables. Supports responsive viewport scaling and light/dark theme toggling, persisting theme choices locally via `localStorage`.
*   **Debounced Action Handling**: Debounces timeline refresh actions to prevent duplicate API requests and protect feed sources from rate-limiting.
*   **Twitter Web Intent Integration**: Allows users to select a release item from the timeline and instantly prepare a pre-formatted tweet containing the note title and link, automatically stripping HTML tags and adhering to Twitter's 280-character limit.

---

## 📁 Project Structure

```text
bq-releases-notes/
├── e2e_tests/
│   ├── adversarial_tests.py   # Cache/offline robustness tests
│   ├── mock_feed.xml          # Mock feed data for tests
│   └── run_e2e.py             # 38-case end-to-end suite
├── static/
│   ├── app.js                 # Frontend interactivity, sharing, themeing
│   ├── index.html             # UI layout structure
│   └── style.css              # Custom layout, responsive styling, and theme rules
├── .gitignore                 # Excluded system files & build paths
├── app.py                     # Flask application & RSS parsing controllers
├── requirements.txt           # Python application dependencies
├── run_verification.py        # Automated API & verification sanity checks
└── TEST_INFRA.md              # Documentation of testing architecture & coverage
```

---

## 🛠️ Installation & Setup

### 1. Install Dependencies
Make sure you have Python 3 installed. Run the command to install packages:
```bash
pip install -r requirements.txt
```
*(If on an externally-managed Linux environment, append `--break-system-packages` to proceed)*

### 2. Start the Application
Run the Flask server:
```bash
python3 app.py
```
By default, the server runs at **`http://localhost:5000`**. Open this address in your browser to interact with the frontend timeline.

---

## 🧪 Testing and Verification

### 🛡️ Programmatic Server Verification
Run the quick verification script to test server startup, API responses, cache header status, and static page routing:
```bash
python3 run_verification.py
```

### 📈 Execute 38 End-to-End Test Scenarios
Verify all core interactions, styling variables, rate-limiting, and Twitter URLs with the main test suite:
```bash
python3 e2e_tests/run_e2e.py
```

### ⛈️ Run Adversarial & Robustness Tests
Verify feed offline-handling, cache persistence checks, and malformed XML fallback strategies:
```bash
python3 e2e_tests/adversarial_tests.py
```
