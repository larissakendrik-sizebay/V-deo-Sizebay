#!/usr/bin/env bash
# Tratamento de voz standalone. Uso: audio_process.sh in.(mp4|wav) out.wav [musica.mp3]
# Sem musica: limpa/equaliza/comprime/normaliza (-14 LUFS). Com musica: ducking automatico pela voz.
set -euo pipefail
IN="$1"; OUT="$2"; MUSIC="${3:-}"
VOICE="highpass=f=80,afftdn=nr=12:nf=-40,equalizer=f=220:t=q:w=1:g=-2,equalizer=f=3200:t=q:w=1:g=2.5,deesser=i=0.3,acompressor=threshold=-20dB:ratio=2.5:attack=15:release=140:makeup=2"
LN="loudnorm=I=-14:TP=-1.5:LRA=9"
if [ -z "$MUSIC" ]; then
  ffmpeg -y -loglevel error -i "$IN" -vn -af "$VOICE,$LN" -ar 48000 "$OUT"
else
  ffmpeg -y -loglevel error -i "$IN" -stream_loop -1 -i "$MUSIC" -filter_complex \
   "[0:a]$VOICE,asplit=2[v][sc];[1:a]volume=-22dB[m];[m][sc]sidechaincompress=threshold=0.03:ratio=10:attack=20:release=500[md];[v][md]amix=inputs=2:normalize=0:duration=first,$LN[o]" \
   -map "[o]" -vn -ar 48000 "$OUT"
fi
echo "-> $OUT"
