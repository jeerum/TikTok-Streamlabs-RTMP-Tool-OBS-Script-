import obspython as obs
import urllib.request
import urllib.parse
import urllib.error
import json
import re
import glob
import os
import platform
import subprocess
from datetime import datetime

# ---------------- GLOBAL STATE ----------------
script_settings_ref = None

last_stream_id = None
last_rtmp = ""
last_key = ""
last_title = ""
last_category_name = ""
last_category_id = ""

account_info_cache = {}
category_results_cache = []

STATE_FILE = os.path.join(os.path.expanduser("~"), "obs_tiktok_streamlabs_state.json")


# ---------------- LOG ----------------
def log(msg):
    obs.script_log(obs.LOG_INFO, f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def log_warn(msg):
    obs.script_log(obs.LOG_WARNING, f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def log_err(msg):
    obs.script_log(obs.LOG_ERROR, f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


# ---------------- HELPERS ----------------
def clean_text(value):
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    return value.replace("\ufeff", "").replace("\x00", "").strip()

def parse_json(raw):
    try:
        return json.loads(raw)
    except Exception:
        return None

def mask_key(value):
    value = clean_text(value)
    if not value:
        return "(none)"
    if len(value) <= 24:
        return value
    return value[:16] + " ... " + value[-16:]

def set_clipboard(text):
    text = clean_text(text)
    if not text:
        log_warn("Nothing to copy")
        return

    try:
        if platform.system() == "Windows":
            p = subprocess.Popen("clip", stdin=subprocess.PIPE, shell=True)
            p.communicate(text.encode("utf-16"))
            log("Copied to clipboard")
        else:
            log_warn("Clipboard copy is only implemented for Windows")
    except Exception as e:
        log_err(f"Clipboard copy failed: {e}")


# ---------------- SETTINGS ----------------
def get_s(name, default=""):
    global script_settings_ref
    if not script_settings_ref:
        return default
    try:
        return clean_text(obs.obs_data_get_string(script_settings_ref, name))
    except Exception:
        return default

def set_s(name, val):
    global script_settings_ref
    if script_settings_ref:
        try:
            obs.obs_data_set_string(script_settings_ref, name, clean_text(val))
        except Exception:
            pass

def get_b(name, default=False):
    global script_settings_ref
    if not script_settings_ref:
        return default
    try:
        return obs.obs_data_get_bool(script_settings_ref, name)
    except Exception:
        return default


# ---------------- FILE STATE ----------------
def save_state_file():
    data = {
        "saved_at": datetime.now().isoformat(),
        "stream_id": clean_text(last_stream_id),
        "rtmp": clean_text(last_rtmp),
        "key": clean_text(last_key),
        "title": clean_text(last_title),
        "category_name": clean_text(last_category_name),
        "category_id": clean_text(last_category_id),
    }

    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        log(f"State saved to file: {STATE_FILE}")
    except Exception as e:
        log_err(f"Failed to save state file: {e}")

def load_state_file():
    global last_stream_id, last_rtmp, last_key, last_title, last_category_name, last_category_id

    if not os.path.exists(STATE_FILE):
        return

    try:
        with open(STATE_FILE, "r", encoding="utf-8-sig") as f:
            data = json.load(f)

        last_stream_id = clean_text(data.get("stream_id")) or None
        last_rtmp = clean_text(data.get("rtmp"))
        last_key = clean_text(data.get("key"))
        last_title = clean_text(data.get("title"))
        last_category_name = clean_text(data.get("category_name"))
        last_category_id = clean_text(data.get("category_id"))

        if last_stream_id:
            log(f"Restored stream ID from file: {last_stream_id}")
    except Exception as e:
        log_err(f"Failed to load state file: {e}")

def clear_state_file():
    try:
        if os.path.exists(STATE_FILE):
            os.remove(STATE_FILE)
            log("State file removed")
    except Exception as e:
        log_err(f"Failed to remove state file: {e}")


# ---------------- UI ----------------
def update_boxes():
    stream_id_display = clean_text(last_stream_id) or "(none)"
    title_display = clean_text(last_title) or "(none)"
    category_display = clean_text(last_category_name) or "(none)"
    rtmp_display = clean_text(last_rtmp) or "(none)"
    key_display = mask_key(last_key)

    set_s(
        "stream_info",
        f"Stream ID: {stream_id_display}\n"
        f"Title: {title_display}\n"
        f"Category: {category_display}\n"
        f"RTMP: {rtmp_display}\n"
        f"KEY: {key_display}"
    )

    if account_info_cache:
        try:
            set_s("account_info", json.dumps(account_info_cache, indent=2, ensure_ascii=False))
        except Exception:
            set_s("account_info", str(account_info_cache))
    else:
        set_s("account_info", "No account info loaded")

def clear_stream_state():
    global last_stream_id, last_rtmp, last_key, last_title, last_category_name, last_category_id
    last_stream_id = None
    last_rtmp = ""
    last_key = ""
    last_title = ""
    last_category_name = ""
    last_category_id = ""
    update_boxes()
    clear_state_file()


# ---------------- TOKEN ----------------
def get_token():
    patterns = [
        os.path.expandvars(r"%appdata%\slobs-client\Local Storage\leveldb\*.log"),
        os.path.expandvars(r"%appdata%\slobs-client\Local Storage\leveldb\*.ldb"),
    ]

    files = []
    for pattern in patterns:
        files.extend(glob.glob(pattern))

    files = sorted(set(files), key=os.path.getmtime, reverse=True)

    regexes = [
        r'"apiToken":"([^"]+)"',
        r'"apiToken"\s*:\s*"([^"]+)"',
        r'apiToken\\?"\s*:\s*\\?"([^"\\]+)',
        r'"token":"([^"]+)"',
    ]

    for f in files:
        try:
            with open(f, "rb") as fh:
                txt = fh.read().decode("utf-8", errors="ignore")
            txt = clean_text(txt)

            for rgx in regexes:
                matches = re.findall(rgx, txt)
                if matches:
                    token = clean_text(matches[-1])
                    if token:
                        log(f"Token loaded from: {os.path.basename(f)}")
                        return token
        except Exception:
            continue

    return None


# ---------------- HTTP ----------------
def http_post(url, token, payload=None):
    token = clean_text(token)
    if not token:
        log_err("Missing token")
        return None

    try:
        if payload is None:
            data = b""
        else:
            clean_payload = {}
            for k, v in payload.items():
                clean_payload[clean_text(k)] = clean_text(v)
            data = urllib.parse.urlencode(clean_payload).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": "Mozilla/5.0",
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json"
            },
            method="POST"
        )

        with urllib.request.urlopen(req) as r:
            raw = r.read().decode("utf-8", errors="ignore")
            return parse_json(raw)

    except urllib.error.HTTPError as e:
        try:
            raw = e.read().decode("utf-8", errors="ignore")
        except Exception:
            raw = str(e)
        log_err(f"HTTP Error {e.code}: {raw}")
        return None
    except Exception as e:
        log_err(str(e))
        return None

def http_get(url, token):
    token = clean_text(token)
    if not token:
        log_err("Missing token")
        return None

    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json"
        },
        method="GET"
    )

    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read().decode("utf-8", errors="ignore")
            return parse_json(raw)
    except urllib.error.HTTPError as e:
        try:
            raw = e.read().decode("utf-8", errors="ignore")
        except Exception:
            raw = str(e)
        log_err(f"HTTP Error {e.code}: {raw}")
        return None
    except Exception as e:
        log_err(str(e))
        return None


