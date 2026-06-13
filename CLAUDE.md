# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI language tutor — a multilingual conversation partner using DeepSeek LLM + edge-tts voice. **Web UI**: Flask server + WeChat-style browser UI, auto-opens browser, accessible via IP.

Keyboard input, AI responds with text + TTS audio + Chinese translation. User documentation in README.md covers setup, character customization, and adding languages.

## Commands

```bash
pip install -r requirements.txt         # install deps (requests, edge-tts, miniaudio, flask)
pip install pyttsx3                     # (optional) offline TTS, lower quality
python main.py                          # start web server, auto-open browser
rm memory/user_profile.json             # clear cross-session AI memory
```

No tests, linters, or formatters are configured.

## Workflow rules

- **每次 push 前先升版本号**: 修改 `README.md` 第一行的版本号（如 v16 → v17），作为该次 commit 的一部分。
- **push 前检查文档同步**: 确认 README.md、CLAUDE.md、memory 文件都已更新。

## Project structure

```
├── main.py                 # Entry point; from server import create_app
├── apikey.py               # Gitignored — API key, model name, URL
├── docker-compose.yml      # Docker services (SearXNG, Ollama, etc.)
├── server/                 # Flask application
│   ├── __init__.py         #   create_app() factory, init_providers, globals
│   ├── routes.py           #   All Flask routes (@app.route)
│   ├── config.py           #   All config (merged from old config.py + local_config.py)
│   └── state.py            #   Mutable shared state (chat_flow, cache, engines)
├── templates/
│   └── chat.html           # Single-page WeChat-style frontend (vanilla JS, no framework)
├── static/
│   ├── css/
│   │   └── chat.css        # Chat UI styles
│   └── js/                 # ES modules (type="module", no bundler)
│       ├── app.js          # Entry: module wiring, global events
│       ├── state.js        # Global state singleton
│       ├── chat-ui.js      # DOM manipulation (messages, status, input)
│       ├── stream-reader.js # NDJSON stream reader
│       ├── audio-player.js # Audio playback via Web Audio API
│       ├── asr.js          # Web Speech API voice recognition
│       ├── sidebar.js      # Config panel sidebar
│       └── scroll.js       # Auto-scroll to bottom
├── config/                  # (reserved — future config consolidation)
├── memory/
│   └── user_profile.json   # Auto-created; cross-session AI memory (gitignored)
└── tutor/                  # Business logic modules
    ├── __init__.py         #   Public API exports
    ├── llm.py              #   LLMProvider → DeepSeekProvider (OpenAI-compat REST)
    ├── tts.py              #   TTSProvider → EdgeTTSProvider / Pyttsx3Provider
    ├── asr.py              #   ASRProvider → KeyboardInputProvider (mic placeholder)
    ├── search.py           #   SearchProvider → SearXNG search
    ├── conversation.py     #   Conversation — history management, truncation, system prompt
    ├── memory.py           #   MemoryManager — JSON-persisted user profile, MEMORY_SAVE: protocol
    ├── chat_flow.py        #   ChatFlow orchestrator — wires LLM+TTS+search+memory+switch
    ├── search_broker.py    #   Search decision logic + result injection
    ├── lang_switcher.py    #   Language switch protocol parser (LANG_SWITCH:<key>)
    ├── audio_cache.py      #   Bounded TTS audio cache with LRU eviction
    ├── format_checker.py   #   AI reply format validation
    ├── service_detector.py #   Local service health checks (Ollama, SearXNG)
    └── utils.py            #   parse_response(), split_segments() — AI reply parser
```

## Core architecture

### Web mode (default): `server/routes.py` + `templates/chat.html`
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

### Common patterns
- **Language switching**: `LANG_SWITCH:<key>` → confirm in current lang → `LANG_SWITCH:confirmed:<key>` → switch voice + prompt.
- **Welcome**: first LLM call generates a creative greeting (non-hardcoded).
- **API cancellation**: `pending_question` captures user input during AI thinking; the pending response is discarded and a new request fires. Guarded by `api_lock`.
- **Script mismatch detection**: warns when English output has CJK or Japanese output lacks it.
- **Typo-tolerant language resolution**: prefix matching — `"jap"` matches `"japanese"`.

### `tutor/llm.py` — LLM abstraction
- `LLMProvider.chat(history, temperature, max_tokens) → str`
- `DeepSeekProvider` uses `requests.post()` to OpenAI-compatible endpoint.
- `create_llm_provider(config)` factory — extensible with new `elif` branches.

### `tutor/tts.py` — TTS abstraction
- `TTSProvider.speak(text) → bool`, `speak_segments(segments, on_before)`, `cancel()`
- `EdgeTTSProvider`: edge-tts → `mp3_read_file_s16` → `_trim_silence()` → `_generate_wav_bytes()` (web). Key patterns:
  - **Pipeline**: edge-tts MP3 → `mp3_read_file_s16()` decodes to native 1ch 24000Hz PCM → `_trim_silence(threshold=30)` removes ~197ms MP3 encoder silence.
  - **`cancel()`**: sets `_cancelled` flag → `_play_pcm()` polling loop breaks → `device.stop()`. Response ~0.4s.
  - **`speak_segments()`**: background thread pre-generates next segment PCM. `on_before(idx)` drives progressive UI reveal.
  - **`set_voice(voice)`**: runtime voice switching.
  - **`speak_async()`**: non-blocking variant returning `wait()` callable.
  - **`_generate_wav_bytes(text) → bytes`**: returns trimmed WAV (1ch 24000Hz, no lead silence) for browser playback.
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

## Configuration (`server/config.py`)

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
| `VOICE_SILENCE_TIMEOUT` | Voice silence timeout in seconds (0=manual) | `3` |
| `API_TIMEOUT` | 30 seconds |
| `WEB_HOST` / `WEB_PORT` | `"0.0.0.0"` / `5000` (web mode) |
| `AUTO_OPEN_BROWSER` | `True` (web mode auto-opens browser) |

`apikey.py` (gitignored): `LLM_ENGINE`, `DEEPSEEK_API_KEY`, `DEEPSEEK_API_URL`, `DEEPSEEK_MODEL`. Imported by `server/config.py` with fallback placeholders if missing.

## Key patterns

### Web mode
- **Sequential segment reveal**: `revealNextResponseSegment()` shows one segment → plays audio via AudioContext → `onended` triggers next. `pendingSegments[]` buffer + `revealGeneration` counter for cancellation safety.
- **Autoplay unlock**: Capture-phase event listeners (`addEventListener(type, handler, true)`) fire before target-phase handlers. Resume AudioContext + 50ms silent dummy buffer on first interaction.
- **NDJSON streaming**: `POST /api/chat` returns `application/x-ndjson`. Frontend reads with `fetch` + `ReadableStream.getReader()` + `TextDecoder`. Each line is a complete JSON event.
- **Welcome lazy-cache**: `generate_welcome()` generates on first call, cached in `welcome_data` global. Thread-safe with `welcome_lock`.

## Adding features

- **New language**: add entry to `server/config.py` `LANGUAGE_CONFIGS` (display name, voice, names, confirm text, prompt).
- **New LLM/TTS/ASR provider**: implement ABC in `tutor/*.py`, register in the factory function.
