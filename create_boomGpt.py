import os
import sys
from getpass import getpass

from create_boomlify_account import create_boomlify_account
from create_chatgpt_account import create_chatgpt_account


DEFAULT_BOOMLIFY_EMAIL = "staywhizzy2023@gmail.com"
DEFAULT_BOOMLIFY_PASSWORD = "Katana@23033"


def create_boomgpt(boomlify_login_email, boomlify_login_password):
    """
    Create a Boomlify inbox, then use it to create a ChatGPT account.

    Returns:
        (ok, new_email)
        ok: True if ChatGPT signup succeeds
        new_email: the created Boomlify inbox or None on failure
    """
    new_email = create_boomlify_account(boomlify_login_email, boomlify_login_password)
    if not new_email:
        print("[BOOMGPT] Failed to create Boomlify inbox.")
        return False, None

    print(f"[BOOMGPT] Created Boomlify inbox: {new_email}")
    ok = create_chatgpt_account(new_email)
    print(f"[BOOMGPT] ChatGPT signup result: {ok}")
    print(f"New Chatgpt account: {new_email}")
    return ok, new_email


if __name__ == "__main__":
    login_email = DEFAULT_BOOMLIFY_EMAIL
    if not login_email:
        if sys.stdin.isatty():
            login_email = input(f"Boomlify login email [{DEFAULT_BOOMLIFY_EMAIL}]: ").strip()
        else:
            login_email = DEFAULT_BOOMLIFY_EMAIL
    if not login_email:
        login_email = DEFAULT_BOOMLIFY_EMAIL

    login_password = DEFAULT_BOOMLIFY_PASSWORD
    if not login_password:
        if sys.stdin.isatty():
            login_password = getpass("Boomlify login password (leave blank for default): ").strip()
        else:
            login_password = DEFAULT_BOOMLIFY_PASSWORD
    if not login_password:
        login_password = DEFAULT_BOOMLIFY_PASSWORD

    ok, new_email = create_boomgpt(login_email, login_password)
    print(f"BoomGPT result: {ok}, email: {new_email}")