# ---------------- ACCOUNT ----------------
def load_account(props, prop):
    global account_info_cache

    token = get_token()
    if not token:
        log_err("Could not find Streamlabs token")
        return True

    res = http_get("https://streamlabs.com/api/v5/slobs/tiktok/info", token)

    if res:
        account_info_cache = res
        update_boxes()
        log("Account info loaded")
    else:
        log_err("Failed to load account info")

    return True


# ---------------- CATEGORY ----------------
def search_cat(props, prop):
    global category_results_cache

    token = get_token()
    if not token:
        log_err("Could not find Streamlabs token")
        return True

    q = clean_text(get_s("cat_search"))
    if not q:
        log_warn("Search query is empty")
        return True

    res = http_get(
        f"https://streamlabs.com/api/v5/slobs/tiktok/info?category={urllib.parse.quote(q)}",
        token
    )

    if not res:
        log_err("Category search failed")
        return True

    category_results_cache = res.get("categories", [])
    if not isinstance(category_results_cache, list):
        category_results_cache = []

    category_results_cache.append({"full_name": "Other", "game_mask_id": ""})

    p = obs.obs_properties_get(props, "cat_list")
    if p is not None:
        obs.obs_property_list_clear(p)
        for c in category_results_cache:
            obs.obs_property_list_add_string(
                p,
                clean_text(c.get("full_name", "Other")),
                clean_text(c.get("game_mask_id", ""))
            )

    log("Categories updated")
    return True

