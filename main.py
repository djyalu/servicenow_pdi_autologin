import os
import sys
import time
from playwright.sync_api import sync_playwright

# Target URL
URL = "https://dev198124.service-now.com"

# Credentials from Environment Variables
USERNAME = os.getenv("SN_USERNAME")
PASSWORD = os.getenv("SN_PASSWORD")

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
            response = page.goto(URL, timeout=300000) # 5 minutes timeout
            
            # Check for common "Waking up" indicators or wait for login form
            print("Waiting for login form (Timeout: 5 minutes)...")
            
            # This selector is standard for the main frame login on ServiceNow
            # If inside an iframe, logic might need adjustment, but usually PDI login is top-level.
            page.wait_for_selector("#user_name", state="visible", timeout=300000)
            
            print("Login form detected. Entering credentials...")
            page.fill("#user_name", USERNAME)
            page.fill("#user_password", PASSWORD)
            
            print("Submitting login form...")
            page.click("#sysverb_login")
            
            # Wait for navigation and load
            print("Waiting for post-login page load...")
            page.wait_for_load_state("networkidle", timeout=60000)
            
            # Validating login success
            # Use a generic check or title check. 
            # If we see the user menu or specific post-login elements, it's a success.
            # But simply not erroring out and ensuring URL changed or specific elements are gone is a good start.
            
            current_title = page.title()
            print(f"Current Page Title: {current_title}")
            
            # Take a screenshot for validaton in artifacts
            page.screenshot(path="login_result.png")
            print("Screenshot 'login_result.png' saved.")
            
            if "Sign In" in current_title or "Login" in current_title:
                print("Warning: Title still suggests login page. Identify if login failed.")
            else:
                print("Login appears successful based on page title.")

        except Exception as e:
            print(f"An error occurred: {e}")
            # Capture error state
            try:
                page.screenshot(path="error_state.png")
                print("Screenshot 'error_state.png' saved.")
            except:
                pass
            sys.exit(1)
        finally:
            browser.close()
            print("Browser closed.")

if __name__ == "__main__":
    run()
