package com.sm.tactics
{
    import flash.display.DisplayObject;
    import flash.display.Sprite;
    import flash.text.TextField;
    import flash.text.TextFieldAutoSize;
    import flash.text.TextFormat;
    import flash.text.Font;
    import flash.events.Event;

    import net.wg.infrastructure.base.AbstractView;
    import net.wg.data.constants.generated.LAYER_NAMES;
    import net.wg.gui.components.containers.MainViewContainer;
    import net.wg.gui.battle.views.BaseBattlePage;
    import net.wg.gui.battle.views.minimap.Minimap;
    import net.wg.gui.battle.views.minimap.EpicMinimap;

    /**
     * SM Tactics scheme overlay attached INSIDE the game minimap.
     *
     * Architecture follows the open-source community reference
     * wotstat/wotstat-positions (Minimap Overlay): a Scaleform View whose
     * AS3 layer is added as a child of minimap.entriesContainer, so all
     * drawing happens in minimap-local pixels. Inputs are normalized 0..1
     * coordinates - the exact format of the desktop app's scheme data.
     *
     * Contract with python (mod_sm_tactics.py):
     *   as_register()      - minimap appeared, attach the layer
     *   as_unregister()    - minimap gone, detach
     *   as_setElements(s)  - JSON array of scheme elements -> redraw
     *   as_setVisible(b)   - Alt visibility modes
     *   as_setDebug(b)     - debug frame (remove after verification, #1463)
     *   as_ping()          - roundtrip proof, returns 'ok'
     *   as_attachInfo()    - which branch setup() took, for the log
     */
    public class SmTacticsOverlay extends AbstractView
    {
        [Embed(source="xvmsymbol.ttf", fontName="XVMSymbol")]
        private static var _xvmFont:Class;

        [Embed(source="fontawesome-webfont.ttf", fontName="FontAwesome")]
        private static var _faFont:Class;

        private var _layer:Sprite = new Sprite();
        private var _dbg:Sprite = new Sprite();
        private var _elements:Array = [];
        private var _size:Number = 1;
        private var _registered:Boolean = false;
        private var _attached:Boolean = false;
        private var _attachBranch:String = "pending";
        private var _debug:Boolean = false;
        private var _mm:* = null;
        private var _mode:String = "entries";
        private var _visibleOn:Boolean = true;
        private var _host:* = null;
        private var _gridRef:DisplayObject = null;
        private var _rx:Number = 0;
        private var _ry:Number = 0;
        private var _rw:Number = 0;
        private var _rh:Number = 0;
        private var _watchOn:Boolean = false;
        private var _userScale:Number = 1;   // settings slider 50..200%

        private static const FA_TREE:String = String.fromCharCode(0xF18C);
        private static const XVM_SCALE:Object = {
            0x2B: 0.7, 0x2C: 0.7, 0x2D: 0.7, 0x2E: 0.7, 0x3A: 0.7, 0x3B: 0.7,
            0x3F: 0.7, 0x42: 0.7, 0x45: 0.7, 0x50: 0.7, 0x52: 0.7, 0x5C: 0.7,
            0x6F: 0.7
        };

        public function SmTacticsOverlay()
        {
            super();
        }

        override protected function configUI():void
        {
            super.configUI();
            try
            {
                Font.registerFont(new _xvmFont());
                Font.registerFont(new _faFont());
            }
            catch (e:*)
            {
            }
            // register() may already have been requested by python
            if (_registered)
            {
                setup();
            }
        }

        override protected function onDispose():void
        {
            unsetup();
            super.onDispose();
        }

        // ---------------- minimap attach (wotstat pattern) ----------------

        private function getBattlePage():BaseBattlePage
        {
            var container:MainViewContainer = App.containerMgr.getContainer(
                LAYER_NAMES.LAYER_ORDER.indexOf(LAYER_NAMES.VIEWS)) as MainViewContainer;
            if (container == null)
            {
                return null;
            }
            for (var i:int = 0; i < container.numChildren; ++i)
            {
                var child:DisplayObject = container.getChildAt(i);
                if (child is BaseBattlePage)
                {
                    return child as BaseBattlePage;
                }
            }
            return null;
        }

        private function setup():void
        {
            if (_attached || !_registered)
            {
                return;
            }
            var page:BaseBattlePage = getBattlePage();
            if (page == null)
            {
                _attachBranch = "nopage";
                return;
            }

            if (page.minimap is Minimap)
            {
                var mm:Minimap = page.minimap as Minimap;
                // _size = width of the WIDEST sprite child = the map/grid box in
                // entriesContainer-local units, measured BEFORE our layers attach
                // (empty layers have width 0 and cannot win). flags.width=210 is
                // the inner marker box (16px narrower than the grid), currentWidth
                // lives in another space - calibration 05.10.2026 proved both wrong
                // (455px box inside the 490px game grid, corners +17px inset).
                // Diagnostics (05.10.2026): full children inventory - names and
                // sizes - so the grid child can be identified by FACT, not guess.
                var best:DisplayObject = null;
                var kids:String = "";
                for (var ci:int = 0; ci < mm.entriesContainer.numChildren; ci++)
                {
                    var child:DisplayObject = mm.entriesContainer.getChildAt(ci);
                    if (kids.length > 0)
                        kids += "|";
                    kids += child.name + ":" + Math.round(child.width) + "x" + Math.round(child.height);
                    if (child is Sprite && (best == null || child.width > best.width))
                        best = child;
                }
                // entriesContainer = MARKER space only (kids inventory 05.10.2026:
                // flags/points/icons/... all 210x210 + personal strip - NO grid).
                // The map+grid holder is the "background" instance; its bounds in
                // Minimap-local space = the GRID RECT exactly (space-agnostic:
                // getBounds works whatever coordinate system it uses).
                _mm = mm;
                var gridRef:DisplayObject = mm["background"] as DisplayObject;
                if (gridRef != null)
                {
                    _mode = "grid";
                    _relayout(kids);
                }
                else
                {
                    var idx:int = mm.entriesContainer.getChildIndex(mm.entriesContainer.flags);
                    mm.entriesContainer.addChildAt(_dbg, idx + 1);
                    mm.entriesContainer.addChildAt(_layer, idx + 2);
                    _mode = "entries";
                    _size = Number(mm.entriesContainer.flags.width);
                    _attachBranch = "fallback210;w=" + _size + ";kids=" + kids;
                }
            }
            else if (page.minimap is EpicMinimap)
            {
                var epic:EpicMinimap = page.minimap as EpicMinimap;
                epic.background.addChild(_dbg);
                epic.background.addChild(_layer);
                _size = epic.background.originalWidth;
                _attachBranch = "epic";
            }
            else
            {
                _attachBranch = "unknown:" + typeof(page.minimap);
                return;
            }

            // entriesContainer children are centered on the minimap middle
            _layer.x = _dbg.x = -_size / 2;
            _layer.y = _dbg.y = -_size / 2;
            _layer.visible = _visibleOn;
            _attached = true;
            redraw();
        }

        private function unsetup():void
        {
            if (!_attached)
            {
                return;
            }
            if (_layer.parent != null)
            {
                _layer.parent.removeChild(_layer);
            }
            if (_dbg.parent != null)
            {
                _dbg.parent.removeChild(_dbg);
            }
            _attached = false;
            _attachBranch = "detached";
        }

        // ---------------- python -> AS3 API ----------------

        // Re-run on EVERY element push: the game repositions/finishes the map
        // widget AFTER populate (live evidence05.10.2026: frame corner stuck at
        // screen 250,257 over the sky; layer=1 = attached before game children
        // existed, so later game layers covered us). Fresh bounds + re-append
        // to the TOP of the parent keeps us aligned and visible.
        private function _relayout(kids:String):void
        {
            // Host = background's PARENT: bounds and our layer then live in the
            // SAME coordinate space by construction (no Point/pixelBounds - both
            // unavailable in this toolchain; and addChild to OUR view was the bug
            // that stuck the frame at screen 250,257, 05.10.2026).
            if (_mm == null) return;
            var gridRef:DisplayObject = _mm["background"] as DisplayObject;
            if (gridRef == null || gridRef.parent == null) return;
            var host:* = gridRef.parent;
            var r:* = gridRef.getBounds(host);
            _size = r.width;
            _host = host;
            _gridRef = gridRef;
            _rx = r.x; _ry = r.y; _rw = r.width; _rh = r.height;
            host.addChild(_dbg);
            host.addChild(_layer); // same parent = aligned; re-append = top of z
            _layer.x = _dbg.x = r.x;
            _layer.y = _dbg.y = r.y;
            _attachBranch = _mode + ";w=" + Math.round(_size * 10) / 10
                + ";r=" + Math.round(r.x) + "," + Math.round(r.y)
                + "," + Math.round(r.height)
                + (kids != null ? ";kids=" + kids : "");
        }

        public function as_register():void
        {
            _registered = true;
            setup();
            // Live minimap resize: the game re-lays the background out
            // LOCALLY (no ancestor scale), so the cached rect goes stale
            // and the scheme stops following the map (06.10.2026).
            if (!_watchOn)
            {
                addEventListener(Event.ENTER_FRAME, _onFrame);
                _watchOn = true;
            }
        }

        private function _onFrame(e:Event):void
        {
            if (!_registered || _mode != "grid" || _host == null || _gridRef == null)
                return;
            var r:* = _gridRef.getBounds(_host);
            if (Math.abs(r.x - _rx) > 0.5 || Math.abs(r.y - _ry) > 0.5
                || Math.abs(r.width - _rw) > 0.5 || Math.abs(r.height - _rh) > 0.5)
            {
                _relayout(null);
                redraw();
            }
        }

        public function as_unregister():void
        {
            _registered = false;
            unsetup();
            if (_watchOn)
            {
                removeEventListener(Event.ENTER_FRAME, _onFrame);
                _watchOn = false;
            }
        }

        // ---------------- payload reader ----------------
        // The client's JSON global stopped working after the 2.4.0.2 update
        // (JSON.parse silently emptied the elements, JSON.stringify threw and
        // aborted the python call). No working community mod uses JSON in AS3
        // on this client - so we parse our own payload shape with a plain
        // reader: array of flat objects (string/number/array/bool/null).

        private var _psrc:String = "";
        private var _ppos:int = 0;

        private function _skipWs():void
        {
            while (_ppos < _psrc.length)
            {
                var c:String = _psrc.charAt(_ppos);
                if (c == " " || c == "\t" || c == "\n" || c == "\r")
                {
                    _ppos++;
                }
                else
                {
                    break;
                }
            }
        }

        private function _expectWord(word:String):void
        {
            if (_psrc.substr(_ppos, word.length) != word)
            {
                throw new Error("kw@" + _ppos);
            }
            _ppos += word.length;
        }

        private function _parseValue():*
        {
            _skipWs();
            var c:String = _psrc.charAt(_ppos);
            if (c == "[")
            {
                return _parseArray();
            }
            if (c == "{")
            {
                return _parseObject();
            }
            if (c == '"')
            {
                return _parseString();
            }
            if (c == "t")
            {
                _expectWord("true");
                return true;
            }
            if (c == "f")
            {
                _expectWord("false");
                return false;
            }
            if (c == "n")
            {
                _expectWord("null");
                return null;
            }
            return _parseNumber();
        }

        private function _parseArray():Array
        {
            var out:Array = [];
            _ppos++; // [
            _skipWs();
            if (_psrc.charAt(_ppos) == "]")
            {
                _ppos++;
                return out;
            }
            while (true)
            {
                out.push(_parseValue());
                _skipWs();
                var c:String = _psrc.charAt(_ppos);
                if (c == ",")
                {
                    _ppos++;
                    continue;
                }
                if (c == "]")
                {
                    _ppos++;
                    return out;
                }
                throw new Error("array@" + _ppos);
            }
            return out; // unreachable - ASC requires an exit path
        }

        private function _parseObject():Object
        {
            var out:Object = {};
            _ppos++; // {
            _skipWs();
            if (_psrc.charAt(_ppos) == "}")
            {
                _ppos++;
                return out;
            }
            while (true)
            {
                _skipWs();
                if (_psrc.charAt(_ppos) != '"')
                {
                    throw new Error("key@" + _ppos);
                }
                var k:String = _parseString();
                _skipWs();
                if (_psrc.charAt(_ppos) != ":")
                {
                    throw new Error("colon@" + _ppos);
                }
                _ppos++;
                out[k] = _parseValue();
                _skipWs();
                var c:String = _psrc.charAt(_ppos);
                if (c == ",")
                {
                    _ppos++;
                    continue;
                }
                if (c == "}")
                {
                    _ppos++;
                    return out;
                }
                throw new Error("object@" + _ppos);
            }
            return out; // unreachable - ASC requires an exit path
        }

        private function _parseString():String
        {
            _ppos++; // opening quote
            var sb:String = "";
            while (_ppos < _psrc.length)
            {
                var c:String = _psrc.charAt(_ppos);
                if (c == '"')
                {
                    _ppos++;
                    return sb;
                }
                if (c == "\\")
                {
                    _ppos++;
                    var e:String = _psrc.charAt(_ppos);
                    if (e == "u")
                    {
                        sb += String.fromCharCode(parseInt(_psrc.substr(_ppos + 1, 4), 16));
                        _ppos += 4;
                    }
                    else if (e == "n")
                    {
                        sb += "\n";
                    }
                    else if (e == "t")
                    {
                        sb += "\t";
                    }
                    else if (e == "r")
                    {
                        sb += "\r";
                    }
                    else if (e == "b")
                    {
                        sb += "\b";
                    }
                    else if (e == "f")
                    {
                        sb += "\f";
                    }
                    else
                    {
                        sb += e; // ", \, /
                    }
                    _ppos++;
                }
                else
                {
                    sb += c;
                    _ppos++;
                }
            }
            throw new Error("string: unterminated");
        }

        private function _parseNumber():Number
        {
            var start:int = _ppos;
            if (_psrc.charAt(_ppos) == "-")
            {
                _ppos++;
            }
            while (_ppos < _psrc.length)
            {
                var c:String = _psrc.charAt(_ppos);
                if ((c >= "0" && c <= "9") || c == "." || c == "e" || c == "E" || c == "+" || c == "-")
                {
                    _ppos++;
                }
                else
                {
                    break;
                }
            }
            if (_ppos == start)
            {
                throw new Error("number@" + start);
            }
            return Number(_psrc.substring(start, _ppos));
        }

        private function _parseJson(src:String):*
        {
            _psrc = src;
            _ppos = 0;
            var v:* = _parseValue();
            _skipWs();
            if (_ppos < _psrc.length)
            {
                throw new Error("trailing@" + _ppos);
            }
            return v;
        }

        public function as_setElements(jsonStr:String):String
        {
            try
            {
                if (_mode == "grid") _relayout(null);
                var parsed:* = _parseJson(jsonStr);
                _elements = parsed is Array ? parsed as Array : [];
                redraw();
                return "ok n=" + _elements.length;
            }
            catch (e:*)
            {
                _elements = [];
                redraw();
                return "parseErr: " + e;
            }
            return "parseErr: unreachable"; // ASC requires an exit path
        }

        public function as_setVisible(on:Boolean):void
        {
            _visibleOn = on;
            _layer.visible = on;
            _dbg.visible = on;
        }

        // ModsSettingsAPI slider: uniform size factor for ALL element
        // sizes (positions stay at stored coords; only sizes scale).
        public function as_setUserScale(v:Number):void
        {
            var s:Number = Number(v);
            if (s > 0.1 && s < 4.0)
            {
                _userScale = s;
                redraw();
            }
        }

        public function as_setDebug(on:Boolean):void
        {
            _debug = on;
            redraw();
        }

        public function as_ping():String
        {
            return "ok";
        }

        // Render-side diagnostics for the python log: how many elements
        // actually reached the SWF, attach state, and where the first
        // element sits in minimap-local pixels (vs flags.width size).
        // Never throws: a failing diagnostic must not abort the python flow
        // (02.10.2026 - JSON.stringify aborted register_and_push before
        // visibility was applied).
        public function as_getDebugInfo():String
        {
            try
            {
                var n:int = (_elements != null) ? int(_elements.length) : 0;
                var firstStr:String = "";
                if (n > 0 && _elements != null)
                {
                    // first element that HAS coords (element[0] may lack them
                    // - rendered fine but left first= empty in the log)
                    for (var i:int = 0; i < n; i++)
                    {
                        var cc:* = (_elements[i] != null) ? _elements[i].coords : null;
                        if (cc is Array && Array(cc).length >= 2)
                        {
                            var pp:Array = px(Number(Array(cc)[0]), Number(Array(cc)[1]));
                            firstStr = int(pp[0]) + "," + int(pp[1]);
                            break;
                        }
                    }
                }
                var hasLayer:int = (_layer != null && _layer.parent != null) ? 1 : 0;
                var childIdx:int = -1;
                if (hasLayer == 1)
                {
                    childIdx = int(_layer.parent.getChildIndex(_layer));
                }
                return "n=" + n + " size=" + int(_size) +
                    " attached=" + (_attached ? 1 : 0) +
                    " reg=" + (_registered ? 1 : 0) +
                    " branch=" + _attachBranch +
                    " vis=" + (visible ? 1 : 0) + "/" + (_visibleOn ? 1 : 0) +
                    " layer=" + hasLayer + " idx=" + childIdx +
                    " first=" + firstStr;
            }
            catch (e:*)
            {
                return "dbgErr: " + e;
            }
            return "dbgErr: unreachable"; // ASC requires an exit path
        }

        public function as_attachInfo():String
        {
            return _attachBranch + ";size=" + _size + ";n=" + _elements.length;
        }

        // ---------------- rendering ----------------

        private function px(nx:Number, ny:Number):Array
        {
            // scheme coords are normalized over the minimap image (y down) -
            // the same space as entriesContainer content. No flip needed;
            // verified live (flip only required for arena-space coords).
            return [nx * _size, ny * _size];
        }

        private function redraw():void
        {
            _layer.graphics.clear();
            while (_layer.numChildren > 0)
            {
                _layer.removeChildAt(0);
            }
            _dbg.graphics.clear();

            if (!_attached)
            {
                return;
            }

            if (_debug)
            {
                _dbg.graphics.lineStyle(2, 0x00FF00, 0.9);
                _dbg.graphics.drawRect(0, 0, _size, _size);
                _dbg.graphics.lineStyle(2, 0xFF00FF, 1.0);
                _dbg.graphics.moveTo(_size / 2 - 10, _size / 2);
                _dbg.graphics.lineTo(_size / 2 + 10, _size / 2);
                _dbg.graphics.moveTo(_size / 2, _size / 2 - 10);
                _dbg.graphics.lineTo(_size / 2, _size / 2 + 10);
                _drawCalib();
            }

            if (_elements == null || _elements.length == 0)
            {
                return;
            }

            var sc:Number = Math.min(_size, _size) / 800.0 * _userScale;
            for (var i:int = 0; i < _elements.length; i++)
            {
                try
                {
                    drawElement(_elements[i], sc);
                }
                catch (e:*)
                {
                }
            }
        }

        private function num(v:*, d:Number):Number
        {
            return v === undefined || v === null ? d : Number(v);
        }

        private function hexColor(v:*):uint
        {
            if (v is String && String(v).charAt(0) == "#")
            {
                return uint(parseInt(String(v).substring(1), 16));
            }
            return 0xFFAA00;
        }

        private function drawElement(obj:Object, sc:Number):void
        {
            if (obj == null)
            {
                return;
            }
            var objSc:Number = num(obj.scale, 1.0);
            var scEff:Number = sc * objSc;
            var r12:Number = Math.max(3, 12 * scEff);
            var r4:Number = Math.max(2, 4 * scEff);
            var lw:Number = Math.max(1, num(obj.thickness, 3) * scEff);
            var mtSz:int = Math.max(6, int(9 * scEff));
            var poiBase:int = Math.max(12, int(48 * scEff));
            var ttSz:int = Math.max(6, int(10 * scEff));
            var col:uint = hexColor(obj.color);

            var coords:Array = obj.coords as Array;
            if ((coords == null || coords.length < 2) && obj.x1 !== undefined)
            {
                coords = [obj.x1, obj.y1,
                    obj.x2 !== undefined ? obj.x2 : obj.x1,
                    obj.y2 !== undefined ? obj.y2 : obj.y1];
            }
            if (coords == null || coords.length < 2)
            {
                return;
            }

            var type:String = String(obj.type);

            if (type == "dot")
            {
                var p:Object = px(coords[0], coords[1]);
                var dsz:Number = Math.max(2, num(obj.size, 3) * scEff);
                _layer.graphics.beginFill(col, 1);
                _layer.graphics.drawRect(p[0] - dsz, p[1] - dsz, dsz * 2, dsz * 2);
                _layer.graphics.endFill();
                return;
            }

            if (type == "marker" || type == "arrow")
            {
                if (coords.length < 4)
                {
                    return;
                }
                var a:Object = px(coords[0], coords[1]);
                var b:Object = px(coords[2], coords[3]);
                dashedLine([a[0], a[1], b[0], b[1]], col, lw);
                arrowHead(a[0], a[1], b[0], b[1], col, lw);
                if (type == "marker")
                {
                    _layer.graphics.lineStyle(Math.max(1, lw - 1), col, 1);
                    _layer.graphics.drawCircle(a[0], a[1], r12);
                    _layer.graphics.lineStyle(0, 0xFFFFFF, 1);
                    _layer.graphics.beginFill(0xFFFFFF, 1);
                    _layer.graphics.drawCircle(a[0], a[1], r4);
                    _layer.graphics.endFill();
                    if (obj.text)
                    {
                        var mp:Object = markerTextPos(obj, coords, sc);
                        label(String(obj.text), "Arial", mtSz, col, mp.x, mp.y, true);
                    }
                }
                return;
            }

            if (type == "brush")
            {
                if (coords.length < 4)
                {
                    return;
                }
                var flat:Array = [];
                for (var ci:int = 0; ci + 1 < coords.length; ci += 2)
                {
                    var q:Object = px(coords[ci], coords[ci + 1]);
                    flat.push(q[0], q[1]);
                }
                dashedLine(flat, col, lw);
                if (obj.arrow_start && flat.length >= 4)
                {
                    dirArrow(flat[2], flat[3], flat[0], flat[1], col, lw);
                }
                if (obj.arrow_end && flat.length >= 4)
                {
                    var li:int = flat.length - 1;
                    // arrow at last point traveling from the previous point
                    dirArrow(flat[li - 1], flat[li], flat[li - 3], flat[li - 2], col, lw);
                }
                if (obj.text)
                {
                    var cen:Object = polylineCentroid(flat);
                    label(String(obj.text), "Arial", mtSz, col, cen.x, cen.y - 10 * sc, true);
                }
                return;
            }

            if (type == "zone")
            {
                if (coords.length < 4)
                {
                    return;
                }
                var wz:Number = Math.max(1, lw - 1);
                var zonePts:Array = [];
                for (var zi:int = 0; zi + 1 < coords.length; zi += 2)
                {
                    var zp:Object = px(coords[zi], coords[zi + 1]);
                    zonePts.push(zp[0], zp[1]);
                }
                zonePts.push(zonePts[0], zonePts[1]);
                dashedLine(zonePts, col, wz);
                return;
            }

            if (type == "text")
            {
                var anchor:Object = px(coords[0], coords[1]);
                var poiData:* = obj.poi;
                if (poiData is String)
                {
                    var ps:String = String(poiData);
                    if (ps.indexOf("xvm_") == 0)
                    {
                        poiData = [parseInt(ps.substring(4), 16)];
                    }
                    else if (ps == "tree")
                    {
                        poiData = ["tree"];
                    }
                    else
                    {
                        poiData = [];
                    }
                }
                if (!(poiData is Array))
                {
                    poiData = [];
                }
                var arr:Array = poiData as Array;
                if (arr.length > 0)
                {
                    drawPoiRow(arr, anchor[0], anchor[1], poiBase, ttSz, col, sc); // no lift: glyph centered on the stored point
                }
                if (obj.text)
                {
                    label(String(obj.text), "Arial", ttSz, col,
                        anchor[0], anchor[1] + (arr.length > 0 ? 15 * sc : 0), true);
                }
                else if (arr.length == 0)
                {
                    // empty text with empty poi - nothing to draw
                }
            }
        }

        private function markerTextPos(obj:Object, coords:Array, sc:Number):Object
        {
            var cw:Number = _size;
            var ch:Number = _size;
            if (obj.text_coords != null && obj.text_coords.length >= 2)
            {
                return px(obj.text_coords[0], obj.text_coords[1]);
            }
            return {x: (coords[0] + coords[2]) / 2 * cw,
                    y: (coords[1] + coords[3]) / 2 * ch - 10 * sc};
        }

        private function polylineCentroid(flat:Array):Object
        {
            var sx:Number = 0;
            var sy:Number = 0;
            var n:int = flat.length / 2;
            for (var i:int = 0; i < flat.length; i += 2)
            {
                sx += flat[i];
                sy += flat[i + 1];
            }
            return {x: n > 0 ? sx / n : 0, y: n > 0 ? sy / n : 0};
        }

        private function dashRuns(pts:Array, on:Number, off:Number):Array
        {
            // explicit dash segmentation (Tk -dash is unreliable, painter #2009)
            var runs:Array = [];
            var acc:Number = 0;
            var phaseOn:Boolean = true;
            var run:Array = [pts[0], pts[1]];
            var i:int = 0;
            while (i + 3 < pts.length)
            {
                var x1:Number = pts[i];
                var y1:Number = pts[i + 1];
                var x2:Number = pts[i + 2];
                var y2:Number = pts[i + 3];
                var seg:Number = Math.sqrt((x2 - x1) * (x2 - x1) + (y2 - y1) * (y2 - y1));
                if (seg <= 0)
                {
                    i += 2;
                    continue;
                }
                var posInSeg:Number = 0;
                var limit:Number = phaseOn ? on : off;
                while (posInSeg + (limit - acc) <= seg)
                {
                    var step:Number = limit - acc;
                    posInSeg += step;
                    var tx:Number = x1 + (x2 - x1) * (posInSeg / seg);
                    var ty:Number = y1 + (y2 - y1) * (posInSeg / seg);
                    run.push(tx, ty);
                    if (phaseOn && run.length >= 4)
                    {
                        runs.push(run);
                    }
                    phaseOn = !phaseOn;
                    acc = 0;
                    limit = phaseOn ? on : off;
                    if (phaseOn)
                    {
                        run = [tx, ty];
                    }
                }
                acc += seg - posInSeg;
                if (phaseOn)
                {
                    run.push(x2, y2);
                }
                i += 2;
            }
            if (phaseOn && run.length >= 4)
            {
                runs.push(run);
            }
            return runs;
        }

        private function dashedLine(pts:Array, col:uint, lw:Number):void
        {
            var runs:Array = dashRuns(pts, 2.6 * lw, 1.5 * lw);
            for (var i:int = 0; i < runs.length; i++)
            {
                var r:Array = runs[i];
                _layer.graphics.lineStyle(lw, col, 1);
                _layer.graphics.moveTo(r[0], r[1]);
                for (var j:int = 2; j + 1 < r.length; j += 2)
                {
                    _layer.graphics.lineTo(r[j], r[j + 1]);
                }
            }
        }

        private function arrowHead(x1:Number, y1:Number, x2:Number, y2:Number,
                                   col:uint, lw:Number):void
        {
            var dx:Number = x2 - x1;
            var dy:Number = y2 - y1;
            var d:Number = Math.sqrt(dx * dx + dy * dy);
            if (d <= 0)
            {
                return;
            }
            var ux:Number = dx / d;
            var uy:Number = dy / d;
            // painter: short line -> solid tail = whole segment (d), else alen
            var alen:Number = 16.0 * (lw / 3.0);
            drawArrowShape(x2, y2, ux, uy, col, lw, (d > alen) ? alen : d);
        }

        private function dirArrow(tx:Number, ty:Number, bx:Number, by:Number,
                                  col:uint, lw:Number):void
        {
            // arrow AT (tx,ty) traveling away from (bx,by)
            var dx:Number = tx - bx;
            var dy:Number = ty - by;
            var d:Number = Math.sqrt(dx * dx + dy * dy);
            if (d <= 0)
            {
                return;
            }
            var alen:Number = 16.0 * (lw / 3.0);
            drawArrowShape(tx, ty, dx / d, dy / d, col, lw, (d > alen) ? alen : d);
        }

        private function drawArrowShape(tipx:Number, tipy:Number, ux:Number, uy:Number,
                                        col:uint, lw:Number, tailLen:Number):void
        {
            // SAME shape as the desktop painter._arrow_shape (01.10.2026):
            // Tk (16, 20, 6) * k with k = lw/3 - strictly linear in lw so the
            // head shrinks with the element scale (desktop floor removed the
            // same day - screenshot 380: 16x20 head over a 2px line).
            var k:Number = lw / 3.0;
            var alen:Number = 16.0 * k;      // head length (solid tail too)
            var halfW:Number = 10.0 * k;     // (20.0 * k) / 2
            var notch:Number = 6.0 * k;
            var pxn:Number = -uy;
            var pyn:Number = ux;
            var tailx:Number = tipx - ux * tailLen;
            var taily:Number = tipy - uy * tailLen;
            var basecx:Number = tipx - ux * alen;
            var basecy:Number = tipy - uy * alen;
            var notchx:Number = tipx - ux * (alen - notch);
            var notchy:Number = tipy - uy * (alen - notch);
            _layer.graphics.lineStyle(lw, col, 1);
            _layer.graphics.moveTo(tailx, taily);
            _layer.graphics.lineTo(tipx, tipy);
            _layer.graphics.beginFill(col, 1);
            _layer.graphics.moveTo(tipx, tipy);
            _layer.graphics.lineTo(basecx + pxn * halfW, basecy + pyn * halfW);
            _layer.graphics.lineTo(notchx, notchy);
            _layer.graphics.lineTo(basecx - pxn * halfW, basecy - pyn * halfW);
            _layer.graphics.lineTo(tipx, tipy);
            _layer.graphics.endFill();
        }

        private function drawPoiRow(poi:Array, cx:Number, cy:Number,
                                    poiBase:int, ttSz:int, col:uint, sc:Number):void
        {
            var items:Array = [];
            var total:Number = 0;
            var i:int;
            for (i = 0; i < poi.length; i++)
            {
                var code:* = poi[i];
                if (code === "tree")
                {
                    var szT:int = int(poiBase * 0.5);
                    var wT:Number = measure(FA_TREE, szT, "FontAwesome") + 4 * sc;
                    items.push({kind: "tree", sz: szT, w: wT});
                    total += wT;
                }
                else
                {
                    var icode:int = int(code);
                    var scale:Number = XVM_SCALE[icode] !== undefined ? Number(XVM_SCALE[icode]) : 1.0;
                    var sz:int = int(poiBase * scale);
                    var g:String = String.fromCharCode(icode);
                    var w:Number = measure(g, sz, "XVMSymbol") + 4 * sc;
                    items.push({kind: "xvm", ch: g, sz: sz, w: w});
                    total += w;
                }
            }
            var x:Number = cx - total / 2;
            for (i = 0; i < items.length; i++)
            {
                var it:Object = items[i];
                var icx:Number = x + it.w / 2;
                if (it.kind == "tree")
                {
                    label(String(it.ch), "FontAwesome", int(it.sz), col, icx, cy, false);
                }
                else
                {
                    label(String(it.ch), "XVMSymbol", int(it.sz), 0x000000, icx, cy, false);
                    label(String(it.ch), "XVMSymbol", Math.max(6, int(it.sz) - Math.max(2, int(4 * sc))),
                        col, icx, cy, false);
                }
                x += it.w;
            }
        }

        private function measure(text:String, size:int, font:String):Number
        {
            var tf:TextField = new TextField();
            tf.autoSize = TextFieldAutoSize.LEFT;
            if (font != "Arial")
            {
                // Icon fonts must go through the EMBEDDED path: GFx does not
                // enumerate arbitrary installed Windows fonts, so the device
                // lookup silently fell back to raw ASCII (minimap showed
                // '-'/';'/'. instead of XVMSymbol icons - 04.10.2026).
                tf.embedFonts = true;
            }
            tf.defaultTextFormat = new TextFormat(font, size, 0xFFFFFF);
            tf.text = text;
            return tf.textWidth;
        }

        // Calibration crosses (debug cycle 05.10.2026): magenta = stored
        // anchor of the E4 square, yellow = base1 data, cyan = corners.
        // Measuring them against the game grid on ONE screenshot gives the
        // exact px() offset to bake in as _CAL_X/_CAL_Y (removed with debug).
        private function _drawCalib():void
        {
            _cross(0.358, 0.528, 0xFF00FF, 16);   // square anchor (data)
            _cross(0.534, 0.084, 0xFFFF00, 16);   // base1 data
            _cross(0.0, 0.0, 0x00FFFF, 14);       // corners
            _cross(1.0, 0.0, 0x00FFFF, 14);
            _cross(0.0, 1.0, 0x00FFFF, 14);
            _cross(1.0, 1.0, 0x00FFFF, 14);
        }

        private function _cross(nx:Number, ny:Number, color:uint, arm:int):void
        {
            var p:Array = px(nx, ny);
            var x:Number = Number(p[0]);
            var y:Number = Number(p[1]);
            _dbg.graphics.lineStyle(2, color, 0.95);
            _dbg.graphics.moveTo(x - arm, y);
            _dbg.graphics.lineTo(x + arm, y);
            _dbg.graphics.moveTo(x, y - arm);
            _dbg.graphics.lineTo(x, y + arm);
        }

        private function label(text:String, font:String, size:int, color:uint,
                               cx:Number, cy:Number, bold:Boolean):void
        {
            if (!text)
            {
                return;
            }
            var tf:TextField = new TextField();
            tf.autoSize = TextFieldAutoSize.LEFT;
            tf.selectable = false;
            tf.mouseEnabled = false;
            if (font != "Arial")
            {
                tf.embedFonts = true;   // see measure(): embedded icon fonts
            }
            tf.defaultTextFormat = new TextFormat(font, size, color, bold);
            tf.text = text;
            tf.x = cx - tf.textWidth / 2;
            tf.y = cy - tf.textHeight / 2;
            _layer.addChild(tf);
        }
    }
}
