# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI language tutor — a multilingual conversation partner using DeepSeek LLM + edge-tts voice. **Two UI modes:**
- **Web** (default): Flask server + WeChat-style browser UI, auto-opens browser, accessible via IP
- **CLI** (legacy): Rich terminal-based interface

Keyboard input (both modes), AI responds with text + TTS audio + Chinese translation. User documentation in README.md covers setup, character customization, and adding languages.

## Commands

```bash
pip install -r requirements.txt         # install deps (requests, edge-tts, miniaudio, rich, flask)
pip install pyttsx3                     # (optional) offline TTS, lower quality
python main.py                          # default: Web mode, auto-open browser
python main.py --cli                    # CLI mode (legacy Rich interface)
python main.py --cli --lang japanese    # CLI mode with specific language
rm memory/user_profile.json             # clear cross-session AI memory
```

No tests, linters, or formatters are configured.

## Project structure

```
├── main.py                 # Entry point; --cli for terminal, default = Flask web server
├── web_server.py           # Flask server: SSE streaming (NDJSON), TTS audio serving
├── templates/
│   └── chat.html           # Single-page WeChat-style frontend (vanilla JS, no framework)
├── config.py               # Character prompt, language configs, engine selection, web settings
├── apikey.py               # Gitignored — API key, model name, URL
├── requirements.txt
├── memory/
│   └── user_profile.json   # Auto-created; cross-session AI memory (gitignored)
└── tutor/                  # Plugin-style modules with ABCs + factory functions
    ├── llm.py              # LLMProvider → DeepSeekProvider (OpenAI-compat REST)
    ├── tts.py              # TTSProvider → EdgeTTSProvider / Pyttsx3Provider
    ├── asr.py              # ASRProvider → KeyboardInputProvider (mic placeholder)
    ├── conversation.py     # Conversation — history management, truncation, system prompt
    ├── memory.py           # MemoryManager — JSON-persisted user profile, MEMORY_SAVE: protocol
    └── utils.py            # parse_response(), split_segments() — AI reply parser
```

## Core architecture

### Web mode (default): `web_server.py` + `templates/chat.html`
- **Flask** server with SSE streaming via NDJSON (newline-delimited JSON over `POST /api/chat`).
- **WeChat-style frontend**: pure vanilla JS, flexbox layout, chat bubbles (green=user, white=AI), auto-scroll, audio playback via Web Audio API (AudioContext).
- **Stream protocol**: `POST /api/chat` returns `application/x-ndjson`:
  ```
  {"type":"status","status":"thinking"}
  {"type":"segment","index":0,"content":"...","translation":"..."}
  {"type":"audio","index":0,"url":"/api/audio/uuid"}
  {"type":"done"}
  ```
- **Audio**: `EdgeTTSProvider._generate_wav_bytes()` returns WAV bytes, served via `/api/audio/<uid>`, cached in `audio_cache` dict.
- **Welcome**: pre-generated on first `GET /api/init`, lazy-cached.
- **Init flow**: browser loads → `GET /api/init` → render welcome segments with audio. Welcome audio auto-plays on first user click via capture-phase event listeners.
- **Segment reveal**: AI response segments are buffered during streaming. After `done` event, `revealNextResponseSegment()` shows one segment at a time, plays its audio via AudioContext, then reveals the next on `onended` callback. Status bar shows `[current/total]` progress.
- **Autoplay unlock**: AudioContext created on page load (suspended). Capture-phase listeners (`click`/`touchstart`/`keydown` with `true`) fire on first interaction → `await audioCtx.resume()` + 50ms dummy buffer to unlock browser autoplay policy.

### CLI mode (legacy): `main.py --cli`
- **InputEngine** — daemon thread, Windows `msvcrt.getwch()` (arrow keys, backspace, Ctrl+C) falls back to `stdin.readline()` on other platforms. Buffers text; submits on Enter via `queue.Queue`.
- **Rich Live** loop: check input queue → dispatch API call → poll for response → progressive reveal via `threading.Event` chain → render panels.
- **MAX_ITEMS = 10** limits displayed panels; input/status panels always visible.

### Common (both modes)
- **Language switching**: `LANG_SWITCH:<key>` → confirm in current lang → `LANG_SWITCH:confirmed:<key>` → switch voice + prompt.
- **Welcome**: first LLM call generates a creative greeting (non-hardcoded).
- **API cancellation**: `pending_question` captures user input during AI thinking; the pending response is discarded and a new request fires. Guarded by `api_lock`.
- Helper functions: `resolve_lang()` (prefix/fuzzy matching), `_script_mismatch()` (CJK drift detection), `_strip_emoji()`.

### `tutor/llm.py` — LLM abstraction
- `LLMProvider.chat(history, temperature, max_tokens) → str`
- `DeepSeekProvider` uses `requests.post()` to OpenAI-compatible endpoint.
- `create_llm_provider(config)` factory — extensible with new `elif` branches.

