import secrets
import string

from utils import *
from is_pages.is_incorrect_page import *
from get_boomlify_code import *
from access_keys import *
from seleniumbase import sb_cdp


def _generate_password(length: int = 15) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    # Ensure at least one of each type for better strength.
    base = [
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.digits),
        secrets.choice("!@#$%^&*"),
    ]
    if length < len(base):
        length = len(base)
    remaining = length - len(base)
    base.extend(secrets.choice(alphabet) for _ in range(remaining))
    # Shuffle without leaking order; secrets.choice above is already random.
    secrets.SystemRandom().shuffle(base)
    return "".join(base)

def _reset_password_once(email, password, new_password):
    debug()
    print("[PASSWROD RESET] Starting password reset in separate session...")
    password_reset_sb = sb_cdp.Chrome("https://platform.openai.com/docs/overview")
    password_reset_sb.cdp = password_reset_sb
    try:
        debug()
        short_sleep_dbg(password_reset_sb, "Chatgpt password change page")

        password_reset_sb.sleep(3)
        debug()
        # Fill login form
        if not safe_wait_visible(password_reset_sb, 'button:contains("Log in")', timeout=20, label="reset_login_button"):
            debug()
            return None
        short_sleep_dbg(password_reset_sb, "Log in button visible")
        save_ss(password_reset_sb, "Password change page")
        debug()
        if not safe_click(password_reset_sb, 'button:contains("Log in")', label="reset_login_click"):
            debug()
            return None
        short_sleep_dbg(password_reset_sb, "Log in button clicked")
        print("Log in button clicked")
        password_reset_sb.sleep(15)
        debug()
        password_reset_sb.sleep(10)
        save_ss(password_reset_sb, "Login clicked")

        if not safe_wait_visible(password_reset_sb, 'input[type="email"]', timeout=20, label="reset_email_input"):
            debug()
            return None
        if not safe_click(password_reset_sb, 'input[type="email"]', label="reset_email_click"):
            debug()
            return None
        if not safe_type(password_reset_sb, 'input[type="email"]', email, label="reset_email_type"):
            debug()
            return None
        short_sleep_dbg(password_reset_sb, "Email filled")
        save_ss(password_reset_sb, "Email filled")
        debug()
        password_reset_sb.sleep(2)
        if not safe_click(password_reset_sb, 'button:contains("Continue")', label="reset_email_continue"):
            debug()
            return None
        if not safe_wait_visible(password_reset_sb, 'input[type="password"]', timeout=20, label="reset_password_input"):
            debug()
            return None
        if not safe_click(password_reset_sb, 'input[type="password"]', label="reset_password_click"):
            debug()
            return None
        sb_password = None
        debug()
        if password and password != "password-from-get_password":
            sb_password = password
            debug()
        if not sb_password:
            sb_password = get_password(email)
            debug()

        if sb_password:
            debug()
            if not safe_type(password_reset_sb, 'input[type="password"]', sb_password, label="reset_password_type"):
                debug()
                return None
            save_ss(password_reset_sb, "typed login password")
            debug()
            short_sleep_dbg(password_reset_sb, "typed login password")
            if not safe_click(password_reset_sb, 'button:contains("Continue")', label="reset_password_continue"):
                debug()
                return None
            password_reset_sb.sleep(3)
            debug()
            check = is_incorrect_credentials_page_visible(password_reset_sb)
            print(f'is incorrect credentials page: {check}')
            debug()
            if check == False:
                return sb_password
            password_reset_sb.sleep(1)
        else:
            print("[PASSWORD RESET] Stored password is empty; continuing to reset flow.")

        # Wait for it to be visible and then click
        reset_link_selectors = [
            "a[href='/reset-password']",
            "a:contains('Reset password')",
            "a:contains('Forgot password')",
            "button:contains('Reset password')",
            "a:contains('Forgot password?')",
        ]
        debug()
        reset_clicked = click_first(password_reset_sb, reset_link_selectors, label="reset-password-link")
        if not reset_clicked:
            debug()
            with suppress(Exception):
                debug()
                password_reset_sb.cdp.open("https://platform.openai.com/reset-password")
                short_sleep_dbg(password_reset_sb, "opened reset-password directly")
                reset_clicked = True
        if not reset_clicked:
            debug()
            print("[PASSWROD RESET][ERROR] Reset password link not found")
            save_ss(password_reset_sb, "reset_password_link_missing")
            return None
        password_reset_sb.sleep(5)
        debug()
        if not safe_wait_visible(password_reset_sb, 'button:contains("Continue")', timeout=10, label="reset_link_continue"):
            debug()
            return None
        if not safe_click(password_reset_sb, 'button:contains("Continue")', label="reset_link_continue_click"):
            debug()
            return None
        password_reset_sb.sleep(2)
        debug()
        save_ss(password_reset_sb, "Password reset verification")
        code = fetch_chatgpt_code_from_boomlify_separate(email)
        debug()
        password_reset_sb.sleep(2)
        if not safe_wait_visible(password_reset_sb, 'div:contains("Code")', timeout=10, label="reset_code_input"):
            debug()
            return None
        if not safe_type(password_reset_sb, 'div:contains("Code")', code, label="reset_code_type"):
            debug()
            return None
        password_reset_sb.sleep(2)
        save_ss(password_reset_sb, "Typed boomlify code in chatgpt page.")
        print("Typed boomlify code in chatgpt page.")
        password_reset_sb.sleep(10)
        debug()
        if not safe_wait_visible(password_reset_sb, 'button:contains("Continue")', timeout=10, label="reset_code_continue"):
            debug()
            return None
        if not safe_click(password_reset_sb, 'button:contains("Continue")', label="reset_code_continue_click"):
            debug()
            return None
        password_reset_sb.sleep(10)

        if not safe_wait_visible(password_reset_sb, 'div:contains("New password")', timeout=10, label="reset_new_password"):
            debug()
            return None
        if not safe_click(password_reset_sb, 'div:contains("New password")', label="reset_new_password_click"):
            debug()
            return None
        if not safe_type(password_reset_sb, 'div:contains("New password")', new_password, label="reset_new_password_type"):
            debug()
            return None
        password_reset_sb.sleep(2)
        debug()
        # New password must contain atleast 12 characters
        if not safe_wait_visible(password_reset_sb, 'div:contains("Re-enter new password")', timeout=10, label="reset_reenter_password"):
            debug()
            return None
        if not safe_click(password_reset_sb, 'input[placeholder="Re-enter new password"]', label="reset_reenter_password_click"):
            debug()
            return None
        if not safe_type(password_reset_sb, 'input[placeholder="Re-enter new password"]', new_password, label="reset_reenter_password_type"):
            debug()
            return None
        password_reset_sb.sleep(2)
        save_ss(password_reset_sb, "Before password reset continue button")
        debug()
        if not safe_wait_visible(password_reset_sb, 'button:contains("Continue")', timeout=10, label="reset_final_continue"):
            debug()
            return None
        if not safe_click(password_reset_sb, 'button:contains("Continue")', label="reset_final_continue_click"):
            debug()
            return None
        debug()
        password_reset = True
        save_ss(password_reset_sb, "After password reset continue button")
        update_password(email, new_password)
        sleep_dbg(password_reset_sb, secs=None, a=30, b=50, label="")
        save_ss(password_reset_sb, "After clicking Continue button")
        debug()
        return new_password
    except Exception as e:
        debug()
        print(f"[PASSWROD RESET][ERROR] {str(e)[:200]}")
        save_ss(password_reset_sb, "password_reset_failed")
        return None
    finally:
        debug()
        password_reset_sb.driver.stop()

def reset_password(email, password, max_attempts=3):
    debug()
    new_password = _generate_password(15)
    for attempt in range(1, max_attempts + 1):
        if attempt > 1:
            debug()
            print(f"[PASSWROD RESET] Retry attempt {attempt}/{max_attempts}")
            time.sleep(3)
        result = _reset_password_once(email, password, new_password)
        if result:
            return result
        debug()
    debug()
    return None


if __name__ == "__main__":
    # email = input("Enter the account email to reset: ").strip()
    # password = input("Enter the current password (leave blank to use stored password): ").strip()
    # result = reset_password(email, password or "password-from-get_password")
    result = reset_password("gx2zd9yeug@dev.nondon.store", "password-from-get_password")
    print(f"Reset result: {result}")
