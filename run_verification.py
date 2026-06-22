import os
import subprocess
import time
import requests
import json

def run_verification():
    print("=== Starting Verification ===")
    
    # 1. Install dependencies
    print("Installing dependencies...")
    try:
        subprocess.run(["pip", "install", "--break-system-packages", "-r", "requirements.txt"], check=True)
    except Exception as e:
        print(f"Pip install failed: {e}. Trying pip3...")
        try:
            subprocess.run(["pip3", "install", "--break-system-packages", "-r", "requirements.txt"], check=True)
        except Exception as e3:
            print(f"Pip3 install failed too: {e3}")
            return False

    # 2. Set environment variables
    mock_feed_path = os.path.abspath("e2e_tests/mock_feed.xml")
    os.environ["FEED_URL"] = f"file://{mock_feed_path}"
    os.environ["PORT"] = "5005"
    print(f"Setting FEED_URL to: file://{mock_feed_path}")

    # Remove existing cache file to ensure fresh fetch
    cache_file = "releases_cache.json"
    if os.path.exists(cache_file):
        os.remove(cache_file)
        print("Removed existing cache file.")

    # 3. Start Flask app
    print("Starting Flask app on port 5005...")
    proc = subprocess.Popen(["python3", "app.py"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    time.sleep(2)  # Wait for server to spin up
    
    # 4. Check if process is still running
    if proc.poll() is not None:
        print("Flask app failed to start!")
        stdout, stderr = proc.communicate()
        print("Stdout:", stdout)
        print("Stderr:", stderr)
        return False
        
    try:
        # 5. Query /api/releases (first time: should be fetched)
        print("\n--- Querying /api/releases (First attempt: Expected Status: fetched) ---")
        res1 = requests.get("http://localhost:5005/api/releases")
        print("Status Code:", res1.status_code)
        print("X-Cache-Status:", res1.headers.get("X-Cache-Status"))
        releases = res1.json()
        print(f"Number of releases fetched: {len(releases)}")
        if len(releases) > 0:
            print("First release title:", releases[0]["title"])
            print("First release date:", releases[0]["pubDate"])
        
        # Verify fields
        for rel in releases:
            for field in ["title", "link", "description", "pubDate"]:
                if field not in rel:
                    print(f"Error: missing field '{field}' in release")
                    return False
        
        # Check cache file existence
        if not os.path.exists(cache_file):
            print("Error: cache file releases_cache.json was not created!")
            return False
            
        # 6. Query /api/releases (second time: should be cache_hit)
        print("\n--- Querying /api/releases (Second attempt: Expected Status: cache_hit) ---")
        res2 = requests.get("http://localhost:5005/api/releases")
        print("Status Code:", res2.status_code)
        print("X-Cache-Status:", res2.headers.get("X-Cache-Status"))
        
        # 7. Query root / to check index.html serving
        print("\n--- Querying / (Static index.html) ---")
        res3 = requests.get("http://localhost:5005/")
        print("Status Code:", res3.status_code)
        print("Content preview:\n", res3.text[:100])
        
        if "BigQuery Release Notes" not in res3.text:
            print("Error: index.html was not served correctly!")
            return False

        # 8. Curl check (as requested specifically by user instructions)
        print("\n--- Performing curl check on /api/releases ---")
        curl_res = subprocess.run(["curl", "-i", "http://localhost:5005/api/releases"], capture_output=True, text=True)
        print(curl_res.stdout)
        
        print("\nVerification successful!")
        return True
        
    except Exception as e:
        print(f"Error during API calls: {e}")
        return False
    finally:
        print("Stopping Flask app...")
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            
if __name__ == "__main__":
    success = run_verification()
    if not success:
        os._exit(1)
