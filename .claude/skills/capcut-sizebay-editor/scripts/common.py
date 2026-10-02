"""Utilidades compartilhadas: EDL, mapa de tempo origem->saida."""
import json

def load(path): return json.load(open(path))

def keep_from_edl(edl, duration):
    """Retorna lista de {start,end,pace} a manter. Aceita 'keep' direto ou 'cuts' (complemento)."""
    if edl.get("keep"):
        keep = [dict(k) for k in edl["keep"]]
    else:
        keep, pos = [], 0.0
        for c in sorted(edl.get("cuts", []), key=lambda c: c["start"]):
            if c["start"] > pos: keep.append({"start": pos, "end": c["start"]})
            pos = max(pos, c["end"])
        if pos < duration: keep.append({"start": pos, "end": duration})
    return [k for k in keep if k["end"] - k["start"] > 0.08]

def subtract(keep, a, b):
    out = []
    for k in keep:
        if b <= k["start"] or a >= k["end"]: out.append(k); continue
        if a > k["start"]: out.append({**k, "end": a})
        if b < k["end"]: out.append({**k, "start": b})
    return out

def remap(t, timeline):
    """tempo da origem -> tempo na saida (None se cortado)."""
    for seg in timeline:
        if seg["src_start"] <= t < seg["src_end"]:
            return seg["out_start"] + (t - seg["src_start"])
    return None
