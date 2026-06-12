"""
Web 服务器 — AI 语言助教的浏览器界面
=====================================
用法:
  python main.py              # 启动 Web 模式，自动打开浏览器

在浏览器中打开 http://localhost:5000
"""

import json
import os
import re
import sys
import threading
import time
import uuid
import webbrowser

from flask import Flask, Response, jsonify, request

# 确保能导入项目模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config as cfg
from tutor.conversation import Conversation
from tutor.llm import create_llm_provider
from tutor.memory import MemoryManager
from tutor.tts import create_tts_provider
from tutor.utils import parse_response, split_segments
from tutor import service_detector

app = Flask(__name__)

# ── 全局状态 ──────────────────────────────────────
memory: MemoryManager | None = None
conv: Conversation | None = None
tts = None
llm = None
current_lang_key: str = "english"
current_lang: dict = cfg.LANGUAGE_CONFIGS["english"]
audio_cache: dict[str, bytes] = {}
welcome_data: dict | None = None
welcome_lock = threading.Lock()

# 引擎与功能配置（运行时，可通过 /api/config 切换）
current_llm_engine: str = cfg.DEFAULT_LLM_ENGINE   # "deepseek" | "local"
current_search_engine: str = cfg.DEFAULT_SEARCH_ENGINE  # "disabled" | "searxng"


# ── 工具函数 ──────────────────────────────────────

def _resolve_lang(lang_key: str):
    """模糊匹配语种 key（同 main.py）"""
    lang = lang_key.lower()
    if lang in cfg.LANGUAGE_CONFIGS:
        return lang, cfg.LANGUAGE_CONFIGS[lang]
    for key, val in cfg.LANGUAGE_CONFIGS.items():
        if key.startswith(lang) or lang.startswith(key):
            return key, val
    return None, None


def _script_mismatch(text: str, lang_key: str) -> bool:
    has_cjk = bool(re.search(r'[぀-ゟ゠-ヿ一-鿿]', text))
    if lang_key == "english" and has_cjk:
        return True
    if lang_key in ("japanese",) and not has_cjk:
        return True
    return False


# ── 初始化 ────────────────────────────────────────

def init_providers(lang_key: str = "english"):
    """初始化所有 provider（同 main.py 启动流程）"""
    global memory, conv, tts, llm, current_lang_key, current_lang

    current_lang_key, current_lang = _resolve_lang(lang_key)
    if current_lang is None:
        current_lang_key = "english"
        current_lang = cfg.LANGUAGE_CONFIGS["english"]

    config = {
        "TTS_ENGINE": cfg.TTS_ENGINE, "PYTTX3_RATE": 160,
        "PYTTX3_VOLUME": 0.9, "ASR_ENGINE": cfg.ASR_ENGINE,
        "LLM_ENGINE": cfg.LLM_ENGINE, "DEEPSEEK_API_KEY": cfg.DEEPSEEK_API_KEY,
        "DEEPSEEK_API_URL": cfg.DEEPSEEK_API_URL,
        "DEEPSEEK_MODEL": cfg.DEEPSEEK_MODEL, "lang": current_lang,
        "API_TIMEOUT": cfg.API_TIMEOUT,
    }

    global tts
    tts = create_tts_provider(config)
    llm = create_llm_provider(config)
    memory = MemoryManager()
    memory.on_session_start()
    conv = Conversation(llm, system_prompt=current_lang["prompt"],
                        max_rounds=cfg.MAX_HISTORY_ROUNDS)
    memory_ctx = memory.get_context()
    if memory_ctx:
        conv.history.append({"role": "system", "content": memory_ctx})


def generate_welcome():
    """生成欢迎词（缓存，仅首次调用时真正生成）"""
    global welcome_data
    if welcome_data is not None:
        return welcome_data

    with welcome_lock:
        if welcome_data is not None:
            return welcome_data

        conv.history.append({
            "role": "system",
            "content": ("Greet the user warmly but concisely — 1-2 sentences, friendly tone, "
                        "under 25 words total. Show warmth but keep it brief. "
                        "Be creative each time. Follow the normal reply format.")
        })
        try:
            reply = llm.chat(conv.history, temperature=cfg.TEMPERATURE, max_tokens=600)
        except Exception:
            reply = "Hi there! Ready to practice today?\n---\n嗨！准备好今天的练习了吗？"
        conv.history.pop()
        reply = memory.process_reply(reply)
        segments = split_segments(parse_response(reply))

        result_segments = []
        audio_infos = []
        for idx, (content, translation) in enumerate(segments):
            result_segments.append({"content": content, "translation": translation})
            uid: str | None = None
            if tts:
                try:
                    wav = tts._generate_wav_bytes(content)
                    uid = str(uuid.uuid4())
                    audio_cache[uid] = wav
                except Exception:
                    pass
            audio_infos.append({"index": idx, "url": f"/api/audio/{uid}" if uid else None})

        welcome_data = {"segments": result_segments, "audio_urls": audio_infos}
        return welcome_data