def select_cat(props, prop):
    global last_category_id, last_category_name

    cid = clean_text(get_s("cat_list"))

    for c in category_results_cache:
        game_mask_id = clean_text(c.get("game_mask_id", ""))
        if game_mask_id == cid:
            last_category_id = game_mask_id
            last_category_name = clean_text(c.get("full_name", "Other"))
            save_state_file()
            update_boxes()
            log(f"Selected: {last_category_name}")
            return True

    log_warn("Selected category not found")
    return True


# ---------------- START ----------------
def start_stream(props, prop):
    global last_stream_id, last_rtmp, last_key, last_title

    token = get_token()
    if not token:
        log_err("Could not find Streamlabs token")
        return True

    last_title = clean_text(get_s("title")) or "TikTok Live"

    payload = {
        "title": last_title,
        "device_platform": "win32",
        "category": clean_text(last_category_id),
        "audience_type": "0"
    }

    res = http_post(
        "https://streamlabs.com/api/v5/slobs/tiktok/stream/start",
        token,
        payload
    )

    if not res:
        log_err("Start stream failed")
        return True

    last_stream_id = clean_text(res.get("id")) or None
    last_rtmp = clean_text(res.get("rtmp"))
    last_key = clean_text(res.get("key"))

    if not last_stream_id:
        log_err("No stream ID returned")
        return True

    save_state_file()
    update_boxes()

    log("STREAM START OK")
    log(f"Stream ID: {last_stream_id}")
    log(f"RTMP: {last_rtmp}")
    log(f"KEY: {last_key}")

    if last_key:
        set_clipboard(last_key)

    return True


# ---------------- STOP ----------------
def stop_stream(props, prop):
    token = get_token()
    if not token:
        log_err("Could not find Streamlabs token")
        return True

    manual_id = clean_text(get_s("manual_id"))
    sid = manual_id or clean_text(last_stream_id)

    log(f"Using stream ID for stop: {repr(sid)}")

    if not sid:
        log_err("No stream ID")
        return True

    res = http_post(
        f"https://streamlabs.com/api/v5/slobs/tiktok/stream/{sid}/end",
        token
    )

    if res and res.get("success"):
        log("STREAM STOP OK")
        clear_stream_state()
    else:
        if isinstance(res, dict):
            log_err(f"Stop failed: {json.dumps(res, ensure_ascii=False)}")
        else:
            log_err("Stop failed")

    return True


# ---------------- OBS ----------------
def script_description():
    return "TikTok Streamlabs Tool (English)"

def script_defaults(settings):
    obs.obs_data_set_default_string(settings, "title", "TikTok Live")
    obs.obs_data_set_default_string(settings, "cat_search", "")
    obs.obs_data_set_default_string(settings, "cat_list", "")
    obs.obs_data_set_default_string(settings, "manual_id", "")
    obs.obs_data_set_default_string(settings, "account_info", "No account info loaded")
    obs.obs_data_set_default_string(settings, "stream_info", "No stream info available")

def script_load(settings):
    global script_settings_ref
    script_settings_ref = settings
    load_state_file()
    update_boxes()

def script_update(settings):
    global script_settings_ref
    script_settings_ref = settings
    update_boxes()

def script_save(settings):
    save_state_file()

def script_properties():
    props = obs.obs_properties_create()

    obs.obs_properties_add_button(props, "acc", "1. Load Account Info", load_account)
    obs.obs_properties_add_text(props, "account_info", "Account", obs.OBS_TEXT_MULTILINE)

    obs.obs_properties_add_text(props, "title", "Stream Title", obs.OBS_TEXT_DEFAULT)

    obs.obs_properties_add_text(props, "cat_search", "Search Game", obs.OBS_TEXT_DEFAULT)
    obs.obs_properties_add_button(props, "search", "2. Search Categories", search_cat)

    p = obs.obs_properties_add_list(
        props,
        "cat_list",
        "Categories",
        obs.OBS_COMBO_TYPE_LIST,
        obs.OBS_COMBO_FORMAT_STRING
    )
    obs.obs_property_list_add_string(p, "(search first)", "")

    obs.obs_properties_add_button(props, "sel", "3. Select Category", select_cat)

    obs.obs_properties_add_button(props, "start", "4. START STREAM", start_stream)
    obs.obs_properties_add_button(props, "stop", "5. STOP STREAM", stop_stream)

    obs.obs_properties_add_text(props, "manual_id", "Manual Stream ID", obs.OBS_TEXT_DEFAULT)

    obs.obs_properties_add_text(props, "stream_info", "Stream Info", obs.OBS_TEXT_MULTILINE)

    return props
