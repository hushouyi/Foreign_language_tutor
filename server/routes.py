"""
Flask 路由 — 纯路由层，所有业务逻辑委托给 tutor/* 模块
=====================================================
"""

import json
import os
import threading
import time

from flask import Response, jsonify, request

from . import app, cfg, state
from . import _print_docker_reminder
from tutor import service_detector


# ── 页面 ──────────────────────────────────────

@app.route("/")
def index():
    """返回聊天界面 HTML。"""
    template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates", "chat.html")
    with open(template_path, encoding="utf-8") as f:
        return f.read(), 200, {"Content-Type": "text/html; charset=utf-8"}


# ── API: 初始化 ───────────────────────────────

@app.route("/api/init")
def api_init():
    """初始化页面数据：欢迎词 + 当前语言 + 会话信息。"""
    if state.chat_flow is None:
        return jsonify({"error": "not initialized"}), 503
    welcome = state.chat_flow.generate_welcome()
    return jsonify({
        "welcome": welcome,
        "current_lang": state.chat_flow.lang_key,
        "lang_display": state.chat_flow.lang_config["display"],
        "character_name": cfg.CHARACTER_NAME,
        "silence_timeout": state.current_silence_timeout,
    })


# ── API: 聊天 ─────────────────────────────────

@app.route("/api/chat", methods=["POST"])
def api_chat():
    """发送消息 → NDJSON 流式事件。"""
    if state.chat_flow is None:
        return "Server not initialized", 503

    data = request.get_json(force=True)
    user_text = (data.get("message") or "").strip()
    if not user_text:
        return (json.dumps({"type": "error", "message": "消息不能为空"}) + "\n",
                400, {"Content-Type": "application/x-ndjson"})

    def generate():
        yield from state.chat_flow.process(user_text)

    return Response(generate(), mimetype="application/x-ndjson")


# ── API: 音频 ─────────────────────────────────

@app.route("/api/audio/<uid>")
def api_audio(uid):
    """返回缓存的 WAV 音频字节。"""
    ac = state.audio_cache
    wav = ac.get(uid) if ac else None
    if wav is None:
        return "Not found", 404
    return Response(wav, mimetype="audio/wav")


# ── API: 清空对话 ─────────────────────────────

@app.route("/api/clear", methods=["POST"])
def api_clear():
    """清空对话历史。"""
    if state.chat_flow:
        state.chat_flow.conv.clear()
    return jsonify({"status": "ok"})


# ── API: 状态 ─────────────────────────────────

@app.route("/api/status")
def api_status():
    """返回当前状态。"""
    if state.chat_flow is None:
        return jsonify({"lang_key": "english", "lang_display": "English"})
    return jsonify({
        "lang_key": state.chat_flow.lang_key,
        "lang_display": state.chat_flow.lang_config["display"],
    })


# ── API: 配置 ─────────────────────────────────

@app.route("/api/config", methods=["GET", "POST"])
def api_config():
    """获取/更新引擎与功能配置。"""
    if request.method == "GET":
        services = service_detector.detect_all()
        local_llm_available = services["ollama"]["status"] == "running"
        search_available = services["searxng"]["status"] == "running"

        return jsonify({
            "current": {
                "llm": state.current_llm_engine,
                "search": state.current_search_engine,
                "silence_timeout": state.current_silence_timeout,
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
        state.current_silence_timeout = value_int
        return jsonify({"status": "ok", "current": {"silence_timeout": state.current_silence_timeout}})

    if engine == "llm":
        if value == "local":
            services = service_detector.detect_all()
            if services["ollama"]["status"] != "running":
                return jsonify({"status": "error", "message": "Ollama 服务未运行"}), 400
        from . import _recreate_llm
        _recreate_llm(value)
        state.current_llm_engine = value
        return jsonify({"status": "ok", "current": {"llm": state.current_llm_engine}})

    elif engine == "search":
        if value == "searxng":
            services = service_detector.detect_all()
            if services["searxng"]["status"] != "running":
                return jsonify({"status": "error", "message": "SearXNG 服务未运行"}), 400
        state.current_search_engine = value
        if state.chat_flow:
            state.chat_flow.set_search_engine(value)
        return jsonify({"status": "ok", "current": {"search": state.current_search_engine}})

    return jsonify({"status": "error", "message": "未知引擎"}), 400


# ── API: 关闭服务器 ───────────────────────────

@app.route("/api/shutdown", methods=["POST"])
def api_shutdown():
    """关闭服务器（浏览器 tab 关闭时触发）。"""
    threading.Thread(target=lambda: (
        time.sleep(0.5),
        _print_docker_reminder(),
        os._exit(0),
    ), daemon=True).start()
    return jsonify({"status": "shutting_down"})
