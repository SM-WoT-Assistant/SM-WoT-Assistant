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

Data flow (user spec09.10.2026 - schemes are self-sufficient): when the
minimap appears (battle start) the mod resolves the battle map from
arena.arenaType.geometryName and shows exactly one of: 1) the starred
scheme (user's explicit choice); 2) the base scheme (is_base) for THIS
map; 3) a warning that the map has no scheme. Tactic-section schemes are
never shown. selected_scheme.json is NOT read.

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
from gui.Scaleform.framework import ScopeTemplates, ViewSettings
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
# the program's full scheme store# the program's full scheme store (same folder) - read directly so the mod
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
        _push_warn_if_ready()  # battle HUD is ready -> flush pending toast
        _g['view'] = self
        LOG.info('%s view populated (scheme=%r, elements=%s)', TAG,
                 _g['scheme_name'],
                 len(_g['elements']) if _g['elements'] else 0)
        if _g['should_register'] and not _g.get('resolving'):
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

    def as_showWarning(self, text):
        # View base class does NOT auto-forward unknown as_* attributes to
        # flashObject (AttributeError 'SmTacticsOverlay' object has no
        # attribute 'as_showWarning' in game.log 12.10.2026) - every as_*
        # callable from python needs an explicit wrapper like this one.
        self.flashObject.as_showWarning(str(text))

    def as_hideWarning(self):
        self.flashObject.as_hideWarning()


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
    # battle start moment: the minimap has just appeared (user spec): the
    # mod must pin the map of THIS battle and pick star -> base -> warn
    _g['should_register'] = True
    _start_battle_resolution()


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


def _entities_factory():
    """Scaleform entities factory.

    Client < 2.4.1 (e.g. 2.4.0.2): gui.Scaleform.framework.g_entitiesFactories.
    Client 2.4.1.0: that module attribute was REMOVED (0 occurrences in
    scripts.pkg) - importing it raises ImportError at module import and the
    whole mod dies before init(), so the ModsSettingsAPI menu entry never
    appears. The new access path is dependency.instance(IGuiLoader)
    (helpers.dependency + skeletons.gui.impl.IGuiLoader) -> .entitiesFactory
    (GuiLoader.entitiesFactory property). Same shim as the MIT OpenWG
    openwg_scaleform.get_entities_factory, consumed today by XVM on 2.4.1.0.
    """
    try:
        from gui.Scaleform.framework import g_entitiesFactories
        return g_entitiesFactories
    except ImportError:
        from helpers import dependency
        from skeletons.gui.impl import IGuiLoader
        return dependency.instance(IGuiLoader).entitiesFactory


