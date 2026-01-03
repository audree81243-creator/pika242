import json
import os
import re
import time
from contextlib import suppress

from seleniumbase import sb_cdp

from activate_search_mode import activate_search_mode
from is_pages.is_pop_ups import is_popups_visible
from utils import click_first, save_ss, safe_send_keys, safe_type, sleep_dbg, wait_for_textarea


def create_chatgpt_incognito_cdp_session():
    """Create a SeleniumBase CDP session for chatgpt.com and capture an initial screenshot."""
    sb = sb_cdp.Chrome("https://chatgpt.com", headless=False)
    sb.cdp = sb
    sleep_dbg(sb, a=8, b=20, label="cdp session warmup")
    save_ss(sb, "cdp_start")
    return sb


def _accept_cookies(sb):
    cookie_selectors = [
        'button#onetrust-accept-btn-handler',
        'button:contains("Accept all")',
        'button:contains("Accept all cookies")',
        'button:contains("Accept")',
        'button[aria-label*="Accept"][aria-label*="cookie" i]',
    ]
    clicked = click_first(sb, cookie_selectors, label="accept-cookies")
    if not clicked:
        labels = ["accept all", "accept all cookies", "accept"]
        t0 = time.time()
        while time.time() - t0 < 8:
            try:
                buttons = sb.cdp.find_all("button", timeout=2)
                for btn in buttons:
                    text = (btn.text or "").strip().lower()
                    if not text:
                        with suppress(Exception):
                            text = (btn.get_attribute("aria-label") or "").strip().lower()
                    if any(label in text for label in labels):
                        btn.click()
                        clicked = True
                        break
            except Exception:
                pass
            if clicked:
                break
            try:
                clicked = bool(sb.driver.execute_script(
                    "const labels = arguments[0];"
                    "const buttons = Array.from(document.querySelectorAll('button'));"
                    "const target = buttons.find(b => labels.some(l => (b.innerText||'').toLowerCase().includes(l)));"
                    "if (target) { target.click(); return true; } return false;",
                    labels,
                ))
            except Exception:
                clicked = False
            if clicked:
                break
            sb.sleep(0.5)
    if clicked:
        sleep_dbg(sb, a=8, b=20, label="post accept-cookies")
        save_ss(sb, "cookies_accepted")
    return bool(clicked)


def _tab_count(sb):
    try:
        return len(sb.driver.window_handles)
    except Exception:
        return 1


def _scroll_to_bottom(sb, max_scrolls=6):
    last_height = 0
    for _ in range(max_scrolls):
        height = None
        try:
            height = sb.driver.execute_script("return document.body.scrollHeight")
        except Exception:
            height = None
        if height is None:
            with suppress(Exception):
                sb.cdp.scroll_down(1200)
            sb.sleep(1.5)
            continue
        if height == last_height:
            break
        last_height = height
        with suppress(Exception):
            sb.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        sb.sleep(1.5)
    with suppress(Exception):
        sb.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    with suppress(Exception):
        sb.cdp.scroll_down(2000)


def _open_chatgpt_tab(sb, timeout=40):
    opened = False
    try:
        sb.driver.execute_script("window.open('about:blank','_blank');")
        opened = True
    except Exception:
        if hasattr(sb, "open_new_tab"):
            with suppress(Exception):
                sb.open_new_tab("about:blank")
                opened = True
    if not opened:
        return False
    with suppress(Exception):
        sb.switch_to_window(sb.driver.window_handles[-1])
    try:
        sb.cdp.open("https://chatgpt.com")
    except Exception:
        with suppress(Exception):
            sb.driver.get("https://chatgpt.com")
    _accept_cookies(sb)
    save_ss(sb, "chatgpt_tab_opened")
    ready = bool(wait_for_textarea(sb, timeout=timeout))
    if ready:
        is_popups_visible(sb)
        save_ss(sb, "chatgpt_tab_ready")
    return ready


def _create_ready_session(max_session_attempts=3, timeout=40):
    for attempt in range(1, max_session_attempts + 1):
        sb = create_chatgpt_incognito_cdp_session()
        _accept_cookies(sb)
        if wait_for_textarea(sb, timeout=timeout):
            is_popups_visible(sb)
            save_ss(sb, f"chatgpt_ready_{attempt}")
            return sb
        save_ss(sb, f"chatgpt_open_failed_{attempt}")
        with suppress(Exception):
            sb.driver.stop()
    return None


