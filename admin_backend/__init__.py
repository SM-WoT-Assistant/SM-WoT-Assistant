"""Admin backend package: business logic for SM WoT Assistant Admin.

Pure Python (no Tkinter). Modules:
  - core: Application state + lifecycle.
  - api: Flask + SSE endpoints for the webview frontend.
  - build_generator: generate_builds, _upload_build, _upload_prompt.
  - manifest: detect_changed_tanks, snapshot_manifest, _BAD_TAG_MARKERS.
  - tank_db: load_tank_db, check_prompt_tank_mismatch, _tank_record_from_client.
  - prompts: load_prompts, load_prompts_merged, save_prompt, _is_build_complete.
  - community: fetchers for YouTube/Reddit/GitHub/Ko-fi/Patreon/Errors.
  - tray: pystray-based tray icon (replaces AdminTray from admin_app.py).
  - report: report_error, report_fallback, verify_admin_credentials.

Public surface used by the webview frontend is exposed via admin_backend.api.
"""

__version__ = "1.0.0"
