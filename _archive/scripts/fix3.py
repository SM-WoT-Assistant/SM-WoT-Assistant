import re

with open('stats_ai.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the method
pattern = r'(    def _finish_filter_with_items\(self, items_to_show\):.*?)(?=\n    def _animate_realtime)'
match = re.search(pattern, content, re.DOTALL)
if not match:
    print("Method not found")
    exit()

# New method with correct indentation
new_method = '''    def _finish_filter_with_items(self, items_to_show):
        """Build new grid in background, then swap instantly to avoid black flash."""
        max_cols = self._last_cols if self._last_cols > 0 else 5
        
        # Build new grid in a temporary frame (not yet shown)
        new_grid = tk.Frame(self.ai_canvas, bg="#000", padx=0.5, pady=0.5)
        
        if not items_to_show:
            # Show translated "NO TANKS FOUND" message
            msg_text = self.t("no_tanks_found", "NO TANKS FOUND")
            msg_label = tk.Label(
                new_grid,
                text=msg_text,
                bg="#000",
                fg="#bbbbbb",
                font=("Arial", 14, "bold"),
                anchor="center",
                justify="center"
            )
            msg_label.pack(expand=True, fill="both")
        else:
            row, col = 0, 0
            for tag, data in items_to_show:
                if not isinstance(data, dict):
                    continue
                card_f = tk.Frame(new_grid, bg="#111", width=170, height=155)
                card_f.grid(row=row, column=col, sticky="nsew", padx=0.5, pady=0.5)
                card_f.grid_propagate(False)
                
                nation = data.get("nation", "Unknown")
                img = self.get_composite_icon(tag, nation)
                card_f.bind("<Button-1>", lambda e, t=tag: self.on_ai_tank_select(t))
                
                if img:
                    lbl = tk.Label(card_f, image=img, bg="#111", cursor="hand2", bd=0)
                    lbl.place(relx=0.5, y=0, width=170, height=120, anchor="n")
                    lbl.bind("<Button-1>", lambda e, t=tag: self.on_ai_tank_select(t))
                    
                is_prem = data.get("is_premium", False)
                accent_color = "#e09b1b" if is_prem else "#bbbbbb"
                
                l1_f = tk.Frame(card_f, bg="#111")
                l1_f.place(relx=0.5, y=133, anchor="s")
                
                roman_tiers = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI"]
                try:
                    tier_num = int(data.get('tier', 0) or 0)
                except Exception:
                    tier_num = 0
                rt = roman_tiers[tier_num - 1] if 1 <= tier_num <= 11 else str(tier_num)
                tl = tk.Label(l1_f, text=rt, font=("Arial", 12, "bold"), fg=accent_color, bg="#111", bd=0)
                tl.pack(side="left", padx=3)
                
                s_flag = self.get_small_flag(nation)
                if s_flag:
                    fl = tk.Label(l1_f, image=s_flag, bg="#111", bd=0)
                    fl.pack(side="left", padx=3)
                    fl.bind("<Button-1>", lambda e, t=tag: self.on_ai_tank_select(t))
                    
                xvm_classes = {"LT": chr(0x3A), "MT": chr(0x3B), "HT": chr(0x3F), "TD": chr(0x2E), "SPG": chr(0x2D)}
                sym = xvm_classes.get(str(data.get('class', '')).upper(), "?")
                cl = tk.Label(l1_f, text=sym, font=("XVMSymbol", 17), fg=accent_color, bg="#111", bd=0)
                cl.pack(side="left", padx=3)
                
                raw_name = str(data.get("name", tag)).replace("_", " ")
                sys_id = tag.split('_')[0].lower()
                m = re.search(r'^([a-z]+)(\d*)$', sys_id)
                if m:
                    letters, digits = m.groups()
                    country_codes = {"gb", "uk", "usa", "ussr", "ger", "fr", "ch", "cz", "pl", "swe", "it", "jp", "cn", "r", "a", "g", "f", "s", "j"}
                    if letters in country_codes:
                        rn_low = raw_name.lower()
                        if rn_low.startswith(sys_id + " "):
                            raw_name = raw_name[len(sys_id):].strip()
                        elif digits and rn_low.startswith(f"{letters} {digits} "):
                            raw_name = raw_name[len(letters) + len(digits) + 1:].strip()
                        elif rn_low.startswith(letters + " "):
                            raw_name = raw_name[len(letters):].strip()
                
                name_words = raw_name.split()
                if not name_words:
                    name_words = [data.get("name", tag)]
                disp_name = ""
                for w in name_words:
                    if len(disp_name) + len(w) <= 22:
                        disp_name += w + " "
                    else:
                        break
                disp_name = disp_name.strip() if disp_name else name_words[0][:20]
                
                text_color = "#e09b1b" if is_prem else "#bbbbbb"
                nl = tk.Label(card_f, text=disp_name, bg="#111", fg=text_color, font=("Arial", 9, "bold"))
                nl.place(relx=0.5, y=152, anchor="s")
                
                for w in [tl, cl, nl, l1_f]:
                    w.bind("<Button-1>", lambda e, t=tag: self.on_ai_tank_select(t))
                
                col += 1
                if col >= max_cols:
                    col = 0
                    row += 1
            
            # Configure columns for the new grid
            for c in range(max_cols):
                new_grid.columnconfigure(c, weight=1)
            for c in range(max_cols, max_cols + 15):
                new_grid.columnconfigure(c, weight=0)
        
        # Bind scrollregion update
        new_grid.bind("<Configure>", lambda e: self.ai_canvas.configure(scrollregion=self.ai_canvas.bbox("all")))
        
        # SWAP: Update canvas window to point to new frame, then destroy old
        self.ai_canvas.itemconfig(self.ai_canvas_window, window=new_grid)
        old_grid = self.ai_grid_frame
        self.ai_grid_frame = new_grid
        old_grid.destroy()
        
        # Update scrollregion
        self.ai_canvas.configure(scrollregion=self.ai_canvas.bbox("all"))
        self.ai_canvas.update_idletasks()
        
        # Now hide progress bar
        try:
            canvas_width = self.filter_progress_canvas.winfo_width()
            if canvas_width > 1:
                self.filter_progress_canvas.coords(self._progress_rect, 0, 0, canvas_width, 4)
        except Exception:
            pass
'''

new_content = content[:match.start()] + new_method + content[match.end():]
with open('stats_ai.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Method replaced successfully")
