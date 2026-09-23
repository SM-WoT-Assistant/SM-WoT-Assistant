# -*- coding: utf-8 -*-
"""
SM WoT Tactics — in-game minimap overlay for tactical schemes.
Reads selected_scheme.json from %APPDATA%/SM WoT Assistant/
Renders markers, arrows, and brush routes on the minimap.

WoT Python 2.7 — uses MinimapComponent hooks and Flash graphics API.
"""
import os
import json
import math
import BigWorld
import GUI
from gui.Scaleform.daapi.view.battle.shared.minimap.component import MinimapComponent
from gui.Scaleform.daapi.view.battle.shared.minimap.settings import TRANSFORM_FLAG
from gui.Scaleform.genConsts.LAYERS import LAYERS
from PlayerEvents import g_playerEvents
from gui import g_guiResetters
from gui.shared import g_eventBus, events
import Keys

TAG = '[SM Tactics]'
SCHEME_FILE = os.path.join(
    os.environ.get('APPDATA', ''), 'SM WoT Assistant', 'selected_scheme.json')

_scheme = None
_visible = True
_active = False
_minimap = None
_overlay_swf = None


def _read_scheme():
    global _scheme
    try:
        if not os.path.isfile(SCHEME_FILE):
            _scheme = None
            return
        with open(SCHEME_FILE, 'r') as f:
            raw = f.read()
        if raw.strip() == 'null' or not raw.strip():
            _scheme = None
            return
        data = json.loads(raw)
        if data and isinstance(data, dict) and data.get('elements'):
            _scheme = data
            print('%s Loaded: %s (%d elements)' % (
                TAG, data.get('scheme_name', '?'), len(data.get('elements', []))))
        else:
            _scheme = None
    except Exception as e:
        print('%s Read error: %s' % (TAG, e))
        _scheme = None


def _get_minimap_comp():
    try:
        session = BigWorld.player().sessionProvider
        if session is None:
            return None
        gui = session.gui
        if gui is None:
            return None
        battlePage = getattr(gui, '_battlePage', None)
        if battlePage is None:
            return None
        minimap = getattr(battlePage, '_minimap', None)
        return minimap
    except Exception:
        return None


def _get_minimap_size(minimap):
    try:
        w = minimap.as_width()
        h = minimap.as_height()
        if w > 0 and h > 0:
            return w, h
    except Exception:
        pass
    return None, None


def _draw_marker(gfx, x, y, size=4, color=0xFF4444):
    try:
        gfx.lineStyle(0, color, 0.0)
        gfx.beginFill(color, 0.8)
        gfx.drawCircle(x, y, size)
        gfx.endFill()
    except Exception:
        pass


def _draw_arrow(gfx, x1, y1, x2, y2, color=0xFF4444, width=2):
    try:
        gfx.lineStyle(width, color, 0.8)
        gfx.moveTo(x1, y1)
        gfx.lineTo(x2, y2)
        angle = math.atan2(y2 - y1, x2 - x1)
        arrow_len = 6
        a1x = x2 - arrow_len * math.cos(angle - 0.4)
        a1y = y2 - arrow_len * math.sin(angle - 0.4)
        a2x = x2 - arrow_len * math.cos(angle + 0.4)
        a2y = y2 - arrow_len * math.sin(angle + 0.4)
        gfx.lineStyle(width, color, 0.8)
        gfx.moveTo(x2, y2)
        gfx.lineTo(a1x, a1y)
        gfx.moveTo(x2, y2)
        gfx.lineTo(a2x, a2y)
    except Exception:
        pass


def _draw_brush(gfx, coords_flat, color=0xFF4444, width=2):
    """Draw a polyline (brush) element via Flash graphics.
    coords_flat is [x1,y1, x2,y2, ...] in normalized 0..1."""
    try:
        if len(coords_flat) < 4:
            return
        gfx.lineStyle(width, color, 0.6)
        x0 = coords_flat[0]
        y0 = coords_flat[1]
        gfx.moveTo(x0, y0)
        i = 2
        while i < len(coords_flat) - 1:
            gfx.lineTo(coords_flat[i], coords_flat[i + 1])
            i += 2
    except Exception:
        pass


def _draw_dot(gfx, x, y, size=3, color=0xFF4444):
    """Draw a small filled rectangle (position marker)."""
    try:
        gfx.lineStyle(0, color, 0.0)
        gfx.beginFill(color, 0.8)
        gfx.drawRect(x - size, y - size, size * 2, size * 2)
        gfx.endFill()
    except Exception:
        pass


def _draw_zone(gfx, coords_flat, color=0xFF4444):
    """Draw a dashed closed polygon outline (zone boundary).
    Flash doesn't have native dash, so we draw segments with gaps."""
    try:
        n = len(coords_flat)
        if n < 6:
            return
        gfx.lineStyle(1, color, 0.7)
        dash_on = True
        i = 0
        while i < n:
            x1 = coords_flat[i]
            y1 = coords_flat[i + 1]
            x2 = coords_flat[(i + 2) % n]
            y2 = coords_flat[(i + 3) % n]
            if dash_on:
                gfx.moveTo(x1, y1)
                gfx.lineTo(x2, y2)
            dash_on = not dash_on
            i += 2
    except Exception:
        pass


POI_SCALES = {
    0x3F: 1.0,   # HT (heavy tank) - largest
    0x3B: 0.85,  # MT (medium tank)
    0x2E: 0.75,  # TD (tank destroyer)
    0x2D: 0.65,  # SPG (artillery)
    0x3A: 0.50,  # LT (light tank) - smallest
}


