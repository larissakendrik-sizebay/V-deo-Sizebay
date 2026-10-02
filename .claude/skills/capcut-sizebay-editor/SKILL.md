---
name: capcut-sizebay-editor
description: Edita vídeos verticais (Reels/TikTok/Shorts) da Sizebay para finalizar no CapCut - transcreve, corta silêncios/hesitações/repetições, escolhe o hook, define ritmo visual, trata e mixa áudio (ducking, loudnorm) e gera legendas animadas com as fontes e cores da marca. Use quando o usuário pedir para editar, cortar, legendar ou "preparar para o CapCut" um vídeo.
---

# Edição de vídeo Sizebay → CapCut

Pipeline: **transcrever → analisar → decidir edição (EDL) → renderizar rough cut → legendas → CapCut**.
Pasta de trabalho: `out/<nome-do-video>/`. Scripts em `scripts/`. Marca em `brand/brand.json` (fontes, cores, posição da legenda, LUFS) - **leia antes de gerar legendas** e avise o usuário se ainda estiver com valores padrão (`_note`).

## Estilo de referência (vídeo de exemplo analisado)
Entrevista vertical 720x1280, 109 s, ~33 cortes (≈3,3 s por plano), alternando 2-3 câmeras/locais, com flashes de cor sutis em algumas transições, loudness -14,5 LUFS. Legenda: **minúsculas, branca, sans geométrica bold (tipo Outfit), sem contorno, sombra suave, centralizada a ~63% da altura (meio-baixo), 1-3 palavras por vez**, sem cor de destaque. Já refletido em `brand/brand.json` (`animation: simple_fade`); troque para `pop_highlight_word` + `highlight_color` para legenda com palavra ativa colorida. **Fonte oficial da Sizebay: Outfit (Google Fonts)**, em `assets/fonts/` (Bold/SemiBold). Instale no sistema antes de renderizar o `.ass` e no CapCut.

### Referência 2 (painel/entrevista de evento, 40 s)
~11 cortes (≈3,6 s/plano), -14,1 LUFS. Padrões a reproduzir:
- **Hook visual com dado**: 1º frame já com número gigante na cor de destaque + frase curta embaixo (`callouts` kind `stat`, ex.: "78%" + "dos empresários ainda não sabem"). Fala e texto entram juntos nos primeiros 2 s.
- **Legenda**: branca, bold, centro-baixo, 1-3 palavras; peso/caixa varia levemente (ênfase) - use ênfase só em palavras-chave.
- **Citação encenada** ("Ah, eu to no simples…") em **balão** sobre fundo desfocado (`quote`).
- **Palavra-chave em caixa** ("PENALIZADO") e **palavra grande** sobre montagem de vários entrevistados em tela dividida ("Multas") (`keyword_box` / `keyword`; a tela dividida é feita no CapCut).
- **Transição com blur** ao trocar de pessoa/assunto (`"blur_in":true` no trecho do `keep`).
- Legenda digitada com cursor em trechos de citação: fazer no CapCut (efeito "Máquina de escrever").
Cores de destaque vêm de `brand.palette.accent` (o azul do vídeo é de outra marca; **use a cor Sizebay**).

## Limites honestos
- O CapCut não tem API oficial e o `draft_content.json` das versões recentes é criptografado. O caminho **confiável** é entregar `rough.mp4` + `captions.srt/.ass` + EDL para importar. `scripts/capcut_draft.py` (pycapcut) é opcional e pode quebrar entre versões.
- Legenda estilizada final: o `.ass` serve para pré-visualização (`ffmpeg -vf ass=...`); no CapCut, aplique a fonte/estilo da marca sobre o `.srt` (Legendas → Importar legenda → estilo salvo "Sizebay").
- Se o usuário só enviou um link do Instagram, você não consegue baixar/ver. Peça o arquivo ou prints do estilo de referência.

