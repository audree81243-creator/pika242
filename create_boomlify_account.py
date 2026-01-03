import re
import time
import unicodedata
from contextlib import suppress

from seleniumbase import sb_cdp

from utils import *
from access_keys import add_email_row


def _extract_emails(html):
    return set(re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}", html or ""))

def _norm_text(text):
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower().strip()

def _extract_emails_from_text(sb):
    emails = set()
    with suppress(Exception):
        nodes = sb.find_elements("xpath=//*[contains(text(),'@')]")
        for node in nodes:
            try:
                for match in re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}", node.text or ""):
                    emails.add(match)
            except Exception:
                pass
    return emails

def _handle_cloudflare_verification(sb, stage):
    cf_selectors = [
        'div:contains("Security Verification")',
        'div:contains("Verify you are human")',
        'div:contains("Cloudflare")',
        'iframe[src*="turnstile"]',
        'iframe[src*="challenges.cloudflare.com"]',
        'iframe[title*="challenge" i]',
    ]
    show_selectors = [
        'button:contains("Show")',
        '//button[contains(., "Show")]',
    ]
    iframe_selectors = [
        'iframe[src*="turnstile"]',
        'iframe[src*="challenges.cloudflare.com"]',
        'iframe[title*="challenge" i]',
        'iframe[title*="Cloudflare" i]',
    ]
    click_targets = [
        'div.cf-turnstile',
        '.cf-turnstile-wrapper',
        'div#turnstile-widget',
        'div[id*="turnstile"]',
        'div[class*="turnstile"]',
    ] + iframe_selectors

    def _cf_visible():
        for sel in cf_selectors:
            if visible(sb, sel):
                return True
        return False

    if not _cf_visible():
        return True

    save_ss(sb, f"boomlify_cloudflare_{stage}")

    def _wait_cf_clear(timeout=12):
        t0 = time.time()
        while time.time() - t0 < timeout:
            if not _cf_visible():
                return True
            sb.sleep(0.5)
        return False

    def _click_turnstile_targets():
        for sel in click_targets:
            if visible(sb, sel):
                with suppress(Exception):
                    sb.gui_click_with_offset(sel, 30, 30)
                with suppress(Exception):
                    sb.click_with_offset(sel, 30, 30)
                return True
        return False

    def _find_cf_iframes():
        frames = []
        with suppress(Exception):
            frames = sb.find_elements("iframe")
        if not frames:
            return []
        tagged = []
        for frame in frames:
            src = ""
            with suppress(Exception):
                src = frame.get_attribute("src") or ""
            if any(key in src for key in ("cloudflare", "challenges", "turnstile")):
                tagged.append(frame)
        return tagged or frames

    def _click_turnstile_in_iframe():
        inner_selectors = [
            'input[type="checkbox"]',
            'label input[type="checkbox"]',
            'div#challenge-stage',
            'div.cf-turnstile',
        ]
        for frame in _find_cf_iframes():
            for sel in inner_selectors:
                try:
                    inner = frame.query_selector(sel)
                except Exception:
                    inner = None
                if inner:
                    with suppress(Exception):
                        inner.scroll_into_view()
                    with suppress(Exception):
                        inner.mouse_click()
                    return True
            with suppress(Exception):
                frame.click_with_offset(28, 28)
                return True
        with suppress(Exception):
            elems = sb.cdp.page.select_all(
                'input[type="checkbox"]',
                timeout=1,
                include_frames=True,
            )
            elems = sb.cdp.loop.run_until_complete(elems)
            for elem in elems:
                with suppress(Exception):
                    sb.cdp.loop.run_until_complete(elem.mouse_click_async())
                    return True
        return False

    t0 = time.time()
    while time.time() - t0 < 6:
        if any(visible(sb, sel) for sel in iframe_selectors):
            break
        sb.sleep(0.3)

    for attempt in range(3):
        click_first(sb, show_selectors, label="boomlify-cloudflare-show")
        with suppress(Exception):
            sb.solve_captcha()
        with suppress(Exception):
            sb.gui_click_captcha()
        with suppress(Exception):
            sb.click_visible_elements('input[type="checkbox"]', limit=1)
        _click_turnstile_in_iframe()
        _click_turnstile_targets()
        click_first(sb, show_selectors, label="boomlify-cloudflare-show-after")
        if _wait_cf_clear(timeout=12):
            return True
        sleep_dbg(sb, a=2, b=4, label=f"wait cloudflare verify {attempt + 1}")

    save_ss(sb, f"boomlify_cloudflare_still_visible_{stage}")
    return False

