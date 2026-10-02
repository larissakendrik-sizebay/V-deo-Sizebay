#!/usr/bin/env python3
"""Gera legendas palavra-a-palavra (ASS com palavra ativa destacada) + SRT, ja remapeadas para o video editado.
Uso: captions.py transcript.json timeline.json out/captions [--brand brand/brand.json]"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))

ap = argparse.ArgumentParser()
ap.add_argument("transcript"); ap.add_argument("timeline"); ap.add_argument("outbase")
ap.add_argument("--brand", default=os.path.join(os.path.dirname(__file__), "..", "brand", "brand.json"))
ap.add_argument("--edl")
a = ap.parse_args()
B = json.load(open(a.brand)); C, V = B["caption"], B["canvas"]
tl = json.load(open(a.timeline))["shots"]
bgr = lambda h: "&H00" + h[5:7] + h[3:5] + h[1:3] + "&"          # #RRGGBB -> &H00BBGGRR&
ts = lambda t: f"{int(t//3600)}:{int(t%3600//60):02d}:{t%60:05.2f}"
srt = lambda t: f"{int(t//3600):02d}:{int(t%3600//60):02d}:{int(t%60):02d},{int(t%1*1000):03d}"

words = []
for sh in sorted(tl, key=lambda x: x["out_start"]):   # por plano: suporta hook repetido no inicio
    for w in json.load(open(a.transcript))["words"]:
        if not (sh["src_start"] - 0.02 <= w["start"] < sh["src_end"] - 0.05): continue
        s = sh["out_start"] + max(w["start"] - sh["src_start"], 0)
        e = min(sh["out_start"] + (w["end"] - sh["src_start"]), sh["out_end"])
        words.append({"t": w["w"].upper() if C["uppercase"] else w["w"], "s": s, "e": max(e, s + .05)})

# agrupa em blocos curtos (quebra em pontuacao, pausa ou limite de caracteres)
chunks, cur = [], []
for w in words:
    if cur and (len(cur) >= C["words_per_chunk"] or w["s"] - cur[-1]["e"] > .45
                or len(" ".join(x["t"] for x in cur + [w])) > C["max_chars_per_line"] + 6 or cur[-1]["t"][-1:] in ".?!"):
        chunks.append(cur); cur = []
    cur.append(w)
if cur: chunks.append(cur)

mv = C["margin_bottom_px"]
hdr = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {V['width']}
PlayResY: {V['height']}
WrapStyle: 2

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Sizebay,{C['font_family']},{C['font_size']},{bgr(C['text_color'])},{bgr(C['highlight_color'])},{bgr(C['outline_color'])},&H64000000&,-1,0,0,0,100,100,0,0,1,{C['outline_px']},{C['shadow_px']},2,60,60,{mv},1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
ev, sr = [], []
for n, ch in enumerate(chunks, 1):
    end_chunk = ch[-1]["e"]
    if C.get("animation") == "simple_fade":   # estilo referencia: bloco curto, sem destaque por palavra
        ev.append(f"Dialogue: 0,{ts(ch[0]['s'])},{ts(end_chunk)},Sizebay,,0,0,0,,{{\\fad(50,0)}}{' '.join(x['t'] for x in ch)}")
        sr.append(f"{n}\n{srt(ch[0]['s'])} --> {srt(end_chunk)}\n{' '.join(x['t'] for x in ch)}\n"); continue
    for k, w in enumerate(ch):
        st = w["s"]; en = ch[k + 1]["s"] if k + 1 < len(ch) else end_chunk
        parts = []
        for j, x in enumerate(ch):
            if j == k:
                parts.append("{\\c%s\\fscx100\\fscy100\\t(0,90,\\fscx118\\fscy118)\\t(90,180,\\fscx105\\fscy105)}%s{\\r}" % (bgr(C["highlight_color"]), x["t"]))
            else: parts.append(x["t"])
        ev.append(f"Dialogue: 0,{ts(st)},{ts(en)},Sizebay,,0,0,0,,{' '.join(parts)}")
    sr.append(f"{n}\n{srt(ch[0]['s'])} --> {srt(end_chunk)}\n{' '.join(x['t'] for x in ch)}\n")
open(a.outbase + ".ass", "w", encoding="utf-8").write(hdr + "\n".join(ev) + "\n")
open(a.outbase + ".srt", "w", encoding="utf-8").write("\n".join(sr))
print(f"{len(chunks)} blocos -> {a.outbase}.ass / .srt")

# ---- callouts (dado em destaque, palavra-chave, caixa, balao de citacao) -> captions_callouts.ass
if a.edl and json.load(open(a.edl)).get("callouts"):
    P = B["palette"]; acc = bgr(P["accent"]); wh = bgr("#FFFFFF")
    sty = lambda n, sz, col, bs=1, back=None, al=5, mv=0: (f"Style: {n},{C['font_family']},{sz},{col},{col},{back if bs==3 else bgr('#000000')},{'&H64000000&' if bs==3 else (back or '&H64000000&')},-1,0,0,0,100,100,0,0,{bs},{4 if bs==3 else 0},{0 if bs==3 else 3},{al},80,80,{mv},1")
    styles = "\n".join([sty("stat", 190, acc, al=8, mv=int(V['height']*.38)), sty("statsub", 62, wh, al=8, mv=int(V['height']*.38)+210),
                        sty("keyword", 150, acc, al=5), sty("keybox", 96, bgr("#000000"), bs=3, back=bgr("#FFFFFF"), al=5),
                        sty("quote", 58, wh, bs=3, back=acc, al=8, mv=int(V['height']*.17))])
    h2 = hdr.split("[V4+ Styles]")[0] + "[V4+ Styles]\n" + hdr.split("[V4+ Styles]\n")[1].split("\n")[0] + "\n" + styles + "\n\n[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n"
    ev2 = []
    for c in json.load(open(a.edl))["callouts"]:
        st, en = c["t"], c["t"] + c.get("dur", 2.0); k = c["kind"]; txt = c["text"]
        pop = "{\\fad(80,80)\\fscx60\\fscy60\\t(0,150,\\fscx100\\fscy100)}"
        if k == "stat":
            ev2.append(f"Dialogue: 1,{ts(st)},{ts(en)},stat,,0,0,0,,{pop}{txt}")
            if c.get("sub"): ev2.append(f"Dialogue: 1,{ts(st)},{ts(en)},statsub,,0,0,0,,{{\\fad(80,80)}}{c['sub']}")
        else:
            ev2.append(f"Dialogue: 1,{ts(st)},{ts(en)},{ {'keyword':'keyword','keyword_box':'keybox','quote':'quote'}[k] },,0,0,0,,{pop}{txt}")
    open(a.outbase + "_callouts.ass", "w", encoding="utf-8").write(h2 + "\n".join(ev2) + "\n")
    print(f"{len(ev2)} callouts -> {a.outbase}_callouts.ass")