## Passo a passo
1. **Transcrição**: `python scripts/transcribe.py video.mp4 out/x/transcript.json` (faster-whisper, palavra a palavra; mantém hesitações).
2. **Análise**: `python scripts/analyze.py out/x/transcript.json out/x/analysis.json --media video.mp4` → silêncios, hesitações (hard/soft), repetições e falsos começos, mudanças de assunto, `hook_candidates`, `suggested_cuts`.
3. **Decisão (você, não o script)**. Leia transcript + analysis e monte `edl.json` (formato no cabeçalho de `scripts/build_edit.py`):
   - Aplique `suggested_cuts`, mas revise: "tipo/né" (soft) só cortar se atrapalhar; falso começo → manter o **último** take; não corte pausa dramática antes de dado/punchline.
   - Mantenha ~0.1-0.15 s de respiro entre frases (já embutido); nunca cole palavra com palavra.
   - **Hook (0-2 s)**: escolha entre `hook_candidates` (ou outra frase) a mais forte: pergunta, número, contradição, erro comum, promessa. Use `"hook":{start,end}` para colocá-la no início. Se o hook for ≤ 2 s e ficar redundante, use `remove_original:true`.
   - **Sem introdução**: corte "Oi, gente, tudo bem?", "Então, hoje eu vou falar sobre…" e apresentações, **a menos que façam parte do conteúdo/humor**. Pergunte quando for ambíguo.
   - **Ritmo por densidade** (`pace` por trecho): `fast` (≈2 s/plano) para explicação objetiva e listas; `normal` (≈3 s); `slow` (≈5,5 s) e `authority` (≈8 s) para fala que exige autoridade, emoção ou contexto. Sem `pace`, é calculado por palavras/seg.
   - **Movimento visual**: `frames` alterna zoom (1.0 → 1.14 → 1.0 → 1.26) a cada plano; nenhum enquadramento dura mais que o alvo do `pace`. Mudanças de assunto (`topic_shifts`) são bons pontos para trocar de enquadramento, B-roll ou texto na tela.
   - **Música/SFX**: só se o usuário fornecer arquivos (`assets/music`, `assets/sfx`). SFX apenas em: transição de assunto (whoosh leve), dado/número em destaque, hook. Máx. ~1 a cada 8-10 s, `gain_db` -12 ou menos. Se faltarem, sugira e não invente.
4. **Render**: `python scripts/build_edit.py video.mp4 out/x/edl.json out/x/rough.mp4 --transcript out/x/transcript.json` (use `--dry` para ver o comando). Gera `timeline.json`.
   - Cortes suaves: fade de 25 ms em cada emenda de áudio, cortes encaixados no início de palavras.
   - Voz: HPF 80 Hz, `afftdn` (ruído), -2 dB em 220 Hz, +2,5 dB em 3,2 kHz, de-esser, compressor leve 2.5:1.
   - Música: -22 dB base + **sidechain ducking** pela voz (música nunca compete), fade in/out.
   - Final: `loudnorm` -14 LUFS / TP -1,5 dB.
   - Só áudio: `scripts/audio_process.sh in out.wav [musica]`.
5. **Legendas**: `python scripts/captions.py out/x/transcript.json out/x/timeline.json out/x/captions` → `.ass` (palavra ativa destacada, pop) e `.srt`, já remapeados para o tempo editado e sem as palavras cortadas.
6. **CapCut**: opcional `scripts/capcut_draft.py` ou importar manualmente. Entregue ao usuário: `rough.mp4`, `captions.srt`, `captions.ass`, e um resumo com o checklist abaixo.

## Verificação antes de entregar
- Extraia 3-4 frames (`ffmpeg -ss T -i rough.mp4 -frames:v 1`) e confira legenda dentro da área segura (fora da UI do Reels: ~250 px topo / 480 px base).
- `ffmpeg -i rough.mp4 -af ebur128 -f null -` → ~-14 LUFS; sem clipping.
- O hook começa em ≤ 1 s? Alguma pausa > 0.5 s restante? Algum plano > alvo do ritmo?
- Reporte o que foi cortado (tempo total removido e motivos) e peça aprovação do hook.

## Requisitos
`ffmpeg` (com `afftdn`, `deesser`, `sidechaincompress`, `loudnorm`), `python3`, `pip install faster-whisper` (e opcional `pycapcut`). Fontes da marca em `assets/fonts/` (instale no sistema/CapCut).
