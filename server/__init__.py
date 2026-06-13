"""
Flask 应用 — 工厂函数 + 全局初始化
===================================
create_app() 创建并初始化 Flask 应用。
路由定义在 routes.py 中，共享状态在 state.py 中。
"""

import os
import sys
import threading
import time
import webbrowser

from flask import Flask

# 确保根目录在 path 中（让 import tutor/ 和 apikey.py 可用）
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

# ── Flask 实例 ──────────────────────────────
# static/templates 指向根目录以保持目录结构不变
app = Flask(__name__,
    static_folder=os.path.join(_root, 'static'),
    template_folder=os.path.join(_root, 'templates'))

# ── 配置加载（必须先于其他 import） ──────────
from . import config as cfg

# ── 共享状态 ────────────────────────────────
from . import state


# ── 初始化函数 ──────────────────────────────

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
    from tutor.tts import create_tts_provider
    from tutor.llm import create_llm_provider
    from tutor.memory import MemoryManager
    from tutor.conversation import Conversation
    from tutor.search import create_search_provider
    from tutor.chat_flow import ChatFlow
    from tutor.audio_cache import AudioCache

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

    state.search_provider = create_search_provider({
        "SEARCH_ENGINE": "searxng",
        "SEARXNG_API_URL": cfg.SEARXNG_API_URL,
    })

    state.audio_cache = AudioCache(max_size=200)

    state.chat_flow = ChatFlow(
        llm=llm, tts=tts, conv=conv, memory=memory,
        audio_cache=state.audio_cache, search_provider=state.search_provider,
    )
    state.chat_flow.set_language(resolved_key, lang_config)
    state.chat_flow.search_engine = state.current_search_engine


def _recreate_llm(engine: str):
    """重新创建 LLM provider 并更新 ChatFlow。"""
    from tutor.llm import create_llm_provider

    if state.chat_flow is None:
        return

    if engine == "local":
        llm_config = {
            "LLM_ENGINE": "deepseek",
            "DEEPSEEK_API_KEY": "ollama",
            "DEEPSEEK_API_URL": cfg.OLLAMA_API_URL + "/v1/chat/completions",
            "DEEPSEEK_MODEL": cfg.OLLAMA_MODEL,
            "API_TIMEOUT": cfg.API_TIMEOUT,
        }
    else:
        llm_config = {
            "LLM_ENGINE": cfg.LLM_ENGINE,
            "DEEPSEEK_API_KEY": cfg.DEEPSEEK_API_KEY,
            "DEEPSEEK_API_URL": cfg.DEEPSEEK_API_URL,
            "DEEPSEEK_MODEL": cfg.DEEPSEEK_MODEL,
            "API_TIMEOUT": cfg.API_TIMEOUT,
        }
    llm_config["TTS_ENGINE"] = cfg.TTS_ENGINE
    llm_config["PYTTX3_RATE"] = 160
    llm_config["PYTTX3_VOLUME"] = 0.9
    llm_config["ASR_ENGINE"] = cfg.ASR_ENGINE

    llm = create_llm_provider(llm_config)
    state.chat_flow.llm = llm
    state.chat_flow.conv._llm = llm
    if state.chat_flow.search_broker:
        state.chat_flow.search_broker.llm = llm


# ── Docker 关闭提醒 ──────────────────────────

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


# ── 路由注册（必须在 app 和全局变量之后） ──
from . import routes


# ── 工厂函数 ─────────────────────────────────

def create_app():
    """创建并初始化 Flask 应用，返回 app 实例。"""
    init_providers("english")

    # 后台预生成欢迎词
    def _pregen():
        time.sleep(0.5)
        try:
            if state.chat_flow:
                state.chat_flow.generate_welcome()
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

    return app


# ══════════════════════════════════════════════
# 直接运行
# ══════════════════════════════════════════════

if __name__ == "__main__":
    app = create_app()
    app.run(host=cfg.WEB_HOST, port=cfg.WEB_PORT, debug=False, threaded=True)
