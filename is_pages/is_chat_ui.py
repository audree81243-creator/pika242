import json
import os
import re
import random
import time
from contextlib import suppress
from seleniumbase import SB
from utils import *
from utils import _get_cdp
from access_keys import *
from .is_pop_ups import *

def is_chat_ui_visible(sb):
    # Try current page first
    cdp = _get_cdp(sb)
    popups=is_popups_visible(sb)
    sel = wait_for_textarea(sb, timeout=12)
    if sel!=None:
        print(f"[CHAT-UI] Textarea found ({sel}) without redirect")
        return True

    save_ss(sb, "login_after_password_failed")
    return False