def _draw_poi(gfx, x, y, code, size=6, color=0xFF4444):
    """Draw a vehicle class icon as a geometric shape on the minimap.
    Uses WoT minimap-style symbols: diamond (LT/MT/HT), triangle (TD), square (SPG).
    Size is scaled by class: HT largest, LT smallest."""
    try:
        s = size * POI_SCALES.get(code, 0.7)
        gfx.lineStyle(1, color, 0.9)
        gfx.beginFill(color, 0.7)

        if code in (0x3A, 0x3B, 0x3F):
            gfx.moveTo(x, y - s)
            gfx.lineTo(x + s * 0.7, y)
            gfx.lineTo(x, y + s)
            gfx.lineTo(x - s * 0.7, y)
            gfx.lineTo(x, y - s)
        elif code == 0x2E:
            gfx.moveTo(x, y + s)
            gfx.lineTo(x - s * 0.7, y - s * 0.6)
            gfx.lineTo(x + s * 0.7, y - s * 0.6)
            gfx.lineTo(x, y + s)
        elif code == 0x2D:
            gfx.drawRect(x - s * 0.6, y - s * 0.6, s * 1.2, s * 1.2)
        else:
            gfx.drawCircle(x, y, s * 0.7)

        gfx.endFill()
    except Exception:
        pass


def _hex_to_int(hex_str):
    try:
        hex_str = hex_str.lstrip('#')
        return int(hex_str, 16)
    except Exception:
        return 0xFF4444


def _el_coords_to_px(el, mm_w, mm_h):
    """Extract pixel coords from element using 'coords' array."""
    coords = el.get('coords', [])
    if len(coords) < 2:
        return None
    px = []
    for i, c in enumerate(coords):
        if i % 2 == 0:
            px.append(c * mm_w)
        else:
            px.append(c * mm_h)
    return px


def _render_scheme(minimap, mm_w, mm_h):
    if not _scheme or not _visible:
        return
    elements = _scheme.get('elements', [])
    if not elements:
        return
    try:
        gfx = minimap._Flash__component
        for el in elements:
            etype = el.get('type', '')
            color = _hex_to_int(el.get('color', '#FF4444'))
            thickness = el.get('thickness', 2)
            size = el.get('size', 4)

            if etype == 'marker':
                px = _el_coords_to_px(el, mm_w, mm_h)
                if px and len(px) >= 2:
                    _draw_marker(gfx, px[0], px[1], size=size, color=color)

            elif etype == 'dot':
                px = _el_coords_to_px(el, mm_w, mm_h)
                if px and len(px) >= 2:
                    dot_sz = max(2, int(size * 0.8))
                    _draw_dot(gfx, px[0], px[1], size=dot_sz, color=color)

            elif etype == 'arrow':
                px = _el_coords_to_px(el, mm_w, mm_h)
                if px and len(px) >= 4:
                    _draw_arrow(gfx, px[0], px[1], px[2], px[3],
                                color=color, width=thickness)

            elif etype == 'brush':
                coords = el.get('coords', [])
                if len(coords) >= 4:
                    flat_px = []
                    for i, c in enumerate(coords):
                        if i % 2 == 0:
                            flat_px.append(c * mm_w)
                        else:
                            flat_px.append(c * mm_h)
                    _draw_brush(gfx, flat_px, color=color, width=thickness)

            elif etype == 'zone':
                coords = el.get('coords', [])
                if len(coords) >= 6:
                    flat_px = []
                    for i, c in enumerate(coords):
                        if i % 2 == 0:
                            flat_px.append(c * mm_w)
                        else:
                            flat_px.append(c * mm_h)
                    _draw_zone(gfx, flat_px, color=color)

            elif etype == 'text':
                px = _el_coords_to_px(el, mm_w, mm_h)
                if px and len(px) >= 2:
                    poi = el.get('poi', [])
                    if isinstance(poi, list) and poi:
                        poi_scale = el.get('poi_scale', 0.7)
                        base_sz = max(3, int(6 * poi_scale))
                        _draw_poi(gfx, px[0], px[1], poi[0], size=base_sz, color=color)
                    else:
                        _draw_dot(gfx, px[0], px[1], size=3, color=color)

    except Exception as e:
        print('%s Render error: %s' % (TAG, e))


def _on_avatar_ready():
    global _active, _scheme
    _active = True
    _read_scheme()
    print('%s Battle started. Scheme: %s' % (
        TAG, _scheme.get('scheme_name', 'none') if _scheme else 'none'))


def _on_become_non_player():
    global _active, _scheme, _minimap
    _active = False
    _scheme = None
    _minimap = None


def _toggle_visible():
    global _visible
    _visible = not _visible
    print('%s Overlay %s' % (TAG, 'visible' if _visible else 'hidden'))


def _handle_key(event):
    if event.key == Keys.KEY_F12:
        _toggle_visible()
        return True
    return False


def init():
    g_playerEvents.onAvatarReady += _on_avatar_ready
    g_playerEvents.onAvatarBecomeNonPlayer += _on_become_non_player
    BigWorld.addKeyEventHandler(_handle_key)
    print('%s Loaded (F12 to toggle)' % TAG)


def fini():
    g_playerEvents.onAvatarReady -= _on_avatar_ready
    g_playerEvents.onAvatarBecomeNonPlayer -= _on_become_non_player
    BigWorld.removeKeyEventHandler(_handle_key)
    print('%s Unloaded' % TAG)
