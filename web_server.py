"""
Web 服务器 — AI 语言助教的浏览器界面
=====================================
纯路由层，所有业务逻辑委托给 tutor/* 模块。

用法:
  python main.py              # 启动 Web 模式，自动打开浏览器
"""

import json
import os
import sys
import threading
import time
import webbrowser

from flask import Flask, Response, jsonify, request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config as cfg
from tutor.audio_cache import AudioCache
from tutor.chat_flow import ChatFlow
from tutor.conversation import Conversation
from tutor.llm import create_llm_provider
from tutor.memory import MemoryManager
from tutor.tts import create_tts_provider
from tutor import service_detector
from tutor.search import create_search_provider

app = Flask(__name__)

# ── 全局状态（仅路由需要访问的） ──────────────
chat_flow: ChatFlow | None = None
audio_cache = AudioCache(max_size=200)
current_llm_engine: str = cfg.DEFAULT_LLM_ENGINE
current_search_engine: str = cfg.DEFAULT_SEARCH_ENGINE
current_silence_timeout: int = cfg.VOICE_SILENCE_TIMEOUT
search_provider = None


# ── 初始化 ────────────────────────────────────────

def _resolve_lang(lang_key: str):
    """模糊匹配语种 key（同 main.py）"""
    lang = lang_key.lower()
    if lang in cfg.LANGUAGE_CONFIGS:
        return lang, cfg.LANGUAGE_CONFIGS[lang]
    for key, val in cfg.LANGUAGE_CONFIGS.items():
        if key.startswith(lang) or lang.startswith(key):
            return key, val
    return None, None


def init_providers(lang_key: str = "english"):
    """初始化所有 provider 和 ChatFlow。"""
    global chat_flow, search_provider, current_llm_engine, current_search_engine

    resolved_key, lang_config = _resolve_lang(lang_key)
    if lang_config is None:
        resolved_key = "english"
        lang_config = cfg.LANGUAGE_CONFIGS["english"]

    config = {
        "TTS_ENGINE": cfg.TTS_ENGINE, "PYTTX3_RATE": 160,
        "PYTTX3_VOLUME": 0.9, "ASR_ENGINE": cfg.ASR_ENGINE,
        "LLM_ENGINE": cfg.LLM_ENGINE, "DEEPSEEK_API_KEY": cfg.DEEPSEEK_API_KEY,
        "DEEPSEEK_API_URL": cfg.DEEPSEEK_API_URL,
        "DEEPSEEK_MODEL": cfg.DEEPSEEK_MODEL, "lang": lang_config,
        "API_TIMEOUT": cfg.API_TIMEOUT,
    }

    tts = create_tts_provider(config)
    llm = create_llm_provider(config)
    memory = MemoryManager()
    memory.on_session_start()
    conv = Conversation(llm, system_prompt=lang_config["prompt"],
                        max_rounds=cfg.MAX_HISTORY_ROUNDS)
    memory_ctx = memory.get_context()
    if memory_ctx:
        conv.history.append({"role": "system", "content": memory_ctx})

    # 搜索 provider
    search_provider = create_search_provider({
        "SEARCH_ENGINE": "searxng",
        "SEARXNG_API_URL": cfg.SEARXNG_API_URL,
    })

    chat_flow = ChatFlow(
        llm=llm, tts=tts, conv=conv, memory=memory,
        audio_cache=audio_cache, search_provider=search_provider,
    )
    chat_flow.set_language(resolved_key, lang_config)
    chat_flow.search_engine = current_search_engine


# ── 路由 ──────────────────────────────────────────

@app.route("/")
def index():
    """返回聊天界面 HTML。"""
    template_path = os.path.join(os.path.dirname(__file__), "templates", "chat.html")
    with open(template_path, encoding="utf-8") as f:
        return f.read(), 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/api/init")
