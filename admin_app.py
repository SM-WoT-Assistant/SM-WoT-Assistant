#!/usr/bin/env python3
"""SM WoT Assistant — Admin Desktop Application
Monitors game changes via WG API + scripts.pkg scan,
auto-generates builds via AI Mode, notifies on results.

Usage:
  python admin_app.py --wot-path="C:/Games/World_of_Tanks_EU"
"""
import os, sys, json, time, re, threading, shutil, datetime, subprocess, tkinter as tk
from tkinter import ttk, scrolledtext
import ctypes
from ctypes import wintypes
import webbrowser

if getattr(sys, 'frozen', False):
    _BUNDLE_DIR = sys._MEIPASS
else:
    _BUNDLE_DIR = os.path.dirname(os.path.abspath(__file__))

os.chdir(_BUNDLE_DIR)
sys.path.insert(0, _BUNDLE_DIR)

import requests
import admin_auth

from admin_build_generator import (
    detect_changed_tanks, generate_builds, generate_popular,
    load_tank_db, load_prompts, _create_driver,
    _put_json, _get_json, _rtdb_url,
    _update_pending_status, check_wg_tanks_version,
    _WG_API_URL, _is_build_complete,
    check_wg_game_version, snapshot_manifest, update_manifest_for_tags,
    update_manifest_failures, exclude_failed_tags, scan_incomplete_builds,
    check_prompt_tank_mismatch,
    _kill_chrome_matching, _copy_chrome_profile, CHROME_PROFILE,
    CHROME_PROFILE_DIR, _DRIVER_RETRY_MARKERS
)
from admin_vault import (vault_get, vault_set, vault_has, vault_delete_field)

BG = "#1a1a1a"
BG2 = "#222222"
FG = "#cccccc"
ACCENT = "#ffaa00"
GREEN = "#66cc66"
RED = "#cc6666"

_NID = 1
_WM_APP = 0x8000
_WM_TRAY_CALLBACK = _WM_APP + 1
_GUID = "{4A2C4E6B-3B1A-4B8A-9E1F-7D3A5F8C2B6E}"

# ── i18n (EN authoritative, UK cached) ────────────
_ADMIN_UK_CACHE = os.path.join(os.environ.get("APPDATA", "."), "SM WoT Assistant", "admin_uk_cache.json")

_TR_EN = {
    "lang_en": "EN",
    "lang_uk": "UK",
    "not_set": "not set",
    "on": "ON",
    "off": "OFF",
    "label_admin": "Admin",
    "status_init": "Initializing...",
    "status_ok": "OK",
    "status_no_wot": "No WoT",
    "card_admin_ver": "Admin Version",
    "card_wg_ver": "WG Game Version",
    "card_game_status": "Game Status",
    "card_queue": "Queue",
    "card_last_scan": "Last Scan",
    "btn_scan": "Scan Now",
    "btn_gen_queue": "Generate Queue",
    "btn_gen_popular": "Generate Popular",
    "btn_regen_all": "Regen All",
    "menu_start_windows": "Start with Windows",
    "menu_start_minimized": "Start minimized to tray",
    "menu_wot_path": "WoT Path...",
    "menu_exit": "Exit",
    "menu_help": "Help",
    "menu_copy": "Copy",
    "menu_select_all": "Select All",
    "menu_cut": "Cut",
    "menu_paste": "Paste",
    "dlg_wot_path": "WoT Path",
    "dlg_wot_path_label": "WoT Path:",
    "dlg_save": "Save",
    "log_started": "Admin started (WoT: {path})",
    "log_tanks_prompts": "Tanks: {tanks}, Prompts: {prompts}",
    "card_tp": "Tanks / Prompts",
    "log_tp_mismatch": "[ERROR] Tanks/Prompts mismatch: {tanks} tanks vs {prompts} prompts",
    "log_tp_orphan_prompt": "  prompt without tank: {tag}",
    "log_tp_orphan_tank": "  tank without prompt: {tag}",
    "log_manifest_seeded": "Manifest seeded from dev copy",
    "log_manifest_baseline": "Manifest baseline created from scripts.pkg",
    "log_manifest_baseline_fail": "Manifest baseline failed: {err}",
    "log_wot_path_set": "WoT path set to: {val}",
    "log_start_windows": "Start with Windows: {state}",
    "log_scan_running": "Scan already in progress",
    "log_scanning": "Scanning scripts.pkg for changes...",
    "log_changed": "Detected {n} changed tanks!",
    "log_no_changes": "No changes detected",
    "log_scan_error": "Scan error: {err}",
    "log_queue_empty": "Queue is empty. Run Scan first.",
    "log_generating": "Generating builds for {n} tanks...",
    "log_gen_done": "Generation complete!",
    "log_gen_failed": "Generation FAILED",
    "log_gen_error": "Generation error: {err}",
    "log_popular_start": "Generating popular tanks...",
    "log_popular_ok": "Popular tanks updated!",
    "log_popular_fail": "Popular tanks FAILED",
    "log_popular_error": "Popular error: {err}",
    "log_regen_warn": "WARNING: Regen All will regenerate ALL tanks via AI!",
    "log_wg_ts": "WG tanks_updated_at changed: {ts}",
    "log_auto_detected": "Auto-detected {n} changed tanks!",
    "log_periodic": "Periodic scan: {n} changed tanks!",
    "log_bg_error": "Background error: {err}",
    "log_tray_started": "Started minimized to tray",
    "log_tray_running": "Running in tray (WoT: {path})",
    "log_cleanup_done": "Cleaned {n} old error reports (>60 days)",
    "log_sweep_queued": "Incomplete builds queued for regeneration",
    "log_sweep_error": "Fill sweep failed: {err}",
    "notif_changes": "Changes Detected",
    "notif_changes_body": "{n} tanks changed",
    "notif_gen_started": "Generation Started",
    "notif_gen_started_body": "{n} tanks queued",
    "notif_builds_updated": "Builds Updated",
    "notif_builds_updated_body": "{n} tanks regenerated",
    "notif_gen_failed": "Generation Failed",
    "notif_gen_failed_body": "Check logs for details",
    "notif_error": "Error",
    "notif_popular": "Popular Tanks",
    "notif_popular_body": "List updated successfully",
    "notif_regen_all": "Regen All",
    "notif_regen_all_body": "{n} tanks queued - this takes days",
    "notif_auto_detected": "Auto-Detected",
    "notif_auto_detected_body": "{n} tanks changed via WG API",
    "help_title": "Help",
    "help_intro": "SM WoT Assistant Admin monitors World of Tanks changes and generates AI builds automatically. Below is a description of all functions and buttons.",
    "h_sec_buttons": "Buttons",
    "h_btn_scan_t": "Scan Now",
    "h_btn_scan_d": "Scans scripts.pkg for changed tanks and queues them for generation.",
    "h_btn_gen_queue_t": "Generate Queue",
    "h_btn_gen_queue_d": "Generates builds for all tanks in the queue (the changed tanks).",
    "h_btn_gen_popular_t": "Generate Popular",
    "h_btn_gen_popular_d": "Regenerates the popular tanks list (tiers 8-11).",
    "h_btn_regen_all_t": "Regen All",
    "h_btn_regen_all_d": "Regenerates ALL tanks via AI. Takes a very long time - use with caution.",
    "h_sec_settings": "Settings (gear icon)",
    "h_menu_start_windows_d": "Starts the app automatically with Windows.",
    "h_menu_start_minimized_d": "Starts the app minimized to the system tray.",
    "h_menu_wot_path_d": "Sets the path to the World of Tanks installation.",
    "h_menu_exit_d": "Fully exits the app (the X button only minimizes to tray).",
    "h_menu_help_d": "Opens this help window.",
    "h_lang_d": "Switches the interface language between English and Ukrainian.",
    "h_sec_tray": "Tray",
    "h_tray_x_d": "The X button minimizes the app to the tray. The app keeps working in the background.",
    "h_tray_click_d": "Clicking the tray icon restores the window.",
    "h_sec_background": "Background automation",
    "h_bg_wg_d": "Checks the WG API every 30 minutes for new tanks. On changes - automatically generates builds.",
    "h_bg_scan_d": "Scans scripts.pkg every 60 minutes for changed tanks.",
    "h_sec_log": "Log",
    "h_log_newest_d": "Newest messages appear at the top; older ones move down.",
    "h_log_copy_d": "Right-click the log to copy a message (Copy / Select All).",
    "h_f1_d": "Press F1 to open this help at any time.",
    # ── Community & Stats ──
    "btn_community": "Community",
    "comm_fs_hint": "ESC — exit fullscreen",
    "tile_overview": "Overview",
    "tile_youtube": "YouTube",
    "tile_github": "GitHub",
    "tile_kofi": "Ko-fi",
    "tile_reddit": "Reddit",
    "tile_patreon": "Patreon",
    "tile_installs": "Installs",
    "tile_errors": "Errors",
    "tile_needs_key": "⚠ needs API key",
    "tile_needs_creds": "⚠ needs credentials",
    "tile_needs_login": "⚠ needs login",
    "tile_blocked": "⚠ blocked",
    "tile_action": "⚠ action needed",
    "tile_error": "⚠ error",
    "tab_overview": "Overview",
    "tab_youtube": "YouTube",
    "tab_reddit": "Reddit",
    "tab_github": "GitHub",
    "tab_kofi": "Ko-fi",
    "tab_patreon": "Patreon",
    "tab_apikeys": "API Keys",
    "tab_errors": "Errors",
    "ov_social": "Social networks",
    "ov_donations": "Donations",
    "ov_rtdb": "Service counters (RTDB)",
    "ov_sources": "Data sources status",
    "ov_installs": "Installations",
    "ov_installs_by_ver": "by version",
    "ov_errors": "Errors",
    "ov_schemes": "Schemes",
    "ov_users": "Users",
    "ov_builds_ver": "Builds version",
    "ov_last_gen": "Last generation",
    "st_ok": "OK",
    "st_no_key": "no API key — Chrome fallback",
    "st_not_conf": "not configured",
    "st_loading": "Loading...",
    "st_error": "error",
    "st_blocked": "blocked",
    "st_updated": "updated {time}",
    "st_paypal_qr": "QR on website only",
    "btn_refresh": "Refresh",
    "btn_link": "Link",
    "st_linked": "Linked",
    "st_not_linked": "Not linked",
    "btn_save_keys": "Save",
    "btn_reset_browser": "Reset browser data",
    "col_video": "Video",
    "col_date": "Date",
    "col_views": "Views",
    "col_likes": "Likes",
    "col_comments": "Comments",
    "col_post": "Post",
    "col_score": "Score",
    "col_release": "Release",
    "col_downloads": "Downloads",
    "col_amount": "Amount",
    "col_type": "Type",
    "col_time": "Time",
    "col_source": "Source",
    "col_version": "Version",
    "col_error": "Error",
    "col_field": "Field",
    "col_value": "Value",
    "col_patrons": "Patrons",
    "col_paid": "Paid members",
    "col_pledge": "Monthly pledge",
    "col_posts": "Posts",
    "col_created": "Created",
    "key_youtube_api": "YouTube Data API key",
    "key_reddit_user": "Reddit username",
    "key_reddit_pass": "Reddit password",
    "key_kofi_email": "Ko-fi email",
    "key_kofi_pass": "Ko-fi password",
    "key_kofi_client_id": "Ko-fi client ID",
    "key_kofi_secret": "Ko-fi client secret",
    "key_kofi_token": "Ko-fi refresh token",
    "key_saved": "Credentials saved (DPAPI encrypted)",
    "key_clear": "Empty field = remove saved value",
    "act_action_needed": "Action needed",
    "act_captcha": "CAPTCHA detected — solve it in the embedded browser",
    "act_login_google": "Log in to Google in the embedded browser (YouTube session)",
    "act_login_reddit": "Reddit session expired — log in",
    "act_login_kofi": "Ko-fi session expired — log in",
    "notif_community_action": "Community — action needed",
    "st_yt_manual_login": "Google login is manual (auto-login is blocked by Google security)",
    "log_comm_start": "Community: browser started",
    "log_comm_kill": "Community: browser stopped",
    "log_comm_reset": "Community: browser data reset",
    "log_comm_error": "Community refresh error: {err}",
    "log_yt_ok": "YouTube: {n} videos",
    "log_red_ok": "Reddit: {n} posts",
    "log_gh_ok": "GitHub: {n} releases, {dl} downloads",
    "log_kofi_ok": "Ko-fi: {n} donations, total {total}",
    "h_sec_community": "Community",
    "h_comm_tiles_d": "The tile strip shows overall stats: AI builds version, YouTube views, GitHub downloads, Ko-fi donations, Patreon patrons, Reddit posts, installations and errors. Click a tile to open the Community view with that platform's page in the browser.",
    "h_comm_fs_d": "The Community button or a tile click opens fullscreen Community: tiles, per-platform stats tables and the embedded Chrome browser (no separate windows appear).",
    "h_comm_login_d": "Reddit and Ko-fi log in automatically with vault credentials; Google login is manual. If action is needed (CAPTCHA, login form), the app notifies you and you solve it inside the embedded browser.",
    "h_comm_vault_d": "API keys and passwords are stored encrypted with Windows DPAPI in admin_vault.json (AppData). They are decrypted only on demand and never logged.",
    "h_comm_profile_d": "Logins persist in the dedicated community Chrome profile (community_chrome_profile). You do not need to re-authorize after a restart; reset it with 'Reset browser data'.",
}

_SHIELD_TOKENS = [
    "SM WoT Assistant", "scripts.pkg", "tanks_updated_at",
    "World of Tanks", "F1", "Ctrl", "WG", "AI", "WoT", "EN", "UK",
    "admin.log", "OK", "HKCU", "AppData",
]
_SHIELD_RE = re.compile(r"\{[a-z0-9_ '\.\-]+\}")


def _shield(text):
    """Protect placeholders {..} and known tokens from Google Translate."""
    parts = []

    def _ph(m):
        parts.append(m.group(0))
        return "\ue000%d\ue001" % (len(parts) - 1)

    t = _SHIELD_RE.sub(_ph, text)
    for tok in sorted(_SHIELD_TOKENS, key=len, reverse=True):
        if tok in t:
            t = t.replace(tok, "\ue000%d\ue001" % len(parts))
            parts.append(tok)
    return t, parts


def _unshield(text, parts):
    for i, p in enumerate(parts):
        text = text.replace("\ue000%d\ue001" % i, p)
    return text


def _translate_en2uk(text):
    try:
        from deep_translator import GoogleTranslator
        shielded, parts = _shield(text)
        res = GoogleTranslator(source="en", target="uk").translate(shielded)
        if not res:
            return text
        return _unshield(res, parts)
    except Exception:
        return text


def _load_uk_translations():
    """Load cached UK translations; re-translate only changed/new keys."""
    data = None
    try:
        if os.path.exists(_ADMIN_UK_CACHE):
            with open(_ADMIN_UK_CACHE, "r", encoding="utf-8") as f:
                data = json.load(f)
    except Exception:
        data = None
    if not data:
        seed = os.path.join(_BUNDLE_DIR, "admin_uk_seed.json")
        if os.path.exists(seed):
            try:
                with open(seed, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = None
    uk = dict((data or {}).get("uk", {}) or {})
    old_snapshot = (data or {}).get("en_snapshot", {}) or {}
    changed = {k: v for k, v in _TR_EN.items() if old_snapshot.get(k) != v}
    if changed:
        for k, v in changed.items():
            uk[k] = _translate_en2uk(v)
        try:
            with open(_ADMIN_UK_CACHE, "w", encoding="utf-8") as f:
                json.dump({"en_snapshot": _TR_EN, "uk": uk,
                           "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")}, f,
                          ensure_ascii=False, indent=2)
        except Exception:
            pass
    return uk

# ── Settings ─────────────────────────────────────
_ADMIN_SETTINGS_PATH = os.path.join(os.environ.get("APPDATA", "."), "SM WoT Assistant", "admin_settings.json")

