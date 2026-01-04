import os
import platform
import random
import time
from contextlib import suppress, contextmanager
from typing import Callable, Optional, Sequence
from is_pages.is_verification_page import *
from is_pages.is_chat_ui import *
from is_pages.is_incorrect_page import *
from is_pages.is_pop_ups import is_popups_visible

from seleniumbase import SB, sb_cdp

from get_boomlify_code import fetch_chatgpt_code_from_boomlify_separate
from password_reset_chatgpt import _generate_password
from access_keys import update_password
from utils import *
from utils import _complete_onboarding
from password_reset_chatgpt import *

_ss_counter = 1  # global screenshot counter across the flow
_GATEWAY_PREFIX = "GATEWAY_TIMEOUT"

first_names = [
    "James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph", "Thomas", "Charles",
    "Christopher", "Daniel", "Matthew", "Anthony", "Mark", "Donald", "Steven", "Paul", "Andrew", "Joshua",
    "Kenneth", "Kevin", "Brian", "George", "Timothy", "Ronald", "Edward", "Jason", "Jeffrey", "Ryan",
    "Jacob", "Gary", "Nicholas", "Eric", "Stephen", "Jonathan", "Larry", "Justin", "Scott", "Brandon",
    "Benjamin", "Samuel", "Gregory", "Frank", "Alexander", "Patrick", "Jack", "Dennis", "Jerry", "Tyler",
    "Aaron", "Henry", "Douglas", "Peter", "Adam", "Nathan", "Zachary", "Walter", "Kyle", "Ethan",
    "Mary", "Patricia", "Jennifer", "Linda", "Elizabeth", "Barbara", "Susan", "Jessica", "Sarah", "Karen",
    "Nancy", "Lisa", "Margaret", "Betty", "Sandra", "Ashley", "Kimberly", "Emily", "Donna", "Michelle",
    "Carol", "Amanda", "Melissa", "Deborah", "Stephanie", "Rebecca", "Sharon", "Laura", "Cynthia", "Kathleen",
    "Amy", "Shirley", "Angela", "Helen", "Anna", "Brenda", "Pamela", "Nicole", "Emma", "Samantha",
    "Christine", "Catherine", "Victoria", "Allison", "Hannah", "Grace", "Chloe", "Julia",
]
last_names = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
    "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
    "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson",
    "Walker", "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
    "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell", "Carter", "Roberts",
    "Gomez", "Phillips", "Evans", "Turner", "Diaz", "Parker", "Cruz", "Edwards", "Collins", "Reyes",
    "Stewart", "Morris", "Morales", "Murphy", "Cook", "Rogers", "Gutierrez", "Ortiz", "Morgan", "Cooper",
    "Peterson", "Bailey", "Reed", "Kelly", "Howard", "Ramos", "Kim", "Cox", "Ward", "Richardson",
    "Watson", "Brooks", "Chavez", "Wood", "James", "Bennett", "Gray", "Mendoza", "Ruiz", "Hughes",
    "Price", "Alvarez", "Castillo", "Sanders", "Patel", "Myers", "Long", "Ross",
]
# sleep_dbg(sb, secs=None, a=8, b=20, label="")
class _CdpShim:
    def __init__(self, sb):
        self._sb = sb
        self.cdp = sb

    def __getattr__(self, name):
        return getattr(self._sb, name)

_CHAT_UI_QUICK_SELECTORS = [
    "#prompt-textarea",
    "textarea#prompt-textarea",
    'textarea[placeholder*="Message" i]',
]

def _chat_ui_visible_quick(sb) -> bool:
    for sel in _CHAT_UI_QUICK_SELECTORS:
        if visible(sb, sel):
            return True
    return False

