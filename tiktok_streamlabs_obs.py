import obspython as obs
import urllib.request
import urllib.parse
import json
import re
import glob
import os
import platform
import subprocess

# ── GLOBAL STATE ─────────────────────────────────────────
sl_token = ""
stream_title = ""
stream_category = ""
audience_type = "0"

current_stream_id = None
last_key = ""
last_rtmp = ""

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# ── HELPERS ──────────────────────────────────────────────
def log(msg):
    obs.script_log(obs.LOG_INFO, msg)

def log_err(msg):
    obs.script_log(obs.LOG_ERROR, msg)

def clean_text(v):
    if not v:
        return ""
    return str(v).replace("\ufeff", "").replace("\x00", "").strip()

def copy_to_clipboard(text):
    text = clean_text(text)
    if not text:
        log("Nothing to copy")
        return
    try:
        if platform.system() == "Windows":
            p = subprocess.Popen("clip", stdin=subprocess.PIPE, shell=True)
            p.communicate(text.encode("utf-16"))
            log("Copied to clipboard")
    except:
        log("Clipboard failed")

# ── API ──────────────────────────────────────────────────
def sl_request(method, url, token, data=None):
    token = clean_text(token)

    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("User-Agent", HEADERS["User-Agent"])

    if data is not None:
        encoded = urllib.parse.urlencode({k: clean_text(v) for k, v in data.items()}).encode("utf-8")
        req.data = encoded

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8", errors="ignore"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        log_err(f"HTTP {e.code}: {body}")
        return None
    except Exception as e:
        log_err(str(e))
        return None

def sl_start_stream(token, title, category_id, aud_type):
    url = "https://streamlabs.com/api/v5/slobs/tiktok/stream/start"
    data = {
        "title": title,
        "device_platform": "win32",
        "category": category_id,
        "audience_type": aud_type,
    }
    resp = sl_request("POST", url, token, data)
    if resp and "rtmp" in resp and "key" in resp:
        return resp["rtmp"], resp["key"], resp.get("id")
    log_err(f"start response: {resp}")
    return None, None, None

def sl_end_stream(token, stream_id):
    url = f"https://streamlabs.com/api/v5/slobs/tiktok/stream/{stream_id}/end"
    resp = sl_request("POST", url, token, {})
    return resp and resp.get("success", False)

def sl_search_category(token, game_name):
    if not game_name:
        return ""
    url = f"https://streamlabs.com/api/v5/slobs/tiktok/info?category={urllib.parse.quote(game_name)}"
    resp = sl_request("GET", url, token)
    if resp and "categories" in resp:
        for cat in resp["categories"]:
            if cat.get("full_name", "").lower() == game_name.lower():
                return cat.get("game_mask_id", "")
    return ""

def load_token():
    pattern = os.path.expandvars(r"%appdata%\slobs-client\Local Storage\leveldb\*.log")
    files = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)

    for f in files:
        try:
            txt = open(f, "rb").read().decode("utf-8", errors="ignore")
            txt = clean_text(txt)
            m = re.findall(r'"apiToken":"([^"]+)"', txt)
            if m:
                token = clean_text(m[-1])
                log(f"Token loaded: ...{token[-8:]}")
                return token
        except:
            pass
    return None

# ── ACTIONS ──────────────────────────────────────────────
def on_go_live(props, prop):
    global current_stream_id, sl_token, last_key, last_rtmp

    if not sl_token:
        log("No token")
        return

    cat_id = sl_search_category(sl_token, stream_category)
    rtmp, key, sid = sl_start_stream(sl_token, stream_title, cat_id, audience_type)

    if not rtmp or not key:
        log_err("Failed to start stream")
        return

    current_stream_id = sid
    last_key = key
    last_rtmp = rtmp

    log(f"STREAM STARTED ID: {sid}")
    log(f"RTMP: {rtmp}")
    log(f"KEY: {key}")

    # set OBS
    settings = obs.obs_data_create()
    obs.obs_data_set_string(settings, "server", rtmp)
    obs.obs_data_set_string(settings, "key", key)

    service = obs.obs_service_create("rtmp_custom", "TikTok", settings, None)
    obs.obs_frontend_set_streaming_service(service)
    obs.obs_service_release(service)
    obs.obs_data_release(settings)

    obs.obs_frontend_streaming_start()

def on_end_live(props, prop):
    global current_stream_id, sl_token

    if obs.obs_frontend_streaming_active():
        obs.obs_frontend_streaming_stop()
        log("OBS stopped")

    if current_stream_id:
        ok = sl_end_stream(sl_token, current_stream_id)
        if ok:
            log("STREAM STOP OK")
        else:
            log_err("Stop failed")

        current_stream_id = None

def on_copy_key(props, prop):
    if last_key:
        copy_to_clipboard(last_key)
    else:
        log("No key yet")

def on_load_token(props, prop):
    global sl_token
    t = load_token()
    if t:
        sl_token = t

# ── OBS ──────────────────────────────────────────────────
def script_description():
    return "TikTok Streamlabs Tool (Enhanced)"

def script_properties():
    props = obs.obs_properties_create()

    obs.obs_properties_add_button(props, "load", "Load Token", on_load_token)
    obs.obs_properties_add_text(props, "stream_title", "Title", obs.OBS_TEXT_DEFAULT)
    obs.obs_properties_add_text(props, "stream_category", "Category", obs.OBS_TEXT_DEFAULT)

    obs.obs_properties_add_button(props, "start", "START", on_go_live)
    obs.obs_properties_add_button(props, "stop", "STOP", on_end_live)

    obs.obs_properties_add_button(props, "copy", "📋 Copy Stream Key", on_copy_key)

    return props

def script_update(settings):
    global sl_token, stream_title, stream_category, audience_type

    stream_title = obs.obs_data_get_string(settings, "stream_title")
    stream_category = obs.obs_data_get_string(settings, "stream_category")