def _load_admin_settings():
    defaults = {"start_with_windows": False, "start_minimized": True, "wot_path": ""}
    try:
        if os.path.exists(_ADMIN_SETTINGS_PATH):
            with open(_ADMIN_SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                defaults.update(data)
    except:
        pass
    return defaults

def _save_admin_settings(settings):
    try:
        os.makedirs(os.path.dirname(_ADMIN_SETTINGS_PATH), exist_ok=True)
        with open(_ADMIN_SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except:
        pass

_COMMUNITY_CACHE_PATH = os.path.join(os.environ.get("APPDATA", "."), "SM WoT Assistant", "community_cache.json")

def _load_community_cache():
    """Community platform data cache — shown instantly at startup, refreshed
    on Community entry / every 12h / manually. Validated on load."""
    try:
        if os.path.exists(_COMMUNITY_CACHE_PATH):
            with open(_COMMUNITY_CACHE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                stats = data.get("stats")
                if isinstance(stats, dict):
                    return {k: v for k, v in stats.items() if k in
                            ("youtube", "reddit", "github", "kofi", "patreon")}
    except Exception:
        pass
    return {}

def _save_community_cache(stats):
    """Validate + persist the platform stats cache."""
    try:
        valid = {}
        for k in ("youtube", "reddit", "github", "kofi", "patreon"):
            v = stats.get(k)
            if isinstance(v, dict):
                valid[k] = v
        os.makedirs(os.path.dirname(_COMMUNITY_CACHE_PATH), exist_ok=True)
        with open(_COMMUNITY_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump({"stats": valid, "updated_at": time.time()}, f, indent=2)
    except Exception:
        pass

def _set_windows_startup(enable):
    """Add/remove HKCU\\Run entry for admin app."""
    import winreg
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE | winreg.KEY_READ)
        if enable:
            exe_path = sys.executable if getattr(sys, 'frozen', False) else __file__
            winreg.SetValueEx(key, "SM WoT Assistant Admin", 0, winreg.REG_SZ, f'"{exe_path}" --tray')
        else:
            try:
                winreg.DeleteValue(key, "SM WoT Assistant Admin")
            except:
                pass
        winreg.CloseKey(key)
    except:
        pass

def _read_admin_version():
    try:
        with open(os.path.join(_BUNDLE_DIR, "admin_version.txt"), "r") as f:
            return f.read().strip()
    except:
        return "0.0.0"


# ── Community & Stats ─────────────────────────────
_COMMUNITY_PROFILE_DIR = os.path.join(os.environ.get("APPDATA", "."),
                                      "SM WoT Assistant", "community_chrome_profile")
_YT_VIDEO_ID = "4JlDkM65PxY"
_YT_CHANNEL_URL = "https://www.youtube.com/@SMWoTAssistant"
_YT_API = "https://www.googleapis.com/youtube/v3"
_GITHUB_REPO = "SM-WoT-Assistant/SM-WoT-Assistant"
_GITHUB_API = f"https://api.github.com/repos/{_GITHUB_REPO}"
_REDDIT_USER = "SM-WoT-Assistant"
_PATREON_URL = "https://www.patreon.com/cw/SMWoTAssistant"
# Публічний legacy-API (без auth, без Chrome): campaign id 16413892 взято з
# og:image teaser сторінки patreon.com/cw/SMWoTAssistant.
_PATREON_API = "https://www.patreon.com/api/campaigns/16413892"

_COMMUNITY_PAGE_URLS = {
    "overview": "https://sm-wot-assistant.web.app/admin.html",
    "reddit": "https://www.reddit.com/user/" + _REDDIT_USER + "/",
    "github": "https://github.com/SM-WoT-Assistant/SM-WoT-Assistant/releases",
    "kofi": "https://ko-fi.com/Manage/",
    "patreon": _PATREON_URL,
}
_UA = "SM-WoT-Assistant-Admin/1.0"
_APP_DATA_DIR = os.path.join(os.environ.get("APPDATA", "."), "SM WoT Assistant")

_GWL_STYLE = -16
_GWL_EXSTYLE = -20
_WS_POPUP = 0x80000000
_WS_CHILD = 0x40000000
_WS_EX_TOOLWINDOW = 0x80
_SWP_FRAMECHANGED = 0x0020
_SWP_SHOWWINDOW = 0x0040
_SWP_NOZORDER = 0x0004


def _fmt_num(n):
    try:
        n = int(n)
    except Exception:
        return "—"
    if n >= 1000000:
        return "%.1fM" % (n / 1000000.0)
    if n >= 1000:
        return "%.1fK" % (n / 1000.0)
    return str(n)


def _fmt_money(v):
    try:
        return "%.2f" % float(v)
    except Exception:
        return "—"


def _fmt_ts(iso):
    """ISO '2026-08-20T10:00:00Z' → '20.08 10:00'. Returns '—' on garbage."""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})", str(iso or ""))
    if not m:
        return "—"
    return "%s.%s %s:%s" % (m.group(3), m.group(2), m.group(4), m.group(5))


def _parse_views(txt):
    """'12K views' / '11 тис. переглядів' / '1,2 млн' / '450' → int. Returns 0 on garbage."""
    m = re.search(r"([\d\s.,\u00a0]+)\s*((?:тис|тыс|млн|млрд|[KMBкмл])\w*)?", str(txt), re.I)
    if not m:
        return 0
    try:
        n = float(m.group(1).replace("\u00a0", "").replace(" ", "").replace(",", "."))
    except Exception:
        return 0
    suffix = (m.group(2) or "").lower()
    word = suffix if suffix in ("тис", "тыс", "млн", "млрд") else suffix[:1]
    mult = {"тис": 1000, "тыс": 1000, "млн": 1000000, "млрд": 1000000000,
            "k": 1000, "m": 1000000, "b": 1000000000,
            "к": 1000, "м": 1000000, "л": 1000000000}.get(word, 1)
    return int(n * mult)


def _safe_int(v, default=0):
    try:
        return int(v)
    except Exception:
        return default


def _yt_initial_data(html):
    m = re.search(r"var ytInitialData = ({.*?});(?:</script>|var )", html, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:
        return None


def _parse_yt_videos(data):
    """Extract video list from ytInitialData (channel /videos tab).

    Handles both legacy videoRenderer and the 2026 lockupViewModel layout:
    title = metadata.lockupMetadataViewModel.title.content,
    stats = metadata...contentMetadataViewModel.metadataRows[*].metadataParts[*].text.content.
    """
    videos = []
    try:
        tabs = data["contents"]["twoColumnBrowseResultsRenderer"]["tabs"]
        items = []
        for tab in tabs:
            cont = tab.get("tabRenderer", {}).get("content", {})
            if "richGridRenderer" in cont:
                items = cont["richGridRenderer"]["contents"]
            elif "sectionListRenderer" in cont:
                for sec in cont["sectionListRenderer"]["contents"]:
                    items += sec.get("itemSectionRenderer", {}).get("contents", [])
            else:
                continue
            break
        for it in items:
            content = it.get("richItemRenderer", {}).get("content", {}) if "richItemRenderer" in it else it
            vr = content.get("videoRenderer")
            lv = content.get("lockupViewModel")
            if not vr and not lv:
                continue
            if vr:
                vid = vr.get("videoId", "")
                title = "".join(r.get("text", "") for r in (vr.get("title", {}).get("runs") or []))
                views_txt = (vr.get("viewCountText", {}).get("simpleText") or
                             "".join(r.get("text", "") for r in (vr.get("viewCountText", {}).get("runs") or [])))
                date_txt = (vr.get("publishedTimeText", {}).get("simpleText") or "")
            else:
                lm = (lv.get("metadata", {}).get("lockupMetadataViewModel") or {})
                title = ((lm.get("title") or {}).get("content") or "").strip()
                parts = []
                for row in (lm.get("metadata") or {}).get("contentMetadataViewModel", {}).get("metadataRows", []):
                    for mp in row.get("metadataParts", []):
                        t = ((mp.get("text") or {}).get("content") or "").strip()
                        if t:
                            parts.append(t)
                views_txt = parts[0] if parts else ""
                date_txt = parts[1] if len(parts) > 1 else ""
                img = (lv.get("contentImage") or {}).get("thumbnailViewModel", {}).get("image", {}).get("sources") or []
                m = re.search(r"/vi/([A-Za-z0-9_-]{11})/", img[0].get("url", "")) if img else None
                vid = m.group(1) if m else ""
            videos.append({"id": vid, "title": title, "date": date_txt,
                           "views": _parse_views(views_txt), "views_txt": views_txt,
                           "likes": 0, "comments": 0})
    except Exception:
        pass
    return videos


def _parse_reddit_html(html):
    """Extract posts from shreddit-feed HTML (user profile page)."""
    posts = []
    for attrs_str, body in re.findall(r"<shreddit-post\b([^>]*)>(.*?)</shreddit-post>", html, re.S):
        attrs = dict(re.findall(r'([a-z0-9-]+)="([^"]*)"', attrs_str))
        title = ""
        mt = re.search(r"<h3[^>]*>(.*?)</h3>", body, re.S)
        if mt:
            title = re.sub(r"<[^>]+>", "", mt.group(1)).strip()
        ts = attrs.get("created-timestamp", "")
        posts.append({"title": title, "date": ts[:10] if len(ts) >= 10 else "",
                      "score": _safe_int(attrs.get("score")),
                      "comments": _safe_int(attrs.get("comment-count")),
                      "url": "https://www.reddit.com" + attrs.get("permalink", "")})
    return posts


def _parse_kofi_amounts(html):
    """Best-effort donation amount extraction from Ko-fi dashboard HTML."""
    amounts = []
    for m in re.finditer(r'<[^>]+class="[^"]*(?:amount|donation|transaction-row-amount)[^"]*"[^>]*>\s*([€£$¥]\s*[\d.,]+)\s*<',
                         html, re.I):
        txt = re.sub(r"[^\d.,]", "", m.group(1)).replace(",", ".")
        try:
            amounts.append(float(txt))
        except Exception:
            pass
    return amounts


def _chrome_main_pid(profile_dir):
    """PID of the main chrome.exe browser process for a profile dir
    (the process without --type= holds the top-level window)."""
    pat = profile_dir.replace("'", "''")
    q = ("Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | "
         "Where-Object {{ $_.CommandLine -like '*{0}*' -and $_.CommandLine -notlike '*--type=*' }} | "
         "Select-Object -First 1 -ExpandProperty ProcessId").format(pat)
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", q],
                             capture_output=True, text=True, timeout=20,
                             creationflags=subprocess.CREATE_NO_WINDOW)
        pid = out.stdout.strip()
        return int(pid) if pid.isdigit() else None
    except Exception:
        return None


def _find_hwnd_by_pid(pid):
    """Top-level window HWNDs belonging to a PID.
    Returns the LARGEST visible window (by area) — Chrome may show small
    modal dialogs ('Restore pages?') alongside the main window, and the
    main window must always win the embed selection."""
    result = []
    EnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def _cb(hwnd, lparam):
        pid_out = wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_out))
        if pid_out.value == pid:
            result.append(hwnd)
        return True

    try:
        ctypes.windll.user32.EnumWindows(EnumProc(_cb), 0)
    except Exception:
        pass
    best, best_area = None, 0
    user32 = ctypes.windll.user32
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    for h in result:
        if not user32.IsWindowVisible(h):
            continue
        rect = wintypes.RECT()
        if not user32.GetWindowRect(h, ctypes.byref(rect)):
            continue
        area = (rect.right - rect.left) * (rect.bottom - rect.top)
        if area > best_area:
            best_area, best = area, h
    if best is not None:
        return best
    return result[-1] if result else None


def _embed_hwnd(hwnd, parent_hwnd, w, h):
    """Reparent a Chrome window into a tkinter frame (no stray windows).
    Returns True only when SetParent actually attached the window."""
    user32 = ctypes.windll.user32
    user32.SetParent.argtypes = [wintypes.HWND, wintypes.HWND]
    user32.SetParent.restype = wintypes.HWND
    user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongPtrW.restype = ctypes.c_void_p
    user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
    user32.SetWindowLongPtrW.restype = ctypes.c_void_p
    user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_int, wintypes.UINT]
    prev = user32.SetParent(hwnd, parent_hwnd)
    if prev is None:
        return False
    style = user32.GetWindowLongPtrW(hwnd, _GWL_STYLE)
    user32.SetWindowLongPtrW(hwnd, _GWL_STYLE, (style & ~_WS_POPUP) | _WS_CHILD)
    user32.SetWindowPos(hwnd, 0, 0, 0, w, h,
                        _SWP_FRAMECHANGED | _SWP_SHOWWINDOW | _SWP_NOZORDER)
    return True


def _cursor_over_hwnd(hwnd):
    """True, якщо курсор миші знаходиться над вікном (або його дочірніми).

    WindowFromPoint повертає найглибше вікно під курсором (Chrome renderer
    window, WS_CHILD canvas тощо), тому піднімаємося ланцюгом GetParent
    (до 12 рівнів) і порівнюємо з цільовим hwnd — патерн #1500."""
    try:
        pt = wintypes.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        h = ctypes.windll.user32.WindowFromPoint(pt)
        for _ in range(12):
            if h == hwnd:
                return True
            h = ctypes.windll.user32.GetParent(h)
            if not h:
                break
        return False
    except Exception:
        return False


def _unembed_hwnd(hwnd):
    """Detach a previously embedded window back to top-level (so EnumWindows
    can find it again on the next embed attempt)."""
    user32 = ctypes.windll.user32
    user32.SetParent.argtypes = [wintypes.HWND, wintypes.HWND]
    user32.SetParent.restype = wintypes.HWND
    user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongPtrW.restype = ctypes.c_void_p
    user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
    user32.SetWindowLongPtrW.restype = ctypes.c_void_p
    try:
        user32.SetParent(hwnd, None)
        style = user32.GetWindowLongPtrW(hwnd, _GWL_STYLE)
        user32.SetWindowLongPtrW(hwnd, _GWL_STYLE, (style & ~_WS_CHILD) | _WS_POPUP)
    except Exception:
        pass


def _move_hwnd(hwnd, x, y, w, h):
    user32 = ctypes.windll.user32
    user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_int, wintypes.UINT]
    try:
        user32.SetWindowPos(hwnd, 0, x, y, w, h,
                            _SWP_SHOWWINDOW | _SWP_NOZORDER)
    except Exception:
        pass


def _top_level_windows(pid):
    """All top-level HWNDs belonging to a PID."""
    result = []
    EnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def _cb(hwnd, lparam):
        pid_out = wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_out))
        if pid_out.value == pid:
            result.append(hwnd)
        return True

    try:
        ctypes.windll.user32.EnumWindows(EnumProc(_cb), 0)
    except Exception:
        pass
    return result


def _toolwindow_hwnd(hwnd):
    """WS_EX_TOOLWINDOW — removes the taskbar button for a window."""
    user32 = ctypes.windll.user32
    user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongPtrW.restype = ctypes.c_void_p
    user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
    user32.SetWindowLongPtrW.restype = ctypes.c_void_p
    try:
        ex = user32.GetWindowLongPtrW(hwnd, _GWL_EXSTYLE)
        user32.SetWindowLongPtrW(hwnd, _GWL_EXSTYLE, ex | _WS_EX_TOOLWINDOW)
    except Exception:
        pass


def _pid_alive(pid):
    """Quick ctypes check whether a PID exists (no PowerShell)."""
    if not pid:
        return False
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    h = kernel32.OpenProcess(0x1000, False, pid)
    if not h:
        return False
    kernel32.CloseHandle(h)
    return True


def _hwnd_alive(hwnd):
    try:
        return bool(ctypes.windll.user32.IsWindow(hwnd))
    except Exception:
        return False