def create_chatgpt_account(email: str) -> bool:
    url = "https://chatgpt.com/auth/login"
    debug()
    def _attempt_signup() -> bool:
        sb = sb_cdp.Chrome(url)
        shim = _CdpShim(sb)
        pwd_value = None
        sleep_dbg(sb, secs=None, a=8, b=20, label="")
        try:
            short_sleep_dbg(sb, label="after open /auth/login")
            save_ss(sb, "auth_login_loaded")
            debug()
            # Accept cookies banner if present
            cookies_accept_selectors = [
                'button:contains("Accept all")',
                'button:contains("Accept all cookies")',
                'button[aria-label*="Accept"][aria-label*="cookie" i]',
                'button[data-testid*="accept"][data-testid*="cookie" i]',
            ]
            if click_first(shim, cookies_accept_selectors, label="accept-cookies"):
                short_sleep_dbg(sb, label="post accept-cookies")
                sleep_dbg(sb, secs=None, a=8, b=20, label="")
                save_ss(sb, "cookies_accepted")
                debug()
            # Click the main CTA to sign up
            signup_selectors = [
                'button:contains("Sign up for free")',
                'a:contains("Sign up for free")',
                'button[data-testid*="sign-up"]',
                'button[aria-label*="sign up" i]',
            ]
            signup_clicked = click_first(shim, signup_selectors, label="sign-up-for-free")
            sleep_dbg(sb, secs=None, a=90, b=120, label="")
            debug()
            if signup_clicked:
                short_sleep_dbg(sb, label="post sign-up click")
                save_ss(sb, "signup_clicked")
                debug()
                url_after = (shim.cdp.get_current_url() or "").strip().lower()
                html = shim.cdp.get_page_source() or ""
                if url_after in ("about:blank", "data:", "") or len(html) < 800:
                    debug()
                    save_ss(sb, "signup_blank_detected")
                    shim.cdp.open("https://auth.openai.com/log-in-or-create-account")
                    sleep_dbg(sb, secs=None, a=35, b=50, label="")
                    short_sleep_dbg(sb, label="after forcing signup URL")

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
                    'input[type="email"]',
                    'input[name="email"]',
                    'input[id="email"]',
                    'input[autocomplete="username"]',
                    'input[placeholder*="Email" i]',
                ]
                email_sel = None
                t0 = time.time()
                while time.time() - t0 < 30:
                    for sel in email_selectors:
                        try:
                            if visible(sb, sel):
                                email_sel = sel
                                debug()
                                break
                            shim.cdp.find_element(sel, timeout=1)
                            email_sel = sel
                            break
                        except Exception:
                            pass
                    if email_sel:
                        debug()
                        break
                    sb.sleep(1.0)

                if not email_sel:
                    debug()
                    save_ss(sb, "signup_email_not_found")
                    return False

                if not safe_click(shim, email_sel, label="signup_email_click"):
                    debug()
                    return False
                short_sleep_dbg(sb, label="before typing email")
                if not safe_type(shim, email_sel, email, label="signup_email_type"):
                    debug()
                    return False
                short_sleep_dbg(sb, label="after typing email")
                save_ss(sb, "signup_email_filled")
                sleep_dbg(sb, secs=None, a=10, b=20, label="")
                continue_selectors = [
                    'button[type="submit"]',
                    'button:contains("Continue")',
                    'button:contains("Next")',
                ]
                cont_sel = click_first(shim, continue_selectors, label="Clicking continue button-after-email")
                if not cont_sel:
                    debug()
                    save_ss(sb, "signup_continue_not_found")
                    return False
                short_sleep_dbg(sb, label="after continue email")
                sleep_dbg(sb, secs=None, a=10, b=20, label="")
                save_ss(sb, "signup_continue_not_found")
                pwd_selectors = [
                    'input[type="password"]',
                    'input[name="password"]',
                    'input[autocomplete="new-password"]',
                    'input[autocomplete="current-password"]',
                    'input[placeholder*="Password" i]',
                    'input[placeholder="Password"]',
                ]
                debug()
                pwd_sel = None
                t1 = time.time()
                while time.time() - t1 < 30:
                    for sel in pwd_selectors:
                        try:
                            if visible(sb, sel):
                                debug()
                                pwd_sel = sel
                                break
                            shim.cdp.find_element(sel, timeout=1)
                            pwd_sel = sel
                            break
                        except Exception:
                            pass
                    if pwd_sel:
                        debug()
                        break
                    sb.sleep(1.0)

                if not pwd_sel:
                    debug()
                    save_ss(sb, "signup_password_not_found")
                    return False
                sleep_dbg(sb, secs=None, a=10, b=20, label="")
                save_ss(sb, "signup_continue_not_found")
                if not safe_click(shim, pwd_sel, label="signup_password_click"):
                    debug()
                    return False
                short_sleep_dbg(sb, label="before typing password")
                pwd_value = _generate_password(15)
                debug()
                # pwd_value = "Katana@2303abcd"
                if not safe_type(shim, pwd_sel, pwd_value, label="signup_password_type"):
                    debug()
                    return False
                short_sleep_dbg(sb, label="after typing password")
                save_ss(sb, "signup_password_filled")
                sleep_dbg(sb, secs=None, a=10, b=20, label="")
                cont_pwd_sel = click_first(shim, continue_selectors, label="Clicking continue button-after-password")
                debug()
                if not cont_pwd_sel:
                    debug()
                    save_ss(sb, "signup_continue_password_missing")
                    return False
                short_sleep_dbg(sb, label="after continue password")
                sleep_dbg(sb, secs=None, a=90, b=120, label="")
                save_ss(sb, "After clicking continue button of password to create new account")
                debug()
                if is_incorrect_credentials_page_visible(sb):
                    debug()
                    reset_password(email,pwd_value)
                    return True
                if is_verification_page_visible(sb):
                    code = fetch_chatgpt_code_from_boomlify_separate(email)
                    if not code or code == -1:
                        debug()
                        save_ss(sb, "signup_otp_fetch_failed")
                        return False

                    otp_selectors = [
                        'input[type="text"]',
                        'input[name*="code" i]',
                        'input[id*="code" i]',
                        'input[autocomplete*="one-time" i]',
                        'input[placeholder*="code" i]',
                        'input[aria-label*="code" i]',
                    ]
                    otp_sel = None
                    debug()
                    t2 = time.time()
                    while time.time() - t2 < 30:
                        for sel in otp_selectors:
                            try:
                                if visible(sb, sel):
                                    otp_sel = sel
                                    debug()
                                    break
                                shim.cdp.find_element(sel, timeout=1)
                                otp_sel = sel
                                break
                            except Exception:
                                pass
                        if otp_sel:
                            break
                        sb.sleep(1.0)
                    debug()
                    if not otp_sel:
                        debug()
                        save_ss(sb, "signup_otp_input_not_found")
                        return False

                    if not safe_click(shim, otp_sel, label="signup_otp_click"):
                        debug()
                        return False
                    short_sleep_dbg(sb, label="before typing otp")
                    if not safe_type(shim, otp_sel, str(code), label="signup_otp_type"):
                        debug()
                        return False
                    short_sleep_dbg(sb, label="after typing otp")

                    save_ss(sb, "signup_otp_filled")

                    otp_continue_selectors = continue_selectors + [
                        'button:contains("Verify")',
                        'button:contains("Submit")',
                        'button:contains("Continue")',
                    ]
                    debug()
                    sleep_dbg(sb, secs=None, a=10, b=20, label="")
                    debug()
                    cont_otp_sel = click_first(shim, otp_continue_selectors, label="continue-after-otp")
                    sleep_dbg(sb, secs=None, a=30, b=50, label="")
                    debug()
                    if not cont_otp_sel:
                        debug()
                        save_ss(sb, "signup_continue_otp_missing")
                        return False
                    short_sleep_dbg(sb, label="after continue otp")
                    sleep_dbg(sb, secs=None, a=30, b=50, label="")
                    save_ss(sb, "signup_completed")
                    debug()
                sb.sleep(10)
                if is_chat_ui_visible(sb):
                    return True

                try:
                    onboarding_ok = _complete_onboarding(
                        shim,
                        first_names,
                        last_names,
                        snap=lambda name: save_ss(sb, name),
                    )
                    debug()
                    sleep_dbg(sb, secs=None, a=30, b=50, label="")
                    if is_chat_ui_visible(sb):
                        debug()
                        update_password(email, pwd_value)
                        save_ss(sb, "Sign up completed, Chat ui visible")
                        return True
                except RuntimeError as e:
                    debug()
                    print(f"[ONBOARDING][WARN] {e}")
                    save_ss(sb, "onboarding_click_failed")
                    onboarding_ok = False
                if not onboarding_ok and _chat_ui_visible_quick(shim):
                    debug()
                    if pwd_value:
                        debug()
                        update_password(email, pwd_value)
                    save_ss(sb, "signup_completed_chat_ui_visible")
                    return True
                # these 2 lines are newly added only
                sleep_dbg(sb, secs=None, a=10, b=20, label="")
                save_ss(sb, "signup_completed")
                debug()
                if not onboarding_ok:
                    debug()
                    save_ss(sb, "onboarding_failed")
                    return False
                if pwd_value:
                    debug()
                    update_password(email, pwd_value)
                return True
            return False
        finally:
            sb.driver.stop()

    attempts = 0
    debug()
    while attempts < 5:
        debug()
        attempts += 1
        if _attempt_signup():
            return True
    return False


if __name__ == "__main__":
    # email = input("Enter the email to use: ").strip()
    email="qs6g6kloryum@dev.nondon.store"
    ok = create_chatgpt_account(email)
    print(f"Sign-up result: {ok}")
