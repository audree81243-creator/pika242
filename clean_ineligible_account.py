import re
import time
from contextlib import suppress

from seleniumbase import sb_cdp

from utils import *
from access_keys import delete_account, list_accounts
from create_boomlify_account import _handle_cloudflare_verification
from access_keys import delete_accounts

emails = [
  "sd5nmrme6@dev.nondon.store",
  "ozfntlhehezuhh@dev.nondon.store",
  "uaguhagohcgf@dev.nondon.store",
  "w9w6uhamj@dev.nondon.store",
  "dglrx81n2zcq7@dev.nondon.store",
  "bj1eagf5cy@dev.nondon.store",
  "ug3z3eumxdjthte@dev.nondon.store",
  "zppzrv4yr5@dev.nondon.store",
  "jqlj3euuq@dev.nondon.store",
  "sfvf7aee7ltg@dev.nondon.store",
  "xs8zummhyhm@dev.nondon.store",
  "qewlkljpef75j@dev.nondon.store",
  "j0m7zxscqu@dev.nondon.store"
]

def _safe_name(value):
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value or "unknown")
    return (cleaned or "unknown")[:60]


def _login_boomlify(sb, login_email, login_password):
    short_sleep_dbg(sb, "boomlify login page")
    sb.sleep(5)

    if not safe_wait_visible(sb, 'input[type="email"]', timeout=20, label="boomlify_email_input"):
        save_ss(sb, "boomlify_email_input_missing")
        return False
    if not safe_click(sb, 'input[type="email"]', label="boomlify_email_click"):
        return False
    if not safe_type(sb, 'input[type="email"]', login_email, label="boomlify_email_type"):
        return False
    save_ss(sb, "boomlify_email_filled")
    short_sleep_dbg(sb, "typed login email")

    if not safe_wait_visible(sb, 'input[type="password"]', timeout=20, label="boomlify_password_input"):
        save_ss(sb, "boomlify_password_input_missing")
        return False
    if not safe_click(sb, 'input[type="password"]', label="boomlify_password_click"):
        return False
    if not safe_type(sb, 'input[type="password"]', login_password, label="boomlify_password_type"):
        return False
    save_ss(sb, "boomlify_password_filled")
    short_sleep_dbg(sb, "typed login password")

    sb.sleep(4)
    with suppress(Exception):
        sb.solve_captcha()
    with suppress(Exception):
        sb.wait_for_element_absent("input[disabled]")
    sb.sleep(14)
    with suppress(Exception):
        sb.scroll_down(30)
    sb.sleep(10)
    save_ss(sb, "boomlify_cloudflare_verified")
    sb.sleep(6)

    click_first(
        sb,
        [
            'button:contains("Access Your Secure Inbox")',
            'button[type="submit"]',
        ],
        label="boomlify-login-submit",
    )
    sleep_dbg(sb, a=6, b=10, label="after submit login")

    with suppress(Exception):
        if not re.search(r"/dashboard", sb.get_current_url() or "", re.I):
            sb.open("https://boomlify.com/en/dashboard")
            sleep_dbg(sb, a=2, b=4, label="ensure dashboard")

    save_ss(sb, "boomlify_dashboard_check")
    if not _handle_cloudflare_verification(sb, "after_login"):
        return False
    return True


def _search_and_check(sb, search_email, timeout=8):
    search_selectors = [
        'input[placeholder*="Search" i]',
        'input[type="search"]',
        'input[aria-label*="Search" i]',
    ]
    ssel = click_first(sb, search_selectors, label="boomlify-search")
    if not ssel:
        save_ss(sb, "boomlify_search_missing")
        return None

    with suppress(Exception):
        sb.cdp.clear_input(ssel)
    if not safe_type(sb, ssel, search_email, label="boomlify_search_type"):
        return None

    sb.sleep(4)
    save_ss(sb, f"boomlify_search_{_safe_name(search_email)}")

    t0 = time.time()
    while time.time() - t0 < timeout:
        html = sb.get_page_source()
        if re.search(r"Access\s+Deactivated", html, re.I):
            print(f"[BOOMLIFY][NOTICE] Access deactivated for {search_email}")
            save_ss(sb, f"boomlify_access_deactivated_{_safe_name(search_email)}")
            return True
        sb.sleep(1.5)
    return False


def clean_ineligible_accounts(
    boomlify_login_email,
    boomlify_login_password,
    limit=None,
    delete_after_list=False,
):
    accounts = list_accounts(limit=limit)
    if not accounts:
        print("[CLEAN] No accounts found in Supabase.")
        return [], 0

    boom_sb = sb_cdp.Chrome("https://boomlify.com/en/login")
    boom_sb.cdp = boom_sb
    ineligible = []
    removed = 0
    try:
        if not _login_boomlify(boom_sb, boomlify_login_email, boomlify_login_password):
            print("[CLEAN][ERROR] Boomlify login failed.")
            return [], 0

        total = len(accounts)
        for idx, row in enumerate(accounts, start=1):
            email = (row.get("email") or "").strip()
            if not email:
                continue
            print(f"[CLEAN] ({idx}/{total}) Checking {email}")
            _handle_cloudflare_verification(boom_sb, f"before_search_{idx}")
            status = _search_and_check(boom_sb, email)
            if status is None:
                print(f"[CLEAN] Ineligible so far: {len(ineligible)}")
                continue
            if status:
                ineligible.append(email)
                print(f"[CLEAN] Ineligible: {email}")
            print(f"[CLEAN] Ineligible so far: {len(ineligible)}")
            boom_sb.sleep(2.0)
    finally:
        boom_sb.driver.stop()

    if ineligible:
        print("[CLEAN] Ineligible accounts:")
        for email in ineligible:
            print(f" - {email}")
    else:
        print("[CLEAN] No ineligible accounts found.")

    if delete_after_list and ineligible:
        for email in ineligible:
            delete_account(email)
            removed += 1
        print(f"[CLEAN] Deleted {removed} account(s) from Supabase.")
    return ineligible, removed


if __name__ == "__main__":
#######################################################################
    boom_email = "staywhizzy2023@gmail.com"
    boom_password = "Katana@23033"
    DELETE_AFTER_LIST = False
    ineligible_accounts, removed_count = clean_ineligible_accounts(
        boom_email,
        boom_password,
        delete_after_list=DELETE_AFTER_LIST,
    )
    print(f"Ineligible accounts: {len(ineligible_accounts)}")
    print(f"Removed accounts: {removed_count}")
#######################################################################
    removed = delete_accounts(ineligible_accounts)
    print(f"Removed: {removed}")
