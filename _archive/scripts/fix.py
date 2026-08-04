with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()
old = '            self._po_win.geometry(f"{cw}x{ch}+{cx}+{cy}")\n        for var in self.selected_classes.values():\n            var.trace_add("write", lambda *args: self.painter.redraw())\n            \n'
new = '            self._po_win.geometry(f"{cw}x{ch}+{cx}+{cy}")\n\n'
idx = content.find(old)
if idx >= 0:
    content = content[:idx] + new + content[idx+len(old):]
    with open('main.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('FIXED')
else:
    print('NOT FOUND')
