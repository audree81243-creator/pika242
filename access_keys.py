import os
from datetime import datetime, timezone, timedelta

import requests
from dotenv import load_dotenv

load_dotenv(override=False)

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")

# Base web address for the Supabase table.
_BASE = f"{SUPABASE_URL}/rest/v1/chatgpt_accounts"

# Required headers so Supabase knows who we are and that we send JSON.
_HEADERS = {
    "apikey": SUPABASE_SERVICE_ROLE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

# This function helps us to create the time stamp we store in the table.
def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

# This function helps us to send one web request to Supabase using the standard URL and headers.
def _req(method: str, params=None, json=None):
    resp = requests.request(method, _BASE, headers=_HEADERS, params=params, json=json, timeout=15)
    resp.raise_for_status()
    if not resp.text:
        return None
    return resp.json()

# This function helps us to find the first free account, reserve it, and hand back its details.
def get_available_account():
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=12)).isoformat()
    rows = _req(
        "GET",
        params={
            "select": "email,password,index,id",
            "is_in_use": "eq.false",
            "or": f"(last_get_account.is.null,last_get_account.lt.{cutoff})",
            "order": "index.asc",
            "limit": 1,
        },
    )
    if not rows:
        return None
    record = rows[0]
    account_id = record["id"]
    _req(
        "PATCH",
        params={"id": f"eq.{account_id}"},
        json={"is_in_use": True, "last_get_account": _now()},
    )
    return {"email": record.get("email"), "password": record.get("password"), "index": record.get("index")}

# This function helps us to get the password stored for this email.
def get_password(email: str):
    rows = _req(
        "GET",
        params={"select": "password", "email": f"eq.{email}", "limit": 1},
    )
    if not rows:
        return None
    return rows[0].get("password")

# This function helps us to save a new password for this email.
def update_password(email: str, new_password: str):
    _req(
        "PATCH",
        params={"email": f"eq.{email}"},
        json={"password": new_password, "last_password_update": _now()},
    )
    return True

# This function helps us to mark this email as free to use.
def release_account(email: str):
    _req(
        "PATCH",
        params={"email": f"eq.{email}"},
        json={"is_in_use": False, "last_account_released": _now()},
    )
    return True

# This function helps us to add a new email row to Supabase.
def add_email_row(email: str, password: str = None, is_in_use: bool = False):
    if not email:
        return False

    try:
        existing = _req(
            "GET",
            params={"select": "id", "email": f"eq.{email}", "limit": 1},
        )
        if existing:
            return False
    except Exception:
        pass

    payload = {
        "email": email,
        "is_in_use": is_in_use,
        "password": password if password is not None else "",
    }

    for _ in range(3):
        try:
            rows = _req(
                "GET",
                params={"select": "index", "order": "index.desc", "limit": 1},
            )
            next_index = 1
            if rows:
                try:
                    next_index = int(rows[0].get("index") or 0) + 1
                except Exception:
                    next_index = 1
            payload["index"] = next_index
            _req("POST", json=payload)
            return True
        except requests.exceptions.HTTPError as exc:
            if getattr(exc, "response", None) is not None and exc.response.status_code == 409:
                try:
                    existing = _req(
                        "GET",
                        params={"select": "id", "email": f"eq.{email}", "limit": 1},
                    )
                    if existing:
                        return False
                except Exception:
                    pass
                continue
            raise
    return False

# This function helps us to list stored accounts (email/id/index by default).
def list_accounts(select: str = "email,id,index", limit: int = None, offset: int = None):
    params = {"select": select, "order": "index.asc"}
    if limit is not None:
        params["limit"] = limit
    if offset is not None:
        params["offset"] = offset
    rows = _req("GET", params=params)
    return rows or []

# This function helps us to delete an account by email.
def delete_account(email: str):
    if not email:
        return False
    _req("DELETE", params={"email": f"eq.{email}"})
    return True

# This function helps us delete multiple accounts by email list.
def delete_accounts(emails):
    if not emails:
        return 0
    removed = 0
    for email in emails:
        try:
            if delete_account(email):
                removed += 1
        except Exception:
            pass
    return removed

# This thing helps us to try the functions quickly from the command line.
if __name__ == "__main__":
    sample_email = "someone@example.com"
    sample_new_password = "new-password-here"

    print("Trying to get an available account:")
    print(get_available_account())

    print(f"Getting password for {sample_email}:")
    print(get_password(sample_email))

    print(f"Updating password for {sample_email}:")
    print(update_password(sample_email, sample_new_password))

    print(f"Releasing account for {sample_email}:")
    print(release_account(sample_email))