def create_boomlify_account(login_email, login_password):
    """
    Log into Boomlify and stop once the dashboard/inbox is reached.
    Returns the newly created email on success.
    """
    print("[BOOMLIFY] Starting Boomlify login session...")

    boom_sb = sb_cdp.Chrome("https://boomlify.com/en/login")
    boom_sb.cdp = boom_sb
    try:
        short_sleep_dbg(boom_sb, "boomlify login page")
        boom_sb.sleep(3)
        sleep_dbg(boom_sb, a=2, b=5, label="after login page load")

        # Fill login form
        if not safe_wait_visible(boom_sb, 'input[type="email"]', timeout=20, label="boomlify_email_input"):
            save_ss(boom_sb, "boomlify_email_input_missing")
            return None

        if not safe_click(boom_sb, 'input[type="email"]', label="boomlify_email_click"):
            return None
        if not safe_type(boom_sb, 'input[type="email"]', login_email, label="boomlify_email_type"):
            return None
        save_ss(boom_sb, "boomlify_email_filled")
        short_sleep_dbg(boom_sb, "typed login email")
        sleep_dbg(boom_sb, a=2, b=4, label="after typing email")

        if not safe_wait_visible(boom_sb, 'input[type="password"]', timeout=20, label="boomlify_password_input"):
            save_ss(boom_sb, "boomlify_password_input_missing")
            return None
        if not safe_click(boom_sb, 'input[type="password"]', label="boomlify_password_click"):
            return None
        if not safe_type(boom_sb, 'input[type="password"]', login_password, label="boomlify_password_type"):
            return None
        save_ss(boom_sb, "boomlify_password_filled")
        short_sleep_dbg(boom_sb, "typed login password")
        sleep_dbg(boom_sb, a=2, b=4, label="after typing password")

        boom_sb.sleep(2)
        boom_sb.solve_captcha()
        boom_sb.wait_for_element_absent("input[disabled]")
        boom_sb.sleep(10)
        boom_sb.scroll_down(30)
        boom_sb.sleep(8)
        save_ss(boom_sb, "boomlify_cloudflare_verified")
        boom_sb.sleep(10)
        sleep_dbg(boom_sb, a=3, b=6, label="after cloudflare verify")

        # Submit login
        click_first(
            boom_sb,
            [
                'button:contains("Access Your Secure Inbox")',
                'button[type="submit"]',
            ],
            label="boomlify-login-submit",
        )
        print("[BOOMLIFY] Access your inbox button clicked")
        sleep_dbg(boom_sb, a=3, b=5, label="after submit login")
        sleep_dbg(boom_sb, a=2, b=4, label="post login settle")

        # Ensure dashboard
        with suppress(Exception):
            if not re.search(r"/dashboard", boom_sb.get_current_url() or "", re.I):
                boom_sb.open("https://boomlify.com/en/dashboard")
                sleep_dbg(boom_sb, a=2, b=4, label="ensure dashboard")

        save_ss(boom_sb, "boomlify_dashboard_check")
        sleep_dbg(boom_sb, a=2, b=5, label="after dashboard check")

        t0 = time.time()
        while time.time() - t0 < 30:
            url = (boom_sb.get_current_url() or "").lower()
            if "dashboard" in url or "/inbox" in url:
                save_ss(boom_sb, "boomlify_dashboard_ready")
                break
            if visible(boom_sb, 'input[placeholder*="Search" i]'):
                save_ss(boom_sb, "boomlify_dashboard_ready")
                break
            boom_sb.sleep(1.0)
        else:
            save_ss(boom_sb, "boomlify_dashboard_timeout")
            return None

        before_emails = _extract_emails(boom_sb.get_page_source())
        sleep_dbg(boom_sb, a=2, b=4, label="before create click")
        if not _handle_cloudflare_verification(boom_sb, "before_create"):
            return None

        create_selectors = [
            "/html/body/div[1]/div[2]/main/div/div[1]/div[2]/div/button",
            "/html/body/div[1]/div[2]/main/div/div[1]/div[2]/div/button/span",
            'button:contains("Create")',
        ]
        clicked = click_first(boom_sb, create_selectors, label="boomlify-create-email")
        if not clicked:
            if safe_click(boom_sb, "/html/body/div[1]/div[2]/main/div/div[1]/div[2]/div/button", label="boomlify-create-email-fallback"):
                clicked = True
        if not clicked:
            try:
                buttons = boom_sb.find_elements("button")
            except Exception:
                buttons = []
            for btn in buttons:
                try:
                    text = _norm_text(getattr(btn, "text", ""))
                    if text.startswith("cre") and len(text) <= 8:
                        btn.click()
                        clicked = True
                        break
                except Exception:
                    pass

        if not clicked:
            save_ss(boom_sb, "boomlify_create_missing")
            return None
        sleep_dbg(boom_sb, a=2, b=4, label="after create click")
        sleep_dbg(boom_sb, a=10, b=20, label="after create click settle")
        if not _handle_cloudflare_verification(boom_sb, "after_create"):
            return None

        new_email = None
        t1 = time.time()
        while time.time() - t1 < 30:
            try:
                new_email = boom_sb.get_text("/html/body/div[1]/div[2]/main/div/div[3]/ul/div[2]/div/div/div[1]/div[1]/div[1]/p")
                new_email = (new_email or "").strip()
                if new_email and "@" in new_email:
                    break
            except Exception:
                pass
            html = boom_sb.get_page_source()
            emails = _extract_emails(html)
            diff = emails - before_emails
            if diff:
                new_email = sorted(diff)[0]
                break
            text_emails = _extract_emails_from_text(boom_sb)
            diff = text_emails - before_emails
            if diff:
                new_email = sorted(diff)[0]
                break
            boom_sb.sleep(1.0)

        if not new_email:
            save_ss(boom_sb, "boomlify_create_email_not_found")
            return None

        print(f"[BOOMLIFY] New email created: {new_email}")
        save_ss(boom_sb, "boomlify_email_created")
        add_email_row(new_email)
        return new_email
    finally:
        boom_sb.driver.stop()


if __name__ == "__main__":
    email = "staywhizzy2023@gmail.com"
    password = "Katana@23033"
    new_email = create_boomlify_account(email, password)
    print(f"Boomlify create result: {new_email}")
