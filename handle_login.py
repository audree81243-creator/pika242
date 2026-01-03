from utils import *
from access_keys import get_password, update_password
from is_pages.is_verification_page import *
from is_pages.is_chat_ui import *
from is_pages.is_incorrect_page import *
from is_pages.is_pop_ups import is_popups_visible
from seleniumbase import sb_cdp
from get_boomlify_code import fetch_chatgpt_code_from_boomlify_separate
from password_reset_chatgpt import reset_password


def _handle_login_once(sb, email, password):
    print("(handle login) Navigating to https://chatgpt.com/auth/login")
    debug()
    try:
        # Ensure CDP is available before using sb.cdp
        if hasattr(sb, "activate_cdp_mode"):
            if not getattr(sb, "cdp", None):
                sb.activate_cdp_mode("https://chatgpt.com/auth/login")
                debug()
            else:
                sb.cdp.open("https://chatgpt.com/auth/login")
        else:
            sb.cdp = sb
            sb.cdp.open("https://chatgpt.com/auth/login")
            debug()
    except Exception as e:
        print("(handle login)[ERROR] Could not open /auth/login:", str(e)[:200])
        save_ss(sb, "login_open_error")
        return "reopen"

    sleep_dbg(sb, a=8, b=15, label="after /auth/login open")
    save_ss(sb, "login_page")
    debug()
    login_button_selectors = [
        'button[data-testid="login-button"]',
        'button[data-testid="log-in-button"]',
        'button:has(span:contains("Log in"))',
        'button:contains("Log in")',
    ]

    # Accept cookies if the banner is present before proceeding.
    cookies_accept_selectors = [
        'button:contains("Accept all")',
        'button:contains("Accept all cookies")',
        'button:contains("Accept")',
        'button:contains("Yes")',
        'button[aria-label*="Accept"][aria-label*="cookie" i]',
    ]
    debug()
    cookies_clicked = click_first(sb, cookies_accept_selectors, label="accept-cookies")
    if cookies_clicked:
        sleep_dbg(sb, a=3, b=10, label="post accept-cookies")
        save_ss(sb, "after_login_btn")
        debug()

    clicked_login_btn = click_first(sb, login_button_selectors, label="login button")
    debug()
    if not clicked_login_btn:
        # Fallback: some pages hide the login button under a "More options" dropdown.
        more_options_selectors = [
            'button:contains("More options")',
            'div:contains("More options")',
        ]
        debug()
        sb.sleep(2)
        save_ss(sb, "after_login_btn")
        mo_clicked = click_first(sb, more_options_selectors, label="more-options")
        if mo_clicked:
            debug()
            sleep_dbg(sb, a=1, b=3, label="post more-options click")
            save_ss(sb, "after_login_btn")
            clicked_login_btn = click_first(sb, login_button_selectors, label="login button after more options")

    if clicked_login_btn:
        print(f"[(handle login)LOGIN] Clicked login button: {clicked_login_btn}")
        sleep_dbg(sb, a=5, b=10, label="post login-button click")
        sb.sleep(3)
        debug()
        save_ss(sb, "after_login_btn")
    sb.sleep(15)
    debug()
    email_selectors = [
        'div[role="dialog"] input#email',
        'div[role="dialog"] input[name="email"]',
        'div[role="dialog"] input[type="email"]',
        'div[role="dialog"] input[placeholder*="Email" i]',
        'div[role="dialog"] input[aria-label*="Email" i]',
        'input#email',
        'input[name="email"]',
        'input[name="username"]',
        'input[id="username"]',
        'input[type="email"]',
        'input[autocomplete="username"]',
        'input[placeholder*="Email" i]',
        'input[aria-label*="Email" i]',
    ]
    debug()
    email_input = None
    for _ in range(60):
        for sel in email_selectors:
            if visible(sb, sel):
                email_input = sel
                break
        if email_input:
            break
        sb.sleep(0.5)
    debug()
    if not email_input:
        print("[ERROR]: [ERROR] Email input not found in login dialog")
        save_ss(sb, "email_input_not_found")
        return "reopen"
    debug()
    print(f"(handle login) Email input found: {email_input}")
    try:
        if not safe_click(sb, email_input, label="login_email_click"):
            debug()
            return "reopen"
        short_sleep_dbg(sb, label="before typing email")
        if not safe_type(sb, email_input, email, label="login_email_type"):
            debug()
            return "reopen"
        short_sleep_dbg(sb, label="after typing email")
        save_ss(sb, "email_typed")
    except Exception as e:
        print("(handle login)[ERROR] Typing email failed:", str(e)[:200])
        save_ss(sb, "email_type_error")
        return "reopen"

    debug()
    continue_btn_selectors = [
        'button[type="submit"]',
        'button:contains("Continue")',
        'div[role="dialog"] button[type="submit"]',
        'div[role="dialog"] button:contains("Continue")',
    ]
    debug()
    sb.sleep(15)
    cont_sel = click_first(sb, continue_btn_selectors, label="continue-after-email")
    if not cont_sel:
        print("(handle login)[ERROR] Continue button after email not found/clickable")
        save_ss(sb, "continue_button_missing")
        debug()
        return "reopen"

    sleep_dbg(sb, a=8, b=15, label="after Continue (email)")
    debug()
    # If email verification page appears here, report and stop login flow
    if is_verification_page_visible(sb, timeout=8, screenshot_name="verification_after_email"):
        print("(handle login) Verification code required after email step")
        debug()
        return "verification"

    # Password input on auth.openai.com
    pwd_selectors = [
        'input[type="password"]',
        'input[autocomplete="current-password"]',
        'input[id*="current-password"]',
        'input[name="password"]',
        'input[placeholder*="Password" i]',
    ]
    debug()
    pwd_input = None
    for _ in range(40):
        for sel in pwd_selectors:
            if visible(sb, sel):
                pwd_input = sel
                break
        if pwd_input:
            break
        sb.sleep(0.5)
    debug()
    if not pwd_input:
        print("[ERROR] Password input not found")
        save_ss(sb, "password_input_not_found")
        debug()
        return "reopen"

    print(f"(handle login) Password input found: {pwd_input}")
    debug()
    try:
        if not safe_click(sb, pwd_input, label="login_password_click"):
            debug()
            return "reopen"
        short_sleep_dbg(sb, label="before typing password")
        sb_password = password or get_password(email)
        debug()
        if not sb_password:
            print("[handle login][ERROR] Password missing for email; cannot continue")
            save_ss(sb, "password_missing")
            debug()
            return "reopen"
        if not safe_type(sb, pwd_input, sb_password, label="login_password_type"):
            debug()
            return "reopen"
        short_sleep_dbg(sb, label="after typing password")
        debug()
        save_ss(sb, "password_typed")
    except Exception as e:
        print("[handle login][ERROR] Typing password failed:", str(e)[:200])
        save_ss(sb, "password_type_error")
        return "reopen"

    continue_button_selectors = [
        'button[type="submit"]',
        'button:contains("Continue")',
    ]
    debug()
    pw_sel = click_first(sb, continue_button_selectors, label="password-continue")
    if not pw_sel:
        print("[ERROR] Password submit button not found/clickable")
        save_ss(sb, "password_continue_missing")
        debug()
        return "reopen"

    sleep_dbg(sb, a=8, b=15, label="after Continue (password)")
    save_ss(sb, "after_password_continue")
    debug()
    try:
        sb.sleep(3)
        cookies_verification = sb.cdp.get_all_cookies()  # ✅ Correct
        print(f"(handle login) [COOKIES] Saved {len(cookies_verification)} cookies")
        debug()
    except Exception as e:
        print(f"(handle login) [COOKIES] Error saving cookies: {e}")
    
    # If verification page appears after password, report and stop login flow
    if is_verification_page_visible(sb, timeout=8, screenshot_name="verification_after_password"):
        print("(handle login) Verification code required after password step")
        error_page="verification"
        debug()
        return "verification"
    
    
    if is_incorrect_credentials_page_visible(sb):  
        print("(handle login) Incorrect credentials detected! Need to reset password now!")
        error_page="password incorrect"
        debug()
        return "password_incorrect"
    
    if is_chat_ui_visible(sb):
        save_ss(sb, "chat_ui_ready")
        popups=is_popups_visible(sb)
        print("(handle login) Login successful, chat UI visible")
        sb.sleep(10)
        popups=is_popups_visible(sb)
        debug()
        error_page="we_passed"
        return "ok"
    
    # Handle error: retry with another account or abort
    debug()
    print("[ERROR] After login, #prompt-textarea not visible")
    return "reopen"