def _fix_crashed_profile_prefs():
    """Chrome shows a 'Restore pages?' bubble when the profile was killed
    (exit_type=Crashed + stale Last Session/Current Session files) — a modal
    window that ignores --window-position, pops up on screen, and can win the
    embed HWND selection. Rewrite Preferences to Normal and delete the stale
    session files before driver start."""
    try:
        prof = os.path.join(_COMMUNITY_PROFILE_DIR, CHROME_PROFILE_DIR)
        prefs = os.path.join(prof, "Preferences")
        if os.path.isfile(prefs):
            with open(prefs, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("exit_type") == "Crashed":
                data["exit_type"] = "Normal"
                with open(prefs, "w", encoding="utf-8") as f:
                    json.dump(data, f)
        for sess in ("Last Session", "Current Session", "Last Tabs", "Last Version"):
            p = os.path.join(prof, sess)
            try:
                if os.path.isfile(p):
                    os.remove(p)
            except Exception:
                pass
    except Exception:
        pass

class AdminTray:
    def __init__(self, parent):
        self.parent = parent
        self._tid = _NID
        self._hwnd = None
        self._create_window()
        self._add_icon()

    def _create_window(self):
        user32 = ctypes.windll.user32
        user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user32.DefWindowProcW.restype = wintypes.LPARAM
        WNDPROC = ctypes.WINFUNCTYPE(wintypes.LPARAM, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
        def wndproc(hwnd, msg, wparam, lparam):
            try:
                if msg == _WM_TRAY_CALLBACK and (lparam & 0xFFFF) in (0x0202, 0x0203):
                    self.parent.root.deiconify()
                    self.parent.root.lift()
            except Exception:
                pass
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)
        self._wndproc = WNDPROC(wndproc)
        hinst = ctypes.windll.kernel32.GetModuleHandleW(None)
        cls_name = "AdminTrayClass"
        class WNDCLASSEXW(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.c_uint),
                ("style", ctypes.c_uint),
                ("lpfnWndProc", ctypes.c_void_p),
                ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int),
                ("hInstance", ctypes.c_void_p),
                ("hIcon", ctypes.c_void_p),
                ("hCursor", ctypes.c_void_p),
                ("hbrBackground", ctypes.c_void_p),
                ("lpszMenuName", ctypes.c_wchar_p),
                ("lpszClassName", ctypes.c_wchar_p),
                ("hIconSm", ctypes.c_void_p),
            ]
        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(wc)
        wc.lpfnWndProc = ctypes.cast(self._wndproc, ctypes.c_void_p)
        wc.hInstance = hinst
        wc.lpszClassName = cls_name
        ctypes.windll.user32.RegisterClassExW(ctypes.byref(wc))
        self._hwnd = ctypes.windll.user32.CreateWindowExW(0, cls_name, "", 0, 0, 0, 0, 0, 0, 0, hinst, None)

    def _add_icon(self):
        icon_path = os.path.join(_BUNDLE_DIR, "admin_icon.ico")
        hicon = 0
        if os.path.exists(icon_path):
            hicon = ctypes.windll.user32.LoadImageW(0, icon_path, 1, 0, 0, 0x00000010)
        class NOTIFYICONDATAW(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.c_uint),
                ("hWnd", ctypes.c_void_p),
                ("uID", ctypes.c_uint),
                ("uFlags", ctypes.c_uint),
                ("uCallbackMessage", ctypes.c_uint),
                ("hIcon", ctypes.c_void_p),
                ("szTip", ctypes.c_wchar * 128),
                ("dwState", ctypes.c_uint),
                ("dwStateMask", ctypes.c_uint),
                ("szInfo", ctypes.c_wchar * 256),
                ("uVersion", ctypes.c_uint),
                ("szInfoTitle", ctypes.c_wchar * 64),
                ("dwInfoFlags", ctypes.c_uint),
                ("guidItem", ctypes.c_byte * 16),
                ("hBalloonIcon", ctypes.c_void_p),
            ]
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(nid)
        nid.hWnd = self._hwnd
        nid.uID = self._tid
        nid.uFlags = 0x00000002 | 0x00000001 | 0x00000004
        nid.uCallbackMessage = _WM_TRAY_CALLBACK
        nid.hIcon = hicon or ctypes.windll.user32.LoadIconW(0, 32512)
        nid.szTip = "SM WoT Assistant Admin"
        ctypes.windll.shell32.Shell_NotifyIconW(0x00000000, ctypes.byref(nid))

    def show_notification(self, title, text, level="info"):
        class NOTIFYICONDATAW(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.c_uint),
                ("hWnd", ctypes.c_void_p),
                ("uID", ctypes.c_uint),
                ("uFlags", ctypes.c_uint),
                ("uCallbackMessage", ctypes.c_uint),
                ("hIcon", ctypes.c_void_p),
                ("szTip", ctypes.c_wchar * 128),
                ("dwState", ctypes.c_uint),
                ("dwStateMask", ctypes.c_uint),
                ("szInfo", ctypes.c_wchar * 256),
                ("uVersion", ctypes.c_uint),
                ("szInfoTitle", ctypes.c_wchar * 64),
                ("dwInfoFlags", ctypes.c_uint),
                ("guidItem", ctypes.c_byte * 16),
                ("hBalloonIcon", ctypes.c_void_p),
            ]
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(nid)
        nid.hWnd = self._hwnd
        nid.uID = self._tid
        nid.uFlags = 0x00000010
        nid.uTimeout = 5000
        nid.szInfoTitle = title[:64]
        nid.szInfo = text[:256]
        nid.dwInfoFlags = 0x00000001 if level == "error" else 0x00000000
        ctypes.windll.shell32.Shell_NotifyIconW(0x00000001, ctypes.byref(nid))

    def remove(self):
        class NOTIFYICONDATAW(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.c_uint),
                ("hWnd", ctypes.c_void_p),
                ("uID", ctypes.c_uint),
                ("uFlags", ctypes.c_uint),
                ("uCallbackMessage", ctypes.c_uint),
                ("hIcon", ctypes.c_void_p),
                ("szTip", ctypes.c_wchar * 128),
                ("dwState", ctypes.c_uint),
                ("dwStateMask", ctypes.c_uint),
                ("szInfo", ctypes.c_wchar * 256),
                ("uVersion", ctypes.c_uint),
                ("szInfoTitle", ctypes.c_wchar * 64),
                ("dwInfoFlags", ctypes.c_uint),
                ("guidItem", ctypes.c_byte * 16),
                ("hBalloonIcon", ctypes.c_void_p),
            ]
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(nid)
        nid.hWnd = self._hwnd
        nid.uID = self._tid
        ctypes.windll.shell32.Shell_NotifyIconW(0x00000002, ctypes.byref(nid))
        if self._hwnd:
            ctypes.windll.user32.DestroyWindow(self._hwnd)


