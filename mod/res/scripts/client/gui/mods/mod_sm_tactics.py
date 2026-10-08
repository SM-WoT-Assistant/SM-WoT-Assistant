# -*- coding: utf-8 -*-
"""SM WoT Tactics - tactical scheme on the in-game minimap.

Architecture follows the open-source community reference
wotstat/wotstat-positions (Minimap Overlay):

- a Scaleform View (ViewSettings + app.loadView on the battle app) hosts
  the AS3 side (SmTacticsOverlay.swf);
- lifecycle comes from ComponentEvent.COMPONENT_REGISTERED for
  BATTLE_VIEW_ALIASES.MINIMAP - no monkeypatch hooks;
- the AS3 layer attaches INSIDE minimap.entriesContainer, so all drawing
  is in minimap-local pixels and coordinates stay normalized 0..1 (the
  exact format of the desktop app's scheme data) - no screen rect, no
  root anchoring, no z-stack handling.

Data flow: the desktop app writes selected_scheme.json at battle start
(main.py:_write_selected_scheme); this mod reads it when the minimap
registers and pushes the elements to the SWF.

Client constraints (live-verified): Python 2.7 (pyc magic 62211);
ModsSettingsAPI is an optional soft-dep; Alt visibility modes use
InputHandler (isAltDown - proven by pruszko and yaya mods).
"""
import os
import sys
import json
import logging
import traceback

import BigWorld
from gui import InputHandler
from gui.Scaleform.framework import g_entitiesFactories, ScopeTemplates, ViewSettings
from gui.Scaleform.framework.entities.View import View
from gui.Scaleform.genConsts.BATTLE_VIEW_ALIASES import BATTLE_VIEW_ALIASES
from gui.app_loader.settings import APP_NAME_SPACE
from gui.Scaleform.framework.managers.loaders import SFViewLoadParams
from gui.shared import events, EVENT_BUS_SCOPE, g_eventBus
from gui.shared.personality import ServicesLocator
from frameworks.wulf import WindowLayer

LOG = logging.getLogger('sm_tactics')
TAG = '[SM Tactics]'

VIEW_ALIAS = 'SM_TACTICS_OVERLAY_VIEW'
SWF_NAME = 'SmTacticsOverlay.swf'
LINKAGE = 'sm.wo-tactics'
SCHEME_FILE = os.path.join(
    os.environ.get('APPDATA', ''), 'SM WoT Assistant', 'selected_scheme.json')
# the program's full scheme store (same folder) - read directly so the mod
# works without the app running (07.10.2026)
SAVED_SCHEMES_FILE = os.path.join(
    os.environ.get('APPDATA', ''), 'SM WoT Assistant', 'saved_schemes.json')

DEBUG = False  # calibration closed 05.10.2026: frame is on the grid +/-1px
               # (lattice V16/H17 vs frame 16/17); init/scheme/attach logs stay

MODE_ALWAYS = 0
MODE_SHOW_ON_ALT = 1
MODE_HIDE_ON_ALT = 2
MODE_LABELS = ['Always', 'Show on Alt', 'Hide on Alt']

_g = {
    'view': None,
    'should_register': False,
    'elements': None,
    'scheme_name': None,
    'mode': MODE_ALWAYS,
    'elemScale': 100,   # ModsSettingsAPI slider, percent
    'alt': False,
    'listeners': False,
    'keys': None,
}


