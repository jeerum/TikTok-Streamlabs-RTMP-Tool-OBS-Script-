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
def parse_json(raw):
    try:
        return json.loads(raw)
    except:
        return None

def mask_key(value):
    if not value:
        return "(none)"
    if len(value) <= 24:
        return value
    return value[:16] + " ... " + value[-16:]

def set_clipboard(text):
    try:
        if platform.system() == "Windows":
            p = subprocess.Popen("clip", stdin=subprocess.PIPE, shell=True)
            p.communicate(text.encode("utf-16"))
            log("Copied to clipboard")
    except:
        pass


# ---------------- SETTINGS ----------------
def get_s(name, default=""):
    return obs.obs_data_get_string(script_settings_ref, name) if script_settings_ref else default

def set_s(name, val):
    if script_settings_ref:
        obs.obs_data_set_string(script_settings_ref, name, val or "")

def get_b(name, default=False):
    return obs.obs_data_get_bool(script_settings_ref, name) if script_settings_ref else default


# ---------------- FILE STATE ----------------
def save_state_file():
    data = {
        "saved_at": datetime.now().isoformat(),
        "stream_id": last_stream_id,
        "rtmp": last_rtmp,
        "key": last_key,
        "title": last_title,
        "category_name": last_category_name,
        "category_id": last_category_id,
    }

    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        log("State saved to file")
    except Exception as e:
        log_err(str(e))


def load_state_file():
    global last_stream_id, last_rtmp, last_key, last_title, last_category_name, last_category_id

    if not os.path.exists(STATE_FILE):
        return

    try:
        data = json.load(open(STATE_FILE, "r", encoding="utf-8"))

        last_stream_id = data.get("stream_id")
        last_rtmp = data.get("rtmp", "")
        last_key = data.get("key", "")
        last_title = data.get("title", "")
        last_category_name = data.get("category_name", "")
        last_category_id = data.get("category_id", "")

        if last_stream_id:
            log(f"Restored stream ID: {last_stream_id}")
    except Exception as e:
        log_err(str(e))


# ---------------- UI ----------------
def update_boxes():
    set_s("stream_info",
        f"Stream ID: {last_stream_id}\n"
        f"Title: {last_title}\n"
        f"Category: {last_category_name}\n"
        f"RTMP: {last_rtmp}\n"
        f"KEY: {mask_key(last_key)}"
    )

    if account_info_cache:
        set_s("account_info", json.dumps(account_info_cache, indent=2))


# ---------------- TOKEN ----------------
def get_token():
    files = glob.glob(os.path.expandvars(r"%appdata%\slobs-client\Local Storage\leveldb\*.log"))
    files = sorted(files, key=os.path.getmtime, reverse=True)

    for f in files:
        try:
            txt = open(f, "rb").read().decode("utf-8", errors="ignore")
            m = re.findall(r'"apiToken":"([^"]+)"', txt)
            if m:
                return m[-1]
        except:
            pass
    return None


# ---------------- HTTP ----------------
def http_post(url, token, payload=None):
    data = urllib.parse.urlencode(payload).encode() if payload else b""

    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/x-www-form-urlencoded"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        log_err(str(e))
        return None


def http_get(url, token):
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}"},
        method="GET"
    )

    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        log_err(str(e))
        return None


# ---------------- ACCOUNT ----------------
def load_account(props, prop):
    global account_info_cache

    token = get_token()
    res = http_get("https://streamlabs.com/api/v5/slobs/tiktok/info", token)

    if res:
        account_info_cache = res
        update_boxes()
        log("Account info loaded")

    return True


# ---------------- CATEGORY ----------------
def search_cat(props, prop):
    global category_results_cache

    token = get_token()
    q = get_s("cat_search")

    res = http_get(
        f"https://streamlabs.com/api/v5/slobs/tiktok/info?category={urllib.parse.quote(q)}",
        token
    )

    if not res:
        return True

    category_results_cache = res.get("categories", [])
    category_results_cache.append({"full_name": "Other", "game_mask_id": ""})

    p = obs.obs_properties_get(props, "cat_list")
    obs.obs_property_list_clear(p)

    for c in category_results_cache:
        obs.obs_property_list_add_string(p, c["full_name"], c["game_mask_id"])

    log("Categories updated")
    return True


def select_cat(props, prop):
    global last_category_id, last_category_name

    cid = get_s("cat_list")

    for c in category_results_cache:
        if str(c["game_mask_id"]) == cid:
            last_category_id = cid
            last_category_name = c["full_name"]
            log(f"Selected: {last_category_name}")
            return True

    return True


# ---------------- START ----------------
def start_stream(props, prop):
    global last_stream_id, last_rtmp, last_key, last_title

    token = get_token()
    last_title = get_s("title") or "TikTok Live"

    res = http_post(
        "https://streamlabs.com/api/v5/slobs/tiktok/stream/start",
        token,
        {
            "title": last_title,
            "device_platform": "win32",
            "category": last_category_id,
            "audience_type": "0"
        }
    )

    if not res:
        return True

    last_stream_id = res.get("id")
    last_rtmp = res.get("rtmp")
    last_key = res.get("key")

    save_state_file()
    update_boxes()

    log("STREAM START OK")
    log(f"RTMP: {last_rtmp}")
    log(f"KEY: {last_key}")

    set_clipboard(last_key)

    return True


# ---------------- STOP ----------------
def stop_stream(props, prop):
    token = get_token()

    sid = get_s("manual_id") or last_stream_id
    if not sid:
        log_err("No stream ID")
        return True

    res = http_post(
        f"https://streamlabs.com/api/v5/slobs/tiktok/stream/{sid}/end",
        token
    )

    if res and res.get("success"):
        log("STREAM STOP OK")
    else:
        log_err("Stop failed")

    return True


# ---------------- OBS ----------------
def script_description():
    return "TikTok Streamlabs Tool (English)"

def script_load(settings):
    global script_settings_ref
    script_settings_ref = settings
    load_state_file()
    update_boxes()


def script_properties():
    props = obs.obs_properties_create()

    obs.obs_properties_add_button(props, "acc", "1. Load Account Info", load_account)
    obs.obs_properties_add_text(props, "account_info", "Account", obs.OBS_TEXT_MULTILINE)

    obs.obs_properties_add_text(props, "title", "Stream Title", obs.OBS_TEXT_DEFAULT)

    obs.obs_properties_add_text(props, "cat_search", "Search Game", obs.OBS_TEXT_DEFAULT)
    obs.obs_properties_add_button(props, "search", "2. Search Categories", search_cat)

    p = obs.obs_properties_add_list(
        props, "cat_list", "Categories",
        obs.OBS_COMBO_TYPE_LIST, obs.OBS_COMBO_FORMAT_STRING
    )

    obs.obs_property_list_add_string(p, "(search first)", "")

    obs.obs_properties_add_button(props, "sel", "3. Select Category", select_cat)

    obs.obs_properties_add_button(props, "start", "4. START STREAM", start_stream)
    obs.obs_properties_add_button(props, "stop", "5. STOP STREAM", stop_stream)

    obs.obs_properties_add_text(props, "manual_id", "Manual Stream ID", obs.OBS_TEXT_DEFAULT)

    obs.obs_properties_add_text(props, "stream_info", "Stream Info", obs.OBS_TEXT_MULTILINE)

    return props
