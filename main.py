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

def _credentials_entry(url):
    """Look up this instance's entry in SN_CREDENTIALS, if any.

    SN_CREDENTIALS (optional) is a JSON object mapping an instance host
    (or full URL) to a credentials object, e.g.:
      {"dev404356.service-now.com": {
          "username": "admin", "password": "...",
          "dev_username": "you@example.com", "dev_password": "..."}}
    Returns the matched dict, or {} if none/parse error.
    """
    creds_raw = os.getenv("SN_CREDENTIALS")
    if not creds_raw:
        return {}
    try:
        creds = json.loads(creds_raw)
        host = url.split("//")[-1].strip("/").lower()
        return creds.get(host) or creds.get(url) or creds.get(url.rstrip("/")) or {}
    except Exception as e:
        print(f"Warning: could not parse SN_CREDENTIALS: {e}")
        return {}

def get_credentials(url):
    """Resolve per-instance standard-login credentials, falling back to the
    global SN_USERNAME / SN_PASSWORD secrets."""
    user, pwd = USERNAME, PASSWORD
    entry = _credentials_entry(url)
    if entry:
        user = entry.get("username", user)
        pwd = entry.get("password", pwd)
        host = url.split("//")[-1].strip("/").lower()
        print(f"Using per-instance credentials for {host}")
    return user, pwd

def get_wake_credentials(url):
    """Resolve the developer.servicenow.com account used to wake a hibernating
    PDI. Precedence: per-instance dev_username/dev_password in SN_CREDENTIALS,
    then global SN_DEV_USERNAME/SN_DEV_PASSWORD, then SN_USERNAME/SN_PASSWORD."""
    user = os.getenv("SN_DEV_USERNAME") or USERNAME
    pwd = os.getenv("SN_DEV_PASSWORD") or PASSWORD
    entry = _credentials_entry(url)
    if entry.get("dev_username"):
        user = entry["dev_username"]
    if entry.get("dev_password"):
        pwd = entry["dev_password"]
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

def dismiss_cookie_banner(page):
    """Best-effort dismissal of the developer.servicenow.com cookie banner,
    which otherwise overlays and blocks clicks."""
    for sel in ["text=Accept and Proceed", "button:has-text('Accept')",
                "#onetrust-accept-btn-handler"]:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click()
                print(f"Dismissed cookie banner via {sel}")
                return
        except Exception:
            pass

def try_click_wake(page):
    """If a wake control is visible, click it. Returns True if clicked."""
    for sel in ["button:has-text('Wake')", "a:has-text('Wake')",
                "text=Wake your instance", "text=Wake instance", "text=Wake"]:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click()
                print(f"Clicked wake control: {sel}")
                return True
        except Exception:
            pass
    return False

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
    # the developer account (email), NOT the instance-local admin. This may be
    # per-instance (SN_CREDENTIALS dev_username/dev_password) or global
    # (SN_DEV_USERNAME / SN_DEV_PASSWORD).
    sso_user, sso_pwd = get_wake_credentials(URL)

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
                print("Logged into Developer Portal. Triggering wake-up...")
                dismiss_cookie_banner(page)
                time.sleep(10)

                # Hibernating PDIs come back gradually. Poll the instance URL,
                # clicking any wake control we find, until the login form shows
                # up or we exhaust the budget (~6 min).
                woke = False
                for attempt in range(1, 19):
                    page.goto(URL, timeout=120000)
                    dismiss_cookie_banner(page)
                    if page.query_selector("#user_name"):
                        woke = True
                        print(f"Login form appeared after {attempt} wake attempt(s).")
                        break
                    try_click_wake(page)
                    print(f"Wake attempt {attempt}/18: instance not ready, waiting 20s...")
                    time.sleep(20)
                if not woke:
                    print("Instance did not finish waking within the budget.")

            # 2. Standard Login
            print("Waiting for login form...")
            page.wait_for_selector("#user_name", state="visible", timeout=120000)
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