def _submit_verification_code(sb, email):
    print("(handle login) Fetching verification code from Boomlify")
    code = fetch_chatgpt_code_from_boomlify_separate(email)
    if code == -1:
        print("(handle login) Access deactivated; marking account as ERROR.")
        with suppress(Exception):
            update_password(email, "ERROR")
        save_ss(sb, "verification_access_deactivated")
        return "deactivated"
    if not code:
        save_ss(sb, "verification_code_missing")
        return False

    otp_selectors = [
        'input[name="code"]',
        'input[autocomplete="one-time-code"]',
        'input[id*="code" i]',
        'input[placeholder*="code" i]',
        'input[aria-label*="code" i]',
        'input[type="text"]',
    ]
    otp_sel = None
    t0 = time.time()
    while time.time() - t0 < 30:
        for sel in otp_selectors:
            try:
                if visible(sb, sel):
                    otp_sel = sel
                    break
                sb.cdp.find_element(sel, timeout=1)
                otp_sel = sel
                break
            except Exception:
                pass
        if otp_sel:
            break
        sb.sleep(1.0)

    if not otp_sel:
        save_ss(sb, "verification_input_missing")
        return False

    try:
        if not safe_click(sb, otp_sel, label="verification_code_click"):
            return False
        short_sleep_dbg(sb, label="before typing verification code")
        if not safe_type(sb, otp_sel, str(code), label="verification_code_type"):
            return False
        short_sleep_dbg(sb, label="after typing verification code")
        save_ss(sb, "verification_code_filled")
    except Exception as e:
        print("(handle login)[ERROR] Typing verification code failed:", str(e)[:200])
        save_ss(sb, "verification_type_error")
        return False

    otp_continue_selectors = [
        'button[type="submit"]',
        'button:contains("Continue")',
        'button:contains("Verify")',
        'button:contains("Submit")',
    ]
    try:
        cont_sel = click_first(sb, otp_continue_selectors, label="continue-after-otp")
    except RuntimeError as e:
        print(f"(handle login)[WARN] {e}")
        save_ss(sb, "verification_continue_click_failed")
        return False
    if not cont_sel:
        save_ss(sb, "verification_continue_missing")
        return False
    sleep_dbg(sb, a=12, b=20, label="after Continue (verification)")
    return True


