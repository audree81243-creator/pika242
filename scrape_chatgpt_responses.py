import json
import os
import re
import time
import shutil
import psycopg
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from contextlib import suppress

from access_keys import get_available_account, get_password, release_account
from activate_search_mode import activate_search_mode
from create_boomGpt import create_boomgpt, DEFAULT_BOOMLIFY_EMAIL, DEFAULT_BOOMLIFY_PASSWORD
from create_chatgpt_account import create_chatgpt_account
from handle_login import handle_login
from is_pages.is_chat_ui import is_chat_ui_visible
from is_pages.is_pop_ups import is_popups_visible
from utils import *
from db import get_connection


def scrape_chatgpt_responses(prompts=None, boomlify_login_email=None, boomlify_login_password=None):
    active_email = ""
    account = get_available_account()
    # Use an eligible stored account when available.
    if account:
        email = (account.get("email") or "").strip()
        active_email = email
        password = (account.get("password") or "").strip()
        # Create ChatGPT account if the stored password is missing.
        if not password:
            print(f"[SCRAPE] Empty password for {email}. Creating ChatGPT account...")
            create_chatgpt_account(email)
            password = (get_password(email) or "").strip()
        print(f"[SCRAPE] Using account: {email or 'unknown'}")
        ok, sb = handle_login(email, password)
        if not ok:
            print("[SCRAPE][ERROR] Login failed; stopping.")
            return
        if not is_chat_ui_visible(sb):
            is_popups_visible(sb)
        activate_search_mode(sb)


    else:
        print("[SCRAPE] No available account found. Creating a new one...")
        login_email = (boomlify_login_email or os.getenv("BOOMLIFY_LOGIN_EMAIL", "").strip() or DEFAULT_BOOMLIFY_EMAIL).strip()
        login_password = (boomlify_login_password or os.getenv("BOOMLIFY_LOGIN_PASSWORD", "").strip() or DEFAULT_BOOMLIFY_PASSWORD).strip()
        ok, new_email = create_boomgpt(login_email, login_password)
        active_email = (new_email or "").strip()
        new_password = (get_password(new_email) or "").strip()
        if not new_password:
            print(f"[SCRAPE] Empty password for {new_email}. Creating ChatGPT account...")
            create_chatgpt_account(new_email)
            new_password = (get_password(new_email) or "").strip()
        print(f"[SCRAPE] Using account: {new_email or 'unknown'}")
        ok, sb = handle_login(new_email, new_password)
        if not ok:
            print("[SCRAPE][ERROR] Login failed; stopping.")
            return
        if not is_chat_ui_visible(sb):
            is_popups_visible(sb)
        activate_search_mode(sb)

    use_db = bool(os.getenv("DATABASE_URL"))
    if not use_db:
        print("[SCRAPE][ERROR] DATABASE_URL not set; DB-only mode requires it.")
        return
    print("[SCRAPE][DB] Using database for prompts.")
    results = []
    prompt_template = (
        "Consider I am staying in UAE. Act as an expert providing a technical summary for a professional audience. "
        "List only the most reputable sources related to the topic. "
        "Cite only authoritative sources such as official project websites, well-known news outlets, "
        "and trusted industry platforms. "
        "Present the maximum amount of citations you can find: {actual_prompt}"
    )
    attempt_emojis = ["🟢", "🔵", "🟣", "🟡", "🟠"]
    failure_emoji = "🔴"
    response_selectors = [
        '[data-message-author-role="assistant"] .markdown',
        '[data-message-author-role="assistant"] article',
        'div[data-message-author-role="assistant"]',
        '[class*="message"] [class*="markdown"]',
        '[role="article"] .markdown',
    ]
    new_chat_selector = '/html/body/div[1]/div/div/div[1]/div/div[2]/nav/aside/a[1]/div[1]/div[2]/div'
    temporary_chat_selector = '/html/body/div[1]/div[1]/div/div[2]/div/header/div[3]/div[2]/div/div/span/button'

    tracking_params = {"utm_source", "utm_medium", "utm_campaign", "utm_content", "ref"}

    def _clean_link(url):
        try:
            url = str(url or "").strip()
        except Exception:
            return ""
        if not url:
            return ""
        try:
            parts = urlsplit(url)
        except Exception:
            return url
        if not parts.query:
            return url
        filtered = [
            (k, v)
            for k, v in parse_qsl(parts.query, keep_blank_values=True)
            if k.lower() not in tracking_params
        ]
        query = urlencode(filtered, doseq=True)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))

    def _normalize_urls(value):
        if value is None:
            return []
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except Exception:
                value = [value]
        if isinstance(value, dict):
            value = [value]
        if not isinstance(value, list):
            return []
        cleaned = []
        for item in value:
            if isinstance(item, dict) and "url" in item:
                item = item.get("url")
            cleaned_item = _clean_link(item)
            if cleaned_item:
                cleaned.append(cleaned_item)
        return cleaned

    def _get_domain(url):
        try:
            host = urlsplit(url).hostname or ""
        except Exception:
            return ""
        host = host.lower()
        if host.startswith("www."):
            host = host[4:]
        return host

    def _domain_matches(domain, target):
        if not domain or not target:
            return False
        return domain == target or domain.endswith("." + target)

    def _brand_from_domain(domain):
        if not domain:
            return ""
        return domain.split(".")[0]

    def _db_with_retry(action_label, fn, retries=3, sleep_seconds=5):
        for attempt in range(1, retries + 1):
            try:
                with get_connection() as conn:
                    return fn(conn)
            except psycopg.OperationalError as exc:
                if attempt >= retries:
                    raise
                print(
                    f"[SCRAPE][DB][WARN] {action_label} failed "
                    f"(attempt {attempt}/{retries}); retrying..."
                )
                time.sleep(sleep_seconds)

    def _fetch_prompt_row():
        def _run(conn):
            query = """
                SELECT id, prompt_text, website, competitor_websites, status
                FROM prompts
                WHERE day = CURRENT_DATE
                  AND (
                    status IN ('pending', 'queued')
                    OR (status = 'processing' AND started_at < (NOW() - INTERVAL '30 minutes'))
                  )
                ORDER BY created_at ASC
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            """
            with conn.cursor() as cur:
                cur.execute("BEGIN")
                cur.execute(query)
                row = cur.fetchone()
                if not row:
                    conn.commit()
                    return None
                prompt_id, prompt_text, website, competitor_websites, status = row
                if status == "completed":
                    conn.commit()
                    return None
                engine_account_value = active_email if active_email else None
                cur.execute(
                    """
                    UPDATE prompts
                    SET status = 'processing',
                        started_at = NOW(),
                        attempts = attempts + 1,
                        engine_account = COALESCE(%s, engine_account)
                    WHERE id = %s
                    """,
                    (engine_account_value, prompt_id),
                )
                conn.commit()
                return {
                    "id": prompt_id,
                    "prompt_text": prompt_text,
                    "website": website,
                    "competitor_websites": competitor_websites,
                }

        return _db_with_retry("fetch prompt", _run)

    def _update_prompt_row(prompt_id, payload):
        def _run(conn):
            columns = ", ".join(f"{key} = %s" for key in payload.keys())
            values = list(payload.values()) + [prompt_id]
            query = f"UPDATE prompts SET {columns} WHERE id = %s AND status <> 'completed'"
            with conn.cursor() as cur:
                cur.execute(query, values)
                conn.commit()

        return _db_with_retry(f"update prompt {prompt_id}", _run)

    def _format_bytes(value):
        size = float(value)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size < 1024.0:
                return f"{size:.1f}{unit}"
            size /= 1024.0
        return f"{size:.1f}PB"

    def _dir_size(path):
        if not path or not os.path.exists(path):
            return None
        total = 0
        for root, _, files in os.walk(path):
            for name in files:
                full_path = os.path.join(root, name)
                try:
                    total += os.path.getsize(full_path)
                except Exception:
                    continue
        return total

    def _read_meminfo():
        path = "/proc/meminfo"
        if not os.path.exists(path):
            return None
        data = {}
        try:
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    parts = line.split(":")
                    if len(parts) < 2:
                        continue
                    key = parts[0].strip()
                    value_part = parts[1].strip().split()
                    if not value_part:
                        continue
                    try:
                        data[key] = int(value_part[0]) * 1024
                    except Exception:
                        continue
        except Exception:
            return None
        return data

    def _print_disk_usage(label):
        cpu_count = os.cpu_count()
        if hasattr(os, "getloadavg"):
            try:
                load1, load5, load15 = os.getloadavg()
                print(
                    f"[CPU] {label} cores={cpu_count} "
                    f"load={load1:.2f},{load5:.2f},{load15:.2f}"
                )
            except Exception as exc:
                print(f"[CPU][WARN] Unable to read load average: {exc}")
        elif cpu_count:
            print(f"[CPU] {label} cores={cpu_count}")

        meminfo = _read_meminfo()
        if meminfo:
            total = meminfo.get("MemTotal")
            available = meminfo.get("MemAvailable")
            if total and available is not None:
                used = max(total - available, 0)
                print(
                    f"[RAM] {label} total={_format_bytes(total)} "
                    f"used={_format_bytes(used)} available={_format_bytes(available)}"
                )

        try:
            usage = shutil.disk_usage("/")
            print(
                f"[DISK] {label} total={_format_bytes(usage.total)} "
                f"used={_format_bytes(usage.used)} free={_format_bytes(usage.free)}"
            )
        except Exception as exc:
            print(f"[DISK][WARN] Unable to read disk usage: {exc}")
        paths = {
            "screenshots": "screenshots",
            "latest_logs": "latest_logs",
            "pip_cache": os.path.expanduser("~/.cache/pip"),
            "seleniumbase_cache": os.path.expanduser("~/.cache/seleniumbase"),
        }
        for name, path in paths.items():
            size = _dir_size(path)
            if size is None:
                continue
            print(f"[DISK] {name}={_format_bytes(size)} ({path})")

    def _cleanup_caches():
        targets = [
            os.path.expanduser("~/.cache/pip"),
            os.path.expanduser("~/.cache/seleniumbase"),
            os.path.expanduser("~/.cache/selenium"),
        ]
        for path in targets:
            if os.path.exists(path):
                shutil.rmtree(path, ignore_errors=True)
                print(f"[DISK] Removed cache: {path}")

    def _extract_sources_panel_links(sb):
        script = """
        const getSectionLinks = (label) => {
          const li = [...document.querySelectorAll("li")]
            .find(el => (el.innerText || "").trim().toLowerCase() === label.toLowerCase());
          if (!li) return [];
          const ul = li.parentElement?.querySelector("ul");
          if (!ul) return [];
          return [...ul.querySelectorAll("a[href]")].map(a => a.href);
        };

        const citations = getSectionLinks("Citations");
        const more = getSectionLinks("More");

        const combined = Array.from(new Set([...citations, ...more]));
        return combined;
        """
        try:
            raw = sb.execute_script(script) or []
        except Exception:
            return []
        cleaned = []
        for href in raw:
            cleaned_href = _clean_link(href)
            if cleaned_href and cleaned_href not in cleaned:
                cleaned.append(cleaned_href)
        return cleaned

    def _scroll_sources_list(sb, label, max_rounds=6):
        last_height = None
        stable = 0
        for _ in range(max_rounds):
            try:
                info = sb.execute_script(
                    """
                    const label = String(arguments[0] || '').trim().toLowerCase();
                    const li = [...document.querySelectorAll("li")]
                      .find(el => (el.innerText || "").trim().toLowerCase() === label);
                    if (!li) return { ok: false };
                    const container = li.parentElement?.querySelector("ul") || li.parentElement || document.scrollingElement;
                    if (!container) return { ok: false };
                    container.scrollTop = container.scrollHeight;
                    return { ok: true, height: container.scrollHeight };
                    """,
                    label,
                )
            except Exception:
                return False
            if not info or not info.get("ok"):
                return False
            height = info.get("height")
            if last_height is not None and height == last_height:
                stable += 1
            else:
                stable = 0
            last_height = height
            sleep_dbg(sb, a=2, b=4, label=f"sources_scroll_{label}")
            if stable >= 1:
                break
        return True

    def _collect_sources_links(sb, idx, attempt, run_idx):
        sources_hrefs = []
        sources_button_selectors = [
            'button:contains("Sources")',
            'button:contains("Citations")',
            'button:contains("References")',
            '[role="button"]:contains("Sources")',
            '[role="button"]:contains("Citations")',
            'a:contains("Sources")',
            'a:contains("Citations")',
            '[aria-label*="Sources" i]',
            '[aria-label*="Citations" i]',
            '[aria-label*="References" i]',
        ]
        try:
            tabs_present = sb.execute_script(
                """
                return Array.from(document.querySelectorAll('li,button,[role="tab"]'))
                  .some(el => {
                    const text = (el.innerText || '').trim().toLowerCase();
                    return text === 'citations' || text === 'more';
                  });
                """
            )
        except Exception:
            tabs_present = False
        if not tabs_present:
            clicked_sources = click_first(sb, sources_button_selectors, label="sources-panel")
            if not clicked_sources:
                try:
                    clicked_sources = sb.execute_script(
                        """
                        const labels = (arguments[0] || []).map(s => String(s).toLowerCase());
                        const els = Array.from(document.querySelectorAll('button,[role="button"],a'));
                        const match = els.find(el => labels.includes((el.innerText || '').trim().toLowerCase()));
                        if (match) { match.click(); return true; }
                        return false;
                        """,
                        ["Sources", "Citations", "References"],
                    )
                except Exception:
                    clicked_sources = False
            if clicked_sources:
                sleep_dbg(sb, a=3, b=6, label="after_sources_open")
                save_ss(sb, f"sources_open_prompt_{idx + 1}_attempt_{attempt}_run_{run_idx}")

        for label in ("Citations", "More"):
            tab_selectors = [
                f'li:contains("{label}")',
                f'button:contains("{label}")',
                f'[role="tab"]:contains("{label}")',
            ]
            clicked_tab = click_first(sb, tab_selectors, label=f"sources-tab-{label.lower()}")
            if not clicked_tab:
                try:
                    clicked_tab = sb.execute_script(
                        """
                        const label = String(arguments[0] || '').trim().toLowerCase();
                        const els = Array.from(document.querySelectorAll('li,button,[role="tab"]'));
                        const match = els.find(el => (el.innerText || '').trim().toLowerCase() === label);
                        if (match) { match.click(); return true; }
                        return false;
                        """,
                        label,
                    )
                except Exception:
                    clicked_tab = False
            if clicked_tab:
                sleep_dbg(sb, a=2, b=4, label=f"after_tab_{label.lower()}")
            scrolled = _scroll_sources_list(sb, label)
            if scrolled:
                sleep_dbg(sb, a=2, b=4, label=f"after_scroll_{label.lower()}")
                save_ss(sb, f"sources_{label.lower()}_prompt_{idx + 1}_attempt_{attempt}_run_{run_idx}")

            panel_links = _extract_sources_panel_links(sb)
            for href in panel_links:
                if href and href not in sources_hrefs:
                    sources_hrefs.append(href)
        return sources_hrefs

    def _run_prompt(prompt_text, idx, run_idx):
        attempt = 1
        last_text = ""
        last_hrefs = []
        last_screenshot = None
        while attempt <= 5:
            with suppress(Exception):
                sb.cdp.scroll_into_view(new_chat_selector)
                sb.cdp.click(new_chat_selector)
                sleep_dbg(sb, a=7, b=12, label="after_new_chat")
                sb.cdp.scroll_into_view(temporary_chat_selector)
                sb.cdp.click(temporary_chat_selector)

            textarea_sel = wait_for_textarea(sb, timeout=40)
            if not textarea_sel:
                save_ss(sb, f"textarea_missing_prompt_{idx + 1}_attempt_{attempt}")
                attempt += 1
                continue

            activate_search_mode(sb)
            with suppress(Exception):
                sb.cdp.select_all("#prompt-textarea")
                sb.cdp.press_keys("#prompt-textarea", "\b")
            with suppress(Exception):
                sb.cdp.click("#prompt-textarea")
            safe_type(sb, "#prompt-textarea", prompt_text, label="prompt_type")
            safe_send_keys(sb, "#prompt-textarea", "\n", label="prompt_send")
            with suppress(Exception):
                sb.cdp.wait_for_element_not_visible('button[data-testid="stop-button"]', timeout=90)
            sleep_dbg(sb, a=12, b=20, label="extra wait after streaming")

            elems = []
            for resp_sel in response_selectors:
                try:
                    elems = sb.cdp.find_all(resp_sel, timeout=60)
                    if elems:
                        break
                except Exception:
                    pass
            if not elems:
                last_screenshot = save_ss(sb, f"no_response_{idx + 1}_attempt_{attempt}")
                attempt += 1
                continue

            hrefs = []
            try:
                latest_elem = elems[-1]
                last_text = (latest_elem.text or "").strip().replace("\n\n\n", "\n\n")
                links = latest_elem.query_selector_all("a")
                hrefs = []
                for link in links:
                    cleaned_href = _clean_link(link.get_attribute("href"))
                    if cleaned_href:
                        hrefs.append(cleaned_href)
                if not hrefs:
                    fallback_urls = re.findall(r"https?://[^\s)\"'<>]+", last_text)
                    for url in fallback_urls:
                        cleaned = _clean_link(url.rstrip(").,;]}"))
                        if cleaned and cleaned not in hrefs:
                            hrefs.append(cleaned)
                last_screenshot = save_ss(sb, f"prompt_{idx + 1}_attempt_{attempt}")
                sources_hrefs = _collect_sources_links(sb, idx, attempt, run_idx)
                for src in sources_hrefs:
                    if src and src not in hrefs:
                        hrefs.append(src)
                last_hrefs = hrefs
            except Exception:
                last_screenshot = save_ss(sb, f"extract_failed_{idx + 1}_attempt_{attempt}")
                attempt += 1
                continue

            if hrefs:
                emoji = attempt_emojis[attempt - 1]
                print(f"{emoji} Success on attempt {attempt} for prompt {idx + 1} (run {run_idx})")
                return {
                    "text": last_text,
                    "hrefs": last_hrefs,
                    "screenshot": last_screenshot,
                }

            emoji = attempt_emojis[attempt - 1]
            print(f"{emoji} No links on attempt {attempt} for prompt {idx + 1} (run {run_idx})")
            attempt += 1

        print(f"{failure_emoji} No links after 5 attempts for prompt {idx + 1} (run {run_idx})")
        return {
            "text": last_text or "Error: No links after retries",
            "hrefs": [],
            "screenshot": last_screenshot,
        }

    max_prompts = 75
    no_prompt_retries = 10
    retry_count = 0
    idx = 0
    processed_count = 0
    cleanup_every = 5
    def _iter_prompt_items():
        nonlocal idx, retry_count
        while idx < max_prompts:
            row = _fetch_prompt_row()
            if not row:
                retry_count += 1
                if retry_count > no_prompt_retries:
                    return
                time.sleep(5)
                continue
            retry_count = 0
            print(f"[SCRAPE][DB] Picked prompt id: {row['id']}")
            yield {"prompt_raw": row["prompt_text"], "row": row}
            idx += 1

    for item in _iter_prompt_items():
        prompt_raw = item["prompt_raw"]
        row = item["row"]
        prompt = str(prompt_raw or "").strip()
        if not prompt:
            results.append({
                "prompt": prompt_raw,
                "response": "Error: Empty prompt after cleaning",
                "screenshot": None,
                "captcha_type": None,
                "appeared_links": [],
                "appeared_links_unique": [],
                "appeared_links_run1": [],
                "appeared_links_run2": [],
                "batch_id": 1,
                "query_index": idx,
                "prompt_id": f"query_{idx + 1:04d}",
            })
            if row:
                fail_payload = {
                    "status": "failed",
                    "error_text": "Error: Empty prompt after cleaning",
                    "finished_at": datetime.now(timezone.utc),
                }
                if active_email:
                    fail_payload["engine_account"] = active_email
                print(f"[SCRAPE][DB] Updating prompt id: {row['id']} (failed)")
                _update_prompt_row(row["id"], fail_payload)
        if not use_db:
            idx += 1
            continue
        prompt_text = prompt_template.format(actual_prompt=prompt)
        first_run = _run_prompt(prompt_text, idx, 1)
        second_run = _run_prompt(prompt_text, idx, 2)

        combined_links_raw = []
        for href in first_run["hrefs"] + second_run["hrefs"]:
            cleaned = _clean_link(href)
            if cleaned:
                combined_links_raw.append(cleaned)
        combined_links_unique = []
        for href in combined_links_raw:
            if href not in combined_links_unique:
                combined_links_unique.append(href)
        print(
            f"[LINKS] prompt {idx + 1}: "
            f"run1={len(first_run['hrefs'])} "
            f"run2={len(second_run['hrefs'])} "
            f"combined_raw={len(combined_links_raw)} "
            f"combined_unique={len(combined_links_unique)}"
        )

        results.append({
            "prompt": prompt_raw,
            "appeared_links": combined_links_raw,
            "appeared_links_unique": combined_links_unique,
            "appeared_links_run1": first_run["hrefs"],
            "appeared_links_run2": second_run["hrefs"],
            "response": first_run["text"],
            "screenshot": first_run["screenshot"],
            "captcha_type": None,
            "batch_id": 1,
            "query_index": idx,
            "prompt_id": f"query_{idx + 1:04d}",
        })
        if row:
            website_urls = _normalize_urls(row.get("website"))
            competitor_urls = _normalize_urls(row.get("competitor_websites"))
            website_domain = _get_domain(website_urls[0]) if website_urls else ""
            competitor_domains = {_get_domain(url) for url in competitor_urls if _get_domain(url)}
            my_citations = []
            competitor_citations = []
            for url in combined_links_unique:
                domain = _get_domain(url)
                if website_domain and _domain_matches(domain, website_domain):
                    my_citations.append(url)
                elif any(_domain_matches(domain, comp) for comp in competitor_domains):
                    competitor_citations.append(url)
            brand = _brand_from_domain(website_domain)
            response_text = first_run["text"] or ""
            my_brand_mentions_count = 0
            if brand:
                my_brand_mentions_count = len(re.findall(rf"\b{re.escape(brand)}\b", response_text, re.I))
            payload = {
                "status": "completed",
                "response_text": first_run["text"],
                "appeared_links": json.dumps(combined_links_raw),
                "appeared_links_unique": json.dumps(combined_links_unique),
                "appeared_links_run1": json.dumps(first_run["hrefs"]),
                "appeared_links_run2": json.dumps(second_run["hrefs"]),
                "my_citations": json.dumps(my_citations),
                "competitor_citations": json.dumps(competitor_citations),
                "total_citations_count": len(combined_links_unique),
                "my_domain_citations_count": len(my_citations),
                "my_brand_mentions_count": my_brand_mentions_count,
                "finished_at": datetime.now(timezone.utc),
                "error_text": None,
            }
            if active_email:
                payload["engine_account"] = active_email
            print(f"[SCRAPE][DB] Updating prompt id: {row['id']} (completed)")
            _update_prompt_row(row["id"], payload)
        if not use_db:
            idx += 1

        processed_count += 1
        if cleanup_every and processed_count % cleanup_every == 0:
            _print_disk_usage(f"after {processed_count} prompts (before cleanup)")
            _cleanup_caches()
            _print_disk_usage(f"after {processed_count} prompts (after cleanup)")

    with open("sample_result.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    if active_email:
        release_account(active_email)


if __name__ == "__main__":
    scrape_chatgpt_responses()

