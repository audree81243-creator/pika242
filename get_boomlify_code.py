from utils import *
import re

# This function helps us to get code from Boomlify it also checks if that account
# is blocked by Chatgpt due to scraping on which it returns -1.
def fetch_chatgpt_code_from_boomlify_separate(
    search_email,
    login_email="staywhizzy2023@gmail.com",
    login_password="Katana@23033",
    total_timeout=60,
):
    """
    SEPARATE SB session for Boomlify only!
    Opens its own browser, logs in, gets the OTP code, then closes.
    Does NOT switch tabs or interact with ChatGPT session.
    """
    print("[BOOMLIFY SERVER] Starting separate Boomlify browser session...")
    
    
    from seleniumbase import sb_cdp
    boom_sb = sb_cdp.Chrome("https://boomlify.com/en/login")
    # Provide .cdp alias for helper utilities that expect it.
    boom_sb.cdp = boom_sb
    try:
        max_attempts = 3
        search_selectors = [
            'input[placeholder*="Search" i]',
            'input[type="search"]',
            'input[aria-label*="Search" i]',
        ]
        for attempt in range(1, max_attempts + 1):
            short_sleep_dbg(boom_sb, "boomlify login page")
            cookie_selectors = [
                "/html/body/div[1]/div[1]/div[2]/button[2]",
                'button:contains("Allow all")',
                'button:contains("Allow all cookies")',
                'button:contains("Accept all")',
                'button:contains("Accept")',
            ]
            if click_first(boom_sb, cookie_selectors, label="boomlify-allow-cookies"):
                sleep_dbg(boom_sb, a=8, b=15, label="after_allow_cookies")
            boom_sb.sleep(3)

            # Fill login form
            if not safe_wait_visible(boom_sb, 'input[type="email"]', timeout=20, label="boomlify_email_input"):
                save_ss(boom_sb, "boomlify_email_input_missing")
                if attempt < max_attempts:
                    sleep_dbg(boom_sb, a=8, b=15, label="retry_after_email_missing")
                    boom_sb.open("https://boomlify.com/en/login")
                    continue
                return None
            if not safe_click(boom_sb, 'input[type="email"]', label="boomlify_email_click"):
                if attempt < max_attempts:
                    sleep_dbg(boom_sb, a=8, b=15, label="retry_after_email_click")
                    boom_sb.open("https://boomlify.com/en/login")
                    continue
                return None
            if not safe_type(boom_sb, 'input[type="email"]', login_email, label="boomlify_email_type"):
                if attempt < max_attempts:
                    sleep_dbg(boom_sb, a=8, b=15, label="retry_after_email_type")
                    boom_sb.open("https://boomlify.com/en/login")
                    continue
                return None
            save_ss(boom_sb, "boomlify_email_filled")
            short_sleep_dbg(boom_sb, "typed login email")

            if not safe_wait_visible(boom_sb, 'input[type="password"]', timeout=20, label="boomlify_password_input"):
                save_ss(boom_sb, "boomlify_password_input_missing")
                if attempt < max_attempts:
                    sleep_dbg(boom_sb, a=8, b=15, label="retry_after_password_missing")
                    boom_sb.open("https://boomlify.com/en/login")
                    continue
                return None
            if not safe_click(boom_sb, 'input[type="password"]', label="boomlify_password_click"):
                if attempt < max_attempts:
                    sleep_dbg(boom_sb, a=8, b=15, label="retry_after_password_click")
                    boom_sb.open("https://boomlify.com/en/login")
                    continue
                return None
            if not safe_type(boom_sb, 'input[type="password"]', login_password, label="boomlify_password_type"):
                if attempt < max_attempts:
                    sleep_dbg(boom_sb, a=8, b=15, label="retry_after_password_type")
                    boom_sb.open("https://boomlify.com/en/login")
                    continue
                return None
            save_ss(boom_sb, "boomlify_password_filled")
            short_sleep_dbg(boom_sb, "typed login password")

            boom_sb.sleep(2)
            boom_sb.solve_captcha()
            boom_sb.wait_for_element_absent("input[disabled]")
            boom_sb.sleep(10)
            boom_sb.scroll_down(30)
            boom_sb.sleep(8)
            save_ss(boom_sb, "boomlify_cloudflare_verified")
            boom_sb.sleep(10)

            # Submit login
            click_first(
                boom_sb,
                [
                    'button:contains("Access Your Secure Inbox")',
                    'button[type="submit"]',
                ],
                label="boomlify-login-submit",
            )
            print("[OTP] Access your inbox button clicked")
            sleep_dbg(boom_sb, a=3, b=5, label="after submit login")
            if click_first(boom_sb, ["/html/body/div[1]/div[1]/div[2]/button[2]"], label="boomlify-allow-cookies-post-login"):
                sleep_dbg(boom_sb, a=8, b=15, label="after_allow_cookies_post_login")

            # Ensure dashboard
            with suppress(Exception):
                if not re.search(r"/dashboard", boom_sb.get_current_url() or "", re.I):
                    boom_sb.open("https://boomlify.com/en/dashboard")
                    sleep_dbg(boom_sb, a=2, b=4, label="ensure dashboard")

            save_ss(boom_sb, "boomlify_dashboard_check")
            if any(visible(boom_sb, sel) for sel in search_selectors):
                break
            if attempt < max_attempts:
                save_ss(boom_sb, f"boomlify_dashboard_not_ready_{attempt}")
                sleep_dbg(boom_sb, a=8, b=15, label="retry_after_dashboard_not_ready")
                boom_sb.open("https://boomlify.com/en/login")
                continue
            return None

        # Search the email
        ssel = click_first(boom_sb, search_selectors, label="boomlify-search")
        if not ssel:
            print("[BOOMLIFY][ERROR] Search input not found on Boomlify dashboard")
            save_ss(boom_sb, "boomlify_search_missing")
            return None

        boom_sb.select_all(ssel)
        if not safe_type(boom_sb, ssel, search_email, label="boomlify_search_type"):
            return None
        short_sleep_dbg(boom_sb, "after typing search email")
        boom_sb.sleep(3)
        # Scrape the 6-digit code
        code = None
        t0 = time.time()
        while time.time() - t0 < total_timeout:
            try:
                html = boom_sb.get_page_source()

                # If Boomlify shows an "Access Deactivated" notice, stop and return -1.
                if re.search(r"Access\s+Deactivated", html, re.I):
                    print(f"[BOOMLIFY][NOTICE] Access deactivated for {search_email}")
                    save_ss(boom_sb, "boomlify_access_deactivated")
                    return -1

                m = re.search(r"Your\s+(?:ChatGPT|OpenAI)\s+(?:code\s+is|password\s+reset\s+code\s+is)\s+(\d{6})", html, re.I)
                
                if m:
                    code = m.group(1)
                    break
            except Exception:
                pass
            boom_sb.sleep(1.0)

        if not code:
            print(f"[BOOMLIFY][ERROR] Could not find ChatGPT code for {search_email}")
            save_ss(boom_sb, "boomlify_code_not_found")
            return None

        print(f"[BOOMLIFY][SUCCESS] Found verification code: {code}")
        save_ss(boom_sb, f"boomlify_code_{code}")
        return code
    finally:
        boom_sb.driver.stop()

if __name__ == "__main__":
    email = input("Which email should I search for the code? ").strip()
    code = fetch_chatgpt_code_from_boomlify_separate(email)
    print(f"Result code: {code}")
