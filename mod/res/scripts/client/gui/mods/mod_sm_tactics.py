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

DEBUG = False  # False after live verification (#1463): no green debug frame
               # on the minimap; init/scheme/attach logs stay unconditional

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
    _g['scheme_name'] = name
    _g['elements'] = elements
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
        'modDisplayName': 'SM Tactics: scheme on minimap',
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
        ],
    }


def _on_settings_changed(linkage, new_settings):
    if linkage != LINKAGE:
        return
    try:
        _g['mode'] = int(new_settings.get('displayMode', MODE_ALWAYS))
        _apply_visibility()
        LOG.info('%s settings: mode=%d', TAG, _g['mode'])
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
            g_modsSettingsApi.registerCallback(
                LINKAGE, _on_settings_changed, _on_settings_button)
        else:
            st = g_modsSettingsApi.setModTemplate(
                LINKAGE, template, _on_settings_changed, _on_settings_button)
            _g['mode'] = int(st.get('displayMode', MODE_ALWAYS))
        LOG.info('%s settings registered (mode=%d)', TAG, _g['mode'])
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
