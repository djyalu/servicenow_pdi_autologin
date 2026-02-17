import os
import sys
import time
import json
from datetime import datetime
from playwright.sync_api import sync_playwright

# Configuration from Environment Variables
# For multi-PDI support, we use a single JSON string in SN_PDI_CONFIG
# Format: [{"url": "...", "username": "...", "password": "..."}, ...]
PDI_CONFIG = os.getenv("SN_PDI_CONFIG")

# Fallback to single PDI if SN_PDI_CONFIG is not set
SINGLE_URL = os.getenv("SN_PDI_URL", "https://dev198124.service-now.com")
SINGLE_USERNAME = os.getenv("SN_USERNAME")
SINGLE_PASSWORD = os.getenv("SN_PASSWORD")

HISTORY_FILE = "login_history.json"

def get_configs():
    # Priority 1: Multi-URL string in SN_PDI_URL (Comma separated)
    raw_url = os.getenv("SN_PDI_URL", "https://dev198124.service-now.com")
    username = os.getenv("SN_USERNAME")
    password = os.getenv("SN_PASSWORD")
    
    if not username or not password:
        return []

    # Split by comma and strip whitespace
    urls = [u.strip() for u in raw_url.split(",") if u.strip()]
    
    if len(urls) > 1:
        print(f"Detected {len(urls)} PDI URLs. Using shared credentials.")
        return [{"url": url, "username": username, "password": password} for url in urls]
    
    # Priority 2: SN_PDI_CONFIG JSON (Legacy/Advanced support)
    if PDI_CONFIG:
        try:
            configs = json.loads(PDI_CONFIG)
            if isinstance(configs, list):
                print(f"Loaded {len(configs)} configurations from SN_PDI_CONFIG.")
                return configs
        except Exception as e:
            print(f"Error parsing SN_PDI_CONFIG: {e}")
    
    # Priority 3: Single PDI
    return [{
        "url": urls[0] if urls else SINGLE_URL,
        "username": username,
        "password": password
    }]

def save_history(instance_url, status, title=None, error=None):
    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
        except:
            pass
    
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "url": instance_url,
        "status": status,
        "title": title,
        "error": str(error) if error else None
    }
    
    history.append(entry)
    # Keep only last 100 entries for multi-pdi
    history = history[-100:]
    
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
    print(f"History for {instance_url} saved to {HISTORY_FILE}")

def login_to_instance(page, config):
    url = config.get("url")
    username = config.get("username")
    password = config.get("password")
    
    print(f"\n--- Processing: {url} ---")
    
    try:
        print(f"Navigating to {url}...")
        # Set a long timeout for navigation because PDI might be waking up (hibernating)
        page.goto(url, timeout=300000) # 5 minutes timeout
        
        # 1. Detection: Check if the instance is hibernating
        content = page.content().lower()
        if "hibernating" in content or "wake your instance" in content:
            print("Detected PDI Hibernation. Starting wake-up process...")
            
            # Navigate to developer portal login
            dev_portal_login_url = "https://signon.service-now.com/x_snc_ssoauth.do?redirectUri=https://developer.servicenow.com/dev.do"
            print(f"Navigating to ServiceNow ID login: {dev_portal_login_url}")
            page.goto(dev_portal_login_url, timeout=120000)
            
            # Step A: Enter Username
            print(f"Entering username: {username}")
            page.wait_for_selector("#username", state="visible", timeout=60000)
            page.fill("#username", username)
            page.click("#identify-submit")
            
            # Step B: Enter Password
            print("Waiting for password field...")
            page.wait_for_selector("#password", state="visible", timeout=60000)
            page.fill("#password", password)
            
            print("Submitting login...")
            page.press("#password", "Enter")
            
            # Wait for redirection to developer portal
            print("Waiting for redirection to Developer Portal...")
            page.wait_for_load_state("networkidle", timeout=120000)
            
            print("Successfully logged into Developer Portal. PDI should be waking up.")
            time.sleep(10) 
            
            # Go back to the PDI URL
            print(f"Returning to PDI URL: {url}")
            page.goto(url, timeout=300000)

        # 2. Standard Login Process
        print("Waiting for PDI login form (Timeout: 5 minutes)...")
        page.wait_for_selector("#user_name", state="visible", timeout=300000)
        
        print("Login form detected. Entering credentials...")
        page.fill("#user_name", username)
        page.fill("#user_password", password)
        
        print("Submitting login form...")
        page.click("#sysverb_login")
        
        # Wait for navigation and load
        print("Waiting for post-login page load...")
        page.wait_for_load_state("networkidle", timeout=60000)
        
        # Check for error messages
        error_message = None
        try:
            error_selector = ".outputmsg_error"
            if page.is_visible(error_selector):
                error_message = page.inner_text(error_selector).strip()
                print(f"Login Error detected: {error_message}")
        except:
            pass

        # Validating login success
        current_title = page.title()
        print(f"Current Page Title: {current_title}")
        
        # Take a screenshot
        safe_name = url.split("//")[-1].strip("/").replace(".", "_").replace("/", "_")
        screenshot_name = f"result_{safe_name}.png"
        page.screenshot(path=screenshot_name)
        print(f"Screenshot '{screenshot_name}' saved.")
        
        if "Sign In" in current_title or "Login" in current_title or error_message:
            print(f"Warning: Login for {url} might have failed.")
            save_history(url, "Warning", title=current_title, error=error_message or "Title suggests login page")
            return False
        else:
            print(f"Login for {url} successful.")
            save_history(url, "Success", title=current_title)
            return True

    except Exception as e:
        print(f"An error occurred for {url}: {e}")
        try:
            safe_name = url.split("//")[-1].strip("/").replace(".", "_").replace("/", "_")
            error_screenshot = f"error_{safe_name}.png"
            page.screenshot(path=error_screenshot)
            print(f"Screenshot '{error_screenshot}' saved.")
        except:
            pass
        save_history(url, "Error", error=e)
        return False

def run():
    print("Starting ServiceNow Auto Login Script (Multi-PDI Support)...")
    
    configs = get_configs()
    if not configs:
        print("Error: No configurations found. Set SN_PDI_CONFIG or SN_USERNAME/SN_PASSWORD.")
        sys.exit(1)

    success_urls = []
    failed_urls = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        for config in configs:
            context = browser.new_context(viewport={'width': 1280, 'height': 720})
            page = context.new_page()
            
            success = login_to_instance(page, config)
            if success:
                success_urls.append(config.get("url"))
            else:
                failed_urls.append(config.get("url"))
            
            context.close()
            time.sleep(2)
            
        browser.close()
        print("\nAll instances processed.")

    # Generate status report for GitHub Actions
    with open("status_report.txt", "w", encoding="utf-8") as f:
        if success_urls:
            f.write("✅ Successful PDI Logins:\n")
            for url in success_urls:
                f.write(f"- {url}\n")
            f.write("\n")
        
        if failed_urls:
            f.write("❌ Failed PDI Logins:\n")
            for url in failed_urls:
                f.write(f"- {url}\n")

    if failed_urls:
        print(f"Logins failed for: {', '.join(failed_urls)}")
        sys.exit(1)
    else:
        print("All logins completed successfully.")

if __name__ == "__main__":
    run()
