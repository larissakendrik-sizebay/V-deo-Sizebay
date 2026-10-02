#!/usr/bin/env python3
"""Analisa transcript.json: silencios, hesitacoes, repeticoes/falsos comecos, mudancas de assunto,
candidatos a hook e lista de cortes. Uso: analyze.py transcript.json analysis.json [--media video.mp4]"""
import argparse, json, re, subprocess

ap = argparse.ArgumentParser()
ap.add_argument("transcript"); ap.add_argument("out"); ap.add_argument("--media")
ap.add_argument("--gap", type=float, default=0.35, help="pausa minima (s) para virar silencio")
ap.add_argument("--keep-pause", type=float, default=0.12, help="pausa residual mantida apos corte")
a = ap.parse_args()
T = json.load(open(a.transcript)); W = T["words"]

norm = lambda s: re.sub(r"[^\wà-ú]", "", s.lower())
HARD_FILLERS = {"eh", "ah", "hum", "hm", "hmm", "ahn", "uh", "um", "ééé", "éé", "aham", "ahm", "er", "tá"}
SOFT_FILLERS = {"tipo", "né", "assim", "então", "basicamente", "sabe"}  # so sinaliza; Claude decide
STOP = set("a o as os de da do das dos e é em um uma para por com que se na no nas nos ao à mas ou eu você voce a gente isso esse essa ele ela não nao já ja mais muito como foi ser tem ter são sao vai vou".split())

# 1) silencios por gaps entre palavras (+ silencedetect do ffmpeg se houver midia)
silences = []
for i in range(len(W) - 1):
    g = W[i + 1]["start"] - W[i]["end"]
    if g >= a.gap: silences.append({"start": W[i]["end"], "end": W[i + 1]["start"], "dur": round(g, 3), "src": "words"})
if W and W[0]["start"] > 0.25: silences.insert(0, {"start": 0, "end": W[0]["start"], "dur": W[0]["start"], "src": "lead-in"})
if a.media:
    r = subprocess.run(["ffmpeg", "-i", a.media, "-af", "silencedetect=n=-35dB:d=0.3", "-f", "null", "-"], capture_output=True, text=True)
    st = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    for s, e in zip(st, en): silences.append({"start": s, "end": e, "dur": round(e - s, 3), "src": "ffmpeg"})

# 2) hesitacoes
fillers = [{"i": i, "w": w["w"], "start": w["start"], "end": w["end"], "kind": "hard" if norm(w["w"]) in HARD_FILLERS else "soft"}
           for i, w in enumerate(W) if norm(w["w"]) in HARD_FILLERS | SOFT_FILLERS]

# 3) repeticoes: palavra duplicada e falso comeco (mesmo n-grama reaparece em ate 10 palavras -> descarta o 1o take)
reps = []
for i in range(len(W) - 1):
    if norm(W[i]["w"]) and norm(W[i]["w"]) == norm(W[i + 1]["w"]):
        reps.append({"type": "word", "start": W[i]["start"], "end": W[i]["end"], "text": W[i]["w"], "i": i})
N = 3
skip_until = 0
for i in range(len(W) - N):
    if i < skip_until: continue   # evita matches deslocados do mesmo falso comeco
    g = [norm(x["w"]) for x in W[i:i + N]]
    if not all(g) or all(x in STOP for x in g): continue
    for j in range(i + N, min(i + 14, len(W) - N)):
        if [norm(x["w"]) for x in W[j:j + N]] == g:
            reps.append({"type": "false_start", "start": W[i]["start"], "end": W[j]["start"],
                         "text": " ".join(x["w"] for x in W[i:j]), "keep_from": W[j]["start"], "i": i}); skip_until = j; break

# 4) mudancas de assunto: janelas de ~8s com baixa sobreposicao lexical + pausa
def terms(ws): return {norm(x["w"]) for x in ws if norm(x["w"]) not in STOP and len(norm(x["w"])) > 3}
shifts, step, win = [], 4.0, 8.0
t = win
while W and t < T["duration"] - win:
    A = terms([w for w in W if t - win <= w["start"] < t]); B = terms([w for w in W if t <= w["start"] < t + win])
    if A and B:
        j = len(A & B) / len(A | B)
        if j < 0.06: shifts.append({"at": t, "similarity": round(j, 3)})
    t += step
# funde proximos, ancora na maior pausa proxima
merged = []
for s in shifts:
    if merged and s["at"] - merged[-1]["at"] < win: continue
    near = [x for x in silences if abs(x["start"] - s["at"]) < 3]
    if near: s["at"] = max(near, key=lambda x: x["dur"])["end"]
    merged.append(s)

# 5) hooks: pontua frases
POWER = r"\b(nunca|erro|segredo|ninguém|ninguem|pare de|por que|porquê|verdade|mentira|jamais|dobrar|dobra|triplic|grátis|gratis|sem|descobri|cuidado|problema)\b"
hooks = []
for s in T["segments"]:
    txt = s["text"]; n = len(txt.split())
    if n < 3: continue
    sc = 0
    sc += 2 if "?" in txt else 0
    sc += 2 if re.search(r"\d", txt) else 0
    sc += 2 * len(re.findall(POWER, txt.lower()))
    sc += 2 if 4 <= n <= 12 else (0 if n <= 18 else -2)
    sc += 1 if re.search(r"\b(você|voce|seu|sua)\b", txt.lower()) else 0
    sc += 1 if re.search(r"\b(mas|porém|só que|em vez)\b", txt.lower()) else 0
    sc -= 3 if re.match(r"^(oi|olá|ola|e aí|bom dia|boa tarde|fala)\b", txt.lower()) else 0
    hooks.append({"score": sc, "start": s["start"], "end": s["end"], "text": txt})
hooks = sorted(hooks, key=lambda h: -h["score"])[:8]

# 6) lista de cortes sugerida (silencios longos, hesitacoes duras, 1o take de falsos comecos)
cuts = []
for s in silences:
    if s["src"] != "ffmpeg" and s["dur"] > a.keep_pause * 2:
        cuts.append({"start": round(s["start"] + a.keep_pause / 2, 3), "end": round(s["end"] - a.keep_pause / 2, 3), "why": "silencio"})
for f in fillers:
    if f["kind"] == "hard": cuts.append({"start": f["start"], "end": f["end"], "why": f"hesitacao '{f['w']}'"})
for r in reps:
    if r["type"] == "false_start": cuts.append({"start": r["start"], "end": r["end"], "why": f"falso comeco: {r['text']}"})
    else: cuts.append({"start": r["start"], "end": r["end"], "why": f"repeticao '{r['text']}'"})
cuts = sorted((c for c in cuts if c["end"] - c["start"] > 0.04), key=lambda c: c["start"])
mg = []
for c in cuts:
    if mg and c["start"] <= mg[-1]["end"] + 0.02:
        mg[-1]["end"] = max(mg[-1]["end"], c["end"]); mg[-1]["why"] += " + " + c["why"]
    else: mg.append(dict(c))

wc = len(W); dur = T["duration"]
json.dump({"duration": dur, "wpm": round(wc / dur * 60) if dur else 0, "silences": silences, "fillers": fillers,
           "repetitions": reps, "topic_shifts": merged, "hook_candidates": hooks, "suggested_cuts": mg},
          open(a.out, "w"), ensure_ascii=False, indent=1)
print(f"silencios={len(silences)} hesitacoes={len(fillers)} repeticoes={len(reps)} assuntos={len(merged)} cortes={len(mg)} hooks={len(hooks)}")
