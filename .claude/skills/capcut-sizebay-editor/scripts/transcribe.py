#!/usr/bin/env python3
"""Transcreve com timestamps por palavra. Uso: transcribe.py video.mp4 out/transcript.json [--lang pt] [--model small]
Requer: pip install faster-whisper"""
import argparse, json, subprocess, tempfile, os

ap = argparse.ArgumentParser()
ap.add_argument("media"); ap.add_argument("out")
ap.add_argument("--lang", default="pt"); ap.add_argument("--model", default="small")
a = ap.parse_args()

wav = os.path.join(tempfile.mkdtemp(), "a.wav")
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", a.media, "-ac", "1", "-ar", "16000", wav], check=True)
from faster_whisper import WhisperModel
model = WhisperModel(a.model, compute_type="int8")
segs, info = model.transcribe(wav, language=a.lang, word_timestamps=True, vad_filter=False,
                              initial_prompt="Sizebay, provador virtual, moda, e-commerce. Mantenha hesitacoes: eh, hum, tipo.")
out = {"language": info.language, "duration": info.duration, "words": [], "segments": []}
for s in segs:
    out["segments"].append({"start": s.start, "end": s.end, "text": s.text.strip()})
    for w in s.words or []:
        out["words"].append({"w": w.word.strip(), "start": round(w.start, 3), "end": round(w.end, 3)})
os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
json.dump(out, open(a.out, "w"), ensure_ascii=False, indent=1)
print(f"{len(out['words'])} palavras -> {a.out}")
