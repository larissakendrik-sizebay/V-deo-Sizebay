#!/usr/bin/env python3
"""(Opcional) Cria um rascunho nativo do CapCut Desktop com video + legendas editaveis (fonte/cores da marca).
Requer: pip install pycapcut  (biblioteca de terceiros; a API do CapCut nao e oficial e pode quebrar entre versoes).
Uso: capcut_draft.py rough.mp4 captions.srt "Nome do projeto" --drafts-dir "<pasta de rascunhos do CapCut>"
Pasta tipica: Windows %LOCALAPPDATA%\\CapCut\\User Data\\Projects\\com.lveditor.draft | macOS ~/Movies/CapCut/User Data/Projects/com.lveditor.draft
Se falhar, importe rough.mp4 + .srt manualmente (ver SKILL.md)."""
import argparse, json, os, re
ap = argparse.ArgumentParser()
ap.add_argument("video"); ap.add_argument("srt"); ap.add_argument("name"); ap.add_argument("--drafts-dir", required=True)
ap.add_argument("--brand", default=os.path.join(os.path.dirname(__file__), "..", "brand", "brand.json"))
a = ap.parse_args()
import pycapcut as cc
B = json.load(open(a.brand)); C, V = B["caption"], B["canvas"]
hexrgb = lambda h: tuple(int(h[i:i+2], 16) / 255 for i in (1, 3, 5))
folder = cc.DraftFolder(a.drafts_dir)
script = folder.create_draft(a.name, V["width"], V["height"], allow_replace=True)
script.add_track(cc.TrackType.video).add_track(cc.TrackType.text)
vid = cc.VideoMaterial(a.video)
script.add_segment(cc.VideoSegment(vid, cc.Timerange(0, vid.duration)))
t2us = lambda s: int((int(s[0])*3600 + int(s[1])*60 + int(s[2]) + int(s[3])/1000) * 1e6)
for blk in open(a.srt, encoding="utf-8").read().strip().split("\n\n"):
    ln = blk.split("\n"); m = re.findall(r"(\d+):(\d+):(\d+),(\d+)", ln[1]); s, e = t2us(m[0]), t2us(m[1])
    seg = cc.TextSegment(" ".join(ln[2:]), cc.Timerange(s, e - s),
        style=cc.TextStyle(size=C["font_size"] / 10, bold=True, color=hexrgb(C["text_color"]), align=1),
        border=cc.TextBorder(color=hexrgb(C["outline_color"]), width=C["outline_px"] * 2),
        clip_settings=cc.ClipSettings(transform_y=-0.55))
    script.add_segment(seg)
script.save(); print("Rascunho criado:", a.name)
