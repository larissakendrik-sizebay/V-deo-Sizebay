#!/usr/bin/env python3
"""Renderiza o rough cut (cortes suaves, enquadramento em movimento, audio tratado, ducking, SFX).
Uso: build_edit.py video.mp4 edl.json out/rough.mp4 [--transcript transcript.json] [--brand brand/brand.json] [--dry]
Grava tambem out/timeline.json (mapa origem->saida) usado por captions.py e capcut_draft.py.

edl.json:
{ "keep":[{"start":0,"end":5.2,"pace":"fast|normal|slow|authority"}]  // ou "cuts":[{start,end}]
  "hook":{"start":31.2,"end":33.0,"remove_original":false},
  "music":"assets/music/x.mp3", "sfx":[{"t":0.0,"file":"assets/sfx/whoosh.wav","gain_db":-12}],
  "frames":[1.0,1.14,1.0,1.26],
  "callouts":[{"t":0.0,"dur":2.0,"kind":"stat|keyword|keyword_box|quote","text":"78%","sub":"dos empresarios ainda nao sabem"}] }  // t = tempo na SAIDA; "blur_in":true no keep = transicao com blur                                   // ciclo de zoom entre planos"""
import argparse, json, math, os, subprocess, sys
sys.path.insert(0, os.path.dirname(__file__))
from common import keep_from_edl, subtract

ap = argparse.ArgumentParser()
ap.add_argument("video"); ap.add_argument("edl"); ap.add_argument("out")
ap.add_argument("--transcript"); ap.add_argument("--brand", default=os.path.join(os.path.dirname(__file__), "..", "brand", "brand.json"))
ap.add_argument("--dry", action="store_true"); ap.add_argument("--no-music", action="store_true")
a = ap.parse_args()

B = json.load(open(a.brand)); cv, au = B["canvas"], B["audio"]
EDL = json.load(open(a.edl))
dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", a.video]))
keep = keep_from_edl(EDL, dur)
words = json.load(open(a.transcript))["words"] if a.transcript else []

# hook nos primeiros 1-2s: coloca a frase-gancho no inicio
hook = EDL.get("hook")
if hook:
    if hook.get("remove_original"): keep = subtract(keep, hook["start"], hook["end"])
    keep.insert(0, {"start": hook["start"], "end": hook["end"], "pace": "fast", "is_hook": True})

# densidade -> ritmo (palavras/seg): rapido em explicacao objetiva, longo para autoridade/emocao
TARGET = {"fast": 2.0, "normal": 3.2, "slow": 5.5, "authority": 8.0}
def pace_of(k):
    if k.get("pace"): return k["pace"]
    ws = [w for w in words if k["start"] <= w["start"] < k["end"]]
    d = len(ws) / max(k["end"] - k["start"], .1)
    return "fast" if d > 3.2 else "normal" if d > 2.2 else "slow"

def snap(t, lo, hi):  # prefere cortar no inicio de uma palavra
    c = [w["start"] for w in words if lo + .5 < w["start"] < hi - .5 and abs(w["start"] - t) < .5]
    return min(c, key=lambda x: abs(x - t)) if c else t

shots = []
for k in keep:
    L = k["end"] - k["start"]; tgt = TARGET[pace_of(k)]
    n = max(1, round(L / tgt)) if not k.get("is_hook") else 1
    edges = [k["start"]] + [snap(k["start"] + L * i / n, k["start"], k["end"]) for i in range(1, n)] + [k["end"]]
    shots += [(edges[i], edges[i + 1], bool(k.get("blur_in")) and i == 0) for i in range(n) if edges[i + 1] - edges[i] > .08]

frames = EDL.get("frames", [1.0, 1.14, 1.0, 1.26])
FADE = 0.025  # fade de audio nas emendas: cortes suaves, sem estalo
fc, outpos, timeline = [], 0.0, []
for i, (s, e, blur) in enumerate(shots):
    z = frames[i % len(frames)]; d = e - s
    fc.append(f"[0:v]trim={s:.3f}:{e:.3f},setpts=PTS-STARTPTS,crop=iw/{z}:ih/{z},"
              f"scale={cv['width']}:{cv['height']}:force_original_aspect_ratio=increase,crop={cv['width']}:{cv['height']},setsar=1,fps={cv['fps']}"
              + (",gblur=sigma=22:enable='lt(t,0.18)',gblur=sigma=8:enable='between(t,0.18,0.3)'" if blur else "") + f"[v{i}]")
    fc.append(f"[0:a]atrim={s:.3f}:{e:.3f},asetpts=PTS-STARTPTS,afade=t=in:d={FADE},afade=t=out:st={max(d-FADE,0):.3f}:d={FADE}[a{i}]")
    timeline.append({"src_start": s, "src_end": e, "out_start": outpos, "out_end": outpos + d, "zoom": z})
    outpos += d
N = len(shots)
fc.append("".join(f"[v{i}][a{i}]" for i in range(N)) + f"concat=n={N}:v=1:a=1[cv][ca]")

# voz: HPF -> reducao de ruido -> corta lama -> presenca -> de-esser -> compressao leve
VOICE = ("highpass=f=80,afftdn=nr=12:nf=-40,equalizer=f=220:t=q:w=1:g=-2,equalizer=f=3200:t=q:w=1:g=2.5,"
         "deesser=i=0.3,acompressor=threshold=-20dB:ratio=2.5:attack=15:release=140:makeup=2")
LN = f"loudnorm=I={au['target_lufs']}:TP={au['true_peak_db']}:LRA=9"
inputs = ["-i", a.video]; mix_ins = []
music = None if a.no_music else EDL.get("music")
if music:
    inputs += ["-stream_loop", "-1", "-i", music]
    fc.append(f"[ca]{VOICE},asplit=2[voice][vsc]")
    fc.append(f"[1:a]atrim=0:{outpos:.3f},asetpts=PTS-STARTPTS,volume={au['music_under_voice_db']}dB,afade=t=in:d=0.8,"
              f"afade=t=out:st={max(outpos-1.2,0):.3f}:d=1.2[m]")
    # ducking automatico: a voz comprime a musica (-12 a -15 dB quando fala, volta em ~0.5s)
    fc.append("[m][vsc]sidechaincompress=threshold=0.03:ratio=10:attack=20:release=500:makeup=1[md]")
    mix_ins = ["[voice]", "[md]"]
else:
    fc.append(f"[ca]{VOICE}[voice]"); mix_ins = ["[voice]"]
for j, s in enumerate(EDL.get("sfx", [])):
    idx = len(inputs) // 2; inputs += ["-i", s["file"]]
    fc.append(f"[{idx}:a]adelay={int(s['t']*1000)}|{int(s['t']*1000)},volume={s.get('gain_db',-12)}dB[sfx{j}]"); mix_ins.append(f"[sfx{j}]")
fc.append("".join(mix_ins) + f"amix=inputs={len(mix_ins)}:normalize=0:duration=first,{LN}[aout]")

cmd = ["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(fc), "-map", "[cv]", "-map", "[aout]",
       "-c:v", "libx264", "-crf", "17", "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", a.out]
os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
json.dump({"duration": outpos, "shots": timeline}, open(os.path.join(os.path.dirname(os.path.abspath(a.out)), "timeline.json"), "w"), indent=1)
print(f"{N} planos, {outpos:.1f}s (origem {dur:.1f}s)")
if a.dry: print(" ".join(cmd)); sys.exit()
subprocess.run(cmd, check=True); print("->", a.out)