### `tutor/tts.py` — TTS abstraction
- `TTSProvider.speak(text) → bool`, `speak_segments(segments, on_before)`, `cancel()`
- `EdgeTTSProvider`: edge-tts → miniaudio decode to WAV → PowerShell SoundPlayer (CLI) or browser `<audio>` (Web). Key patterns:
  - **`speak_segments()`**: pre-generates next segment WAV in background thread for gapless playback. `on_before(idx)` callback fires before each segment plays → drives progressive UI reveal.
  - **`cancel()`**: kills SoundPlayer process under `_proc_lock`.
  - **`set_voice(voice)`**: runtime voice switching for language changes.
  - **`speak_async()`**: non-blocking variant returning `wait()` callable.
  - **`_generate_wav_bytes(text) → bytes`**: returns WAV bytes (no temp files), used by web server.
- `Pyttsx3Provider`: offline fallback, lower quality.
- `create_tts_provider(config)` factory.

### `tutor/conversation.py` — Conversation manager
- `Conversation.__init__(llm, system_prompt, max_rounds)`: history starts with `[{"role": "system", "content": system_prompt}]`.
- `ask(user_text, **kwargs)`: appends user + assistant turns, truncates via sliding window (`max_rounds * 2 + 1` limit), returns reply.
- `set_system_prompt()`: appends a language-switch system message (preserves prior history) rather than replacing.
- `clear()`: resets to just the system prompt.

### `tutor/memory.py` — Cross-session memory
- `MemoryManager`: loads/saves `memory/user_profile.json` (auto-created).
- `on_session_start()`: records `first_seen` date, increments `session_count`.
- `get_context() → str`: injects session metadata (time of day, relationship stage) + format reminders + stored facts into AI's system context.
- `process_reply(str) → str`: strips `MEMORY_SAVE: key = value` lines from AI output, persists them to JSON.
- `add(key, value)`: manual memory insertion.

### `tutor/utils.py` — Reply parsing
- `parse_response(reply) → [(content, translation), ...]`: 3-pass fallback:
  1. **Standard**: split by `\n\n`, each block must contain `\n---` separator.
  2. **Fallback**: single `\n---` → split into content/translation.
  3. **Pure foreign**: no CJK → content with null translation.
- `split_segments(segments)`: if only 1 segment >80 chars, split on sentence boundaries (`.!?` or `。！？`).

## Configuration (`config.py`)

| Key | Description |
|-----|-------------|
| `CHARACTER_PROMPT` | Shared backstory for all languages |
| `LANGUAGE` | Default startup language (`"english"`) |
| `LANGUAGE_CONFIGS` | Per-lang: display, edge-tts voice, names map, confirm_switch text, prompt rules |
| `LANG_NAMES_CN` | Chinese name mapping for fixed confirmation text fallback |
| `TTS_ENGINE` / `ASR_ENGINE` | `"edge-tts"` / `"keyboard"` |
| `TEMPERATURE` | 0.7 |
| `MAX_TOKENS` | 600 |
| `MAX_HISTORY_ROUNDS` | 20 |
| `API_TIMEOUT` | 30 seconds |
| `WEB_HOST` / `WEB_PORT` | `"0.0.0.0"` / `5000` (web mode) |
| `AUTO_OPEN_BROWSER` | `True` (web mode auto-opens browser) |

`apikey.py` (gitignored): `LLM_ENGINE`, `DEEPSEEK_API_KEY`, `DEEPSEEK_API_URL`, `DEEPSEEK_MODEL`. Imported by `config.py` with fallback placeholders if missing.

## Key patterns

### Web mode
- **Sequential segment reveal**: `revealNextResponseSegment()` shows one segment → plays audio via AudioContext → `onended` triggers next. `pendingSegments[]` buffer + `revealGeneration` counter for cancellation safety.
- **Autoplay unlock**: Capture-phase event listeners (`addEventListener(type, handler, true)`) fire before target-phase handlers. Resume AudioContext + 50ms silent dummy buffer on first interaction.
- **NDJSON streaming**: `POST /api/chat` returns `application/x-ndjson`. Frontend reads with `fetch` + `ReadableStream.getReader()` + `TextDecoder`. Each line is a complete JSON event.
- **Welcome lazy-cache**: `generate_welcome()` generates on first call, cached in `welcome_data` global. Thread-safe with `welcome_lock`.

### CLI mode
- **Progressive display via Events**: `speak_segments()` fires `on_before(idx)` → sets `progressive_events[idx]` → main loop reveals segments incrementally in Rich UI.
- **Audio pre-generation**: background thread generates next WAV during current segment playback.

### Common
- **Script mismatch detection**: warns when English output has CJK or Japanese output lacks it.
- **Typo-tolerant language resolution**: prefix matching — `"jap"` matches `"japanese"`.

## Adding features

- **New language**: add entry to `config.py` `LANGUAGE_CONFIGS` (display name, voice, names, confirm text, prompt).
- **New LLM/TTS/ASR provider**: implement ABC in `tutor/*.py`, register in the factory function.
