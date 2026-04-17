#!/usr/bin/env python3
"""Test nation filter button creation."""
import tkinter as tk
import os
from PIL import Image, ImageTk

root = tk.Tk()
root.geometry("800x100")

# Test loading flags
nl = ["USA", "USSR", "Germany", "France", "UK", "China", "Japan", "Czech", "Poland", "Sweden", "Italy"]
fm = {"USA": "usa", "USSR": "ussr", "Germany": "germany", "France": "france", "UK": "uk",
      "China": "china", "Japan": "japan", "Czech": "czech", "Poland": "poland", "Sweden": "sweden", "Italy": "italy"}

flag_size = (38, 25)
nf = tk.Frame(root, bg="#1a1a1a")
nf.pack(side="left", fill="both", expand=True, padx=5)

success_count = 0
fail_count = 0

for i, n in enumerate(nl):
    try:
        fn = fm.get(n)
        fp = os.path.join("extracted_icons", "clean_nations", f"{fn}.png")
        if os.path.exists(fp):
            print(f"  Loading from clean_nations: {fp}")
            fi = Image.open(fp).convert("RGBA").resize(flag_size, Image.LANCZOS)
        else:
            fallback = os.path.join("extracted_icons", "nations", f"{fn}.png")
            if os.path.exists(fallback):
                print(f"  Loading from fallback: {fallback}")
                fi = Image.open(fallback).convert("RGBA").resize(flag_size, Image.LANCZOS)
            else:
                print(f"  ✗ Not found: {fallback}, creating empty image")
                fi = Image.new("RGBA", flag_size, (0,0,0,0))
        
        img = ImageTk.PhotoImage(fi)
        btn = tk.Label(nf, image=img, text="" if img else n[:2], bg="#333333", cursor="hand2")
        btn.grid(row=0, column=i, sticky="nsew", padx=1)
        nf.columnconfigure(i, weight=1, uniform="eq_nf")
        
        success_count += 1
        print(f"✓ {n}: loaded successfully")
    except Exception as e:
        fail_count += 1
        print(f"✗ {n}: {e}")
        import traceback
        traceback.print_exc()

print(f"\n=== Result: {success_count} OK, {fail_count} FAILED ===")

root.mainloop()