def _submit_prompt_once(sb, prompt, response_timeout=90):
    prompt_text = str(prompt or "").strip()
    if not prompt_text:
        print("[SCRAPE][ERROR] Empty prompt")
        return {
            "prompt": prompt,
            "response": "",
            "appeared_links": [],
            "screenshot": save_ss(sb, "empty_prompt"),
        }
    prompt_text = f" {prompt_text}"

    textarea = wait_for_textarea(sb, timeout=40)
    if not textarea:
        print("[SCRAPE][ERROR] Prompt textarea not found")
        return {
            "prompt": prompt,
            "response": "",
            "appeared_links": [],
            "screenshot": save_ss(sb, "prompt_textarea_missing"),
        }

    _accept_cookies(sb)
    is_popups_visible(sb)
    save_ss(sb, "before_prompt_clear")
    with suppress(Exception):
        sb.cdp.select_all("#prompt-textarea")
        sb.cdp.press_keys("#prompt-textarea", "\b")

    activate_search_mode(sb)
    save_ss(sb, "after_search_mode")
    sb.sleep(10)
    if not safe_type(sb, "#prompt-textarea", prompt_text, label="prompt_type"):
        return {
            "prompt": prompt,
            "response": "",
            "appeared_links": [],
            "screenshot": save_ss(sb, "prompt_type_failed"),
        }
    if not safe_send_keys(sb, "#prompt-textarea", "\n", label="prompt_send"):
        return {
            "prompt": prompt,
            "response": "",
            "appeared_links": [],
            "screenshot": save_ss(sb, "prompt_send_failed"),
        }
    save_ss(sb, "prompt_sent")
    is_popups_visible(sb)

    with suppress(Exception):
        sb.cdp.wait_for_element_not_visible('button[data-testid="stop-button"]', timeout=response_timeout)
    sleep_dbg(sb, a=8, b=20, label="extra wait after streaming")
    save_ss(sb, "after_streaming_wait")
    _scroll_to_bottom(sb)
    save_ss(sb, "after_scroll_bottom")

    response_selectors = [
        '[data-message-author-role="assistant"] .markdown',
        '[data-message-author-role="assistant"] article',
        'div[data-message-author-role="assistant"]',
        '[class*="message"] [class*="markdown"]',
        '[role="article"] .markdown',
    ]
    elems = []
    for sel in response_selectors:
        try:
            elems = sb.cdp.find_all(sel, timeout=60)
            if elems:
                break
        except Exception:
            pass

    if not elems:
        return {
            "prompt": prompt,
            "response": "",
            "appeared_links": [],
            "screenshot": save_ss(sb, "no_response"),
        }

    save_ss(sb, "response_candidates_found")
    latest_elem = elems[-1]
    response_text = (latest_elem.text or "").strip().replace("\n\n\n", "\n\n")
    hrefs = []
    with suppress(Exception):
        links = latest_elem.query_selector_all("a")
        hrefs = [link.get_attribute("href") for link in links if link.get_attribute("href")]

    if not hrefs:
        fallback_urls = re.findall(r"https?://[^\s)\"'<>]+", response_text)
        for url in fallback_urls:
            cleaned = url.rstrip(").,;]}")
            if cleaned and cleaned not in hrefs:
                hrefs.append(cleaned)

    screenshot_path = save_ss(sb, "response_extracted")
    return {
        "prompt": prompt,
        "response": response_text,
        "appeared_links": hrefs,
        "screenshot": screenshot_path,
    }


def submit_prompt_with_search(sb, prompt, response_timeout=90, max_attempts=5):
    current_sb = sb
    last_result = None
    new_chat_selector = "/html/body/div[1]/div/div/div[1]/div/div[2]/nav/aside/a[1]/div[1]/div[2]/div"
    attempt = 1
    while attempt <= max_attempts:
        with suppress(Exception):
            current_sb.cdp.scroll_into_view(new_chat_selector)
            current_sb.cdp.click(new_chat_selector)
            current_sb.sleep(6)

        last_result = _submit_prompt_once(current_sb, prompt, response_timeout=response_timeout)
        if last_result.get("appeared_links"):
            print(f"[SCRAPE] Success on attempt {attempt}")
            return last_result, current_sb

        print(f"[SCRAPE][WARN] No citations on attempt {attempt}")
        if attempt < max_attempts:
            print("[SCRAPE][WARN] Creating a new session for retry.")
            with suppress(Exception):
                current_sb.driver.stop()
            current_sb = create_chatgpt_incognito_cdp_session()
        attempt += 1
    return last_result, current_sb