class SmTacticsOverlay(View):
    """Python side of the overlay view; as_* methods forward to the SWF."""

    def _populate(self):
        super(SmTacticsOverlay, self)._populate()
        _g['view'] = self
        LOG.info('%s view populated (scheme=%r, elements=%s)', TAG,
                 _g['scheme_name'],
                 len(_g['elements']) if _g['elements'] else 0)
        if _g['should_register']:
            self.register_and_push()

    def _destroy(self):
        if _g.get('view') is self:
            _g['view'] = None
        LOG.info('%s view destroyed', TAG)
        super(SmTacticsOverlay, self)._destroy()

    def register_and_push(self):
        elements = _g['elements']
        if not elements:
            LOG.info('%s no scheme - layer not registered', TAG)
            return
        try:
            self.as_setDebug(DEBUG)
            self.as_register()
            status = self.as_setElements(json.dumps(elements))
            self.as_setUserScale(_g['elemScale'] / 100.0)
            LOG.info('%s setElements=%s', TAG, status)
            # Visibility BEFORE diagnostics: a failing debug call must never
            # abort the layer becoming visible (02.10.2026 lesson).
            _apply_visibility()
            LOG.info('%s attach=%r ping=%r', TAG,
                     self.flashObject.as_attachInfo(),
                     self.flashObject.as_ping())
            LOG.info('%s render-info %s', TAG,
                     self.flashObject.as_getDebugInfo())

            def _recheck():
                v = _g.get('view')
                if v is None:
                    return
                try:
                    LOG.info('%s render-info(+5s) %s', TAG,
                             v.flashObject.as_getDebugInfo())
                except Exception:
                    pass

            BigWorld.callback(5.0, _recheck)
        except Exception:
            LOG.error('%s push failed:\n%s', TAG, traceback.format_exc())

    def as_register(self):
        self.flashObject.as_register()

    def as_unregister(self):
        self.flashObject.as_unregister()

    def as_setElements(self, payload):
        # Returns a status string from the SWF ("ok n=N" / "parseErr: ...")
        # so the python log can see exactly what happened (JSON in the client
        # stopped working after the 2.4.0.2 update - the SWF now parses the
        # payload with its own reader).
        return self.flashObject.as_setElements(payload)

    def as_setVisible(self, on):
        self.flashObject.as_setVisible(bool(on))

    def as_setDebug(self, on):
        self.flashObject.as_setDebug(bool(on))

    def as_setUserScale(self, v):
        self.flashObject.as_setUserScale(v)


# ---------------- view framework setup (wotstat pattern) ----------------

def on_app_initialized(event):
    if event.ns != APP_NAME_SPACE.SF_BATTLE:
        return
    LOG.info('%s battle app initialized - loading overlay view', TAG)

    def _load():
        try:
            app = ServicesLocator.appLoader.getApp(event.ns)
            if not app:
                LOG.error('%s battle app not found', TAG)
                return
            app.loadView(SFViewLoadParams(VIEW_ALIAS))
        except Exception:
            LOG.error('%s loadView failed:\n%s', TAG, traceback.format_exc())

    BigWorld.callback(0, _load)


def on_component_registered(event):
    if event.alias != BATTLE_VIEW_ALIASES.MINIMAP:
        return
    _g['should_register'] = True
    name, elements = _read_scheme()
    if elements:
        _g['scheme_name'] = name
        _g['elements'] = elements
    else:
        # selected_scheme.json empty (program not running) -> direct store
        # read; async with retries (player entity may not be ready yet).
        # _start_fallback fills _g itself - afterwards read it BACK instead
        # of overwriting with the failed locals (live clobber bug, 08.10).
        _start_fallback()
        name = _g.get('scheme_name')
        elements = _g['elements']
    LOG.info('%s minimap registered (scheme=%r, elements=%s)', TAG, name,
             len(elements) if elements else 0)
    view = _g['view']
    if view is not None:
        view.register_and_push()


def on_component_unregistered(event):
    if event.alias != BATTLE_VIEW_ALIASES.MINIMAP:
        return
    _g['should_register'] = False
    view = _g['view']
    if view is not None:
        try:
            view.as_unregister()
        except Exception:
            LOG.warning('%s unregister failed:\n%s', TAG, traceback.format_exc())


def _setup_view_framework():
    g_entitiesFactories.addSettings(ViewSettings(
        VIEW_ALIAS, SmTacticsOverlay, SWF_NAME,
        WindowLayer.WINDOW, None, ScopeTemplates.GLOBAL_SCOPE))
    g_eventBus.addListener(events.AppLifeCycleEvent.INITIALIZED,
                           on_app_initialized, EVENT_BUS_SCOPE.GLOBAL)
    g_eventBus.addListener(events.ComponentEvent.COMPONENT_REGISTERED,
                           on_component_registered, EVENT_BUS_SCOPE.GLOBAL)
    g_eventBus.addListener(events.ComponentEvent.COMPONENT_UNREGISTERED,
                           on_component_unregistered, EVENT_BUS_SCOPE.GLOBAL)
    _g['listeners'] = True
    LOG.info('%s view registered (alias=%s, swf=%s)', TAG, VIEW_ALIAS, SWF_NAME)


# ---------------- scheme data ----------------