def _setup_view_framework():
    factory = _entities_factory()
    factory.addSettings(ViewSettings(
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


# ---------------- battle resolution (star -> base -> warn) ----------------


def _battle_geometry():
    """Current battle map id; None while the avatar/arena is not ready
    (the avatar usually appears after the minimap registers - retries).
    Access pattern (Avatar.pyc disasm07.10 + live geo 08.10):
    arena.arenaType.geometryName, fallback avatar.geometryName."""
    try:
        avatar = BigWorld.player()
    except Exception:
        avatar = None
    if avatar is None:
        return None, 'player=None'
    g = None
    via = None
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
    except Exception:
        via = 'exc'
    if not g:
        try:
            g = getattr(avatar, 'geometryName', None)
            if g:
                via = 'avatar'
        except Exception:
            pass
    return (str(g) if g else None), via


def _map_matches(map_id, geom):
    """'06_ensk' vs 'ensk', full-id geometry vs full map_id (both forms
    seen live08.10)."""
    if not map_id or not geom:
        return False
    return (map_id == geom or map_id.endswith('_' + geom)
            or geom.endswith('_' + map_id))


def _pick_scheme(geom):
    """The scheme shown on the minimap (user spec09.10.2026):
starred FOR THIS MAP -> base (is_base) for this map -> None
(the caller warns). Tactic-section schemes are never shown."""
    all_s = _load_store()
    schemes = [s for s in all_s if s.get('section') != 'tactic']
    # star is PER-MAP too: a scheme must correspond to the battle map
    starred = [s for s in schemes
            if s.get('is_default') and _map_matches(s.get('map_id', ''), geom)]
    if starred:
        return sorted(starred, key=_fresh)[-1], 'star'
    base = [s for s in schemes
            if s.get('is_base') and _map_matches(s.get('map_id', ''), geom)]
    if base:
        return sorted(base, key=_fresh)[-1], 'base'
    # user spec 11.10: a map that HAS schemes must show its OWN freshest
    # scheme (not a warning) - warn only for maps without ANY scheme
    fresh = [x for x in schemes
             if _map_matches(x.get('map_id', ''), geom)]
    if fresh:
        return sorted(fresh, key=_fresh)[-1], 'map-fresh'
    return None, 'none'


def _resolve_attempt(tries_left):
    geom, via = _battle_geometry()
    LOG.info('%s geo: %r via=%s (%d tries left)', TAG, geom, via, tries_left)
    if not geom:
        if tries_left > 0:
            BigWorld.callback(1.0, lambda: _resolve_attempt(tries_left - 1))
        else:
            LOG.info('%s geometry unknown -> warn', TAG)
            _g['resolving'] = False
            _warn_no_scheme_once()
        return
    try:
        pick, how = _pick_scheme(geom)
    except Exception:
        LOG.error('%s pick failed:\n%s', TAG, traceback.format_exc())
        _g['resolving'] = False
        _warn_no_scheme_once()
        return
    _g['resolving'] = False
    if pick is None:
        LOG.info('%s map=%r -> NO SCHEME (warn)', TAG, geom)
        _warn_no_scheme_once()
        return
    _adopt(how, pick)


def _start_battle_resolution():
    _g['warned'] = False
    _g['pending_warn'] = False
    _g['warned_shown'] = False
    _g['resolving'] = True
    # state clear: the PREVIOUS battle's scheme must never leak onto
    # this map (live11.10: stale Mines n=60 pushed on a no-scheme map
    # right after the correct 'NO SCHEME' decision)
    _g['scheme_name'] = None
    _g['elements'] = None
    LOG.info('[SM Tactics] battle state cleared')
    _resolve_attempt(15)


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
    LOG.info('%s WARN-ENTRY warned=%r pend=%r shown=%r', TAG,
             _g.get('warned'), _g.get('pending_warn'),
             _g.get('warned_shown'))
    """Deferred toast: pushed when the battle view is ready.
    A toast fired while the loading screen is up is swallowed by the
    UI (live evidence09.10: resolve at14:55:56, view populated only
    at14:55:58, no toast visible)."""
    if _g.get('warned'):
        return
    _g['warned'] = True
    _g['pending_warn'] = True
    # do NOT push here: at this moment the battle HUD is still loading
    # and the system-messages layer swallows the toast (live09-10.10:
    # push accepted 1s before 'view populated' -> never shown).
    BigWorld.callback(6.0, _push_warn_if_ready)  # safety retry

def _push_warn_if_ready():
    if not _g.get("pending_warn") or _g.get("warned_shown"):
        return
    view = _g.get("view")
    if view is None:
        LOG.info("[SM Tactics] warning deferred: view not ready")
        return
    _g["pending_warn"] = False
    _g["warned_shown"] = True
    LOG.warning("[SM Tactics] NO SCHEME for this battle -> overlay warning")
    try:
        view.as_showWarning("No scheme for this map/mode")
        LOG.info("[SM Tactics] warning shown on overlay")
    except Exception:
        LOG.warning("[SM Tactics] warning failed:\n%s" % traceback.format_exc())


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
        'modDisplayName': 'SM WoT Assistant: scheme on minimap',
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
        # Always re-register the template (standard ModsSettingsAPI pattern):
        # setModTemplate updates the cached template in the API state file
        # (modDisplayName etc.) and merges saved user settings via
        # compareTemplates. The old if-saved branch never re-registered, so
        # the hangar kept showing the stale first-registration name.
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
