# The 19 rendered episodes

All 19 episodes exist as real MP4 files: **20.60 s, 1080×1920, 30 fps, H.264 +
AAC, narrated**, with the 26-layer sound design mixed underneath.

| Where | What |
| --- | --- |
| `exports/videos/kinetic-episode-01.mp4` … `-19.mp4` | the clips (≈2.9 MB each, ≈55 MB total) |
| `exports/videos/manifest.json` | probe of every file: duration, frames, size, narration settings |
| `exports/StratEvo_19_Videos.zip` | the same 19 files in one download |
| `python scripts/serve_exports.py --port 8000` | gallery page + byte-range streaming |
| Google Drive folder **StratEvo_19_Videos** | the delivered copies: 19 MP4s + README + manifest + the bundle in two zip parts |
| `exports/StratEvo_19_Videos_part{1,2}_of_2.zip` | the bundle split at 85 MB and 49 MB, because one archive is 130 MB |

**Delivery.** The master files live in the Drive folder
<https://drive.google.com/drive/folders/1Q34wSxx19IzNd1LqiI0c2kYWAAzWmt3f>
(public, anyone with the link, reader). An earlier 52 MB CRF 20 bundle was
committed to this branch while every anonymous file host was unreachable; it has
since been removed from the working tree (`git rm`) because it predates the CRF 14
master render. The blob remains in history until the branch is rewritten.

## Encoder

`kinetic.MASTER_CRF = 14`, `MASTER_PRESET = 'slow'`, `x264-params aq-mode=3:bframes=3`,
AAC 192 kb/s, BT.709 colour tags. Measured against a lossless FFV1 reference of a
3 s window (PSNR, average): CRF 20/veryfast = 38.69 dB, CRF 16/medium + aq-mode 3 =
38.88 dB, CRF 14/slow + aq-mode 3 = 38.89 dB, and a Lanczos colour-matrix scaling
pass made it *worse* (38.69 dB), so it was dropped. The residual gap to the source
is 4:2:0 chroma subsampling, kept because yuv420p is the only universally accepted
pixel format for social upload. Master files are ~7.1 MB per clip (2584 kb/s);
the earlier delivery was 2.9 MB (966 kb/s).

Rendered media is intentionally **not committed** (`.gitignore`: `/exports/videos/`,
`/exports/*.zip`); the repository holds the code that produces it, not 55 MB of MP4.

## Narration

Narration is a **neural voice or nothing**. `app/kinetic_voice.py` speaks the
episode's own script through whichever provider has a key, in this order:

| provider | model | env var | default voice |
| --- | --- | --- | --- |
| `fal` | `fal-ai/minimax/speech-2.8-hd` | `FAL_KEY` | `Deep_Voice_Man` |
| `openai` | `gpt-4o-mini-tts` | `OPENAI_API_KEY` | `onyx` |
| `elevenlabs` | `eleven_multilingual_v2` | `ELEVENLABS_API_KEY` | `onwk4e9ZLuTAKqWW03F9` |

`VOICE_ENABLED=false` disables narration everywhere (kill switch); `KINETIC_VOICE`
overrides the voice name. With **no key set, `synthesize()` raises `VoiceError`
and the batch driver stops** — it will not render a robotic read. `--narration
silent` is the only way to render picture + music + foley with no voice.

* Pauses come from the episode's `<#x#>` tags, so the read lands on the scene cuts.
* A take longer than 19.60 s is an error, not something to time-stretch: it would
  run into the 19.90 s lowpass tail.
* The take is high-passed at 85 Hz, low-passed at 9.5 kHz, compressed and limited,
  then padded to the full 20.60 s picture.

### Why eSpeak NG is gone

The first delivery used eSpeak NG (a formant synthesiser) so that no clip was
silent without a key. It sounded like a 1990s robot and made the whole series
unsellable, so it was removed rather than tuned. `tests/test_kinetic.py`
(`test_espeak_is_gone_and_cannot_come_back`) fails if it ever returns.

### Sound design

