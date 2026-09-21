# ReAct Platform – Singing Pipeline

Nadine can sing ten pre-rendered public-domain songs and improvise a short new song about a topic the user names. This page covers the conversational flow, the rendering pipeline, playback with lip-sync, and the offline tooling under `singing_pipeline/`.

---

## Conversational Flow

Singing is a tool of the ReAct agent, `Sing a song` (`SingSong` in `tools.py`). Its description tells the model to call it whenever the user talks about singing, with one of four inputs:

| Input | Behavior | Tool observation returned to the agent |
|---|---|---|
| `any`, or anything that is not a known title | Does not sing. Lists the songs available in the current language. | Tell the human you can sing, name the songs, ask which one; do not choose for them. |
| A known title or keyword, such as `twinkle` or `frère jacques` | Publishes `nadine/agent/control/sing` with `<lang>/<file>`. | Reply with only a one-line introduction naming the song. |
| `new\|en\|<topic>` or `new\|fr\|<topic>` | Starts a background thread that writes lyrics and renders a new song, then streams it to control. | Reply with only a short excited filler line; the song follows in a few seconds. |
| `lyrics` | Does not sing. | Recite the words of the last made-up song, or say there is none yet. |

The two-step flow, offer first and sing on the second turn, is deliberate: the tool refuses to pick a song for the user. The dialogue manager sets the tool's `current_lang` from the session language each turn, so an English conversation is offered only the English songs and a French one only the French songs, with English as the fallback.

Library:

| Language | Songs |
|---|---|
| English | Twinkle Twinkle Little Star, Mary Had a Little Lamb, When the Saints Go Marching In, Oh! Susanna, Yankee Doodle, Jingle Bells |
| French | Frère Jacques, Au clair de la lune, Sur le pont d'Avignon, Ah ! vous dirai-je, maman |

The files are WAVs in `control_StopMic_asd_depth/songs/en/` and `songs/fr/`; made-up songs are written to `songs/makeup/`.

---

## Rendering

### Voice

All songs are sung in the **Hoshino Hanami** DiffSinger voicebank by Lotte V, used directly under its terms of use with credit (see `singing_pipeline/CREDITS.txt`). It is not Nadine's Azure speaking voice. The voicebank's license forbids voice conversion of its output, which is why the RVC model described below is not applied to it.

`singing_pipeline/diffsinger/ds_render.py` is a headless re-implementation of the OpenUtau render graph on ONNX Runtime, run inside `diffsinger/render_venv`:

1. **Phonemize.** English words go through the CMU dictionary; French words through a hand-mapped phoneme table for Hanami's inventory (its French nasal vowels use `ein`, not `in` or `un`). Words that fail lookup sing as `ah`.
2. **Duration model.** Tokens, word divisions, and note durations produce per-phoneme durations. Only vowels stretch to fill a held note; consonants keep their predicted length so they do not smear.
3. **Pitch.** By default the voicebank's pitch model (`dspitch`) predicts the f0 curve from the notes, which gives note attacks, drift, and vibrato. The model works in MIDI note numbers on both input and output. `DSPITCH=0` forces the fallback, a shaped f0 with short portamento glides and eased-in vibrato. In both cases the curve is continuous: rests take the neighboring note's pitch rather than zero, because an f0 of zero under the opening breath garbled the boundary frames and swallowed the first consonant.
4. **Acoustic model and vocoder.** The acoustic model renders a mel spectrogram with a speaker embedding for the `Fragrance` vocal mode, transposed two semitones up, and the `aidolgan` vocoder produces 44.1 kHz audio.

Each song is bracketed with an aspiration and a silence token, and a melody may contain `("R", beats)` entries that render as breath rests.

### Pre-rendered songs

`diffsinger/make_hanami_songs.py` holds the ten scores: tempo, melody, syllables, and for the two songs whose syllables are not dictionary words, explicit phonemes. `add_breaths()` carves a 0.4-beat breath rest out of every phrase-final note of two beats or more, so the meter is unchanged and the singer audibly breathes between lines. Offline renders use 100 diffusion steps and depth 1.0; the live defaults in `ds_render.py` are 50 steps and depth 0.6.

### Made-up songs

`generate_dynamic_hanami(topic, lang)` in `singing.py`:

