# Clip Farm

**An autonomous, multi-agent pipeline that watches the biggest livestreams in real time, finds the moments worth clipping, edits them into vertical Shorts with word-synced animated captions, runs them through a QA gate, and publishes them to YouTube, TikTok and Instagram — with no human in the loop.**

Built in a few days for the GTA 6 launch window (Nov 2026) on a single 16 GB M3 MacBook, orchestrated by LLM agents (Claude Sonnet / Opus via Claude Code headless) on top of a deterministic Python + ffmpeg + Remotion core.

> Code, comments and prompts are in Italian — the system was built for my own use. This README is the English map.

---

## What it does

```
 Twitch / Kick / YouTube                                                       YouTube Shorts
        │                                                                      TikTok
        ▼                                                                      Instagram Reels
 ┌─────────────┐   10-min    ┌──────────┐   ┌───────────┐   ┌──────────┐   ┌──────────┐   ┌───────────┐
 │ sentinella  │──chunks────▶│ analizza │──▶│ seleziona │──▶│  giudica │──▶│  monta   │──▶│  qualita  │──▶ agenti.pubblica
 │ (discovery, │  + chat     │ (audio   │   │ (LLM picks│   │ (LLM as a│   │ (ffmpeg +│   │ (hard QA  │    (browser agent)
 │  recording) │             │  peaks,  │   │  moments) │   │ stranger)│   │ Remotion)│   │  gate)    │
 └─────────────┘             │  chat)   │   └───────────┘   └──────────┘   └──────────┘   └───────────┘
        │                    └──────────┘                                                        │
        └───────────── SQLite state (single source of truth) ──── Obsidian dashboard ──── daily email digest
```

1. **Discovery & recording** — `sentinella.py` ranks live channels every minute (Twitch Helix API, Kick, YouTube), auto-discovers anyone streaming GTA 6 above 10k viewers, and records the top streams *while they are live* in 10-minute chunks (`registra.sh`, streamlink) plus their chat (`chat.py`). Moments that straddle two chunks are handled by concatenating the previous chunk.
2. **Candidate mining** — `analizza.py` scores each chunk (loudness curve, chat velocity, transcript). `ripassa.py` also pulls the clips *viewers* made on Twitch/Kick in the last 24h: measured on 49 hours of footage, crowd-clipped moments beat every heuristic signal, so the crowd decides and the model refines.
3. **Selection in two passes** — a Sonnet agent proposes cuts (`prompt/seleziona.md`), then a second agent judges them *as a stranger who has never seen the stream* from 12 frames + transcript (`prompt/giudica.md`). Below the score threshold, nothing ships: zero clips beats a weak clip.
4. **Editing** — `monta.py` / `laboratorio/monta.py` + Remotion (`remotion/src`):
   - automatic 9:16 framing: facecam + gameplay split, or full-frame "story" layouts where a model picks who is speaking in each cut from a numbered face mosaic;
   - word-level captions: Demucs voice isolation → Whisper large-v3 run 4× keeping the best take → forced alignment for word timings; words are kept only if a second pass confirms them, so the captions never show things that weren't said;
   - two switchable edit styles (`"stile": "classico" | "speedy"`): the richer one is a library of fonts, captions, emoji, arrows, light flashes and endings reverse-engineered frame-by-frame from viral Shorts channels (fonts matched by pixel overlap, e.g. Bebas Neue at 0.96);
   - layout constraints enforced in code: captions never over a face, labels never overlapping their arrow, the arrow tip computed from a face detector (no face → no arrow).
5. **QA gate** — `qualita.py`: mandatory checkboxes, half measured in code, half by a vision model on 8 frames — streamer in frame, no double captions (some streamers burn in their own), no frozen frames ≥ 1 s, A/V sync, *the first 3 seconds are always in motion*. Every defect I spot by eye becomes a new checkbox, not a manual fix.
6. **Publishing** — `agenti.py` drives Claude in Chrome headlessly to upload to each platform with captions and hashtags, retries in a fresh session on refusals, backs off on daily upload limits, recovers platforms a clip missed, and paces posts 45–120 min apart. It can also auto-submit clips to paid clipping campaigns (branded-content flags and `#ad` handled per platform).
7. **Ops** — launchd jobs (`avvia.sh` / `ferma.sh`), one SQLite DB, lock files so Demucs + Whisper + Remotion never run together in 16 GB, an Obsidian dashboard generated from the DB, and one email digest per day.

## Engineering notes (the interesting bugs)

- **Clips that started frozen.** Cutting Kick sources with `ffmpeg -ss` mid-GOP left the base with no video for 0.6–1.9 s, which Remotion silently filled with a still frame — and the QA check measured the *base*, so it never saw it. Fix: 4-second pre-roll in the layout step, and the freeze check moved to the *finished* render and duplicated as the last gate before publishing.
- **Kick clips stuttering every 12 s.** Byte-range segments downloaded via ffmpeg froze for 2 s; replaced with a dedicated downloader plus a stall detector.
- **Whisper on streamer + game audio** randomly skips sentences or loops. A vocabulary `initial_prompt` made it drop dialogue entirely. Solution: multiple decodes, keep the best, cross-confirm words between takes.
- **LLM judge calibration.** Without audio, the judge promoted clips with an explicit premise but rejected 2 of 3 truly viral clips driven by pure emotion — which is why crowd signals now outrank the model's taste.
- **launchd doesn't pass `TMPDIR`**, which made the headless browser agent report "extension not connected". Small, maddening, now fixed in one place.

## Model routing

| Job | Model | Why |
|---|---|---|
| Building the chain, presets, style library | Fable / Opus | one-off, needs judgment |
| Moment selection, judging, QA, publishing, scouting | Sonnet | repetitive, high volume, cheap |
| Final pick & audits | Opus | few calls, high stakes |

## Layout

| Path | Role |
|---|---|
| `sentinella.py`, `registra.sh`, `chat.py` | discovery, live recording, chat capture |
| `catena.py`, `analizza.py`, `ripassa.py` | per-chunk processing chain, crowd-clip ingestion |
| `trascrivi.py` | transcription, alignment, caption filtering |
| `monta.py`, `laboratorio/monta.py`, `remotion/` | editing (classic and "speedy" styles) |
| `qualita.py` | QA gate |
| `agenti.py`, `prompt/` | LLM agents: publish, metrics, scout, campaigns |
| `stato.py`, `obsidian.py`, `notifica.py` | state, dashboard, daily digest |
| `launchd/`, `avvia.sh`, `ferma.sh` | always-on scheduling |
| `laboratorio/strumenti/` | research tools: font matching, flash/light measurement, music matching |

## Running it

Requirements: macOS (Apple Silicon), Python 3.13, ffmpeg, yt-dlp, streamlink, Whisper + Demucs, Node + Remotion, [Claude Code](https://claude.com/claude-code) with the Chrome extension for publishing.

```sh
cp config.example.json config.json         # streamers, thresholds, accounts, email
echo '{"twitch_client_id": "...", "twitch_client_secret": "..."}' > segreti.json
./avvia.sh                                  # starts the launchd jobs
./ferma.sh                                  # stops everything
```

Modules carry assert-based self-checks in their `__main__` block (`notifica.py --prova` runs only the checks).

Not included: recordings, rendered clips, sound effects and music (third-party licences), fonts, secrets.

## Disclaimer

This is a personal engineering project. Clipping third-party streams and publishing them is subject to each platform's terms and to the creators' rights; use it only with content you are allowed to repost (e.g. official clipping programs).

## License

MIT
