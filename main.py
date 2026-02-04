import os
import sys
import time
import json
from datetime import datetime
from playwright.sync_api import sync_playwright

# Configuration from Environment Variables
URL = os.getenv("SN_PDI_URL", "https://dev198124.service-now.com")

# Credentials from Environment Variables
USERNAME = os.getenv("SN_USERNAME")
PASSWORD = os.getenv("SN_PASSWORD")
HISTORY_FILE = "login_history.json"

def save_history(status, title=None, error=None):
    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
        except:
            pass
    
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": status,
        "title": title,
        "error": str(error) if error else None
    }
    
    history.append(entry)
    # Keep only last 50 entries
    history = history[-50:]
    
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
    print(f"History saved to {HISTORY_FILE}")

def run():
    print("Starting ServiceNow Auto Login Script...")
    
    if not USERNAME or not PASSWORD:
        print("Error: Environment variables SN_USERNAME and SN_PASSWORD must be set.")
        sys.exit(1)

    with sync_playwright() as p:
        # Launch browser
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1280, 'height': 720})
        page = context.new_page()

        try:
            print(f"Navigating to {URL}...")
            # Set a long timeout for navigation because PDI might be waking up (hibernating)
            page.goto(URL, timeout=300000) # 5 minutes timeout
            
            # 1. Detection: Check if the instance is hibernating
            content = page.content().lower()
            if "hibernating" in content or "wake your instance" in content:
                print("Detected PDI Hibernation. Starting wake-up process...")
                
                # Navigate to developer portal login
                # This URL usually triggers the SSO flow
                dev_portal_login_url = "https://signon.service-now.com/x_snc_ssoauth.do?redirectUri=https://developer.servicenow.com/dev.do"
                print(f"Navigating to ServiceNow ID login: {dev_portal_login_url}")
                page.goto(dev_portal_login_url, timeout=120000)
                
                # Step A: Enter Username
                print(f"Entering username: {USERNAME}")
                page.wait_for_selector("#username", state="visible", timeout=60000)
                page.fill("#username", USERNAME)
                page.click("#identify-submit")
                
                # Step B: Enter Password
                print("Waiting for password field...")
                page.wait_for_selector("#password", state="visible", timeout=60000)
                page.fill("#password", PASSWORD)
                
                print("Submitting login...")
                # Try both ID and pressing Enter
                page.press("#password", "Enter")
                
                # Wait for redirection to developer portal
                print("Waiting for redirection to Developer Portal...")
                page.wait_for_load_state("networkidle", timeout=120000)
                
                print("Successfully logged into Developer Portal. PDI should be waking up.")
                # Optional: Wait a bit for the wake up process to start
                time.sleep(10) 
                
                # Go back to the PDI URL
                print(f"Returning to PDI URL: {URL}")
                page.goto(URL, timeout=300000)

            # 2. Standard Login Process
            print("Waiting for PDI login form (Timeout: 5 minutes)...")
            # This selector is standard for the main frame login on ServiceNow
            page.wait_for_selector("#user_name", state="visible", timeout=300000)
            
            print("Login form detected. Entering credentials...")
            page.fill("#user_name", USERNAME)
            page.fill("#user_password", PASSWORD)
            
            print("Submitting login form...")
            page.click("#sysverb_login")
            
            # Wait for navigation and load
            print("Waiting for post-login page load...")
            page.wait_for_load_state("networkidle", timeout=60000)
            
            # Check for error messages on the page
            error_message = None
            try:
                # Wait a short bit for potential error alerts to appear
                error_selector = ".outputmsg_error"
                if page.is_visible(error_selector):
                    error_message = page.inner_text(error_selector).strip()
                    print(f"Login Error detected: {error_message}")
            except:
                pass

            # Validating login success
            current_title = page.title()
            print(f"Current Page Title: {current_title}")
            
            # Take a screenshot for validation in artifacts
            page.screenshot(path="login_result.png")
            print("Screenshot 'login_result.png' saved.")
            
            if "Sign In" in current_title or "Login" in current_title or error_message:
                print("Warning: Title still suggests login page or error message found.")
                save_history("Warning", title=current_title, error=error_message or "Title suggests login page")
            else:
                print("Login successful.")
                save_history("Success", title=current_title)

        except Exception as e:
            print(f"An error occurred: {e}")
            try:
                page.screenshot(path="error_state.png")
                print("Screenshot 'error_state.png' saved.")
            except:
                pass
            save_history("Error", error=e)
            sys.exit(1)
        finally:
            browser.close()
            print("Browser closed.")

if __name__ == "__main__":
    run()
