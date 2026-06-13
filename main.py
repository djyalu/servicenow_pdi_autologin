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

def get_credentials(url):
    """Resolve per-instance credentials.

    SN_CREDENTIALS (optional) is a JSON object mapping an instance host
    (or full URL) to {"username": ..., "password": ...}. If a match is
    found for the current URL it is used; otherwise we fall back to the
    global SN_USERNAME / SN_PASSWORD secrets. This lets multiple PDIs
    with different admin accounts share one workflow.
    """
    user, pwd = USERNAME, PASSWORD
    creds_raw = os.getenv("SN_CREDENTIALS")
    if creds_raw:
        try:
            creds = json.loads(creds_raw)
            host = url.split("//")[-1].strip("/").lower()
            entry = creds.get(host) or creds.get(url) or creds.get(url.rstrip("/"))
            if entry:
                user = entry.get("username", user)
                pwd = entry.get("password", pwd)
                print(f"Using per-instance credentials for {host}")
        except Exception as e:
            print(f"Warning: could not parse SN_CREDENTIALS: {e}")
    return user, pwd

def save_history(instance_url, status, title=None, error=None):
    # Create a unique history file for this instance to avoid matrix conflicts
    safe_name = instance_url.split("//")[-1].strip("/").replace(".", "_").replace("/", "_")
    instance_history_file = f"history_{safe_name}.json"
    
    history = []
    if os.path.exists(instance_history_file):
        try:
            with open(instance_history_file, "r", encoding="utf-8") as f:
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
    history = history[-50:] # Keep last 50 for this instance
    
    with open(instance_history_file, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
    print(f"History for {instance_url} saved to {instance_history_file}")

def run():
    print(f"Starting ServiceNow Auto Login for: {URL}")

    if not URL:
        print("Error: SN_PDI_URL must be set.")
        sys.exit(1)

    # Standard instance login uses per-instance credentials (e.g. admin).
    username, password = get_credentials(URL)
    if not username or not password:
        print("Error: No credentials available. Set SN_USERNAME/SN_PASSWORD or SN_CREDENTIALS.")
        sys.exit(1)

    # Wake-up goes through the ServiceNow developer SSO portal, which needs
    # the developer account (email), NOT the instance-local admin. Always use
    # the global SN_USERNAME / SN_PASSWORD for that step.
    sso_user, sso_pwd = USERNAME, PASSWORD

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
                if not sso_user or not sso_pwd:
                    raise RuntimeError(
                        "Instance is hibernating but no developer SSO account "
                        "(SN_USERNAME/SN_PASSWORD) is configured to wake it.")
                dev_portal_login_url = "https://signon.service-now.com/x_snc_ssoauth.do?redirectUri=https://developer.servicenow.com/dev.do"
                page.goto(dev_portal_login_url, timeout=120000)

                page.wait_for_selector("#username", state="visible", timeout=60000)
                page.fill("#username", sso_user)
                page.click("#identify-submit")

                page.wait_for_selector("#password", state="visible", timeout=60000)
                page.fill("#password", sso_pwd)
                page.press("#password", "Enter")

                try:
                    page.wait_for_load_state("networkidle", timeout=120000)
                except Exception:
                    pass  # networkidle can hang on SSO pages; proceed regardless
                print("Successfully logged into Developer Portal. Waiting for wake-up...")
                time.sleep(15) 
                page.goto(URL, timeout=300000)

            # 2. Standard Login
            print("Waiting for login form...")
            page.wait_for_selector("#user_name", state="visible", timeout=300000)
            page.fill("#user_name", username)
            page.fill("#user_password", password)
            page.click("#sysverb_login")

            # ServiceNow keeps long-lived connections open, so networkidle may
            # never fire. Treat a timeout here as non-fatal and judge success by
            # the resulting page title instead.
            try:
                page.wait_for_load_state("networkidle", timeout=60000)
            except Exception:
                print("networkidle wait timed out; continuing to title check.")
                page.wait_for_timeout(5000)

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