1. Asks `gpt-4o-mini` at temperature 0.9 for exactly 28 singable, kid-safe words about the topic in the requested language, letters only. Short or missing tokens are replaced with `la`.
2. Sends the words to `hanami_infer.render()`, which keeps one `hanami_worker.py` process warm in the render venv so a song renders in a second or two after the first; if the worker fails it falls back to a one-shot `ds_render.py --dynamic` call.
3. The renderer picks one of four melody templates at random (`jump`, `fanfare`, `skippy`, or `long`, 14 to 28 notes, 132 to 138 bpm), trims or pads the words to the note count, and renders.
4. The WAV is written to `songs/makeup/`, the lyrics are remembered for the `lyrics` request, and the audio is gzip-compressed and published on `nadine/agent/control/sing_data`.

`singing.py` also contains an earlier rendering method that synthesizes each line with Azure TTS, re-pitches and stretches each word with Praat, and mixes it over a generated backing track, with an optional RVC pass when `NADINE_RVC_MODEL` is set. It is retained but not on the singing tool's path.

---

## Playback and Lip-Sync

Control receives either a relative song path on `sing` or WAV bytes on `sing_data`; the bytes are decompressed to a temporary file. `make_nadine_sing` resolves the path and runs `_sing_thread`:

1. Sleeps one second so the spoken introduction can start, then waits up to six seconds for it to finish.
2. Sets the `singing` flag and publishes `start_speak`, which suspends speech recognition for the whole song. The flag also stops the motion loop's speech-end check from firing during the song; before it existed, the loop saw idle lip channels and published `end_speak` mid-song, which reopened the microphone and let Nadine interrupt herself.
3. Calls `release_audio_device()` on the TTS module so the Azure SDK closes the sound card, then plays the file with `paplay` through PulseAudio. `XDG_RUNTIME_DIR` is set if missing so `paplay` can reach the user's PulseAudio server from a non-login shell.
4. Drives the jaw from the audio: the WAV is downmixed, normalized, and split into 30 frames per second; each frame's RMS scaled by 1.4 and clipped to 1 maps the jaw channel between its closed value 19 and open value 180, sent through `Checker.updateLips()` with the two lip-shape channels at zero.
5. When playback ends, releases the jaw override, clears the flag, and publishes `end_speak`, which reactivates speech recognition.

A song that is not found is logged and skipped without feedback to the interaction layer.

---

## Offline Tooling (`singing_pipeline/`)

| Path | Contents |
|---|---|
| `diffsinger/ds_render.py` | The headless Hanami renderer described above; also a CLI (`--dynamic --lang en|fr --out <wav> <words...>`) |
| `diffsinger/hanami_worker.py` | Warm render worker; line protocol over stdin and stdout (`READY`, `OK`, `ERR`) |
| `diffsinger/make_hanami_songs.py` | Scores and renderer for the ten library songs |
| `diffsinger/render_voice_compare.py` | Renders comparison clips across vocal modes |
| `diffsinger/hanami_vb/`, `hanami.zip` | The voicebank |
| `diffsinger/render_venv/` | ONNX Runtime environment for rendering |
| `Applio/` | RVC training and inference toolkit, with `rvc_worker.py`, a warm inference worker |
| `models/nadine.pth`, `nadine.index` | An RVC model of Nadine's Azure speaking voice, trained on synthesized speech |
| `dataset/nadine_voice/` | The synthesized training corpus |
| `scripts/` | Dataset synthesis, DiffSinger and RVC setup, RVC training and resume scripts, score helpers |
| `README.md` | The phased design notes and runbook for the pipeline |

The RVC model exists and works through `rvc_infer.py`, but the current singing path does not use it: the Hanami voice is used directly, and converting it is not permitted by its license.

---

## Known Limits

- Songs are in Hanami's voice, not Nadine's speaking voice.
- Made-up songs are limited to English and French, fixed melody templates, one word per note, and an LLM that must produce exactly the requested word count.
- The `sing_data` path writes the WAV to the system temporary directory on the control machine.
- Failure to render a made-up song reopens the microphone but sends nothing to control, so the user hears only the filler line.
- Playback timing between the spoken introduction and the song relies on fixed waits rather than a completion signal.
