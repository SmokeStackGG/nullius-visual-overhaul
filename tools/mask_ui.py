#!/usr/bin/env python3
"""Stencil painter for Nullius: Visual Overhaul tier masks.

Open one base frame, SELECT the paintable sections (magic wand / brush / eraser),
then export a *binary stencil* (white = paint region, transparent elsewhere).
Feed the stencil to tools/apply_stencil.py with your base frames to bake the
grayscale mask across every animation frame, then pack it with Spritter.

Tools mirror the browser Mask Stencil Painter:
  - Magic wand: Contiguous or By-color, Tolerance slider; click = replace,
    Shift+click = add, Alt/Option+click = subtract.
  - Brush (add) / Eraser, with a size slider.
  - Grow / Shrink 1px, Invert, Clear, Undo (Cmd/Ctrl+Z).
  - Zoom; "Preview as mask" (grayscale) and a tier dropdown that previews the
    selection in each tier colour read from lib/tiers.lua.

Launch by double-clicking "Mask UI.command", or: python3 tools/mask_ui.py
"""
import os
import sys
import tkinter as tk
from tkinter import filedialog, ttk

import numpy as np
from scipy import ndimage
from PIL import Image, ImageTk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mask_tool import parse_tiers, lua_num  # noqa: E402
from mask_ops import LUMA  # noqa: E402
import mask_ops  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TIERS_LUA = os.path.join(REPO, "lib", "tiers.lua")
DEFAULT_SHEET = os.path.join(REPO, "graphics", "entity", "chemical-stager",
                             "chemical-stager-base.png")
VIEW_W, VIEW_H = 640, 640        # canvas viewport (scrolls for larger images)
CROSS = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], bool)  # 4-connectivity