def _read_scheme():
    try:
        if not os.path.isfile(SCHEME_FILE):
            return None, None
        with open(SCHEME_FILE, 'r') as fh:
            raw = fh.read()
        if not raw.strip() or raw.strip() == 'null':
            return None, None
        data = json.loads(raw)
        elements = data.get('elements') if isinstance(data, dict) else None
        if not elements:
            return None, None
        return data.get('scheme_name'), elements
    except Exception:
        LOG.error('%s scheme read failed:\n%s', TAG, traceback.format_exc())
        return None, None


# arena gameplay/arenaType id -> scheme battle_mode string (same table the
# desktop uses in main.py mode_map: ctf->Standard, domination->Encounter...)
_ARENA_TYPE_MODE = {
    1: 'Standard', 2: 'Encounter', 3: 'Storm',
    4: 'Onslaught', 5: 'OnslaughtLight',
    30: 'Onslaught', 33: 'Onslaught', 34: 'Onslaught', 35: 'OnslaughtLight',
}


def _ui_mode_for_arena(at):
    """Best-effort scheme battle_mode for the current arena; None = unknown."""
    try:
        if isinstance(at, (int, float)):
            return _ARENA_TYPE_MODE.get(int(at))
        gp = getattr(at, 'gameplays', None)
        if gp:
            try:
                return _ARENA_TYPE_MODE.get(int(gp[0]))
            except Exception:
                pass
        return None
    except Exception:
        return None


def _arena_geometry():
    """(geometry, arena_type, detail) of the current battle.
    The avatar often appears AFTER the minimap registers (logs06.10-07.10:
    'no arena geometry') -> caller retries. Correct accessors (verified via
    py2.7 disassembly of avatar_getter.pyc): getArena(avatar) and
    getArenaInfo(avatar) TAKE the avatar argument - calling them without it
    raised TypeError which our silent except was hiding."""
    g = None
    via = None
    at = None
    try:
        avatar = BigWorld.player()
    except Exception:
        avatar = None
    if avatar is None:
        return None, None, 'player=None'
    # Real access pattern (Avatar.pyc disassembly, 07.10): the entity exposes
    # ONLY the chain arena.arenaType.geometryName - direct avatar.geometryName /
    # avatar.arenaType do NOT exist (that is why every getattr(..., None) in the
    # live 'geo try' logs returned None).
    try:
        arena = getattr(avatar, 'arena', None)
        if arena is None:
            from gui.battle_control import avatar_getter
            arena = avatar_getter.getArena(avatar)
        if arena is not None:
            at_obj = getattr(arena, 'arenaType', None)
            if at_obj is None and hasattr(arena, 'getArenaType'):
                try:
                    at_obj = arena.getArenaType()
                except Exception:
                    at_obj = None
            if at_obj is None:
                at_obj = getattr(arena, 'arenaInfo', None)
            if at_obj is not None:
                g = getattr(at_obj, 'geometryName', None)
                if g:
                    via = 'arena.arenaType'
                    at = at_obj
    except Exception:
        pass
    if not g:
        try:
            g = getattr(avatar, 'geometryName', None)
            if g:
                via = 'avatar'
        except Exception:
            pass
    detail = 'via=%s g=%r at=%r' % (via, g, at)
    return (str(g) if g else None), at, detail


def _start_fallback():
    """Resolve scheme without the program running (direct store read);
    retries while the player entity is still loading (07.10.2026)."""
    _g['warned'] = False
    _fallback_attempt(15)


def _fallback_attempt(tries_left):
    geom, at, detail = _arena_geometry()
    LOG.info('%s geo try(%d): %s', TAG, tries_left, detail)
    if not geom:
        if tries_left > 0:
            BigWorld.callback(1.0, lambda: _fallback_attempt(tries_left - 1))
        else:
            _resolve_degraded()
        return
    _resolve_and_store(geom, at)


def _adopt(src, pick):
    _g['scheme_name'] = pick.get('scheme_name')
    _g['elements'] = pick.get('elements') or []
    LOG.info('%s fallback -> %s scheme=%r n=%d', TAG, src,
             _g['scheme_name'], len(_g['elements']))
    if _g.get('should_register'):
        view = _g['view']
        if view is not None:
            view.register_and_push()


