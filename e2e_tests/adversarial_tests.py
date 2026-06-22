import os
import sys
import unittest
import json
import time
from unittest.mock import patch

# Add parent directory to path so we can import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app import app, FeedCache, CACHE_FILE

class MockResponse:
    def __init__(self, text, status_code):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.exceptions.HTTPError(f"HTTP Error: {self.status_code}")

class BackendAdversarialTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        # Ensure we use a test cache file to not overwrite development cache
        self.test_cache_file = "test_releases_cache.json"
        app.config['TESTING'] = True
        
        # Override FeedCache file and Feed URL
        self.original_cache_file = CACHE_FILE
        import app as app_module
        self.original_feed_url = app_module.FEED_URL
        app_module.CACHE_FILE = self.test_cache_file
        app_module.FEED_URL = "https://docs.cloud.google.com/feeds/bigquery-release-notes.xml"
        
        self.cleanup_cache()

    def tearDown(self):
        self.cleanup_cache()
        import app as app_module
        app_module.CACHE_FILE = self.original_cache_file
        app_module.FEED_URL = self.original_feed_url

    def cleanup_cache(self):
        if os.path.exists(self.test_cache_file):
            try:
                os.remove(self.test_cache_file)
            except Exception:
                pass

    @patch('requests.get')
    def test_feed_offline_no_cache(self, mock_get):
        """Verify behavior when feed is offline and no cache is present."""
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection timed out")

        response = self.client.get('/api/releases')
        self.assertEqual(response.status_code, 200)
        
        # Should return empty list
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data, [])
        
        # Header should reflect failure
        cache_status = response.headers.get('X-Cache-Status')
        self.assertTrue(cache_status.startswith("failed: Connection timed out"))

    @patch('requests.get')
    def test_feed_offline_with_fresh_cache(self, mock_get):
        """Verify that fresh cache is served without hitting network."""
        # Setup fresh cache
        cache = FeedCache(cache_file=self.test_cache_file)
        mock_releases = [{"title": "Cached Release", "link": "http://example.com", "description": "Desc", "pubDate": "2026-06-22T00:00:00"}]
        cache.set(mock_releases)

        # Call API - requests.get should not be called since cache is fresh
        response = self.client.get('/api/releases')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data, mock_releases)
        self.assertEqual(response.headers.get('X-Cache-Status'), "cache_hit")
        mock_get.assert_not_called()

    @patch('requests.get')
    def test_feed_offline_with_stale_cache(self, mock_get):
        """Verify that stale cache is served as fallback when feed is offline."""
        # Setup stale cache (timestamp 1 hour ago)
        cache = FeedCache(cache_file=self.test_cache_file)
        mock_releases = [{"title": "Stale Release", "link": "http://example.com", "description": "Desc", "pubDate": "2026-06-22T00:00:00"}]
        
        # Write stale cache manually
        data = {
            "timestamp": time.time() - 3600,
            "releases": mock_releases
        }
        with open(self.test_cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f)

        # Network is offline
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError("Offline")

        # Call API - should attempt fetch, fail, and return fallback cache
        response = self.client.get('/api/releases')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data, mock_releases)
        self.assertEqual(response.headers.get('X-Cache-Status'), "fallback_cache")
        mock_get.assert_called_once()

    @patch('requests.get')
    def test_empty_feed_xml(self, mock_get):
        """Verify behavior when feed XML is completely empty."""
        mock_get.return_value = MockResponse("", 200)

        response = self.client.get('/api/releases')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data, [])
        
        # Should fail parsing
        cache_status = response.headers.get('X-Cache-Status')
        self.assertTrue(cache_status.startswith("failed: Malformed XML"))

    @patch('requests.get')
    def test_invalid_corrupted_feed_xml(self, mock_get):
        """Verify behavior when feed XML is corrupted/invalid."""
        mock_get.return_value = MockResponse("<rss><channel><item><title>Unclosed Tag", 200)

        response = self.client.get('/api/releases')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data, [])
        
        # Should fail parsing
        cache_status = response.headers.get('X-Cache-Status')
        self.assertTrue(cache_status.startswith("failed: Malformed XML"))

    @patch('requests.get')
    def test_caching_and_persistence(self, mock_get):
        """Verify caching, disk persistence, and X-Cache-Status transitions."""
        mock_feed_xml = """<?xml version="1.0" encoding="utf-8"?>
        <rss version="2.0">
          <channel>
            <title>Test Feed</title>
            <item>
              <title>Live Release</title>
              <link>http://example.com/1</link>
              <description>Details</description>
              <pubDate>Mon, 22 Jun 2026 00:00:00 GMT</pubDate>
            </item>
          </channel>
        </rss>"""
        mock_get.return_value = MockResponse(mock_feed_xml, 200)

        # 1. First fetch (no cache exists)
        response1 = self.client.get('/api/releases')
        self.assertEqual(response1.status_code, 200)
        self.assertEqual(response1.headers.get('X-Cache-Status'), "fetched")
        data1 = json.loads(response1.data.decode('utf-8'))
        self.assertEqual(len(data1), 1)
        self.assertEqual(data1[0]['title'], "Live Release")

        # Verify disk persistence
        self.assertTrue(os.path.exists(self.test_cache_file))
        with open(self.test_cache_file, 'r', encoding='utf-8') as f:
            persisted = json.load(f)
            self.assertIn("timestamp", persisted)
            self.assertEqual(persisted["releases"], data1)

        # 2. Second fetch (uses cache, no net calls)
        mock_get.reset_mock()
        response2 = self.client.get('/api/releases')
        self.assertEqual(response2.status_code, 200)
        self.assertEqual(response2.headers.get('X-Cache-Status'), "cache_hit")
        data2 = json.loads(response2.data.decode('utf-8'))
        self.assertEqual(data2, data1)
        mock_get.assert_not_called()

        # 3. Third fetch (with stale cache - simulate by rewriting timestamp)
        with open(self.test_cache_file, 'r', encoding='utf-8') as f:
            persisted = json.load(f)
        persisted["timestamp"] = time.time() - 3600 # 1 hour ago
        with open(self.test_cache_file, 'w', encoding='utf-8') as f:
            json.dump(persisted, f)

        # Change feed response to verify we fetched new data
        new_feed_xml = """<?xml version="1.0" encoding="utf-8"?>
        <rss version="2.0">
          <channel>
            <title>Test Feed</title>
            <item>
              <title>Updated Release</title>
              <link>http://example.com/2</link>
              <description>New details</description>
              <pubDate>Mon, 22 Jun 2026 01:00:00 GMT</pubDate>
            </item>
          </channel>
        </rss>"""
        mock_get.return_value = MockResponse(new_feed_xml, 200)

        response3 = self.client.get('/api/releases')
        self.assertEqual(response3.status_code, 200)
        self.assertEqual(response3.headers.get('X-Cache-Status'), "fetched")
        data3 = json.loads(response3.data.decode('utf-8'))
        self.assertEqual(data3[0]['title'], "Updated Release")
        mock_get.assert_called_once()

if __name__ == "__main__":
    unittest.main()