class MaskUI:
    def __init__(self, root):
        self.root = root
        root.title("NVO Stencil Painter")
        # Tier colours are read solely from lib/tiers.lua (the single source of
        # truth, same palette the mod tints with at load time) -- never hardcoded.
        if not os.path.exists(TIERS_LUA):
            raise SystemExit(f"missing {TIERS_LUA}; tier colours come from lib/tiers.lua")
        self.tiers = parse_tiers(TIERS_LUA)
        if not self.tiers:
            raise SystemExit(f"no tier colours parsed from {TIERS_LUA}")
        self.base = None          # (H,W,4) float32
        self.alpha = None         # (H,W) bool building-pixels
        self.sel = None           # (H,W) bool current selection
        self.history = []         # selection snapshots for undo
        self.src_path = None
        self.zoom = 1.0
        self._build_controls()
        self._build_canvas()
        if os.path.exists(DEFAULT_SHEET):
            self.load_image(DEFAULT_SHEET)

    # ---- layout ---------------------------------------------------------
    def _build_controls(self):
        c = ttk.Frame(self.root, padding=8)
        c.grid(row=0, column=1, sticky="ns")

        ttk.Button(c, text="Open base…", command=self.open_dialog).pack(fill="x")
        ttk.Button(c, text="Import stencil…", command=self.import_dialog).pack(fill="x", pady=(2, 0))
        self.frame_var = tk.IntVar(value=0)
        fr = ttk.Frame(c); fr.pack(fill="x", pady=(4, 8))
        ttk.Label(fr, text="Sheet frame:").pack(side="left")
        self.frame_spin = ttk.Spinbox(fr, from_=0, to=999, width=5,
                                       textvariable=self.frame_var,
                                       command=self.reload_frame)
        self.frame_spin.pack(side="left")

        ttk.Label(c, text="Tool").pack(anchor="w", pady=(8, 0))
        self.mode = tk.StringVar(value="wand")
        for txt, val in [("Magic wand", "wand"),
                         ("Brush (add)", "brush"),
                         ("Eraser", "erase")]:
            ttk.Radiobutton(c, text=txt, value=val,
                            variable=self.mode).pack(anchor="w")

        ttk.Label(c, text="Wand tolerance").pack(anchor="w", pady=(8, 0))
        self.tol = tk.DoubleVar(value=32)
        ttk.Scale(c, from_=0, to=160, variable=self.tol).pack(fill="x")
        self.contig = tk.BooleanVar(value=True)
        cf = ttk.Frame(c); cf.pack(fill="x")
        ttk.Radiobutton(cf, text="Contiguous", value=True,
                        variable=self.contig).pack(side="left")
        ttk.Radiobutton(cf, text="By colour", value=False,
                        variable=self.contig).pack(side="left")
        self.edge_aware = tk.BooleanVar(value=True)
        ttk.Checkbutton(c, text="Edge-aware (stop at seams)",
                        variable=self.edge_aware).pack(anchor="w")
        ef = ttk.Frame(c); ef.pack(fill="x")
        ttk.Label(ef, text="Edge sensitivity").pack(side="left")
        self.show_edges = tk.BooleanVar(value=False)
        ttk.Checkbutton(ef, text="show", variable=self.show_edges,
                        command=self.render).pack(side="right")
        self.edge_thr = tk.DoubleVar(value=0.12)
        ttk.Scale(c, from_=0.02, to=0.5, variable=self.edge_thr,
                  command=lambda _=None: self.render()).pack(fill="x")
        ttk.Label(c, text="Shift+click adds · Alt+click subtracts",
                  foreground="#777").pack(anchor="w")

        ttk.Label(c, text="Brush size").pack(anchor="w", pady=(8, 0))
        self.brush = tk.IntVar(value=14)
        ttk.Scale(c, from_=1, to=80, variable=self.brush).pack(fill="x")

        rf = ttk.Frame(c); rf.pack(fill="x", pady=(10, 0))
        ttk.Button(rf, text="Grow 1px", command=lambda: self.morph(True)).pack(side="left", expand=True, fill="x")
        ttk.Button(rf, text="Shrink 1px", command=lambda: self.morph(False)).pack(side="left", expand=True, fill="x")
        rf2 = ttk.Frame(c); rf2.pack(fill="x")
        ttk.Button(rf2, text="Invert", command=self.invert).pack(side="left", expand=True, fill="x")
        ttk.Button(rf2, text="Clear", command=self.clear).pack(side="left", expand=True, fill="x")
        rf3 = ttk.Frame(c); rf3.pack(fill="x")
        ttk.Button(rf3, text="De-speck", command=lambda: self.cleanup(mask_ops.despeckle)).pack(side="left", expand=True, fill="x")
        ttk.Button(rf3, text="Fill holes", command=lambda: self.cleanup(mask_ops.fill_holes)).pack(side="left", expand=True, fill="x")
        ttk.Button(rf3, text="Smooth", command=lambda: self.cleanup(mask_ops.smooth)).pack(side="left", expand=True, fill="x")
        ttk.Button(c, text="Undo  (Cmd/Ctrl+Z)", command=self.undo).pack(fill="x")

        ttk.Label(c, text="Zoom").pack(anchor="w", pady=(10, 0))
        self.zoom_var = tk.DoubleVar(value=100)
        ttk.Scale(c, from_=25, to=800, variable=self.zoom_var,
                  command=self.on_zoom).pack(fill="x")

        ttk.Label(c, text="Preview").pack(anchor="w", pady=(8, 0))
        self.preview = tk.StringVar(value="Edit (overlay)")
        choices = ["Edit (overlay)", "Mask (grayscale)"] + \
                  [f"Tier {n}" for n in sorted(self.tiers)]
        self.prev_box = ttk.Combobox(c, textvariable=self.preview, values=choices,
                                     state="readonly")
        self.prev_box.pack(fill="x")
        self.prev_box.bind("<<ComboboxSelected>>", lambda _=None: self.render())
        self.swatch = tk.Label(c, width=12, text=" ", relief="solid", bd=1)
        self.swatch.pack(fill="x", pady=4)

        ttk.Button(c, text="Export stencil…", command=self.save).pack(fill="x", pady=(10, 2))
        self.status = ttk.Label(c, text="", wraplength=170, foreground="#555")
        self.status.pack(fill="x", pady=(8, 0))

    def _build_canvas(self):
        wrap = ttk.Frame(self.root)
        wrap.grid(row=0, column=0, sticky="nsew")
        self.canvas = tk.Canvas(wrap, width=VIEW_W, height=VIEW_H,
                                background="#282828", highlightthickness=0)
        hbar = ttk.Scrollbar(wrap, orient="horizontal", command=self.canvas.xview)
        vbar = ttk.Scrollbar(wrap, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=hbar.set, yscrollcommand=vbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        vbar.grid(row=0, column=1, sticky="ns")
        hbar.grid(row=1, column=0, sticky="ew")
        wrap.rowconfigure(0, weight=1); wrap.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1); self.root.columnconfigure(0, weight=1)

        self.canvas.bind("<Button-1>", lambda e: self.on_down(e, "replace"))
        self.canvas.bind("<Shift-Button-1>", lambda e: self.on_down(e, "add"))
        self.canvas.bind("<Alt-Button-1>", lambda e: self.on_down(e, "sub"))
        self.canvas.bind("<Option-Button-1>", lambda e: self.on_down(e, "sub"))
        for seq in ("<B1-Motion>", "<Shift-B1-Motion>",
                    "<Alt-B1-Motion>", "<Option-B1-Motion>"):
            self.canvas.bind(seq, self.on_drag)
        self.root.bind("<Command-z>", lambda e: self.undo())
        self.root.bind("<Control-z>", lambda e: self.undo())

    # ---- image loading --------------------------------------------------
    def open_dialog(self):
        p = filedialog.askopenfilename(
            title="Open base frame or sheet",
            filetypes=[("PNG", "*.png"), ("All", "*.*")])
        if p:
            self.load_image(p)

    def reload_frame(self):
        if self.src_path:
            self.load_image(self.src_path)

    def load_image(self, path):
        self.src_path = path
        img = Image.open(path).convert("RGBA")
        lua = os.path.splitext(path)[0] + ".lua"
        self.is_sheet = False
        if os.path.exists(lua):
            t = open(lua).read()
            cols = lua_num(t, "line_length")
            fw, fh = lua_num(t, "width"), lua_num(t, "height")
            if cols and cols > 1 and fw and fh:
                self.is_sheet = True
                fw, fh, cols = int(fw), int(fh), int(cols)
                i = self.frame_var.get()
                cx, ry = (i % cols) * fw, (i // cols) * fh
                img = img.crop((cx, ry, cx + fw, ry + fh))
        self.frame_spin.configure(state="normal" if self.is_sheet else "disabled")
        self.base = np.asarray(img, dtype=np.float32)
        h, w = self.base.shape[:2]
        self.alpha = self.base[:, :, 3] > 0
        self.edges = mask_ops.sobel_edges(self.base)
        self.sel = np.zeros((h, w), bool)
        self.history = []
        # initial zoom: fit the frame in the viewport (clamped to slider range)
        fit = min(VIEW_W / w, VIEW_H / h, 1.0) * 100
        self.zoom_var.set(max(25, min(800, round(fit))))
        self.zoom = self.zoom_var.get() / 100.0
        # pre-load this building's existing stencil so it can be edited in place
        loaded = ""
        auto = self._find_stencil(path)
        if auto:
            self.sel = self._sel_from_stencil(Image.open(auto).convert("RGBA"))
            loaded = "  · loaded " + os.path.basename(auto)
        self.render()
        self.set_status(f"{os.path.basename(path)}  {w}x{h}"
                        + ("  (sheet)" if self.is_sheet else "") + loaded)

    # ---- stencil import -------------------------------------------------
    def _find_stencil(self, base_path):
        """Find an existing stencil for the opened base (sibling <stem>-stencil.png
        or sprites/<stem>/<stem>-stencil.png), so it loads ready to edit."""
        stem = os.path.basename(base_path).split("-base")[0]
        for p in (os.path.join(os.path.dirname(base_path), stem + "-stencil.png"),
                  os.path.join(REPO, "sprites", stem, stem + "-stencil.png")):
            if os.path.exists(p):
                return p
        return None

    def _sel_from_stencil(self, img):
        """Boolean selection from a stencil image, resized to the base frame."""
        h, w = self.base.shape[:2]
        if img.size != (w, h):
            img = img.resize((w, h), Image.NEAREST)
        return mask_ops.stencil_selection(np.asarray(img, dtype=np.float32))

    def import_dialog(self):
        if self.base is None:
            self.set_status("open a base frame first")
            return
        start = os.path.join(REPO, "sprites")
        p = filedialog.askopenfilename(
            title="Import stencil PNG", initialdir=start if os.path.isdir(start) else None,
            filetypes=[("PNG", "*.png"), ("All", "*.*")])
        if not p:
            return
        self.snapshot()
        self.sel = self._sel_from_stencil(Image.open(p).convert("RGBA"))
        self.render()
        self.set_status(f"imported {os.path.basename(p)}  ({int(self.sel.sum())} px)")

    # ---- history --------------------------------------------------------
    def snapshot(self):
        self.history.append(self.sel.copy())
        if len(self.history) > 40:
            self.history.pop(0)

    def undo(self):
        if self.history:
            self.sel = self.history.pop()
            self.render()

    # ---- coords ---------------------------------------------------------
    def to_img(self, ev):
        x = int(self.canvas.canvasx(ev.x) / self.zoom)
        y = int(self.canvas.canvasy(ev.y) / self.zoom)
        return x, y

    def _in_bounds(self, x, y):
        return self.base is not None and 0 <= x < self.base.shape[1] and 0 <= y < self.base.shape[0]

    # ---- input ----------------------------------------------------------
    def on_down(self, ev, modifier):
        if self.base is None:
            return
        x, y = self.to_img(ev)
        if not self._in_bounds(x, y):
            return
        self.snapshot()
        if self.mode.get() == "wand":
            self.wand(x, y, modifier)
        else:
            self.paint(x, y, add=self.mode.get() == "brush")
        self.render()

    def on_drag(self, ev):
        if self.base is None or self.mode.get() == "wand":
            return
        x, y = self.to_img(ev)
        if self._in_bounds(x, y):
            self.paint(x, y, add=self.mode.get() == "brush")
            self.render()

    # ---- magic wand -----------------------------------------------------
    def wand(self, x, y, modifier):
        edge_aware = self.edge_aware.get()
        region = mask_ops.edge_aware_region(
            self.base, self.alpha, (x, y), self.tol.get(),
            edges=self.edges if edge_aware else None,
            edge_thr=self.edge_thr.get() if edge_aware else None,
            contiguous=self.contig.get())
        if not region.any():
            self.set_status("clicked an edge/empty pixel — raise tolerance")
            return
        if modifier == "replace":
            self.sel = region.copy()
        elif modifier == "add":
            self.sel |= region
        else:  # sub
            self.sel &= ~region
        self.set_status(f"{int(self.sel.sum())} px selected")

    # ---- brush ----------------------------------------------------------
    def paint(self, x, y, add):
        r = max(1, self.brush.get() // 2)
        h, w = self.base.shape[:2]
        y0, y1 = max(0, y - r), min(h, y + r + 1)
        x0, x1 = max(0, x - r), min(w, x + r + 1)
        yy, xx = np.ogrid[y0:y1, x0:x1]
        disk = (yy - y) ** 2 + (xx - x) ** 2 <= r * r
        self.sel[y0:y1, x0:x1][disk] = add

    # ---- refine ---------------------------------------------------------
    def morph(self, grow):
        if self.sel is None:
            return
        self.snapshot()
        op = ndimage.binary_dilation if grow else ndimage.binary_erosion
        self.sel = op(self.sel, structure=CROSS)
        self.render()

    def invert(self):
        if self.sel is None:
            return
        self.snapshot()
        self.sel = ~self.sel
        self.render()

    def cleanup(self, op):
        if self.sel is None or not self.sel.any():
            return
        self.snapshot()
        self.sel = op(self.sel)
        self.render()

    def clear(self):
        if self.sel is None:
            return
        self.snapshot()
        self.sel[:] = False
        self.render()

    # ---- render ---------------------------------------------------------
    def on_zoom(self, _=None):
        if self.base is None:
            return
        self.zoom = self.zoom_var.get() / 100.0
        self.render()

    def _tier_from_preview(self):
        p = self.preview.get()
        if p.startswith("Tier "):
            return int(p.split()[1])
        return None

    def render(self):
        if self.base is None:
            return
        h, w = self.base.shape[:2]
        mode = self.preview.get()
        tier = self._tier_from_preview()
        a = (self.base[:, :, 3] / 255.0)[:, :, None]
        bg = 0x28

        if mode == "Mask (grayscale)":
            luma = np.clip((self.base[:, :, :3] * LUMA).sum(2), 0, 255)
            comp = np.full((h, w, 3), bg, np.float32)
            sa = (self.sel[:, :, None] * a)
            for ch in range(3):
                comp[:, :, ch] = luma * sa[:, :, 0] + bg * (1 - sa[:, :, 0])
            self.swatch.configure(background="#282828")
        elif tier is not None:
            tint = self.tiers[tier]
            self.swatch.configure(background="#%02x%02x%02x"
                                  % tuple(int(v * 255) for v in tint[:3]))
            luma = np.clip((self.base[:, :, :3] * LUMA).sum(2) * 1.3, 0, 255)
            out = self.base[:, :, :3].copy()
            ta = tint[3]
            for ch in range(3):
                blended = self.base[:, :, ch] * (1 - ta) + luma * tint[ch] * ta
                out[:, :, ch] = np.where(self.sel, blended, self.base[:, :, ch])
            comp = out * a + bg * (1 - a)
        else:  # Edit (overlay)
            self.swatch.configure(background="#282828")
            comp = self.base[:, :, :3] * a + bg * (1 - a)
            ov = np.array([255, 59, 107], np.float32)
            sel3 = self.sel[:, :, None]
            comp = np.where(sel3, comp * 0.57 + ov * 0.43, comp)

        if self.show_edges.get():
            e = (self.edges > self.edge_thr.get()) & self.alpha
            comp[e] = comp[e] * 0.25 + np.array([80, 230, 230]) * 0.75
        img = Image.fromarray(comp.astype(np.uint8), "RGB")
        dw, dh = max(1, int(w * self.zoom)), max(1, int(h * self.zoom))
        img = img.resize((dw, dh), Image.NEAREST if self.zoom >= 1 else Image.LANCZOS)
        self.tkimg = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.tkimg)
        self.canvas.configure(scrollregion=(0, 0, dw, dh))
        n = int(self.sel.sum())
        self.set_status(f"{n:,} px selected" if n else "")

    def set_status(self, msg):
        self.status.configure(text=msg)

    # ---- export ---------------------------------------------------------
    def save(self):
        if self.sel is None:
            return
        h, w = self.sel.shape
        out = np.zeros((h, w, 4), np.uint8)
        out[self.sel] = (255, 255, 255, 255)   # binary white stencil
        default_dir = os.path.dirname(self.src_path) if self.src_path else REPO
        default_name = "stencil.png"
        if self.src_path:
            stem = os.path.basename(self.src_path).split("-base")[0]
            default_name = stem + "-stencil.png"
        p = filedialog.asksaveasfilename(
            title="Export stencil PNG", initialdir=default_dir,
            initialfile=default_name, defaultextension=".png",
            filetypes=[("PNG", "*.png")])
        if p:
            Image.fromarray(out, "RGBA").save(p)
            self.set_status(f"exported {os.path.basename(p)}  ({int(self.sel.sum())} px)\n"
                            "→ run apply_stencil.py with your base frames")


def main():
    root = tk.Tk()
    MaskUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