def _fresh(s):
    return s.get('updated_at') or s.get('saved_at') or ''


def _load_store():
    if not os.path.isfile(SAVED_SCHEMES_FILE):
        return []
    with open(SAVED_SCHEMES_FILE, 'r') as fh:
        db = json.load(fh)
    return [s for s in (db or {}).values()
            if isinstance(s, dict) and not s.get('_separator')
            and (s.get('elements') or [])]


def _warn_no_scheme_once():
    if _g.get('warned'):
        return
    _g['warned'] = True
    LOG.warning('%s NO SCHEME for this battle (user must be told)', TAG)
    try:
        from gui.SystemMessages import pushMessage, SM_TYPE
        pushMessage('SM Tactics: no scheme for this map/mode', SM_TYPE.Warning)
    except Exception:
        LOG.warning('%s toast failed:\n%s', TAG, traceback.format_exc())


def _resolve_and_store(geom, at):
    """Per the user spec (07.10): star = explicit user marker (any scheme);
    a base Standard scheme exists PER MAP and is the default; other battle
    modes without a single scheme -> warn the user once."""
    mode = _ui_mode_for_arena(at) or 'Standard'
    try:
        all_s = _load_store()
        # 1) user star - any scheme, any map/mode
        starred = [s for s in all_s if s.get('is_default')]
        if starred:
            _adopt('star', sorted(starred, key=_fresh)[-1])
            return
        # 2) map match
        cand = [s for s in all_s
                if s.get('map_id') == geom
                or (len(s.get('map_id', '')) > len(geom)
                    and s.get('map_id', '').endswith('_' + geom))]
        mode_match = [s for s in cand if s.get('battle_mode') == mode]
        if mode_match:
            _adopt('map-base', sorted(mode_match, key=_fresh)[-1])
            return
        if mode != 'Standard':
            # other battle mode without a single scheme -> tell the user
            LOG.info('%s arena=%r mode=%r -> no scheme for this mode (warn)',
                     TAG, geom, mode)
            _warn_no_scheme_once()
            return
        # 3) standard mode, per-map base not made yet -> global standard base
        base = [s for s in all_s if s.get('battle_mode') == 'Standard']
        if base:
            _adopt('base-any', sorted(base, key=_fresh)[-1])
            return
        LOG.info('%s arena=%r -> store empty', TAG, geom)
    except Exception:
        LOG.error('%s store fallback failed:\n%s', TAG, traceback.format_exc())


def _resolve_degraded():
    """Geometry never resolved (training/topography): best global choice,
    no per-map logic, no warning (the map itself is unknown)."""
    try:
        all_s = _load_store()
        starred = [s for s in all_s if s.get('is_default')]
        if starred:
            _adopt('star-any-map', sorted(starred, key=_fresh)[-1])
            return
        base = [s for s in all_s if s.get('battle_mode') == 'Standard'] or all_s
        if base:
            _adopt('geo-unknown-base', sorted(base, key=_fresh)[-1])
            return
        LOG.info('%s geo unknown and store empty', TAG)
    except Exception:
        LOG.error('%s degraded fallback failed:\n%s', TAG, traceback.format_exc())


# ---------------- visibility (Alt modes) ----------------

class _KeyState(object):
    """Alt tracking via InputHandler events (isAltDown pattern)."""

    def __init__(self):
        self.alt = False
        InputHandler.g_instance.onKeyDown += self._on_key_down
        InputHandler.g_instance.onKeyUp += self._on_key_up

    def _on_key_down(self, event):
        try:
            self.alt = bool(event.isAltDown())
            _g['alt'] = self.alt
            _apply_visibility()
        except Exception:
            pass

    def _on_key_up(self, event):
        try:
            self.alt = bool(event.isAltDown())
            _g['alt'] = self.alt
            _apply_visibility()
        except Exception:
            pass

    def close(self):
        try:
            InputHandler.g_instance.onKeyDown -= self._on_key_down
            InputHandler.g_instance.onKeyUp -= self._on_key_up
        except Exception:
            pass


def _apply_visibility():
    view = _g['view']
    if view is None:
        return
    mode = _g['mode']
    alt = _g['alt']
    if mode == MODE_SHOW_ON_ALT:
        on = alt
    elif mode == MODE_HIDE_ON_ALT:
        on = not alt
    else:
        on = True
    try:
        view.as_setVisible(on)
    except Exception:
        LOG.warning('%s setVisible failed:\n%s', TAG, traceback.format_exc())