def api_init():
    """初始化页面数据：欢迎词 + 当前语言 + 会话信息。"""
    if chat_flow is None:
        return jsonify({"error": "not initialized"}), 503
    welcome = chat_flow.generate_welcome()
    return jsonify({
        "welcome": welcome,
        "current_lang": chat_flow.lang_key,
        "lang_display": chat_flow.lang_config["display"],
        "character_name": cfg.CHARACTER_NAME,
        "silence_timeout": current_silence_timeout,
    })


@app.route("/api/chat", methods=["POST"])
def api_chat():
    """发送消息 → NDJSON 流式事件。"""
    if chat_flow is None:
        return "Server not initialized", 503

    data = request.get_json(force=True)
    user_text = (data.get("message") or "").strip()
    if not user_text:
        return (json.dumps({"type": "error", "message": "消息不能为空"}) + "\n",
                400, {"Content-Type": "application/x-ndjson"})

    def generate():
        yield from chat_flow.process(user_text)

    return Response(generate(), mimetype="application/x-ndjson")


@app.route("/api/audio/<uid>")
def api_audio(uid):
    """返回缓存的 WAV 音频字节。"""
    wav = audio_cache.get(uid)
    if wav is None:
        return "Not found", 404
    return Response(wav, mimetype="audio/wav")


@app.route("/api/clear", methods=["POST"])
def api_clear():
    """清空对话历史。"""
    if chat_flow:
        chat_flow.conv.clear()
    return jsonify({"status": "ok"})


@app.route("/api/status")
def api_status():
    """返回当前状态。"""
    if chat_flow is None:
        return jsonify({"lang_key": "english", "lang_display": "English"})
    return jsonify({
        "lang_key": chat_flow.lang_key,
        "lang_display": chat_flow.lang_config["display"],
    })


@app.route("/api/config", methods=["GET", "POST"])
def api_config():
    """获取/更新引擎与功能配置。"""
    global current_llm_engine, current_search_engine, current_silence_timeout, search_provider

    if request.method == "GET":
        services = service_detector.detect_all()
        local_llm_available = services["ollama"]["status"] == "running"
        search_available = services["searxng"]["status"] == "running"

        return jsonify({
            "current": {
                "llm": current_llm_engine,
                "search": current_search_engine,
                "silence_timeout": current_silence_timeout,
            },
            "options": {
                "llm": [
                    {"id": "deepseek", "name": "DeepSeek API", "available": True},
                    {"id": "local", "name": "本地模型 (Ollama)", "available": local_llm_available},
                ],
                "search": [
                    {"id": "disabled", "name": "关闭", "available": True},
                    {"id": "searxng", "name": "SearXNG (本地)", "available": search_available},
                ],
                "silence_timeout": {"min": 0, "max": 5, "step": 1},
            },
            "services": services,
        })

    # POST: 切换配置
    data = request.get_json(force=True)
    engine = data.get("engine")
    value = data.get("value")

    if engine == "silence_timeout":
        try:
            value_int = int(value)
        except (ValueError, TypeError):
            return jsonify({"status": "error", "message": "超时值必须是数字"}), 400
        if value_int < 0 or value_int > 5:
            return jsonify({"status": "error", "message": "超时值必须在 0-5 之间"}), 400
        current_silence_timeout = value_int
        return jsonify({"status": "ok", "current": {"silence_timeout": current_silence_timeout}})

    if engine == "llm":
        if value == "local":
            services = service_detector.detect_all()
            if services["ollama"]["status"] != "running":
                return jsonify({"status": "error", "message": "Ollama 服务未运行"}), 400
        _recreate_llm(value)
        current_llm_engine = value
        return jsonify({"status": "ok", "current": {"llm": current_llm_engine}})

    elif engine == "search":
        if value == "searxng":
            services = service_detector.detect_all()
            if services["searxng"]["status"] != "running":
                return jsonify({"status": "error", "message": "SearXNG 服务未运行"}), 400
        current_search_engine = value
        if chat_flow:
            chat_flow.set_search_engine(value)
        return jsonify({"status": "ok", "current": {"search": current_search_engine}})

    return jsonify({"status": "error", "message": "未知引擎"}), 400