def run_prompts_with_tabs(prompts, max_attempts=5, response_timeout=90, max_session_attempts=3):
    prompt_list = list(prompts or [])
    results = []
    attempt_emojis = ["🟢", "🔵", "🟣", "🟡", "🟠"]
    failure_emoji = "🔴"

    sb = _create_ready_session(max_session_attempts=max_session_attempts)
    if not sb:
        print("[SCRAPE][ERROR] Failed to open chatgpt.com in a new session")
        return results, None

    for idx, prompt in enumerate(prompt_list):
        prompt_text = str(prompt or "").strip()
        if not prompt_text:
            results.append({
                "prompt": prompt,
                "response": "Error: Empty prompt",
                "appeared_links": [],
                "screenshot": save_ss(sb, "empty_prompt"),
                "tab_count": _tab_count(sb),
            })
            continue

        attempt = 1
        last_result = None
        got_links = False
        while attempt <= max_attempts:
            if idx > 0 or attempt > 1:
                if not _open_chatgpt_tab(sb, timeout=40):
                    save_ss(sb, f"chatgpt_tab_open_failed_{idx + 1}_{attempt}")
                    with suppress(Exception):
                        sb.driver.stop()
                    sb = _create_ready_session(max_session_attempts=max_session_attempts)
                    if not sb:
                        last_result = {
                            "prompt": prompt,
                            "response": "Error: Could not open chatgpt.com",
                            "appeared_links": [],
                            "screenshot": None,
                            "tab_count": 0,
                        }
                        break
            elif not wait_for_textarea(sb, timeout=40):
                with suppress(Exception):
                    sb.driver.stop()
                sb = _create_ready_session(max_session_attempts=max_session_attempts)
                if not sb:
                    last_result = {
                        "prompt": prompt,
                        "response": "Error: Could not open chatgpt.com",
                        "appeared_links": [],
                        "screenshot": None,
                        "tab_count": 0,
                    }
                    break

            tab_count = _tab_count(sb)
            print(f"[TABS] {tab_count} tabs open")

            last_result = _submit_prompt_once(sb, prompt_text, response_timeout=response_timeout)
            last_result["tab_count"] = tab_count
            if last_result.get("appeared_links"):
                emoji = attempt_emojis[min(attempt - 1, len(attempt_emojis) - 1)]
                print(f"{emoji} Success on attempt {attempt} for prompt {idx + 1}")
                got_links = True
                break
            emoji = attempt_emojis[min(attempt - 1, len(attempt_emojis) - 1)]
            print(f"{emoji} No citations on attempt {attempt} for prompt {idx + 1}")
            attempt += 1

        if last_result and not got_links:
            print(f"{failure_emoji} No citations after {max_attempts} attempts for prompt {idx + 1}")

        if last_result:
            results.append(last_result)
        else:
            results.append({
                "prompt": prompt,
                "response": "Error: No result",
                "appeared_links": [],
                "screenshot": save_ss(sb, "no_result"),
                "tab_count": _tab_count(sb),
            })

    return results, sb


if __name__ == "__main__":
    prompt_path = "prompts.json"
    prompts = []
    if os.path.exists(prompt_path):
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_data = json.load(f)
        if isinstance(prompt_data, dict):
            try:
                prompt_keys = sorted(prompt_data.keys(), key=lambda k: int(k))
            except Exception:
                prompt_keys = sorted(prompt_data.keys())
            prompts = [prompt_data[k] for k in prompt_keys]
        elif isinstance(prompt_data, list):
            prompts = prompt_data
    results, sb = run_prompts_with_tabs(prompts)
    with open("sample_result.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    if sb:
        with suppress(Exception):
            sb.driver.stop()