class AdminApp:
    def __init__(self, root, wot_path=None):
        self.root = root
        self._wot_path = wot_path
        self._running = True
        self._scanning = False
        self._generating = False
        self._last_scan = -3600
        self._last_wg = -21600
        self._wg_ver = ""
        self._queue = []
        self._last_detected = []
        self._admin_settings = _load_admin_settings()
        self._lang = self._admin_settings.get("lang", "en")
        if self._lang not in ("en", "uk"):
            self._lang = "en"
        self._tr_uk: dict = _load_uk_translations()
        self._wot_path = self._resolve_wot_path(wot_path)
        if self._wot_path and not self._admin_settings.get("wot_path"):
            self._admin_settings["wot_path"] = self._wot_path
            _save_admin_settings(self._admin_settings)
        self._manifest_path = self._resolve_manifest()

        self.tank_db = load_tank_db()
        self.prompts = load_prompts()
        self.tray = AdminTray(self)

        self._community = {
            "driver": None, "visible": False, "hwnd": None, "creating": False,
            "embed_pending": False, "chrome_pid": None, "tg_started": False,
            "yt_channel_id": None, "fs": False, "refreshing": False,
            "action": None, "last_comm": 0.0, "last_rtdb": 0.0,
            "linked": dict(self._admin_settings.get("community_linked") or {}),
            "stats": {"youtube": None, "reddit": None, "github": None, "kofi": None,
                      "installs": None, "installs_by_ver": {}, "errors": None,
                      "schemes": None, "users": None, "builds_ver": None,
                      "last_generated_at": None},
            "status": {"youtube": "idle", "reddit": "idle", "github": "idle", "kofi": "idle"},
        }
        for _ck, _cv in _load_community_cache().items():
            self._community["stats"][_ck] = _cv

        self._build_ui()
        self._log(self.t("log_started", path=self._wot_path or self.t("not_set")))
        self._check_tank_prompt_match()
        self._last_heartbeat = 0.0
        self._last_cleanup = 0.0
        self._last_sweep = -86280.0  # first fill sweep ~120s after start, then every 24h
        threading.Thread(target=self._report_admin_status,
                         kwargs={"status": "idle"}, daemon=True).start()
        self._start_background()
        # No periodic community fetch on startup: admin tool = manual updates
        # (Refresh / Link buttons; one-shot RTDB counters on Community entry).

    def _report_admin_status(self, status=None):
        """Publish admin app info to RTDB admin_app/ node (fire-and-forget)."""
        try:
            if status:
                _put_json(_rtdb_url("admin_app/status"), status)
            _put_json(_rtdb_url("admin_app/version"), _read_admin_version())
            _put_json(_rtdb_url("admin_app/last_seen"), int(time.time()))
        except Exception:
            pass

    def _cleanup_old_error_reports(self):
        """Видаляє error_reports старші 60 днів (fire-and-forget)."""
        try:
            now_utc = datetime.datetime.utcnow()
            cutoff = (now_utc - datetime.timedelta(days=60)).strftime("%Y-%m-%dT%H:%M:%SZ")
            url = _rtdb_url("error_reports") + '&orderBy="timestamp"&endAt="' + cutoff + '"'
            old = _get_json(url) or {}
            n = 0
            for key, entry in list(old.items()):
                if not isinstance(entry, dict):
                    continue
                try:
                    ts = datetime.datetime.strptime(str(entry.get("timestamp", "")),
                                                    "%Y-%m-%dT%H:%M:%SZ")
                except Exception:
                    continue
                if ts >= now_utc - datetime.timedelta(days=60):
                    continue
                try:
                    _put_json(_rtdb_url("error_reports/" + str(key)), None)
                    n += 1
                except Exception:
                    pass
            if n:
                self._log(self.t("log_cleanup_done", n=n))
        except Exception:
            pass

    def _run_build_fill_sweep(self):
        """Generate strictly incomplete builds (daily self-heal, direct GUI path).

        Generates directly (no pending_updates trigger) so a concurrently running
        daemon --listen does not pick up the same queue and double-generate."""
        try:
            if self._generating:
                return
            st = _get_json(_rtdb_url("pending_updates/builds"))
            if st and st.get("status") == "generating":
                return
            queue = sorted(scan_incomplete_builds().keys())
            queue = exclude_failed_tags(queue, self._manifest_path, self._wot_path or "")
            if queue:
                self._log(self.t("log_sweep_queued"))
                threading.Thread(target=self._do_generate,
                                 args=(queue,), daemon=True).start()
        except Exception as e:
            self._log(self.t("log_sweep_error", err=e))

    def t(self, key, **kw) -> str:
        v = str(_TR_EN.get(key, key))
        if self._lang == "uk":
            ukv = self._tr_uk.get(key)
            if isinstance(ukv, str) and ukv:
                v = str(ukv)
        if kw:
            try:
                return v.format(**kw)
            except Exception:
                return v
        return v

    def _toggle_lang(self):
        self._lang = "uk" if self._lang == "en" else "en"
        self._admin_settings["lang"] = self._lang
        _save_admin_settings(self._admin_settings)
        self._apply_lang()

    def _apply_lang(self):
        if hasattr(self, "_lang_btn") and self._lang_btn:
            self._lang_btn.config(text=self.t("lang_uk") if self._lang == "en" else self.t("lang_en"))
        for w, key in getattr(self, "_tr_widgets", []):
            try:
                w.config(text=self.t(key))
            except Exception:
                pass
        if hasattr(self, "_nb"):
            for name, ix in getattr(self, "_tab_ix", {}).items():
                try:
                    self._nb.tab(ix, text=self.t("tab_" + name))
                except Exception:
                    pass
        self._update_cards()

    def _show_help(self):
        dlg = tk.Toplevel(self.root)
        dlg.title(self.t("help_title"))
        dlg.configure(bg=BG)
        dlg.geometry("680x560")
        dlg.minsize(500, 400)
        dlg.transient(self.root)

        def _help_popup(e):
            m = tk.Menu(dlg, tearoff=0, bg="#222222", fg=FG,
                        activebackground="#333333", activeforeground=ACCENT, bd=1)
            m.add_command(label=self.t("menu_copy"),
                          command=lambda: self._copy_selection(txt))
            m.add_separator()
            m.add_command(label=self.t("menu_select_all"),
                          command=lambda: txt.tag_add("sel", "1.0", "end-1c"))
            try:
                m.tk_popup(e.x_root, e.y_root)
            finally:
                m.grab_release()

        txt = scrolledtext.ScrolledText(dlg, bg="#111111", fg="#cccccc",
                                        insertbackground="#cccccc",
                                        font=("Consolas", 10), bd=0, wrap="word")
        txt.pack(fill="both", expand=True, padx=10, pady=10)
        txt.insert("1.0", self._help_text())
        txt.config(state="disabled")
        txt.bind("<Button-3>", _help_popup)

    def _help_text(self):
        L = [self.t("help_intro"), ""]
        L.append("== " + self.t("h_sec_buttons") + " ==")
        for b in ("scan", "gen_queue", "gen_popular", "regen_all"):
            L.append("\u2022 " + self.t("h_btn_" + b + "_t") + " \u2014 " + self.t("h_btn_" + b + "_d"))
        L.append("")
        L.append("== " + self.t("h_sec_settings") + " ==")
        L.append("\u2022 " + self.t("menu_start_windows") + " \u2014 " + self.t("h_menu_start_windows_d"))
        L.append("\u2022 " + self.t("menu_start_minimized") + " \u2014 " + self.t("h_menu_start_minimized_d"))
        L.append("\u2022 " + self.t("menu_wot_path") + " \u2014 " + self.t("h_menu_wot_path_d"))
        L.append("\u2022 " + self.t("menu_exit") + " \u2014 " + self.t("h_menu_exit_d"))
        L.append("\u2022 " + self.t("menu_help") + " \u2014 " + self.t("h_menu_help_d"))
        L.append("\u2022 " + self.t("lang_en") + "/" + self.t("lang_uk") + " \u2014 " + self.t("h_lang_d"))
        L.append("")
        L.append("== " + self.t("h_sec_tray") + " ==")
        L.append("\u2022 " + self.t("h_tray_x_d"))
        L.append("\u2022 " + self.t("h_tray_click_d"))
        L.append("")
        L.append("== " + self.t("h_sec_background") + " ==")
        L.append("\u2022 " + self.t("h_bg_wg_d"))
        L.append("\u2022 " + self.t("h_bg_scan_d"))
        L.append("")
        L.append("== " + self.t("h_sec_log") + " ==")
        L.append("\u2022 " + self.t("h_log_newest_d"))
        L.append("\u2022 " + self.t("h_log_copy_d"))
        L.append("\u2022 " + self.t("h_f1_d"))
        L.append("")
        L.append("== " + self.t("h_sec_community") + " ==")
        L.append("\u2022 " + self.t("h_comm_tiles_d"))
        L.append("\u2022 " + self.t("h_comm_fs_d"))
        L.append("\u2022 " + self.t("h_comm_login_d"))
        L.append("\u2022 " + self.t("h_comm_vault_d"))
        L.append("\u2022 " + self.t("h_comm_profile_d"))
        return "\n".join(L)

    def _resolve_wot_path(self, cli_wot_path):
        """Resolve WoT path: CLI arg → admin settings → main app settings → common paths."""
        candidates = []
        if cli_wot_path:
            candidates.append(cli_wot_path)
        if self._admin_settings.get("wot_path"):
            candidates.append(self._admin_settings["wot_path"])
        try:
            main_settings_path = os.path.join(os.environ.get("APPDATA", "."), "SM WoT Assistant", "settings.json")
            with open(main_settings_path, "r", encoding="utf-8") as f:
                main_settings = json.load(f)
                if main_settings.get("wot_path"):
                    candidates.append(main_settings["wot_path"])
        except:
            pass
        candidates.extend([
            "C:/Games/World_of_Tanks_EU", "D:/Games/World_of_Tanks_EU",
            "E:/Games/World_of_Tanks_EU", "C:/Games/World_of_Tanks",
            "D:/Games/World_of_Tanks", "E:/Games/World_of_Tanks"
        ])
        for p in candidates:
            p = (p or "").strip()
            if p and os.path.exists(os.path.join(p, "version.xml")):
                return p
        return ""

    def _resolve_manifest(self):
        """Persistent change-tracking manifest in AppData.
        Seeded from a fresh dev manifest (CWD) or a baseline snapshot of scripts.pkg
        so the first scan never reports every tank as changed."""
        manifest_dir = os.path.join(os.environ.get("APPDATA", "."), "SM WoT Assistant")
        path = os.path.join(manifest_dir, ".tank_extract_manifest.json")
        if os.path.exists(path):
            return path
        if self._wot_path:
            cwd_manifest = os.path.join(_BUNDLE_DIR, ".tank_extract_manifest.json")
            if os.path.exists(cwd_manifest):
                try:
                    if not detect_changed_tanks(self._wot_path, cwd_manifest):
                        os.makedirs(manifest_dir, exist_ok=True)
                        shutil.copy(cwd_manifest, path)
                        self._log(self.t("log_manifest_seeded"))
                        return path
                except Exception:
                    pass
            try:
                if snapshot_manifest(self._wot_path, path):
                    self._log(self.t("log_manifest_baseline"))
                    return path
            except Exception as e:
                self._log(self.t("log_manifest_baseline_fail", err=e))
        return path

    def _build_ui(self):
        ver = _read_admin_version()
        self.root.title(f"SM WoT Assistant Admin v{ver}")
        self.root.geometry("860x620")
        self.root.configure(bg=BG)
        self.root.minsize(600, 400)
        try:
            self.root.iconbitmap(default=os.path.join(_BUNDLE_DIR, "admin_icon.ico"))
        except Exception:
            pass

        self._tr_widgets = []

        top = tk.Frame(self.root, bg=BG)
        top.pack(fill="x", padx=12, pady=(12, 4))

        tk.Label(top, text="SM WoT Assistant", font=("Segoe UI", 16, "bold"),
                 fg=ACCENT, bg=BG).pack(side="left")
        self._lbl_admin = tk.Label(top, text=self.t("label_admin"), font=("Segoe UI", 16, "bold"),
                                   fg="#ff4500", bg=BG)
        self._lbl_admin.pack(side="left")
        self._tr_widgets.append((self._lbl_admin, "label_admin"))

        self._settings_btn = tk.Button(top, text="⚙", font=("Segoe UI", 14), bg=BG, fg="#aaa", bd=0,
                                       command=self._show_settings_menu)
        self._settings_btn.pack(side="right", padx=(0, 4))

        self._lang_btn = tk.Button(top, font=("Segoe UI", 10, "bold"), bg=BG, fg=ACCENT, bd=0,
                                   cursor="hand2", command=self._toggle_lang)
        self._lang_btn.pack(side="right", padx=(0, 8))

        self._comm_btn = tk.Button(top, text=self.t("btn_community"), font=("Segoe UI", 9, "bold"),
                                   bg=BG, fg="#88cc88", bd=0, cursor="hand2",
                                   command=self._toggle_community)
        self._comm_btn.pack(side="right", padx=(0, 8))
        self._tr_widgets.append((self._comm_btn, "btn_community"))

        # Status bar
        self.status_lbl = tk.Label(self.root, text=self.t("status_init"), font=("Segoe UI", 10),
                                   fg="#888888", bg=BG, anchor="w")
        self.status_lbl.pack(fill="x", padx=12, pady=(0, 4))
        self._tr_widgets.append((self.status_lbl, "status_init"))

        # Community tiles (overall stats, click → fullscreen Community view)
        self._tiles = self._build_tile_strip(self.root)
        self._tiles["frame"].pack(fill="x", padx=12, pady=(0, 4))
        self._update_tiles()

        # Main content
        content = tk.Frame(self.root, bg=BG)
        content.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        # Left panel: status cards
        left = tk.Frame(content, bg=BG2, padx=12, pady=10)
        left.pack(side="left", fill="y", padx=(0, 8))

        def _card(parent, key):
            f = tk.Frame(parent, bg=BG2, bd=1, relief="solid", highlightbackground="#333")
            lbl = tk.Label(f, text=self.t(key), font=("Segoe UI", 9), fg="#888", bg=BG2)
            lbl.pack(anchor="w")
            self._tr_widgets.append((lbl, key))
            v = tk.Label(f, text="—", font=("Segoe UI", 18, "bold"), fg=ACCENT, bg=BG2)
            v.pack(anchor="w", pady=(2, 0))
            f.pack(fill="x", pady=3)
            return v

        self._card_ver = _card(left, "card_admin_ver")
        self._card_wg = _card(left, "card_wg_ver")
        self._card_status = _card(left, "card_game_status")
        self._card_queue = _card(left, "card_queue")
        self._card_last = _card(left, "card_last_scan")
        self._card_tp = _card(left, "card_tp")

        # Right panel: buttons + log
        right = tk.Frame(content, bg=BG)
        right.pack(side="right", fill="both", expand=True)

        # Buttons
        btn_f = tk.Frame(right, bg=BG)
        btn_f.pack(fill="x", pady=(0, 6))

        self._scan_btn = tk.Button(btn_f, text=self.t("btn_scan"), command=self._scan_now,
                                    bg="#333", fg=FG, bd=0, padx=14, pady=4, cursor="hand2")
        self._scan_btn.pack(side="left", padx=(0, 6))
        self._tr_widgets.append((self._scan_btn, "btn_scan"))

        self._gen_btn = tk.Button(btn_f, text=self.t("btn_gen_queue"), command=self._gen_queue,
                                   bg="#333", fg=FG, bd=0, padx=14, pady=4, cursor="hand2")
        self._gen_btn.pack(side="left", padx=(0, 6))
        self._tr_widgets.append((self._gen_btn, "btn_gen_queue"))

        self._popular_btn = tk.Button(btn_f, text=self.t("btn_gen_popular"), command=self._gen_popular,
                                       bg="#333", fg=FG, bd=0, padx=14, pady=4, cursor="hand2")
        self._popular_btn.pack(side="left", padx=(0, 6))
        self._tr_widgets.append((self._popular_btn, "btn_gen_popular"))

        self._regen_all_btn = tk.Button(btn_f, text=self.t("btn_regen_all"), command=self._gen_all,
                                          bg="#553333", fg=RED, bd=0, padx=14, pady=4, cursor="hand2")
        self._regen_all_btn.pack(side="left")
        self._tr_widgets.append((self._regen_all_btn, "btn_regen_all"))

        # Log
        self.log_text = scrolledtext.ScrolledText(right, bg="#111111", fg="#cccccc",
                                                   insertbackground="#cccccc",
                                                   font=("Consolas", 10), bd=0,
                                                   wrap="word", height=18)
        self.log_text.pack(fill="both", expand=True)
        self.log_text.bind("<Button-3>", self._show_log_menu)

        self.root.bind("<F1>", lambda e: self._show_help())

        self._apply_lang()

    def _show_log_menu(self, event):
        m = tk.Menu(self.root, tearoff=0, bg="#222222", fg=FG,
                    activebackground="#333333", activeforeground=ACCENT, bd=1)
        m.add_command(label=self.t("menu_copy"), command=self._copy_log_selection)
        m.add_separator()
        m.add_command(label=self.t("menu_select_all"),
                      command=lambda: self.log_text.tag_add("sel", "1.0", "end-1c"))
        try:
            m.tk_popup(event.x_root, event.y_root)
        finally:
            m.grab_release()

    def _copy_log_selection(self):
        self._copy_selection(self.log_text)

    def _copy_help_selection(self, txt):
        self._copy_selection(txt)

    def _copy_selection(self, widget):
        try:
            sel = widget.get("sel.first", "sel.last")
        except tk.TclError:
            sel = ""
        if sel:
            self.root.clipboard_clear()
            self.root.clipboard_append(sel)

    def _log(self, msg):
        ts = time.strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        try:
            log_dir = os.path.join(os.environ.get("APPDATA", "."), "SM WoT Assistant")
            os.makedirs(log_dir, exist_ok=True)
            with open(os.path.join(log_dir, "admin.log"), "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except:
            pass
        if hasattr(self, 'log_text') and self.log_text:
            self.log_text.insert("1.0", line + "\n")
            self.log_text.delete("1000.0", tk.END)
            self.log_text.see("1.0")
        else:
            print(line)

    def _update_cards(self):
        self._card_ver.config(text=_read_admin_version())
        self._card_wg.config(text=self._wg_ver or "—")
        if os.path.exists(os.path.join(self._wot_path or "", "version.xml")):
            status = self.t("status_ok")
            color = GREEN
        else:
            status = self.t("status_no_wot")
            color = RED
        self._card_status.config(text=status, fg=color)
        q = len(self._queue)
        self._card_queue.config(text=str(q), fg=ACCENT if q > 0 else "#888")
        self._card_last.config(text=time.strftime("%H:%M") if self._last_scan > 0 else "—")
        try:
            prompts_only, tanks_only = check_prompt_tank_mismatch(self.tank_db, self.prompts)
            mismatch = bool(prompts_only or tanks_only)
            self._card_tp.config(text=f"{len(self.tank_db)} / {len(self.prompts)}",
                                 fg=RED if mismatch else GREEN)
        except Exception:
            self._card_tp.config(text=f"{len(self.tank_db)} / {len(self.prompts)}", fg="#888")

    def _check_tank_prompt_match(self):
        """Лог-перевірка розбіжності Танків/Промптів: [ERROR] з конкретними
        тегами при розбіжності, звичайний рядок при співпадінні (#1604)."""
        self.prompts = load_prompts()
        prompts_only, tanks_only = check_prompt_tank_mismatch(self.tank_db, self.prompts)
        if prompts_only or tanks_only:
            self._log(self.t("log_tp_mismatch", tanks=len(self.tank_db), prompts=len(self.prompts)))
            for tag in prompts_only:
                self._log(self.t("log_tp_orphan_prompt", tag=tag))
            for tag in tanks_only:
                self._log(self.t("log_tp_orphan_tank", tag=tag))
        else:
            self._log(self.t("log_tanks_prompts", tanks=len(self.tank_db), prompts=len(self.prompts)))
        self.root.after(0, self._update_cards)

    # ── Community & Stats ──────────────────────────
    def _build_tile_strip(self, parent):
        frame = tk.Frame(parent, bg=BG)
        tiles = {"frame": frame, "vals": {}, "hints": {}}

        def _tile(key, tab):
            f = tk.Frame(frame, bg=BG2, bd=1, relief="solid", highlightbackground="#333",
                         cursor="hand2")
            f.pack(side="left", padx=(0, 6), fill="x", expand=True)
            t = tk.Label(f, text=self.t("tile_" + key), font=("Segoe UI", 8), fg="#888", bg=BG2)
            t.pack(anchor="w", padx=6, pady=(4, 0))
            v = tk.Label(f, text="—", font=("Segoe UI", 13, "bold"), fg=ACCENT, bg=BG2)
            v.pack(anchor="w", padx=6)
            h = tk.Label(f, text="", font=("Segoe UI", 7), fg="#ffaa00", bg=BG2)
            h.pack(anchor="w", padx=6, pady=(0, 3))
            for wdg in (f, t, v, h):
                wdg.bind("<Button-1>", lambda e, tb=tab: self._open_community_tab(tb))
            self._tr_widgets.append((t, "tile_" + key))
            tiles["vals"][key] = v
            tiles["hints"][key] = h

        _tile("overview", "overview")
        _tile("youtube", "youtube")
        _tile("reddit", "reddit")
        _tile("github", "github")
        _tile("kofi", "kofi")
        _tile("patreon", "patreon")
        _tile("installs", "overview")
        _tile("errors", "errors")
        return tiles

    def _tile_hint(self, status):
        if status in (None, "ok", "idle", "hidden", "empty"):
            return ""
        if status == "no_key":
            return self.t("tile_needs_key")
        if status == "blocked":
            return self.t("tile_blocked")
        if "captcha" in status:
            return self.t("tile_action")
        if status.startswith("needs_"):
            return self.t("tile_needs_login")
        return self.t("tile_error")

    def _update_tiles(self):
        st = self._community["stats"]
        status = self._community["status"]
        for strip in (getattr(self, "_tiles", None), getattr(self, "_tiles_fs", None)):
            if not strip:
                continue
            vals, hints = strip["vals"], strip["hints"]
            vals["overview"].config(
                text=str(st.get("builds_ver")) if st.get("builds_ver") is not None else "—")
            hints["overview"].config(text="")
            yt = st.get("youtube")
            ytv = 0
            if yt and yt.get("channel", {}).get("views"):
                ytv = yt["channel"]["views"]
            elif yt and yt.get("videos"):
                ytv = sum(v.get("views", 0) for v in yt["videos"])
            vals["youtube"].config(text=_fmt_num(ytv) if ytv else "—")
            hints["youtube"].config(text=self._tile_hint(status.get("youtube")))
            gh = st.get("github")
            vals["github"].config(text=_fmt_num(gh.get("total")) if gh else "—")
            hints["github"].config(text="")
            kf = st.get("kofi")
            vals["kofi"].config(text=_fmt_money(kf.get("total")) if kf else "—")
            hints["kofi"].config(text=self._tile_hint(status.get("kofi")))
            red = st.get("reddit")
            vals["reddit"].config(text=_fmt_num(len(red.get("posts", []))) if red else "—")
            hints["reddit"].config(text=self._tile_hint(status.get("reddit")))
            pr = st.get("patreon")
            vals["patreon"].config(text=_fmt_num(pr.get("patrons", 0)) if pr else "—")
            hints["patreon"].config(text=self._tile_hint(status.get("patreon")))
            vals["installs"].config(text=str(st.get("installs")) if st.get("installs") is not None else "—")
            hints["installs"].config(text="")
            vals["errors"].config(text=str(st.get("errors")) if st.get("errors") is not None else "—")
            hints["errors"].config(text="")

    def _open_community_tab(self, tab):
        if not self._community.get("fs"):
            self._enter_community(target_tab=tab)
            return
        self._select_tab(tab)
        # Explicit navigation — selecting the tab of the ALREADY active tab
        # fires no <<NotebookTabChanged>> event, so the tile would do nothing.
        self._navigate_platform_tab(tab)

    def _select_tab(self, tab):
        if hasattr(self, "_nb"):
            try:
                self._nb.select(self._tab_ix.get(tab, 0))
            except Exception:
                pass

    def _navigate_platform_tab(self, tab):
        """Load the platform's admin page into the visible embedded browser
        when the user switches to that tab (manual control — the browser
        always shows the page of the active tab)."""
        if tab in ("apikeys", "errors"):
            return
        url = _COMMUNITY_PAGE_URLS.get(tab)
        if tab == "youtube":
            # The channel page (handle URL) — never autoplay a video.
            url = _YT_CHANNEL_URL
        if not url:
            return

        def _go():
            try:
                drv = self._community_ensure_browser(self._community.get("fs"))
                if drv is None:
                    return
                handles = drv.window_handles
                if handles:
                    # Navigate the user's main tab only — a background fetch
                    # tab (CDP createTarget) may be the current one mid-fetch;
                    # navigation must never land there (and must not open a
                    # new tab either).
                    drv.switch_to.window(handles[0])
                drv.get(url)
            except Exception:
                pass

        threading.Thread(target=_go, daemon=True).start()

    def _on_nb_tab_changed(self, event=None):
        try:
            ix = self._nb.index(self._nb.select())
            for name, i in self._tab_ix.items():
                if i == ix:
                    self._navigate_platform_tab(name)
                    return
        except Exception:
            pass

    def _toggle_community(self):
        if self._community.get("fs"):
            self._exit_community()
        else:
            self._enter_community()

    def _enter_community(self, target_tab=None):
        if self._community.get("fs"):
            return
        self._community["fs"] = True
        if not hasattr(self, "_comm_root"):
            self._build_community_ui()
        self._comm_root.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.root.attributes("-fullscreen", True)
        self.root.focus_force()
        self.root.bind("<Escape>", lambda e: self._exit_community())
        if self._community.get("driver") is None:
            threading.Thread(target=lambda: self._community_ensure_browser(True), daemon=True).start()
        # Tile entry (target_tab set): select the tile's tab immediately so
        # the browser navigates straight to the tile's page — no Overview
        # flash in between. Community-button entry: Overview as usual.
        self._select_tab(target_tab or "overview")
        self.root.after(500, self._community_show_browser)
        self.root.after(200, self._community_poll_embed)

        def _nav_to():
            if self._community.get("creating"):
                self.root.after(1000, _nav_to)
                return
            self._navigate_platform_tab(target_tab or "overview")

        self.root.after(1200, _nav_to)
        self._refresh_community_background()
        self._update_comm_tabs()

    def _exit_community(self):
        if not self._community.get("fs"):
            return
        self._community["fs"] = False
        self.root.attributes("-fullscreen", False)
        try:
            self._comm_root.place_forget()
        except Exception:
            pass
        self.root.unbind("<Escape>")
        self._community_move_browser_offscreen()
        self._community_clear_action()

    def _build_community_ui(self):
        self._comm_root = tk.Frame(self.root, bg=BG)
        main = tk.Frame(self._comm_root, bg=BG)
        main.pack(fill="both", expand=True, padx=12, pady=(8, 6))
        main.grid_columnconfigure(0, weight=3, minsize=480)
        main.grid_columnconfigure(1, weight=2, minsize=480)
        main.grid_rowconfigure(0, weight=1)
        left = tk.Frame(main, bg=BG)
        left.grid(row=0, column=0, sticky="nsew")
        right = tk.Frame(main, bg=BG)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        hdr = tk.Frame(left, bg=BG)
        hdr.pack(fill="x")
        tk.Label(hdr, text=self.t("comm_fs_hint"), font=("Segoe UI", 8), fg="#666", bg=BG).pack(side="left")
        self._tiles_fs = self._build_tile_strip(left)
        self._tiles_fs["frame"].pack(fill="x", pady=(4, 4))
        self._update_tiles()
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background="#333", foreground=FG,
                        padding=[10, 4], font=("Segoe UI", 9))
        style.map("TNotebook.Tab", background=[("selected", ACCENT)],
                  foreground=[("selected", "#000")])
        style.configure("Treeview", background="#111111", fieldbackground="#111111",
                        foreground=FG, borderwidth=0, rowheight=22, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", background="#333", foreground=FG,
                        font=("Segoe UI", 9, "bold"))
        style.map("Treeview", background=[("selected", "#444")], foreground=[("selected", FG)])
        self._nb = ttk.Notebook(left)
        self._nb.pack(fill="both", expand=True, pady=(4, 0))
        self._nb.bind("<<NotebookTabChanged>>", self._on_nb_tab_changed)
        self._tab_status = {}
        self._trees = {}
        self._tab_ix = {}
        ov = tk.Frame(self._nb, bg=BG)
        self._nb.add(ov, text=self.t("tab_overview"))
        self._tab_ix["overview"] = 0
        self._build_overview_tab(ov)
        defs = [
            ("youtube", ("video", "date", "views", "likes", "comments")),
            ("reddit", ("post", "date", "score", "comments")),
            ("github", ("release", "date", "downloads")),
            ("kofi", ("date", "amount", "type")),
            ("patreon", ("field", "value")),
        ]
        i = 1
        for name, cols in defs:
            tab = tk.Frame(self._nb, bg=BG)
            self._nb.add(tab, text=self.t("tab_" + name))
            self._tab_ix[name] = i
            i += 1
            top = tk.Frame(tab, bg=BG)
            top.pack(fill="x", padx=8, pady=(6, 2))
            st = tk.Label(top, text=self.t("st_loading"), font=("Segoe UI", 9), fg="#888", bg=BG)
            st.pack(side="left")
            self._tab_status[name] = st
            tk.Button(top, text=self.t("btn_refresh"), bg="#333", fg=FG, bd=0,
                      padx=10, pady=2, cursor="hand2",
                      command=lambda n=name: self._community_refresh_tab(n)).pack(side="right")
            if name in ("reddit", "kofi"):
                tk.Button(top, text=self.t("btn_link"), bg="#2a5a2a", fg=FG, bd=0,
                          padx=10, pady=2, cursor="hand2",
                          command=lambda n=name: self._community_link_platform(n)).pack(side="right")
            tree_f, tree = self._make_tree(tab, cols)
            tree_f.pack(fill="both", expand=True, padx=8, pady=(0, 8))
            self._trees[name] = tree
        ak = tk.Frame(self._nb, bg=BG)
        self._nb.add(ak, text=self.t("tab_apikeys"))
        self._tab_ix["apikeys"] = i
        self._build_apikeys_tab(ak)
        er = tk.Frame(self._nb, bg=BG)
        self._nb.add(er, text=self.t("tab_errors"))
        self._tab_ix["errors"] = i + 1
        top = tk.Frame(er, bg=BG)
        top.pack(fill="x", padx=8, pady=(6, 2))
        st = tk.Label(top, text=self.t("st_loading"), font=("Segoe UI", 9), fg="#888", bg=BG)
        st.pack(side="left")
        self._tab_status["errors"] = st
        tk.Button(top, text=self.t("btn_refresh"), bg="#333", fg=FG, bd=0,
                  padx=10, pady=2, cursor="hand2",
                  command=lambda: self._community_refresh_tab("errors")).pack(side="right")
        tree_f, tree = self._make_tree(er, ("time", "type", "source", "version", "error"))
        tree_f.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._trees["errors"] = tree
        self._banner_lbl = tk.Label(left, text="", bg="#1a1a1a", fg="#ffaaaa",
                                    font=("Segoe UI", 10, "bold"))
        self._banner_lbl.pack(fill="x", pady=(4, 0))
        self._browser_frame = tk.Frame(right, bg="#000")
        self._browser_frame.pack(fill="both", expand=True)
        self._browser_frame.bind("<Configure>", self._on_browser_frame_configure)
        self._update_comm_tabs()

    def _make_tree(self, parent, cols):
        widths = {"video": 340, "date": 100, "views": 80, "likes": 70, "comments": 80,
                  "post": 360, "score": 70, "release": 150, "downloads": 100,
                  "amount": 100, "type": 120, "time": 110, "source": 170,
                  "version": 90, "error": 300, "field": 160, "value": 120}
        frame = tk.Frame(parent, bg=BG)
        tree = ttk.Treeview(frame, columns=cols, show="headings", height=10)
        for c in cols:
            tree.heading(c, text=self.t("col_" + c))
            tree.column(c, width=widths.get(c, 120), anchor="w" if c in ("video", "post", "release") else "e")
        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        return frame, tree

    def _build_overview_tab(self, parent):
        self._ov_labels = {}
        body = tk.Frame(parent, bg=BG)
        body.pack(fill="both", expand=True, padx=10, pady=8)
        tk.Label(body, text=self.t("ov_social"), font=("Segoe UI", 10, "bold"),
                 fg=ACCENT, bg=BG).pack(anchor="w")
        row = tk.Frame(body, bg=BG)
        row.pack(anchor="w", pady=(2, 8))

        def _link(txt, url):
            tk.Button(row, text=txt, bg="#333", fg=FG, bd=0, padx=10, pady=3, cursor="hand2",
                      command=lambda: webbrowser.open(url)).pack(side="left", padx=(0, 6))

        _link("YouTube", _YT_CHANNEL_URL)
        _link("Reddit", "https://www.reddit.com/user/" + _REDDIT_USER + "/")
        _link("GitHub", "https://github.com/" + _GITHUB_REPO + "/releases")
        _link("Website", "https://sm-wot-assistant.web.app")
        tk.Label(body, text=self.t("ov_donations"), font=("Segoe UI", 10, "bold"),
                 fg=ACCENT, bg=BG).pack(anchor="w")
        row2 = tk.Frame(body, bg=BG)
        row2.pack(anchor="w", pady=(2, 4))
        _link("Ko-fi", "https://ko-fi.com/smwotassistant")
        _link("Monobank", "https://send.monobank.ua/jar/WqyWjTRpy")
        _link("Patreon", _PATREON_URL)
        tk.Label(row2, text="PayPal — " + self.t("st_paypal_qr"), font=("Segoe UI", 9),
                 fg="#888", bg=BG).pack(side="left", padx=(6, 0))
        tk.Label(body, text=self.t("ov_rtdb"), font=("Segoe UI", 10, "bold"),
                 fg=ACCENT, bg=BG).pack(anchor="w", pady=(8, 2))
        grid = tk.Frame(body, bg=BG)
        grid.pack(anchor="w")
        defs = [("installs", "ov_installs"), ("errors", "ov_errors"), ("schemes", "ov_schemes"),
                ("users", "ov_users"), ("builds_ver", "ov_builds_ver"), ("last_gen", "ov_last_gen")]
        for idx, (key, lkey) in enumerate(defs):
            cell = tk.Frame(grid, bg=BG2, bd=1, relief="solid", highlightbackground="#333")
            cell.grid(row=idx // 3, column=idx % 3, padx=4, pady=4, sticky="nsew")
            tk.Label(cell, text=self.t(lkey), font=("Segoe UI", 8), fg="#888", bg=BG2
                     ).pack(anchor="w", padx=6, pady=(4, 0))
            v = tk.Label(cell, text="—", font=("Segoe UI", 12, "bold"), fg=ACCENT, bg=BG2)
            v.pack(anchor="w", padx=6, pady=(0, 4))
            self._ov_labels[key] = v
        self._ov_byver = tk.Label(body, text="", font=("Segoe UI", 8), fg="#999", bg=BG,
                                  justify="left", wraplength=700, anchor="w")
        self._ov_byver.pack(anchor="w", pady=(2, 4))
        tk.Label(body, text=self.t("ov_sources"), font=("Segoe UI", 10, "bold"),
                 fg=ACCENT, bg=BG).pack(anchor="w", pady=(6, 2))
        self._ov_src = {}
        for name in ("youtube", "reddit", "github", "kofi", "patreon"):
            r = tk.Frame(body, bg=BG)
            r.pack(anchor="w")
            tk.Label(r, text=self.t("tab_" + name) + ":", font=("Segoe UI", 9),
                     fg="#aaa", bg=BG, width=12, anchor="w").pack(side="left")
            v = tk.Label(r, text="—", font=("Segoe UI", 9), fg="#888", bg=BG)
            v.pack(side="left")
            self._ov_src[name] = v
        tk.Label(body, text=self.t("st_yt_manual_login"), font=("Segoe UI", 8),
                 fg="#777", bg=BG).pack(anchor="w", pady=(6, 0))

    def _build_apikeys_tab(self, parent):
        body = tk.Frame(parent, bg=BG)
        body.pack(fill="both", expand=True, padx=10, pady=8)
        tk.Label(body, text=self.t("key_clear"), font=("Segoe UI", 8), fg="#888", bg=BG
                 ).pack(anchor="w", pady=(0, 6))
        fields = [
            ("youtube", "api_key", "key_youtube_api", False),
            ("reddit", "username", "key_reddit_user", False),
            ("reddit", "password", "key_reddit_pass", True),
            ("kofi", "username", "key_kofi_email", False),
            ("kofi", "password", "key_kofi_pass", True),
            ("kofi", "client_id", "key_kofi_client_id", False),
            ("kofi", "client_secret", "key_kofi_secret", True),
            ("kofi", "refresh_token", "key_kofi_token", True),
        ]
        self._key_entries = {}
        for service, field, key, secret in fields:
            row = tk.Frame(body, bg=BG)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=self.t(key), font=("Segoe UI", 9), fg=FG, bg=BG,
                     width=24, anchor="w").pack(side="left")
            e = tk.Entry(row, bg="#222", fg=FG, bd=0, insertbackground=FG,
                         show="*" if secret else "")
            e.pack(side="left", fill="x", expand=True, ipady=2)
            if vault_has(service, field):
                e.insert(0, "•" * 8)
            self._bind_entry_menu(e)
            self._key_entries[(service, field)] = e
        btns = tk.Frame(body, bg=BG)
        btns.pack(fill="x", pady=(8, 0))
        tk.Button(btns, text=self.t("btn_save_keys"), bg="#333", fg=FG, bd=0,
                  padx=16, pady=4, cursor="hand2", command=self._save_apikeys).pack(side="left", padx=(0, 8))
        tk.Button(btns, text=self.t("btn_reset_browser"), bg="#553333", fg=RED, bd=0,
                  padx=16, pady=4, cursor="hand2", command=self._reset_browser_data).pack(side="left")
        self._keys_msg = tk.Label(body, text="", font=("Segoe UI", 9), fg=GREEN, bg=BG)
        self._keys_msg.pack(anchor="w", pady=(6, 0))

    def _save_apikeys(self):
        for (service, field), e in self._key_entries.items():
            val = e.get().strip()
            if val and val != "•" * 8:
                vault_set(service, field, val)
            elif not val and vault_has(service, field):
                vault_delete_field(service, field)
        for (service, field), e in self._key_entries.items():
            e.delete(0, tk.END)
            if vault_has(service, field):
                e.insert(0, "•" * 8)
        self._keys_msg.config(text=self.t("key_saved"))
        self._log(self.t("key_saved"))

    def _bind_entry_menu(self, entry):
        m = tk.Menu(entry, tearoff=0, bg="#222", fg=FG)
        m.add_command(label=self.t("menu_cut"), command=lambda: entry.event_generate("<<Cut>>"))
        m.add_command(label=self.t("menu_copy"), command=lambda: entry.event_generate("<<Copy>>"))
        m.add_command(label=self.t("menu_paste"), command=lambda: entry.event_generate("<<Paste>>"))
        m.add_command(label=self.t("menu_select_all"), command=lambda: entry.event_generate("<<SelectAll>>"))
        def show(e):
            try:
                m.tk_popup(e.x_root, e.y_root)
            finally:
                m.grab_release()
        entry.bind("<Button-3>", show)

    def _reset_browser_data(self):
        def _work():
            self._community_kill_browser()
            shutil.rmtree(_COMMUNITY_PROFILE_DIR, ignore_errors=True)
            self._log(self.t("log_comm_reset"))
        threading.Thread(target=_work, daemon=True).start()

    def _fill_tree(self, tree, rows):
        try:
            tree.delete(*tree.get_children())
            for row in rows:
                tree.insert("", "end", values=row)
        except Exception:
            pass

    def _set_tab_status(self, name, status):
        lbl = self._tab_status.get(name)
        if not lbl:
            return
        if name in ("reddit", "kofi") and status in (None, "ok", "idle", "empty"):
            if self._community["linked"].get(name):
                text, color = "\u2713 " + self.t("st_linked"), GREEN
            else:
                text, color = self.t("st_not_linked"), "#888"
        elif status in (None, "ok"):
            text, color = self.t("st_ok"), GREEN
        elif status in ("idle", "hidden"):
            text, color = self.t("st_not_conf") if status == "hidden" else self.t("st_loading"), "#888"
        elif status == "no_key":
            text, color = self.t("st_no_key"), "#888"
        elif status == "blocked":
            text, color = self.t("st_blocked"), RED
        elif status.startswith("needs_"):
            text, color = self.t("tile_needs_login") + " (" + status + ")", "#ffaa00"
        elif "captcha" in status:
            text, color = self.t("act_captcha"), "#ffaa00"
        else:
            text, color = self.t("st_error") + ": " + status, RED
        lbl.config(text=text, fg=color)

    def _update_comm_tabs(self):
        if not hasattr(self, "_trees"):
            return
        st = self._community["stats"]
        status = self._community["status"]
        yt = st.get("youtube")
        rows = []
        if yt and yt.get("videos"):
            for v in yt["videos"]:
                rows.append((v.get("title", ""), v.get("date", ""),
                             _fmt_num(v.get("views", 0)), _fmt_num(v.get("likes", 0)),
                             _fmt_num(v.get("comments", 0))))
        self._fill_tree(self._trees["youtube"], rows)
        self._set_tab_status("youtube", status.get("youtube"))
        red = st.get("reddit")
        rows = []
        if red and red.get("posts"):
            for p in red["posts"]:
                rows.append((p.get("title", ""), p.get("date", ""),
                             _fmt_num(p.get("score", 0)), _fmt_num(p.get("comments", 0))))
        self._fill_tree(self._trees["reddit"], rows)
        self._set_tab_status("reddit", status.get("reddit"))
        gh = st.get("github")
        rows = []
        if gh and gh.get("releases"):
            for r_ in gh["releases"]:
                rows.append((r_.get("tag", ""), r_.get("date", ""),
                             _fmt_num(r_.get("downloads", 0))))
        self._fill_tree(self._trees["github"], rows)
        self._set_tab_status("github", status.get("github"))
        kf = st.get("kofi")
        rows = []
        if kf and kf.get("amounts"):
            for i, a in enumerate(kf["amounts"]):
                rows.append(("", _fmt_money(a), "donation"))
        self._fill_tree(self._trees["kofi"], rows)
        self._set_tab_status("kofi", status.get("kofi"))
        pr = st.get("patreon")
        rows = []
        if pr:
            rows.append((self.t("col_patrons"), _fmt_num(pr.get("patrons", 0))))
            rows.append((self.t("col_paid"), _fmt_num(pr.get("paid", 0))))
            rows.append((self.t("col_pledge"),
                         _fmt_money(pr.get("pledge", 0)) + " " + str(pr.get("currency") or "").upper()))
            rows.append((self.t("col_posts"), _fmt_num(pr.get("posts", 0))))
            rows.append((self.t("col_created"), str(pr.get("created") or "—")))
        self._fill_tree(self._trees["patreon"], rows)
        self._set_tab_status("patreon", status.get("patreon"))
        el = st.get("errors_list")
        rows = []
        if el:
            for r_ in el:
                rows.append((_fmt_ts(r_.get("time")), r_.get("type"),
                             r_.get("source") or r_.get("stage"),
                             r_.get("version"), r_.get("error")[:140]))
        self._fill_tree(self._trees["errors"], rows)
        self._set_tab_status("errors", status.get("errors"))
        ov = self._ov_labels
        ov["installs"].config(text=str(st.get("installs")) if st.get("installs") is not None else "—")
        ov["errors"].config(text=str(st.get("errors")) if st.get("errors") is not None else "—")
        ov["schemes"].config(text=str(st.get("schemes")) if st.get("schemes") is not None else "—")
        ov["users"].config(text=str(st.get("users")) if st.get("users") is not None else "—")
        ov["builds_ver"].config(text=str(st.get("builds_ver")) if st.get("builds_ver") is not None else "—")
        lg = st.get("last_generated_at") or ""
        ov["last_gen"].config(text=str(lg)[:19] if lg else "—")
        byver = st.get("installs_by_ver") or {}
        if byver:
            top = sorted(byver.items(), key=lambda kv: -kv[1])[:10]
            self._ov_byver.config(text=self.t("ov_installs_by_ver") + ": " +
                                  ", ".join(f"{k} = {v}" for k, v in top))
        else:
            self._ov_byver.config(text="")
        for name in ("youtube", "reddit", "github", "kofi", "patreon"):
            s = status.get(name)
            if s == "ok":
                text, color = self.t("st_ok"), GREEN
            elif s in ("idle", "hidden"):
                text, color = self.t("st_loading"), "#888"
            elif s == "no_key":
                text, color = self.t("st_no_key"), "#888"
            elif s == "blocked":
                text, color = self.t("st_blocked"), RED
            elif s and s.startswith("needs_"):
                text, color = self.t("tile_needs_login") + " (" + s + ")", "#ffaa00"
            elif s and "captcha" in s:
                text, color = self.t("act_captcha"), "#ffaa00"
            elif s:
                text, color = self.t("st_error") + ": " + s, RED
            else:
                text, color = "—", "#888"
            self._ov_src[name].config(text=text, fg=color)

    def _community_action_needed(self, msg):
        self._community["action"] = msg
        self.root.after(0, self._update_comm_banner)
        try:
            self.tray.show_notification(self.t("notif_community_action"), msg, level="error")
        except Exception:
            pass

    def _community_clear_action(self):
        self._community["action"] = None
        self.root.after(0, self._update_comm_banner)

    def _update_comm_banner(self):
        if hasattr(self, "_banner_lbl"):
            msg = self._community.get("action") or ""
            self._banner_lbl.config(text=msg, bg="#552222" if msg else "#1a1a1a")
        self._update_tiles()

    def _app_visible(self):
        try:
            return self.root.state() == "normal"
        except Exception:
            return False

    def _community_ensure_browser(self, visible):
        """Lazy driver lifecycle bound to app visibility (no Chrome in tray)."""
        if self._community.get("creating"):
            return None
        self._community["creating"] = True
        try:
            return self._community_ensure_browser_inner(visible)
        finally:
            self._community["creating"] = False

    def _community_ensure_browser_inner(self, visible):
        drv = self._community.get("driver")
        if drv is not None:
            try:
                drv.current_url
            except Exception:
                drv = None
                self._community["driver"] = None
                self._community["hwnd"] = None
                self._community["tg_started"] = False
            else:
                # Visibility is managed by the embed/offscreen lifecycle —
                # NEVER quit here: calls during browser creation (visible=False
                # while fs=True) used to kill the fresh browser repeatedly, so
                # it never got embedded ('no browser at all' symptom).
                return drv
        try:
            self._log(self.t("log_comm_start"))
            _kill_chrome_matching(_COMMUNITY_PROFILE_DIR)
            if not os.path.isdir(_COMMUNITY_PROFILE_DIR):
                try:
                    _kill_chrome_matching(_COMMUNITY_PROFILE_DIR)
                    _copy_chrome_profile(CHROME_PROFILE, _COMMUNITY_PROFILE_DIR)
                except Exception as e:
                    self._log(self.t("log_comm_error", err="profile seed: %s" % e))
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
            opts = Options()
            opts.add_argument(f"--user-data-dir={_COMMUNITY_PROFILE_DIR}")
            opts.add_argument(f"--profile-directory={CHROME_PROFILE_DIR}")
            opts.add_argument("--disable-blink-features=AutomationControlled")
            opts.add_argument("--no-first-run")
            opts.add_argument("--no-default-browser-check")
            opts.add_argument("--window-size=1400,900")
            opts.add_argument("--window-position=-32000,-32000")
            opts.add_argument("--disable-session-crashed-bubble")
            _fix_crashed_profile_prefs()
            opts.add_experimental_option("excludeSwitches", ["enable-automation"])
            opts.add_experimental_option("useAutomationExtension", False)
            last_err = None
            for attempt in (1, 2, 3):
                try:
                    drv = webdriver.Chrome(options=opts,
                                           service=Service(creation_flags=subprocess.CREATE_NO_WINDOW))
                    break
                except Exception as e:
                    last_err = e
                    msg = str(e)
                    if not any(m in msg for m in _DRIVER_RETRY_MARKERS):
                        raise
                    time.sleep(3 if attempt < 3 else 15)
                    _kill_chrome_matching(_COMMUNITY_PROFILE_DIR)
            else:
                raise RuntimeError("Chrome driver failed: %s" % str(last_err)[:120])
            drv.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": """
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US','en'] });
                """})
            self._community["driver"] = drv
            self._community["visible"] = False
            self._community["hwnd"] = None
            self._start_toolwindow_guard()
        except Exception as e:
            self._log(self.t("log_comm_error", err=str(e)[:150]))
            self._community["driver"] = None
            return None
        if visible or self._community.get("fs"):
            self._community_show_browser()
        return drv

    def _community_show_browser(self):
        """Request embedding of the Chrome window into the app frame.

        Thread-safe: the heavy HWND lookup (PowerShell/ctypes) runs in a worker
        thread and only sets a flag; the actual Tkinter embed is done by
        _community_poll_embed on the main thread. No Tk calls from worker
        threads — those used to raise 'main thread is not in main loop' and
        silently skip the embed."""
        drv = self._community.get("driver")
        if drv is None or self._community.get("visible"):
            return

        def _locate():
            for _ in range(10):  # Chrome window may appear a moment after driver start
                drv = self._community.get("driver")
                if drv is None or self._community.get("visible"):
                    return
                pid = _chrome_main_pid(_COMMUNITY_PROFILE_DIR)
                hwnd = _find_hwnd_by_pid(pid) if pid else None
                if hwnd:
                    self._community["hwnd"] = hwnd
                    self._community["chrome_pid"] = pid
                    self._community["embed_pending"] = True
                    self._log("[DEBUG][locate] pid=%s hwnd=%s" % (pid, hwnd))
                    return
                time.sleep(1)

        threading.Thread(target=_locate, daemon=True).start()

    def _community_poll_embed(self):
        """Main thread only (root.after loop): embed the located Chrome window
        and keep it embedded. Retries every 200ms until the frame is mapped
        (winfo_id != 0) and SetParent actually succeeded; keeps watching —
        if Chrome re-creates its window (e.g. last-tab close), the new main
        window is found and embedded again instead of lingering offscreen
        with a taskbar icon."""
        if not self._community.get("fs"):
            return
        hwnd = self._community.get("hwnd")
        if hwnd and not _hwnd_alive(hwnd):
            hwnd = None
            self._community["hwnd"] = None
            self._community["visible"] = False
        if hwnd is None:
            pid = self._community.get("chrome_pid")
            if pid:
                new_hwnd = _find_hwnd_by_pid(pid)
                if new_hwnd:
                    self._community["hwnd"] = new_hwnd
                    hwnd = new_hwnd
        if hwnd and not self._community.get("visible"):
            try:
                if hasattr(self, "_browser_frame"):
                    frame_id = self._browser_frame.winfo_id()
                    if frame_id:
                        w = max(self._browser_frame.winfo_width(), 200)
                        h = max(self._browser_frame.winfo_height(), 200)
                        ok = _embed_hwnd(hwnd, frame_id, w, h)
                        self._log("[DEBUG][embed] frame_id=%s %sx%s ok=%s" % (frame_id, w, h, ok))
                        if ok:
                            self._community["visible"] = True
            except Exception:
                pass
        # Keyboard focus belongs to the embedded Chrome whenever the cursor is
        # over it (every poll, not only after a click). A WS_CHILD window of
        # another process never takes focus from a plain click — without this,
        # typing / Ctrl+V goes to the Tk root whenever the user hovers the
        # browser without clicking (or right after Tk stole focus, e.g.
        # _enter_community → root.focus_force()). The old one-shot SetFocus
        # (150 ms after embed) and click-gated SetFocus raced the renderer and
        # the poll window — paste "sometimes didn't work" (#1604).
        if hwnd and self._community.get("visible"):
            try:
                if _cursor_over_hwnd(hwnd):
                    ctypes.windll.user32.SetFocus(hwnd)
            except Exception:
                pass
        self.root.after(200, self._community_poll_embed)

    def _open_bg_tab(self, drv):
        """Open a NEW BACKGROUND tab WITHOUT activating it in the UI: CDP
        Target.createTarget, then Target.activateTarget back to the user's
        tab — fetch navigations never show in the visible tab (the 'settings
        page -> black JSON page -> Google' symptom). Falls back to a regular
        tab (immediately blanked) when CDP is unavailable. Returns the new
        tab handle, or None to work in the current tab."""
        try:
            main_handle = drv.current_window_handle
        except Exception:
            main_handle = None
        try:
            before = set(drv.window_handles)
            drv.execute_cdp_cmd("Target.createTarget", {"url": "about:blank"})
            time.sleep(0.3)
            new_handles = [h for h in drv.window_handles if h not in before]
            if new_handles:
                bg = new_handles[-1]
                # Order matters: switch_to.window() ACTIVATES the tab in the
                # Chrome UI, so activateTarget(main) must come AFTER it —
                # only then does the UI stay on the user's tab while the
                # Selenium context keeps working on the background tab.
                drv.switch_to.window(bg)
                if main_handle:
                    try:
                        drv.execute_cdp_cmd("Target.activateTarget", {"targetId": main_handle})
                    except Exception:
                        pass
                self._log("[DEBUG][bgtab] cdp=ok bg=%s" % bg)
                return bg
            self._log("[DEBUG][bgtab] cdp=no_new_tab")
        except Exception as e:
            self._log("[DEBUG][bgtab] cdp=fail:%s -> fallback" % str(e)[:80])
            try:
                drv.switch_to.new_window("tab")
                if main_handle:
                    try:
                        drv.execute_cdp_cmd("Target.activateTarget", {"targetId": main_handle})
                    except Exception:
                        pass
                try:
                    drv.get("about:blank")
                except Exception:
                    pass
                return drv.current_window_handle
            except Exception:
                return None
        return None

    def _community_move_browser_offscreen(self):
        hwnd = self._community.get("hwnd")
        self._community["visible"] = False
        if hwnd:
            _unembed_hwnd(hwnd)
            _move_hwnd(hwnd, -32000, -32000, 1400, 900)

    def _start_toolwindow_guard(self):
        """Daemon while the driver lives: every Chrome window of the community
        profile gets WS_EX_TOOLWINDOW (no taskbar buttons ever), and the
        tracked Chrome pid is kept current so re-created windows are found."""
        if self._community.get("tg_started"):
            return
        self._community["tg_started"] = True

        def _loop():
            while self._community.get("driver") is not None:
                try:
                    pid = self._community.get("chrome_pid")
                    if pid and _pid_alive(pid):
                        for h in _top_level_windows(pid):
                            _toolwindow_hwnd(h)
                    else:
                        pid = _chrome_main_pid(_COMMUNITY_PROFILE_DIR)
                        if pid:
                            self._community["chrome_pid"] = pid
                            for h in _top_level_windows(pid):
                                _toolwindow_hwnd(h)
                except Exception:
                    pass
                time.sleep(3)

        threading.Thread(target=_loop, daemon=True).start()

    def _community_kill_browser(self):
        drv = self._community.get("driver")
        self._community["driver"] = None
        self._community["hwnd"] = None
        self._community["visible"] = False
        self._community["tg_started"] = False
        if drv is not None:
            try:
                drv.quit()
            except Exception:
                pass
        _kill_chrome_matching(_COMMUNITY_PROFILE_DIR)
        self._log(self.t("log_comm_kill"))

    def _on_browser_frame_configure(self, e):
        if getattr(e, "widget", None) is not self._browser_frame:
            return
        hwnd = self._community.get("hwnd")
        if hwnd:
            self.root.after_idle(self._sync_browser_geometry)

    def _sync_browser_geometry(self):
        hwnd = self._community.get("hwnd")
        if not hwnd or not self._community.get("fs"):
            return
        try:
            w = self._browser_frame.winfo_width()
            h = self._browser_frame.winfo_height()
            if w > 10 and h > 10:
                _move_hwnd(hwnd, 0, 0, w, h)
        except Exception:
            pass

    def _find_elem(self, drv, selectors):
        for by, sel in selectors:
            try:
                return drv.find_element(by, sel)
            except Exception:
                continue
        return None

    def _refresh_community_background(self):
        if self._community.get("refreshing"):
            return
        self._community["refreshing"] = True

        def _work():
            try:
                self._fetch_rtdb_counters()
                el, st_e = self._fetch_errors_list()
                if el:
                    self._community["stats"]["errors_list"] = el
                    self._community["status"]["errors"] = "ok"
                elif st_e:
                    self._community["status"]["errors"] = st_e
                self._community["stats"]["github"], st = self._fetch_github()
                self._community["status"]["github"] = st or "ok"
                yt = None
                if vault_has("youtube", "api_key"):
                    yt, st = self._fetch_yt_api()
                    self._community["status"]["youtube"] = st or "ok"
                else:
                    self._community["status"]["youtube"] = "no_key"
                if not yt and self._app_visible():
                    yt, st = self._fetch_yt_chrome()
                    self._community["status"]["youtube"] = st or "ok"
                if yt:
                    self._community["stats"]["youtube"] = yt
                red, st = self._fetch_reddit_http()
                if red:
                    self._community["stats"]["reddit"] = red
                    self._community["status"]["reddit"] = "ok"
                else:
                    self._community["status"]["reddit"] = st or "error"
                    if self._app_visible():
                        red2, st2 = self._fetch_reddit_chrome()
                        if red2:
                            self._community["stats"]["reddit"] = red2
                            self._community["status"]["reddit"] = "ok"
                        else:
                            self._community["status"]["reddit"] = st2 or "error"
                if self._app_visible():
                    kf, st3 = self._fetch_kofi_chrome()
                    if kf:
                        self._community["stats"]["kofi"] = kf
                        self._community["status"]["kofi"] = "ok"
                    else:
                        self._community["status"]["kofi"] = st3 or "error"
                else:
                    self._community["status"]["kofi"] = "hidden"
                pr, stp = self._fetch_patreon()
                if pr:
                    self._community["stats"]["patreon"] = pr
                self._community["status"]["patreon"] = stp or "ok"
            except Exception as e:
                self._log(self.t("log_comm_error", err=str(e)[:200]))
            finally:
                self._community["refreshing"] = False
                _save_community_cache(self._community["stats"])
                self._log("[DEBUG][fetch] yt=%s red=%s kofi=%s gh=%s patreon=%s" % (
                    self._community["status"].get("youtube"),
                    self._community["status"].get("reddit"),
                    self._community["status"].get("kofi"),
                    self._community["status"].get("github"),
                    self._community["status"].get("patreon")))
                self.root.after(0, self._update_tiles)
                self.root.after(0, self._update_comm_tabs)

        threading.Thread(target=_work, daemon=True).start()

    def _community_refresh_tab(self, name):
        if self._community.get("refreshing"):
            return
        self._community["refreshing"] = True
        self._set_tab_status(name, "idle")

        def _work():
            try:
                if name == "github":
                    res, st = self._fetch_github()
                elif name == "youtube":
                    res, st = self._fetch_yt_api()
                    if not res:
                        res, st = self._fetch_yt_chrome()
                elif name == "reddit":
                    res, st = self._fetch_reddit_http()
                    if not res:
                        res, st = self._fetch_reddit_chrome()
                elif name == "errors":
                    res, st = self._fetch_errors_list()
                elif name == "patreon":
                    res, st = self._fetch_patreon()
                else:
                    res, st = self._fetch_kofi_chrome()
                if res:
                    self._community["stats"]["errors_list" if name == "errors" else name] = res
                    self._community["status"][name] = "ok"
                else:
                    self._community["status"][name] = st or "error"
            except Exception as e:
                self._community["status"][name] = str(e)[:100]
            finally:
                self._community["refreshing"] = False
                _save_community_cache(self._community["stats"])
                if name in ("reddit", "kofi"):
                    self._remember_linked(name, self._community["status"].get(name) in ("ok", "empty"))
                st_now = self._community["status"].get(name)
                if st_now and st_now not in ("ok", "empty", "idle", "hidden", "no_key"):
                    self._community_action_needed("%s: %s" % (name, st_now))
                self._log("[DEBUG][fetch] tab=%s -> %s" % (
                    name, self._community["status"].get(name)))
                self.root.after(0, self._update_tiles)
                self.root.after(0, self._update_comm_tabs)

        threading.Thread(target=_work, daemon=True).start()

    def _remember_linked(self, name, linked):
        """Persist the platform linked state forever (admin_settings.json)."""
        self._community["linked"][name] = bool(linked)
        self._admin_settings["community_linked"] = dict(self._community["linked"])
        _save_admin_settings(self._admin_settings)

    def _community_link_platform(self, name):
        """Link button: verify the browser session for a platform and remember
        the linked state forever, without waiting for the 10-min cycle."""
        if self._community.get("refreshing"):
            return
        self._community["refreshing"] = True
        self._set_tab_status(name, "idle")

        def _work():
            try:
                if name == "reddit":
                    res, st = self._fetch_reddit_chrome()
                else:
                    res, st = self._fetch_kofi_chrome()
                if res:
                    self._community["stats"][name] = res
                self._community["status"][name] = st or "ok"
                self._remember_linked(name, res is not None or st in ("ok", "empty"))
            except Exception as e:
                self._community["status"][name] = str(e)[:100]
                self._remember_linked(name, False)
            finally:
                self._community["refreshing"] = False
                _save_community_cache(self._community["stats"])
                st_now = self._community["status"].get(name)
                if st_now and st_now not in ("ok", "empty", "idle", "hidden", "no_key"):
                    self._community_action_needed("%s: %s" % (name, st_now))
                self._log("[DEBUG][link] %s -> %s linked=%s" % (
                    name, self._community["status"].get(name),
                    self._community["linked"].get(name)))
                self.root.after(0, self._update_tiles)
                self.root.after(0, self._update_comm_tabs)

        threading.Thread(target=_work, daemon=True).start()

    def _fetch_installations(self):
        """installations/ закрита правилами (#1529, read auth!=null) — читається
        тільки з адмін ID-токеном; без admin_creds.json повертає None (tile "—")."""
        try:
            url = admin_auth._rtdb_url_with_token(_rtdb_url("installations"))
            if not url:
                return None
            d = _get_json(url) or {}
            if isinstance(d, dict):
                by = {}
                for v in d.values():
                    if isinstance(v, dict):
                        ver = str(v.get("version") or "?")
                        by[ver] = by.get(ver, 0) + 1
                return {"total": len(d), "by_ver": by}
        except Exception:
            pass
        return None

    def _fetch_errors_list(self):
        """Останні 200 записів error_reports/ (read-open, bare key OK)."""
        try:
            d = _get_json(_rtdb_url("error_reports") + '&orderBy="timestamp"&limitToLast=200') or {}
            if not isinstance(d, dict):
                return None, "empty"
            rows = []
            for rid, rec in d.items():
                if not isinstance(rec, dict):
                    continue
                rows.append({
                    "id": rid,
                    "time": rec.get("timestamp", ""),
                    "type": rec.get("type", ""),
                    "stage": rec.get("stage", ""),
                    "source": (rec.get("details") or {}).get("source", ""),
                    "version": rec.get("version", ""),
                    "error": rec.get("error", ""),
                })
            rows.sort(key=lambda r: r["time"], reverse=True)
            return rows, None
        except Exception as e:
            return None, str(e)[:80]

    def _fetch_rtdb_counters(self):
        st = self._community["stats"]
        ins = self._fetch_installations()
        if ins is not None:
            st["installs"] = ins["total"]
            st["installs_by_ver"] = ins["by_ver"]
        for node, key in (("error_reports", "errors"), ("schemes", "schemes"), ("users", "users")):
            try:
                d = _get_json(_rtdb_url(node))
                st[key] = len(d) if isinstance(d, dict) else 0
            except Exception:
                pass
        try:
            b = _get_json(_rtdb_url("builds")) or {}
            if isinstance(b, dict):
                st["builds_ver"] = b.get("version")
                st["last_generated_at"] = b.get("last_generated_at")
        except Exception:
            pass

    def _fetch_github(self):
        try:
            r = requests.get(_GITHUB_API + "/releases",
                             headers={"User-Agent": _UA}, timeout=20)
            if r.status_code != 200:
                return None, "http_" + str(r.status_code)
            data = r.json()
            releases = []
            total = 0
            for rel in data:
                dl = sum(a.get("download_count", 0) for a in (rel.get("assets") or []))
                total += dl
                releases.append({"tag": rel.get("tag_name", ""),
                                 "date": (rel.get("published_at") or "")[:10],
                                 "downloads": dl})
            if not releases:
                return None, "empty"
            return {"releases": releases, "total": total}, None
        except Exception as e:
            return None, str(e)[:80]

    def _fetch_patreon(self):
        """Публічний Patreon API (legacy /api/campaigns/{id}) — без auth, без
        Chrome: patron_count, paid_member_count, campaign_pledge_sum (місячний
        дохід), creation_count (пости), created_at (#1587-розширення)."""
        try:
            r = requests.get(_PATREON_API, headers={"User-Agent": _UA}, timeout=15)
            if r.status_code != 200:
                return None, "http_" + str(r.status_code)
            d = ((r.json().get("data") or {}).get("attributes")) or {}
            pledge = d.get("campaign_pledge_sum")
            if pledge is None:
                pledge = d.get("pledge_sum", 0)
            return {
                "patrons": _safe_int(d.get("patron_count")),
                "paid": _safe_int(d.get("paid_member_count")),
                "pledge": pledge,
                "currency": d.get("pledge_sum_currency") or "USD",
                "posts": _safe_int(d.get("creation_count")),
                "created": str(d.get("created_at") or "")[:10],
            }, None
        except Exception as e:
            return None, str(e)[:80]

    def _fetch_yt_api(self):
        key = vault_get("youtube", "api_key")
        if not key:
            return None, "no_key"
        try:
            r = requests.get(_YT_API + "/videos", params={"part": "snippet",
                                                          "id": _YT_VIDEO_ID, "key": key}, timeout=15)
            if r.status_code != 200:
                return None, "http_" + str(r.status_code)
            items = (r.json().get("items") or [])
            if not items:
                return None, "no_video"
            ch = items[0]["snippet"]["channelId"]
            channel = {}
            rc = requests.get(_YT_API + "/channels", params={"part": "statistics",
                                                             "id": ch, "key": key}, timeout=15)
            if rc.status_code == 200:
                ci = (rc.json().get("items") or [])
                if ci:
                    s = ci[0].get("statistics") or {}
                    channel = {"subscribers": _safe_int(s.get("subscriberCount")),
                               "views": _safe_int(s.get("viewCount")),
                               "videos": _safe_int(s.get("videoCount"))}
            playlist = "UU" + ch[2:]
            vids, page = [], ""
            while True:
                rp = requests.get(_YT_API + "/playlistItems",
                                  params={"part": "contentDetails", "playlistId": playlist,
                                          "maxResults": 50, "pageToken": page, "key": key}, timeout=15)
                if rp.status_code != 200:
                    break
                jp = rp.json()
                vids += [it["contentDetails"]["videoId"] for it in (jp.get("items") or [])
                         if "contentDetails" in it and "videoId" in it["contentDetails"]]
                page = jp.get("nextPageToken")
                if not page:
                    break
            videos = []
            for i in range(0, len(vids), 50):
                chunk = vids[i:i + 50]
                rs = requests.get(_YT_API + "/videos", params={"part": "statistics,snippet",
                                                               "id": ",".join(chunk), "key": key}, timeout=15)
                if rs.status_code != 200:
                    continue
                for it in (rs.json().get("items") or []):
                    s = it.get("statistics") or {}
                    sn = it.get("snippet") or {}
                    videos.append({"id": it.get("id", ""), "title": sn.get("title", ""),
                                   "date": (sn.get("publishedAt") or "")[:10],
                                   "views": _safe_int(s.get("viewCount")),
                                   "likes": _safe_int(s.get("likeCount")),
                                   "comments": _safe_int(s.get("commentCount"))})
            return {"videos": videos, "channel": channel}, None
        except Exception as e:
            return None, str(e)[:80]

    def _fetch_yt_chrome(self):
        drv = self._community_ensure_browser(self._community.get("fs"))
        if drv is None:
            return None, "no_browser"
        main_handle = None
        try:
            main_handle = drv.current_window_handle
            self._open_bg_tab(drv)
            try:
                channel = self._community.get("yt_channel_id")
                if not channel:
                    drv.get("https://www.youtube.com/watch?v=" + _YT_VIDEO_ID + "&autoplay=0")
                    time.sleep(2.5)
                    try:
                        drv.execute_script(
                            "var v=document.querySelector('video');if(v){v.pause();v.muted=true;}")
                    except Exception:
                        pass
                    m = re.search(r'"channelId":"(UC[0-9A-Za-z_-]{22})"', drv.page_source)
                    if not m:
                        return None, "no_channel_id"
                    channel = m.group(1)
                    self._community["yt_channel_id"] = channel
                drv.get("https://www.youtube.com/channel/" + channel + "/videos")
                time.sleep(4)
                html = drv.page_source
                videos = _parse_yt_videos(_yt_initial_data(html)) if _yt_initial_data(html) else []
                if not videos:
                    for sel in ("button[aria-label*='consent']", "button[aria-label*='Accept']",
                                "form[action*='consent'] button"):
                        try:
                            drv.find_element("css selector", sel).click()
                            time.sleep(3)
                            break
                        except Exception:
                            continue
                    data = _yt_initial_data(drv.page_source)
                    videos = _parse_yt_videos(data) if data else []
                if not videos:
                    return None, "no_videos_parsed"
                return {"videos": videos, "channel": {}}, None
            finally:
                try:
                    if len(drv.window_handles) > 1:
                        drv.close()
                except Exception:
                    pass
                if main_handle is not None:
                    try:
                        drv.switch_to.window(main_handle)
                    except Exception:
                        pass
        except Exception as e:
            return None, str(e)[:80]

    def _fetch_reddit_http(self):
        try:
            r = requests.get("https://www.reddit.com/user/" + _REDDIT_USER + "/submitted.json",
                             headers={"User-Agent": _UA}, timeout=20)
            ctype = r.headers.get("Content-Type", "")
            if r.status_code != 200 or "json" not in ctype.lower():
                return None, "blocked"
            posts = []
            for ch in (r.json().get("data", {}).get("children") or []):
                d = ch.get("data", {})
                posts.append({"title": d.get("title", ""),
                              "date": time.strftime("%Y-%m-%d",
                                                     time.localtime(d.get("created_utc", 0))),
                              "score": d.get("score", 0), "comments": d.get("num_comments", 0),
                              "url": "https://www.reddit.com" + (d.get("permalink") or "")})
            if not posts:
                return None, "empty"
            return {"posts": posts}, None
        except Exception as e:
            return None, str(e)[:80]

    def _reddit_logged_in(self, drv):
        try:
            # /api/v1/me requires OAuth (never sees a cookie session), and
            # /login/ does NOT redirect logged-in users on modern Reddit.
            # /settings/ is private: logged-in users see it, others get sent
            # to /login — that redirect is the session check.
            drv.get("https://www.reddit.com/settings/")
            time.sleep(3)
            url = drv.current_url.lower()
            if "login" in url:
                return False
            return "404" not in str(drv.title).lower()
        except Exception:
            return False

    def _login_reddit(self, drv):
        user = vault_get("reddit", "username")
        pw = vault_get("reddit", "password")
        if not user or not pw:
            return "needs_reddit_creds"
        try:
            drv.get("https://www.reddit.com/login/")
            time.sleep(3.5)
            if "login" not in drv.current_url.lower():
                return "ok"  # already logged in — /login redirected away
            u = self._find_elem(drv, [("css selector", "input[name='username']"),
                                      ("id", "login-username")])
            p = self._find_elem(drv, [("css selector", "input[name='password']"),
                                      ("id", "login-password")])
            if not u or not p:
                return "login_form_missing"
            u.clear()
            u.send_keys(user)
            p.clear()
            p.send_keys(pw)
            btn = self._find_elem(drv, [("css selector", "button[type='submit']"),
                                        ("id", "login-submit")])
            if not btn:
                return "login_form_missing"
            btn.click()
            for _ in range(20):
                time.sleep(2)
                low = drv.page_source.lower()
                if "captcha" in low or ("verify" in low and "human" in low):
                    self._community_action_needed(self.t("act_captcha"))
                    return "needs_captcha"
                if "login" not in drv.current_url.lower():
                    if self._reddit_logged_in(drv):
                        return "ok"
            return "login_timeout"
        except Exception as e:
            return "login_error: " + str(e)[:80]

    def _fetch_reddit_chrome(self):
        drv = self._community_ensure_browser(self._community.get("fs"))
        if drv is None:
            return None, "no_browser"
        main_handle = None
        try:
            main_handle = drv.current_window_handle
            self._open_bg_tab(drv)
            try:
                if not self._reddit_logged_in(drv):
                    st = self._login_reddit(drv)
                    if st != "ok":
                        if st == "needs_reddit_creds":
                            self._community_action_needed("Reddit — " + self.t("tile_needs_login"))
                        return None, st
                # Public .json API is 403 without OAuth, but the logged-in browser
                # session gets it with cookies — parse JSON, not HTML.
                drv.get("https://www.reddit.com/user/" + _REDDIT_USER + "/submitted.json")
                time.sleep(3)
                posts = []
                m = re.search(r"<pre>(.*?)</pre>", drv.page_source, re.S)
                if m:
                    data = json.loads(m.group(1))
                    for ch in (data.get("data", {}).get("children") or []):
                        d = ch.get("data", {})
                        posts.append({"title": d.get("title", ""),
                                      "date": time.strftime("%Y-%m-%d",
                                                             time.localtime(d.get("created_utc", 0))),
                                      "score": d.get("score", 0),
                                      "comments": d.get("num_comments", 0),
                                      "url": "https://www.reddit.com" + (d.get("permalink") or "")})
                if not posts:
                    return None, "empty"
                return {"posts": posts}, None
            finally:
                try:
                    if len(drv.window_handles) > 1:
                        drv.close()
                except Exception:
                    pass
                if main_handle is not None:
                    try:
                        drv.switch_to.window(main_handle)
                    except Exception:
                        pass
        except Exception as e:
            return None, str(e)[:80]

    def _kofi_logged_in(self, drv):
        try:
            # Old /manage/donations returns a 404 page since 2026; the live
            # dashboard is /Manage/SupportReceived ("Ko-fi | Transactions").
            # It is private: logged-in users see it, others get /login; a 404
            # page must not count as a valid session.
            drv.get("https://ko-fi.com/Manage/SupportReceived")
            time.sleep(4)
            url = drv.current_url.lower()
            if "/login" in url:
                return False
            return "404" not in str(drv.title).lower()
        except Exception:
            return False

    def _login_kofi(self, drv):
        user = vault_get("kofi", "username")
        pw = vault_get("kofi", "password")
        if not user or not pw:
            return "needs_kofi_creds"
        try:
            drv.get("https://ko-fi.com/login")
            time.sleep(3.5)
            if "login" not in drv.current_url.lower():
                return "ok"  # already logged in — /login redirected away
            u = self._find_elem(drv, [("css selector", "input[name='email'], input[type='email']"),
                                      ("id", "email")])
            p = self._find_elem(drv, [("css selector", "input[name='password'], input[type='password']"),
                                      ("id", "password")])
            if not u or not p:
                return "login_form_missing"
            u.clear()
            u.send_keys(user)
            p.clear()
            p.send_keys(pw)
            btn = self._find_elem(drv, [("css selector", "button[type='submit']"),
                                        ("xpath", "//button[contains(.,'Log in') or contains(.,'Sign in')]")])
            if not btn:
                return "login_form_missing"
            btn.click()
            for _ in range(20):
                time.sleep(2)
                low = drv.page_source.lower()
                if "captcha" in low or "cloudflare" in low:
                    self._community_action_needed(self.t("act_captcha"))
                    return "needs_captcha"
                if "login" not in drv.current_url.lower():
                    if self._kofi_logged_in(drv):
                        return "ok"
            return "login_timeout"
        except Exception as e:
            return "login_error: " + str(e)[:80]

    def _fetch_kofi_chrome(self):
        drv = self._community_ensure_browser(self._community.get("fs"))
        if drv is None:
            return None, "no_browser"
        main_handle = None
        try:
            main_handle = drv.current_window_handle
            self._open_bg_tab(drv)
            try:
                if not self._kofi_logged_in(drv):
                    st = self._login_kofi(drv)
                    if st != "ok":
                        if st == "needs_kofi_creds":
                            self._community_action_needed("Ko-fi — " + self.t("tile_needs_login"))
                        return None, st
                    drv.get("https://ko-fi.com/Manage/SupportReceived")
                    time.sleep(4)
                amounts = _parse_kofi_amounts(drv.page_source)
                if not amounts:
                    drv.get("https://ko-fi.com/Manage/SupportReceived")
                    time.sleep(4)
                    amounts = _parse_kofi_amounts(drv.page_source)
                # 0 donations on a valid dashboard is a normal state, not an error.
                return {"total": sum(amounts), "count": len(amounts), "amounts": amounts}, None
            finally:
                try:
                    if len(drv.window_handles) > 1:
                        drv.close()
                except Exception:
                    pass
                if main_handle is not None:
                    try:
                        drv.switch_to.window(main_handle)
                    except Exception:
                        pass
        except Exception as e:
            return None, str(e)[:80]

    def _show_settings_menu(self):
        """Gear button opens a dropdown menu (same pattern as the main app)."""
        menu = tk.Menu(self.root, tearoff=0, bg="#222222", fg=FG,
                       activebackground="#333333", activeforeground=ACCENT, bd=1)
        sw = tk.BooleanVar(value=self._admin_settings.get("start_with_windows", False))
        menu.add_checkbutton(label=self.t("menu_start_windows"), variable=sw,
                             command=lambda: self._on_settings_change("start_with_windows", sw.get()))
        sm = tk.BooleanVar(value=self._admin_settings.get("start_minimized", False))
        menu.add_checkbutton(label=self.t("menu_start_minimized"), variable=sm,
                             command=lambda: self._on_settings_change("start_minimized", sm.get()))
        menu.add_separator()
        menu.add_command(label=self.t("menu_wot_path"), command=self._show_wot_path_dialog)
        menu.add_separator()
        menu.add_command(label=self.t("menu_help"), command=self._show_help)
        menu.add_separator()
        menu.add_command(label=self.t("menu_exit"), command=self._exit_app)
        try:
            x = self._settings_btn.winfo_rootx()
            y = self._settings_btn.winfo_rooty() + self._settings_btn.winfo_height()
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _show_wot_path_dialog(self):
        dlg = tk.Toplevel(self.root)
        dlg.configure(bg=BG)
        dlg.title(self.t("dlg_wot_path"))
        dlg.geometry("420x120")
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()

        tk.Label(dlg, text=self.t("dlg_wot_path_label"), bg=BG, fg="#aaa",
                 font=("Segoe UI", 9)).pack(anchor="w", padx=20, pady=(12, 2))
        wp = tk.Entry(dlg, bg="#222", fg=FG, bd=0, insertbackground=FG,
                      font=("Segoe UI", 9))
        wp.insert(0, self._admin_settings.get("wot_path", self._wot_path or ""))
        wp.pack(fill="x", padx=20, pady=(0, 4))

        def _save_wp():
            val = wp.get().strip()
            self._admin_settings["wot_path"] = val
            self._wot_path = val
            _save_admin_settings(self._admin_settings)
            self._log(self.t("log_wot_path_set", val=val))
            dlg.destroy()

        tk.Button(dlg, text=self.t("dlg_save"), bg="#333", fg=FG, bd=0, padx=20, pady=4,
                  command=_save_wp).pack(pady=6)

    def _on_settings_change(self, key, value):
        self._admin_settings[key] = value
        _save_admin_settings(self._admin_settings)
        if key == "start_with_windows":
            _set_windows_startup(value)
            self._log(self.t("log_start_windows",
                             state=self.t("on") if value else self.t("off")))

    def _scan_now(self):
        if self._scanning:
            self._log(self.t("log_scan_running"))
            return
        threading.Thread(target=self._do_scan, daemon=True).start()

    def _do_scan(self):
        self._scanning = True
        self._scan_btn.config(state="disabled")
        self._log(self.t("log_scanning"))
        try:
            changed = detect_changed_tanks(self._wot_path, self._manifest_path) if self._wot_path else []
            self._last_scan = time.time()
            if changed:
                self._queue = changed
                self._log(self.t("log_changed", n=len(changed)))
                for t in changed[:10]:
                    self._log(f"  {t}")
                self.tray.show_notification(self.t("notif_changes"),
                                            self.t("notif_changes_body", n=len(changed)))
                self.root.after(0, self._update_cards)
                self._do_generate(changed)
            else:
                self._log(self.t("log_no_changes"))
                self.root.after(0, self._update_cards)
        except Exception as e:
            self._log(self.t("log_scan_error", err=e))
        finally:
            self._scanning = False
            self.root.after(0, lambda: self._scan_btn.config(state="normal"))

    def _gen_queue(self):
        if not self._queue:
            self._log(self.t("log_queue_empty"))
            return
        threading.Thread(target=self._do_generate, args=(list(self._queue),), daemon=True).start()

    def _do_generate(self, queue):
        self._generating = True
        self.root.after(0, lambda: self._gen_btn.config(state="disabled"))
        self._log(self.t("log_generating", n=len(queue)))
        _update_pending_status("builds", "generating",
                               message=self.t("log_generating", n=len(queue)))
        self._report_admin_status(status="generating")
        self.tray.show_notification(self.t("notif_gen_started"),
                                    self.t("notif_gen_started_body", n=len(queue)))
        try:
            driver = _create_driver()
            try:
                ok, done_tags, reasons = generate_builds(driver, self.tank_db, self.prompts, queue=queue,
                                                         wot_path=self._wot_path)
                if ok and done_tags:
                    self._queue = [t for t in self._queue if t not in done_tags]
                    try:
                        update_manifest_for_tags(self._wot_path, self._manifest_path, done_tags)
                    except Exception:
                        pass
                    iso = time.strftime("%Y-%m-%dT%H:%M:%S")
                    _put_json(_rtdb_url("builds/last_generated_at"), iso)
                    _put_json(_rtdb_url("prompts/last_generated_at"), iso)
                    _put_json(_rtdb_url("admin_app/last_generation"),
                              {"at": iso, "count": len(done_tags), "ok": True})
                    _update_pending_status("builds", "done",
                                           message=self.t("notif_builds_updated_body", n=len(done_tags)))
                    self._log(self.t("log_gen_done"))
                    self.tray.show_notification(self.t("notif_builds_updated"),
                                                self.t("notif_builds_updated_body", n=len(done_tags)),
                                                level="info")
                else:
                    failed = [t for t in queue if t not in done_tags]
                    try:
                        if failed:
                            update_manifest_failures(self._wot_path, self._manifest_path, failed)
                    except Exception:
                        pass
                    err_msg = (reasons.get("summary") or "generation failed") if reasons else "generation failed"
                    for t, r in list(reasons.items())[:5]:
                        if t != "summary":
                            self._log(f"  {t}: {r}")
                    _update_pending_status("builds", "error", message=err_msg[:300])
                    self._log(self.t("log_gen_failed") + f" — {err_msg[:200]}")
                    self.tray.show_notification(self.t("notif_gen_failed"),
                                                err_msg[:120],
                                                level="error")
            finally:
                driver.quit()
        except Exception as e:
            _update_pending_status("builds", "error", message=str(e)[:200])
            self._log(self.t("log_gen_error", err=e))
            self.tray.show_notification(self.t("notif_error"), str(e)[:80], level="error")
        finally:
            self._generating = False
            self._report_admin_status(status="idle")
            self.root.after(0, lambda: self._gen_btn.config(state="normal"))
            self.root.after(0, self._check_tank_prompt_match)
            self.root.after(0, self._update_cards)

    def _gen_popular(self):
        threading.Thread(target=self._do_popular, daemon=True).start()

    def _do_popular(self):
        self._log(self.t("log_popular_start"))
        self._popular_btn.config(state="disabled")
        try:
            driver = _create_driver()
            try:
                ok = generate_popular(driver, self.tank_db)
                if ok:
                    _put_json(_rtdb_url("popular_tanks/last_generated_at"),
                              time.strftime("%Y-%m-%dT%H:%M:%S"))
                    self._log(self.t("log_popular_ok"))
                    self.tray.show_notification(self.t("notif_popular"),
                                                self.t("notif_popular_body"))
                else:
                    self._log(self.t("log_popular_fail"))
            finally:
                driver.quit()
        except Exception as e:
            self._log(self.t("log_popular_error", err=e))
        finally:
            self.root.after(0, lambda: self._popular_btn.config(state="normal"))

    def _gen_all(self):
        self._log(self.t("log_regen_warn"))
        self.tray.show_notification(self.t("notif_regen_all"),
                                    self.t("notif_regen_all_body", n=len(self.tank_db)),
                                    level="error")
        threading.Thread(target=self._do_generate,
                         args=(list(self.tank_db.keys()),), daemon=True).start()

    def _start_background(self):
        def _loop():
            while self._running:
                try:
                    now = time.time()
                    if now - self._last_heartbeat > 60:
                        self._last_heartbeat = now
                        self._report_admin_status()
                    if now - self._last_cleanup > 86400:  # 24 h
                        self._last_cleanup = now
                        self._cleanup_old_error_reports()
                    if now - self._last_sweep > 86400:  # 24 h fill sweep
                        self._last_sweep = now
                        self._run_build_fill_sweep()
                    if now - self._last_wg > 1800:  # 30 min
                        self._last_wg = now
                        wg_ver, ts = check_wg_game_version()
                        if wg_ver:
                            self._wg_ver = wg_ver
                            self.root.after(0, self._update_cards)
                        if ts:
                            stored = _get_json(_rtdb_url("builds/tanks_updated_at")) or 0
                            if ts != stored:
                                _put_json(_rtdb_url("builds/tanks_updated_at"), ts)
                                self._log(self.t("log_wg_ts", ts=ts))
                                if self._wot_path:
                                    changed = detect_changed_tanks(self._wot_path, self._manifest_path)
                                    if changed:
                                        self._queue = changed
                                        self.root.after(0, self._update_cards)
                                        self._log(self.t("log_auto_detected", n=len(changed)))
                                        self.tray.show_notification(
                                            self.t("notif_auto_detected"),
                                            self.t("notif_auto_detected_body", n=len(changed)))
                                        self._do_generate(changed)
                    if self._wot_path and now - self._last_scan > 3600:
                        self._last_scan = now
                        changed = detect_changed_tanks(self._wot_path, self._manifest_path)
                        if changed:
                            self._queue = changed
                            self.root.after(0, self._update_cards)
                            self._log(self.t("log_periodic", n=len(changed)))
                            self.tray.show_notification(
                                self.t("notif_changes"),
                                self.t("notif_changes_body", n=len(changed)))
                            self._do_generate(changed)
                    if now - self._community["last_comm"] > 43200:  # 12h community data refresh (cache keeps tiles fresh)
                        self._community["last_comm"] = now
                        self._refresh_community_background()
                    # NO periodic 10-min community fetches: 12h cycle + manual
                    # Refresh / Link buttons + cache at startup.
                except Exception as e:
                    self._log(self.t("log_bg_error", err=e))
                time.sleep(10)
        threading.Thread(target=_loop, daemon=True).start()

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(1000, self._scan_now)
        self.root.mainloop()

    def _on_close(self):
        """X button minimizes to tray; full exit via Settings gear -> Exit."""
        self._community_kill_browser()
        self.root.withdraw()

    def _show_window(self):
        self.root.deiconify()
        self.root.lift()

    def _exit_app(self):
        self._running = False
        self._community_kill_browser()
        try:
            threading.Thread(target=self._report_admin_status,
                             kwargs={"status": "offline"}, daemon=True).start()
        except Exception:
            pass
        if hasattr(self, "tray"):
            self.tray.remove()
        self.root.destroy()


def main():
    import argparse

    # Single-instance mutex
    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _k32.CreateMutexW.argtypes = (ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p)
    _k32.CreateMutexW.restype = ctypes.c_void_p
    mutex = _k32.CreateMutexW(None, False, "SM_WoT_Assistant_Admin_SingleInstance")
    if ctypes.get_last_error() == 183:
        hwnd = ctypes.windll.user32.FindWindowW(None, f"SM WoT Assistant Admin v{_read_admin_version()}")
        if hwnd:
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        sys.exit(0)

    parser = argparse.ArgumentParser(description="SM WoT Assistant Admin App")
    parser.add_argument("--wot-path", type=str, default=None, help="Path to WoT installation")
    parser.add_argument("--tray", action="store_true", help="Start minimized to tray")
    args = parser.parse_args()

    root = tk.Tk()
    root.withdraw()
    app = AdminApp(root, wot_path=args.wot_path)
    # Check if should start minimized
    settings = _load_admin_settings()
    if args.tray or settings.get("start_minimized", False):
        # Start in tray - window stays withdrawn, tray icon is visible
        app.root.after(100, app._log, app.t("log_tray_started"))
        app.root.after(300, lambda: app.tray.show_notification(
            "SM WoT Assistant Admin", app.t("log_tray_running",
                                             path=app._wot_path or app.t("not_set"))))
    else:
        root.deiconify()
    app.run()
    ctypes.windll.kernel32.CloseHandle(mutex)

if __name__ == "__main__":
    main()