# ── NDJSON 工具 ──────────────────────────────────

def ndjson(event_type: str, **data) -> str:
    return json.dumps({"type": event_type, **data}, ensure_ascii=False) + "\n"


# ── 路由 ──────────────────────────────────────────

@app.route("/")
def index():
    """返回 WeChat 风格聊天界面"""
    template_path = os.path.join(os.path.dirname(__file__), "templates", "chat.html")
    with open(template_path, encoding="utf-8") as f:
        return f.read(), 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/api/init")
def api_init():
    """初始化页面数据：返回欢迎词 + 当前语言 + 会话信息"""
    welcome = generate_welcome()
    return jsonify({
        "welcome": welcome,
        "current_lang": current_lang_key,
        "lang_display": current_lang["display"],
        "character_name": cfg.CHARACTER_NAME,
    })


@app.route("/api/chat", methods=["POST"])
def api_chat():
    """发送消息 → 返回 NDJSON 流式事件"""
    data = request.get_json(force=True)
    user_text = (data.get("message") or "").strip()
    if not user_text:
        return ndjson("error", message="消息不能为空"), 400, {"Content-Type": "application/x-ndjson"}

    def generate():
        nonlocal user_text
        global current_lang_key, current_lang

        # ── 1. 处理系统命令 ──
        cmd = user_text.lower()
        if cmd in ("clear",):
            conv.clear()
            yield ndjson("cleared")
            yield ndjson("done")
            return

        if cmd in ("bye", "exit", "quit", "goodbye", "再见"):
            yield ndjson("status", status="goodbye")
            yield ndjson("done")
            return

        # ── 2. 通知客户端 AI 开始思考 ──
        yield ndjson("status", status="thinking")

        # ── 3. 调用 LLM ──
        reminder = ("\n\nIMPORTANT FORMAT: Split your reply into segments. "
                    "Each segment = text + newline + '---' + newline + Chinese translation. "
                    "EVERY segment MUST have Chinese translation!")
        try:
            reply = conv.ask(user_text + reminder, temperature=cfg.TEMPERATURE,
                             max_tokens=cfg.MAX_TOKENS)
        except Exception as e:
            yield ndjson("error", message=str(e))
            yield ndjson("done")
            return

        reply = memory.process_reply(reply)

        # ── 4. 处理 LANG_SWITCH: 协议 ──
        if reply.startswith("LANG_SWITCH:"):
            lines = reply.split("\n", 1)
            header = lines[0].replace("LANG_SWITCH:", "").strip()
            is_confirmed = header.startswith("confirmed:")
            target_key = header[10:].strip() if is_confirmed else header

            if target_key not in cfg.LANGUAGE_CONFIGS or target_key == current_lang_key:
                conv.history = [m for m in conv.history
                                if not m["content"].startswith("LANG_SWITCH:")]
                yield ndjson("done")
                return

            rest = lines[1] if len(lines) > 1 else ""

            if not is_confirmed:
                # 未确认：用固定确认话术
                target_name = current_lang.get("names", {}).get(target_key, target_key)
                confirm_text = current_lang["confirm_switch"].format(lang=target_name)
                confirm_cn = current_lang.get("confirm_switch_cn", "").format(
                    lang=cfg.LANG_NAMES_CN.get(target_key, target_key))
                segments = split_segments(parse_response(confirm_text + "\n---\n" + confirm_cn))
                for i, (content, translation) in enumerate(segments):
                    yield ndjson("segment", index=i, content=content, translation=translation)
                    yield from _gen_audio(content, i)
                yield ndjson("done")
                return

            # 已确认：执行切换
            new_lang = cfg.LANGUAGE_CONFIGS[target_key]
            current_lang_key = target_key
            current_lang = new_lang
            if hasattr(tts, "set_voice"):
                tts.set_voice(new_lang["voice"])
            conv.set_system_prompt(new_lang["prompt"])

            yield ndjson("lang_switch", lang_key=target_key, display=new_lang["display"])

            if rest.strip():
                segments = split_segments(parse_response(rest))
                for i, (content, translation) in enumerate(segments):
                    yield ndjson("segment", index=i, content=content, translation=translation)
                    yield from _gen_audio(content, i)
                    if _script_mismatch(content, current_lang_key):
                        yield ndjson("warning", message="AI 用了其他语言回复")
                has_cn = any(cn for _, cn in segments)
                if not has_cn:
                    yield ndjson("warning", message="AI 回复缺少中文翻译")
            yield ndjson("done")
            return

        # ── 5. 处理 ERROR ──
        if reply.startswith("ERROR:"):
            yield ndjson("error", message=reply[6:])
            yield ndjson("done")
            return

        # ── 6. 正常回复：分段 + 音频 ──
        segments = split_segments(parse_response(reply))
        if not segments:
            yield ndjson("done")
            return

        for i, (content, translation) in enumerate(segments):
            yield ndjson("segment", index=i, content=content, translation=translation)
            yield from _gen_audio(content, i)

        # 语言漂移检测
        if _script_mismatch(segments[0][0], current_lang_key):
            yield ndjson("warning", message="AI 用了其他语言回复")
        has_any_cn = any(cn for _, cn in segments)
        if not has_any_cn:
            yield ndjson("warning", message="AI 回复缺少中文翻译")

        yield ndjson("done")

    return Response(generate(), mimetype="application/x-ndjson")


