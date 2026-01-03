from utils import *
from utils import _get_cdp

PROMPT_DISMISS_SELECTORS = [
    'button.btn-secondary:contains("Not now")',
    '//button[contains(text(), "Not now")]',
    '/html/body/div[1]/div/div/div/div[2]/div/div[1]/div[2]/button/div',
    'button[aria-label="Okay, let\'s go"]',
    'div:contains("Okay, let\'s go")',
    '/html/body/div[4]/div/div/div/div/div/div[2]/button/div',  # “Okay, let’s go” / “Skip this step” full XPATH
    'button:contains("Continue")',
    'button:contains("Continue with Free plan")',
    'button:contains("Skip this step")',
    'button:contains("Skip")',
    'button.btn-secondary:contains("Maybe later")',
    'button[type="button"]:contains("Maybe later")',
    'div:contains("Not now")',
    'div:contains("Close")',
    'div:contains("Dismiss")',
    'div:contains("Maybe later")',
    'button:contains("Maybe later")',
    'button:contains("Not now")',
    'a:contains("Stay logged out")',
    'a[href="#"]:contains("Stay logged out")',
    'button:contains("Stay logged out")',
    'div:contains("Stay logged out")',
    'button[type="button"]:contains("Maybe later")',
    '//button[contains(text(), "Maybe later")]',
    'button:contains("Open")',
    'button:contains("Close")',
    'button:contains("Dismiss")',
    'button[aria-label="Close"]',
    'button[aria-label="Dismiss"]',
    'button[aria-label="Not now"]',
]

# 'div[role="dialog"] button',  # Any button in a dialog
#     '[role="dialog"] [aria-label="Close"]',
# 'button.close',
#     'button.dismiss',
#     '.modal-close',
#     '.popup-close',
#     'svg[aria-label="Close"]',  # SVG close icons
#     'button:nth-of-type(1)',  # First button (often close)

def is_popups_visible(sb, timeout=4, screenshot_name="closed_prompt"):
    """Try to detect and close popup prompts/buttons on the page."""
    cdp = _get_cdp(sb)
    sb.sleep(2)
    save_ss(sb,"Checking for a Pop up")
    import time
    import random
    t0 = time.time()
    closed_any = False
    header_text = "What do you want to do with ChatGPT?"
    while time.time() - t0 < timeout:
        handled_pref = False
        try:
            handled_pref = cdp.is_text_visible(header_text)
        except Exception:
            handled_pref = False
        if not handled_pref:
            try:
                handled_pref = visible(sb, f'div:contains("{header_text}")')
            except Exception:
                handled_pref = False
        if handled_pref:
            try:
                option_selectors = [
                    '[role="dialog"] button[role="checkbox"]',
                    '[role="dialog"] button[aria-pressed="false"]',
                    '[role="dialog"] button',
                    'button[role="checkbox"]',
                    'button[aria-pressed="false"]',
                ]
                option_buttons = []
                for sel in option_selectors:
                    try:
                        option_buttons = sb.find_elements(sel)
                    except Exception:
                        option_buttons = []
                    if option_buttons:
                        break
                clicked = 0
                for btn in option_buttons:
                    try:
                        text = (btn.text or "").strip().lower()
                    except Exception:
                        text = ""
                    if not text or "continue" in text:
                        continue
                    try:
                        btn.click()
                        clicked += 1
                        sb.sleep(4.4)
                    except Exception:
                        pass
                    if clicked >= 3:
                        break
                click_first(sb, ['button:contains("Continue")', '//button[contains(., "Continue")]'], label="preferences-continue")
                save_ss(sb, "chatgpt_preferences_closed")
                closed_any = True
                sb.sleep(random.uniform(3, 6))
                continue
            except Exception:
                pass
        for sel in PROMPT_DISMISS_SELECTORS:
            try:
                # visible() and click() are SeleniumBase builtins
                if cdp.is_element_visible(sel):
                    cdp.click(sel)
                    closed_any = True
                    save_ss(sb,"Pop closed")
                    print(f"::warning::[POP UP] Closed popup/button using selector: {sel}")
                    # sb.save_screenshot(screenshot_name)
                    sb.sleep(random.uniform(5, 12))  # Pause after closing to allow follow-up popups
                      
            except Exception:
                continue
        sb.sleep(random.uniform(0.4, 0.8))
        if closed_any==True:
            save_ss(sb,"Closed_any variable is true so a Pop was closed")
    return closed_any
