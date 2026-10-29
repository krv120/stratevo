STRATEVO — kinetic typography series, 19 episodes
===============================================

Format     1080 x 1920 (9:16), 30 fps, H.264 High profile, yuv420p, BT.709 tagged
Runtime    20.60 s per clip (the brief's floor was 20.50 s)
Audio      AAC 192 kbps, 48 kHz stereo: narration + a 26-layer sound design
Encoder    x264 CRF 14, preset slow, aq-mode=3 (variance AQ biased against dark scenes)
Renderer   in-code (Pillow draws every frame, ffmpeg encodes), deterministic:
           the same episode always renders to the same frames
Source     github.com/krv120/stratevo  -  app/kinetic.py, app/kinetic_series.py

Files in this delivery
  kinetic-episode-01.mp4 ... kinetic-episode-19.mp4   the 19 episodes
  manifest.json        per-clip probe: duration, frames, size, sha256, loudness
  README.txt           this file
  StratEvo_19_Videos_part1_of_2.zip   episodes 01-12 + README + manifest
  StratEvo_19_Videos_part2_of_2.zip   episodes 13-19 + README

  The bundle is split in two because a single archive would be 130 MB. Download
  both parts and unzip them into the same folder to get the complete set of 19.

The episodes
  01  A professional profile is not a professional supplier. PROFILE ≠ proof
  02  A perfect sample is not a perfect shipment.          SAMPLE ≠ shipment
  03  The lowest quote is rarely the lowest cost.          QUOTE ≠ cost
  04  A huge catalog is not a factory.                     CATALOG ≠ factory
  05  Fast replies do not build products.                  FAST CHAT ≠ good qc
  06  An ISO PDF is not a factory audit.                   ISO CERT ≠ compliance
  07  We supply big brands is a lie.                       BIG BRANDS ≠ real work
  08  A low MOQ can still trap your cash.                  LOW MOQ ≠ scalable
  09  A factory tour is rented in a day.                   VIDEO TOUR ≠ ownership
  10  A checkmark sheet is not an inspection.              CHECKLIST ≠ inspection
  11  A 30% deposit with no contract is a gift.            INVOICE ≠ protection
  12  Shipped is not the same as delivered.                SHIPPED ≠ delivered
  13  Ten years online is not ten years making.            TENURE ≠ experience
  14  A 3D render hides every fatal flaw.                  RENDER ≠ engineered
  15  A green leaf icon is not a certificate.              GREEN CLAIM ≠ certified
  16  A local warehouse is not a factory.                  LOCAL PIN ≠ local made
  17  A trade show booth is not a factory.                 BIG BOOTH ≠ real plant
  18  No problem, we can make it is a warning.             EASY YES ≠ capability
  19  A golden badge is not a factory audit.               BADGE ≠ vetted

Each clip is the same seven-scene template:
  1 Hook       0.00-2.60   phone mockup, brush X, contrarian hook slammed in emerald
  2 Illusions  2.60-6.70   three "looks credible" tiles, filmstrip into a ring
  3 Chat       6.70-8.30   supplier chat card
  4 Refraction 8.30-9.90   full-screen words through fluted glass
  5 Questions  9.90-13.60  three fear questions: blindspot, quality, catastrophic loss
  6 Equation  13.60-16.50  LEFT != RIGHT
  7 Sign-off  16.50-20.60  chrome S, STRATEVO, FIND. VET. VERIFY., stratevo.online

Audio
  26 layers per clip with millisecond timings and a per-layer sound-design prompt.
  Transients land every 0.6-0.9 s; a final lowpass tail at 19.90 s runs for 0.70 s
  and closes the clip, so it loops cleanly into the opening hum. The soundtrack in
  these files is a synthesised scratch stem rendered locally (free), not recorded
  sound design.

Narration - please read
  The voice in these files is eSpeak NG, an offline formant synthesiser. It is real
  speech that lands on the scene cuts, but it sounds mechanical. The paid neural
  voice (fal.ai MiniMax HD, about $0.031 per clip) is already wired and tested; it
  needs FAL_KEY. Re-render with the neural take when a key exists:
      VOICE_ENABLED=true python scripts/render_kinetic_series.py

Verified before upload
  19/19 clips: 20.60 s, 1080x1920, 30 fps, audio stream present, mean volume about
  -19.8 dB, BT.709 tagged. The sha256 of every clip is in manifest.json.

Nothing here has been posted to any platform.