# ---------------- settings (ModsSettingsAPI soft-dep) ----------------

def _settings_template(templates):
    return {
        'modDisplayName': 'MAPS Assistant',
        'enabled': True,
        'column1': [
            templates.createDropdown(
                'When to show the scheme', 'displayMode', list(MODE_LABELS),
                MODE_ALWAYS,
                tooltip=('{HEADER}Scheme visibility{/HEADER}{BODY}'
                         'Always - the scheme is always drawn on the minimap. '
                         'Show on Alt - appears while Alt is held. '
                         'Hide on Alt - hides while Alt is held.{/BODY}'),
                width=200),
            templates.createSlider(
                'Element size', 'elemScale', 100, 50, 200, 5,
                tooltip=('{HEADER}Scheme element size{/HEADER}{BODY}'
                         'Uniform size factor for all scheme elements'
                         ' on the minimap: 50%..200%, step 5. Positions stay unchanged.{/BODY}'),
                width=200),
        ],
    }


def _on_settings_changed(linkage, new_settings):
    if linkage != LINKAGE:
        return
    try:
        _g['mode'] = int(new_settings.get('displayMode', MODE_ALWAYS))
        _g['elemScale'] = int(new_settings.get('elemScale', 100))
        _apply_visibility()
        view = _g.get('view')
        if view is not None:
            view.as_setUserScale(_g['elemScale'] / 100.0)   # live apply
        LOG.info('%s settings: mode=%d elemScale=%d%%', TAG,
                 _g['mode'], _g['elemScale'])
    except Exception:
        LOG.warning('%s settings change:\n%s', TAG, traceback.format_exc())


def _on_settings_button(linkage, var_name, value):
    pass


def _load_settings():
    try:
        from gui.modsSettingsApi import g_modsSettingsApi, templates
    except Exception:
        LOG.info('%s ModsSettingsAPI unavailable - default mode: Always', TAG)
        return
    try:
        template = _settings_template(templates)
        saved = g_modsSettingsApi.getModSettings(LINKAGE, template)
        if saved:
            _g['mode'] = int(saved.get('displayMode', MODE_ALWAYS))
            _g['elemScale'] = int(saved.get('elemScale', 100))
            g_modsSettingsApi.registerCallback(
                LINKAGE, _on_settings_changed, _on_settings_button)
        else:
            st = g_modsSettingsApi.setModTemplate(
                LINKAGE, template, _on_settings_changed, _on_settings_button)
            _g['mode'] = int(st.get('displayMode', MODE_ALWAYS))
            _g['elemScale'] = int(st.get('elemScale', 100))
        LOG.info('%s settings registered (mode=%d elemScale=%d%%)', TAG, _g['mode'], _g['elemScale'])
    except Exception:
        LOG.warning('%s settings registration:\n%s', TAG, traceback.format_exc())


# ---------------- entry points ----------------

def init():
    try:
        LOG.info('%s init (python %s)', TAG, sys.version.split()[0])
        _load_settings()
        _g['keys'] = _KeyState()
        _setup_view_framework()
        LOG.info('%s ready', TAG)
    except Exception:
        LOG.error('%s init failed:\n%s', TAG, traceback.format_exc())


def fini():
    try:
        if _g['listeners']:
            g_eventBus.removeListener(events.AppLifeCycleEvent.INITIALIZED,
                                      on_app_initialized, EVENT_BUS_SCOPE.GLOBAL)
            g_eventBus.removeListener(events.ComponentEvent.COMPONENT_REGISTERED,
                                      on_component_registered, EVENT_BUS_SCOPE.GLOBAL)
            g_eventBus.removeListener(events.ComponentEvent.COMPONENT_UNREGISTERED,
                                      on_component_unregistered, EVENT_BUS_SCOPE.GLOBAL)
            _g['listeners'] = False
        if _g['keys'] is not None:
            _g['keys'].close()
            _g['keys'] = None
        view = _g['view']
        if view is not None:
            try:
                view.as_unregister()
            except Exception:
                pass
            _g['view'] = None
        LOG.info('%s fini', TAG)
    except Exception:
        LOG.error('%s fini failed:\n%s', TAG, traceback.format_exc())