def handle_login(email, password, sb=None):
    max_attempts = 5
    same_session_attempts = 2
    attempts = 0

    if sb is not None:
        while attempts < max_attempts:
            debug()
            status = _handle_login_once(sb, email, password)
            if status == "ok":
                debug()
                return True, sb
            if status == "verification":
                verification_result = _submit_verification_code(sb, email)
                if verification_result == "deactivated":
                    return False, None
                if verification_result and is_chat_ui_visible(sb):
                    debug()
                    return True, sb
                status = "reopen"
            elif status == "password_incorrect":
                debug()
                new_password = reset_password(email, password)
                if new_password:
                    password = new_password
                    debug()
                sleep_dbg(sb, a=12, b=20, label="after password reset")
                status = "reopen"
            attempts += 1
            if attempts < max_attempts:
                debug()
                sleep_dbg(sb, a=12, b=25, label="before retry login")
        return False, None

    session = None
    while attempts < max_attempts:
        if session is None:
            session = sb_cdp.Chrome("https://chatgpt.com/auth/login")
            debug()
            session.cdp = session
            sleep_dbg(session, a=6, b=10, label="session warmup")

        status = _handle_login_once(session, email, password)
        print(status)
        if status == "ok":
            debug()
            return True, session
        if status == "verification":
            verification_result = _submit_verification_code(session, email)
            if verification_result == "deactivated":
                return False, None
            if verification_result and is_chat_ui_visible(session):
                debug()
                return True, session
            status = "reopen"
        elif status == "password_incorrect":
            debug()
            new_password = reset_password(email, password)
            if new_password:
                password = new_password
            sleep_dbg(session, a=12, b=20, label="after password reset")
            status = "reopen"

        attempts += 1
        if attempts < same_session_attempts:
            sleep_dbg(session, a=12, b=25, label="retry same session")
            continue

        if session is not None:
            try:
                session.driver.stop()
            except Exception:
                pass
            session = None
        if attempts < max_attempts:
            time.sleep(2)

    if session is not None:
        try:
            session.driver.stop()
        except Exception:
            pass
    return False, None


if __name__ == "__main__":
    # Simple runner so a developer can try the login flow directly.
    # email = input("Enter the login email: ").strip()
    # password = input("Enter the password (leave blank to use get_password lookup): ").strip()
    email = "knw1i1dbr1nq@dev.nondon.store"
    password = "VEceq0&K7P&vfan"

    ok, session = handle_login(email, password or "password-from-get_password")
    print(f"Login result: {ok}")
    if session is not None:
        session.driver.stop()