def _recreate_llm(engine: str):
    """重新创建 LLM provider 并更新 ChatFlow。"""
    global chat_flow
    if chat_flow is None:
        return

    if engine == "local":
        config = {
            "LLM_ENGINE": "deepseek",
            "DEEPSEEK_API_KEY": "ollama",
            "DEEPSEEK_API_URL": cfg.OLLAMA_API_URL + "/v1/chat/completions",
            "DEEPSEEK_MODEL": cfg.OLLAMA_MODEL,
            "API_TIMEOUT": cfg.API_TIMEOUT,
        }
    else:
        config = {
            "LLM_ENGINE": cfg.LLM_ENGINE,
            "DEEPSEEK_API_KEY": cfg.DEEPSEEK_API_KEY,
            "DEEPSEEK_API_URL": cfg.DEEPSEEK_API_URL,
            "DEEPSEEK_MODEL": cfg.DEEPSEEK_MODEL,
            "API_TIMEOUT": cfg.API_TIMEOUT,
        }
    config["TTS_ENGINE"] = cfg.TTS_ENGINE
    config["PYTTX3_RATE"] = 160
    config["PYTTX3_VOLUME"] = 0.9
    config["ASR_ENGINE"] = cfg.ASR_ENGINE

    llm = create_llm_provider(config)
    chat_flow.llm = llm
    chat_flow.conv._llm = llm
    # 同时更新 search_broker 中的 llm 引用
    if chat_flow.search_broker:
        chat_flow.search_broker.llm = llm


@app.route("/api/shutdown", methods=["POST"])
def api_shutdown():
    """关闭服务器（浏览器 tab 关闭时触发）。"""
    threading.Thread(target=lambda: (
        time.sleep(0.5),
        _print_docker_reminder(),
        os._exit(0),
    ), daemon=True).start()
    return jsonify({"status": "shutting_down"})


# ── Docker 关闭提醒 ──────────────────────────────

def _print_docker_reminder():
    """检查是否有 Docker 容器在后台运行，提醒用户关闭。"""
    try:
        import subprocess
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}\t{{.Ports}}"],
            capture_output=True, text=True, timeout=5,
        )
        if result.stdout.strip():
            print("\n" + "=" * 50)
            print("  ⚠ 以下 Docker 容器仍在后台运行：")
            for line in result.stdout.strip().split("\n"):
                parts = line.split("\t")
                name = parts[0] if parts else "?"
                ports = parts[1] if len(parts) > 1 else ""
                print(f"    {name}  {ports}")
            print()
            print("  关闭命令：docker compose down")
            print("=" * 50 + "\n")
    except Exception:
        pass


import atexit
atexit.register(_print_docker_reminder)


# ── 启动 ──────────────────────────────────────────

def run_web_server():
    """启动 Web 服务器（由 main.py 调用）。"""
    init_providers("english")

    # 后台预生成欢迎词
    def _pregen():
        time.sleep(0.5)
        try:
            if chat_flow:
                chat_flow.generate_welcome()
        except Exception:
            pass

    threading.Thread(target=_pregen, daemon=True).start()

    if cfg.AUTO_OPEN_BROWSER:
        def _open():
            time.sleep(1.2)
            webbrowser.open(f"http://localhost:{cfg.WEB_PORT}")
        threading.Thread(target=_open, daemon=True).start()

    print(f"  [Web] 浏览器打开 http://localhost:{cfg.WEB_PORT}")
    print(f"  [Web] 局域网访问 http://<本机IP>:{cfg.WEB_PORT}")
    print(f"  [Web] 按 Ctrl+C 停止服务器")
    app.run(host=cfg.WEB_HOST, port=cfg.WEB_PORT, debug=False, threaded=True)


if __name__ == "__main__":
    run_web_server()