Two deterministic stems are synthesised locally, for free:

* **foley** — the episode's 26-layer blueprint (`app/kinetic_audio.py::synthesize`),
  the transients that make the type feel physical;
* **music bed** — `app/kinetic_audio.py::music_bed`: dark B2B deep house, 100 BPM in
  A minor, −19 dB: 4-on-the-floor kick sweeping 90→48 Hz, sub-bass gated in eighths
  and ducked by the kick, closed hats on the off-beats, a detuned two-note pad
  swelling over four bars, and a vinyl floor so silence never sounds digital.

They are mixed with the voice as three inputs (`amix normalize=0`), so the bed
never rides over the narration.

## Batch render

```bash
python scripts/render_kinetic_series.py                  # all 19, neural narration
python scripts/render_kinetic_series.py --start 1 --end 1 # one-episode preview
python scripts/render_kinetic_series.py --narration silent --out exports/preview
```

Each episode: synthesise narration → synthesise the 26-layer foley stem and the
music bed (≈2 s) → `kinetic.mix_audio` (voice + stems, `amix normalize=0`,
`apad=whole_dur=20.600`) → draw 618 frames with Pillow → encode with ffmpeg →
probe the result. A clip is only reported `OK` when it is ≥ 20.50 s, 1080×1920 and
has an audio stream. Measured: **≈55 s of CPU per episode**, so the 19 take ≈18
minutes on 2 vCPU.

## The four layouts

`app/kinetic.py` reads `layout` and `scenes` from each episode, so the picture
changes with the marketing angle instead of repeating one mockup:

| layout | scene 1 | scene 2 | scene 3 | episodes |
| --- | --- | --- | --- | --- |
| **A** | audit dashboard, verdict flips FAILED → VERIFIED | verification radar, 3 steps ping as the sweep passes | contract/escrow checklist, ticks in order | 1, 2, 4, 6, 8 |
| **B** | `WIRE TRANSFER $25,000` with a `PAUSED BY STRATEVO` stamp | UNVETTED QUOTE vs TRUE LANDED COST bars | hidden-defect maths, alarm total | 5, 7 |
| **C** | supplier chat alert (`Container held at customs`) | three missing documents, each struck through | "how we verify" checklist | 3, 9–12 |
| **D** | the kinetic card/device, header and button from the payload | three cards, title then the turn | chat card, heading and messages from the payload | 13–19 |

Every layout ends in the same three beats: the hook in emerald, a glass-refraction
wipe through four flash words, the three-question ladder, the equation and the
sign-off on `stratevo.online`. No episode hardcodes "PROFILE" or "SUBSCRIBE";
layout D's device, button, cards, headings and messages all come from
`episode_data`.

## Verification performed

* `ffprobe` on all 19: duration `20.60`, `1080×1920`, `has_audio: true`.
* Speech-band (300–3400 Hz) loudness in the hook window is ≈8.5 dB higher than the
  same window of the SFX-only render, i.e. the voice is really in the mix, not just
  claimed; the 19.90–20.60 s tail is silent in that band, as designed.
* Frames inspected: the hook (phone mockup, brush X, emerald hook), and the
  sign-off (chrome S, STRATEVO, FIND. VET. VERIFY., stratevo.online).
* Byte-identical output for the same episode across runs (the renderer is
  deterministic; only the narration take changes the bytes).

## Honest limits

* The delivered Drive folder still holds the **eSpeak** masters from the first
  pass. They are the honest record of that run, and they are replaced only once a
  neural key is configured and the 19 clips are re-rendered.
* The neural render cannot be produced in a sandbox: `api.openai.com`,
  `api.elevenlabs.io`, `fal.run` and every model host are outside this network
  allowlist. `FAL_KEY` / `OPENAI_API_KEY` / `ELEVENLABS_API_KEY` must be set where
  the render runs (Vercel env vars / the operator's shell).
* The SFX are synthesised stand-ins for the recorded sound design described by
  each layer's `sfx_prompt`.
* Nothing has been posted: these files are deliverables, not scheduled posts.