def _gen_audio(text: str, index: int):
    """生成音频并 yield audio NDJSON 事件"""
    if not tts:
        return
    try:
        wav = tts._generate_wav_bytes(text)
        uid = str(uuid.uuid4())
        audio_cache[uid] = wav
        yield ndjson("audio", index=index, url=f"/api/audio/{uid}")
    except Exception:
        yield ndjson("audio", index=index, url=None)


@app.route("/api/audio/<uid>")
def api_audio(uid):
    """返回缓存的 WAV 音频字节"""
    wav = audio_cache.get(uid)
    if wav is None:
        return "Not found", 404
    return Response(wav, mimetype="audio/wav")


@app.route("/api/clear", methods=["POST"])
def api_clear():
    """清空对话历史"""
    conv.clear()
    return jsonify({"status": "ok"})


@app.route("/api/status")
def api_status():
    """返回当前状态（前端轮询用）"""
    return jsonify({
        "lang_key": current_lang_key,
        "lang_display": current_lang["display"],
    })


@app.route("/api/config", methods=["GET", "POST"])
def api_config():
    """获取/更新引擎与功能配置"""
    global current_llm_engine, current_search_engine

    if request.method == "GET":
        services = service_detector.detect_all()
        local_llm_available = services["ollama"]["status"] == "running"
        search_available = services["searxng"]["status"] == "running"

        options = {
            "llm": [
                {"id": "deepseek", "name": "DeepSeek API", "available": True},
                {"id": "local", "name": "本地模型 (Ollama)", "available": local_llm_available},
            ],
            "search": [
                {"id": "disabled", "name": "关闭", "available": True},
                {"id": "searxng", "name": "SearXNG (本地)", "available": search_available},
            ],
        }

        return jsonify({
            "current": {
                "llm": current_llm_engine,
                "search": current_search_engine,
            },
            "options": options,
            "services": services,
        })

    # POST: 切换配置
    data = request.get_json(force=True)
    engine = data.get("engine")
    value = data.get("value")

    if engine == "llm":
        if value == "local":
            services = service_detector.detect_all()
            if services["ollama"]["status"] != "running":
                return jsonify({"status": "error", "message": "Ollama 服务未运行"}), 400
            _recreate_llm("local")
            current_llm_engine = "local"
        else:
            _recreate_llm("deepseek")
            current_llm_engine = "deepseek"
        return jsonify({"status": "ok", "current": {"llm": current_llm_engine}})

    elif engine == "search":
        if value == "searxng":
            services = service_detector.detect_all()
            if services["searxng"]["status"] != "running":
                return jsonify({"status": "error", "message": "SearXNG 服务未运行"}), 400
        current_search_engine = value
        return jsonify({"status": "ok", "current": {"search": current_search_engine}})

    return jsonify({"status": "error", "message": "未知引擎"}), 400


def _recreate_llm(engine: str):
    """重新创建 LLM provider（切换引擎）"""
    global llm, conv, tts, memory
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
    config["lang"] = current_lang

    llm = create_llm_provider(config)
    conv._llm = llm


@app.route("/api/shutdown", methods=["POST"])
def api_shutdown():
    """关闭 Flask 服务器（由浏览器 tab 关闭时触发）"""
    # 确保响应返回后再退出，0.5s 后强制终止进程
    threading.Thread(target=lambda: (
        time.sleep(0.5),
        os._exit(0)
    ), daemon=True).start()
    return jsonify({"status": "shutting_down"})


# ── 启动 ──────────────────────────────────────────

def run_web_server():
    """启动 Web 服务器（由 main.py 调用）"""
    # 初始化
    init_providers("english")

    # 后台预生成欢迎词
    def _pregen():
        time.sleep(0.5)
        try:
            generate_welcome()
        except Exception:
            pass

    threading.Thread(target=_pregen, daemon=True).start()

    # 自动打开浏览器
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
