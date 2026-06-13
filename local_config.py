"""
本地 Docker 服务配置
===================
Docker 容器中运行的服务地址，用于本地 LLM / ASR / TTS / 搜索。
"""

# ── 本地 LLM（Ollama） ─────────────────────────
OLLAMA_API_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5:14b"

# ── 本地联网搜索（SearXNG） ────────────────────
SEARXNG_API_URL = "http://localhost:8999"

# ── (预留) 本地语音识别 ────────────────────────
# WHISPER_MODEL = "large-v3"

# ── (预留) 本地 TTS ────────────────────────────
# LOCAL_TTS_MODEL = "chattts"
