import os
import sys
import time
import json
from datetime import datetime
from playwright.sync_api import sync_playwright

# Configuration from Environment Variables
URL = os.getenv("SN_PDI_URL")
USERNAME = os.getenv("SN_USERNAME")
PASSWORD = os.getenv("SN_PASSWORD")
HISTORY_FILE = "login_history.json"

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
    # Keep only last 100 entries
    history = history[-100:]
    
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
    print(f"History for {instance_url} saved to {HISTORY_FILE}")

def run():
    print(f"Starting ServiceNow Auto Login for: {URL}")
    
    if not URL or not USERNAME or not PASSWORD:
        print("Error: SN_PDI_URL, SN_USERNAME, and SN_PASSWORD must be set.")
        sys.exit(1)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1280, 'height': 720})
        page = context.new_page()

        try:
            print(f"Navigating to {URL}...")
            page.goto(URL, timeout=300000)
            
            # 1. Detection: Hibernation
            content = page.content().lower()
            if "hibernating" in content or "wake your instance" in content:
                print("Detected PDI Hibernation. Waking up...")
                dev_portal_login_url = "https://signon.service-now.com/x_snc_ssoauth.do?redirectUri=https://developer.servicenow.com/dev.do"
                page.goto(dev_portal_login_url, timeout=120000)
                
                page.wait_for_selector("#username", state="visible", timeout=60000)
                page.fill("#username", USERNAME)
                page.click("#identify-submit")
                
                page.wait_for_selector("#password", state="visible", timeout=60000)
                page.fill("#password", PASSWORD)
                page.press("#password", "Enter")
                
                page.wait_for_load_state("networkidle", timeout=120000)
                print("Successfully logged into Developer Portal. Waiting for wake-up...")
                time.sleep(15) 
                page.goto(URL, timeout=300000)

            # 2. Standard Login
            print("Waiting for login form...")
            page.wait_for_selector("#user_name", state="visible", timeout=300000)
            page.fill("#user_name", USERNAME)
            page.fill("#user_password", PASSWORD)
            page.click("#sysverb_login")
            
            page.wait_for_load_state("networkidle", timeout=60000)
            
            error_message = None
            try:
                error_selector = ".outputmsg_error"
                if page.is_visible(error_selector):
                    error_message = page.inner_text(error_selector).strip()
            except:
                pass

            current_title = page.title()
            print(f"Current Page Title: {current_title}")
            
            safe_name = URL.split("//")[-1].strip("/").replace(".", "_").replace("/", "_")
            screenshot_path = f"result_{safe_name}.png"
            page.screenshot(path=screenshot_path)
            
            if "Sign In" in current_title or "Login" in current_title or error_message:
                print(f"Login failed for {URL}")
                save_history(URL, "Error", title=current_title, error=error_message or "Login redirected")
                sys.exit(1)
            else:
                print(f"Login successful for {URL}")
                save_history(URL, "Success", title=current_title)

        except Exception as e:
            print(f"Error: {e}")
            safe_name = URL.split("//")[-1].strip("/").replace(".", "_").replace("/", "_")
            page.screenshot(path=f"error_{safe_name}.png")
            save_history(URL, "Error", error=e)
            sys.exit(1)
        finally:
            browser.close()

if __name__ == "__main__":
    run()
