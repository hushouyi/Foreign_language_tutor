"""
OpenClaw AI 语音助手 - 主程序
=============================
用法:
  python main.py                    # 默认英语
  python main.py --lang japanese    # 启动日语模式
"""

import argparse
import sys

import config as cfg
from tutor.asr import create_asr_provider
from tutor.conversation import Conversation
from tutor.llm import create_llm_provider
from tutor.tts import create_tts_provider
from tutor.utils import parse_response


def resolve_lang(lang_key: str):
    """解析语言标识，返回完整的语言配置"""
    lang = lang_key.lower()
    if lang in cfg.LANGUAGE_CONFIGS:
        return lang, cfg.LANGUAGE_CONFIGS[lang]
    # 尝试模糊匹配：english → en, japanese → ja
    for key, val in cfg.LANGUAGE_CONFIGS.items():
        if key.startswith(lang) or lang.startswith(key):
            return key, val
    print(f"⚠ 未知语种: {lang_key}，可用: {', '.join(cfg.LANGUAGE_CONFIGS.keys())}")
    sys.exit(1)


def detect_switch_request(text: str):
    """检测用户是否请求切换语种，返回 (lang_key, confirm_needed) 或 None"""
    lower = text.lower()
    for key in cfg.LANGUAGE_CONFIGS:
        display = cfg.LANGUAGE_CONFIGS[key]["display"].lower()
        # 匹配: switch to X, change to X, speak X, use X
        triggers = [
            f"switch to {key}", f"switch to {display}",
            f"change to {key}", f"change to {display}",
            f"speak {key}", f"speak {display}",
            f"use {key}", f"use {display}",
            f"let's speak {key}", f"let's speak {display}",
        ]
        if any(t in lower for t in triggers):
            return key
    return None


def detect_affirmative(text: str):
    """检测用户是否确认了切换"""
    lower = text.lower().strip()
    return lower in ("yes", "yeah", "ok", "okay", "sure", "go ahead", "please", "y", "yes please")


def main():
    # ── 命令行参数 ──
    parser = argparse.ArgumentParser(description="OpenClaw AI 语音助手")
    parser.add_argument("--lang", default=cfg.LANGUAGE,
                        help=f"语种: {', '.join(cfg.LANGUAGE_CONFIGS.keys())} (默认: {cfg.LANGUAGE})")
    args = parser.parse_args()

    current_lang_key, current_lang = resolve_lang(args.lang)
    name = cfg.CHARACTER_NAME

    # ── 构建引擎配置 ──
    config = {
        "TTS_ENGINE": cfg.TTS_ENGINE,
        "PYTTX3_RATE": 160,
        "PYTTX3_VOLUME": 0.9,
        "ASR_ENGINE": cfg.ASR_ENGINE,
        "LLM_ENGINE": cfg.LLM_ENGINE,
        "DEEPSEEK_API_KEY": cfg.DEEPSEEK_API_KEY,
        "DEEPSEEK_API_URL": cfg.DEEPSEEK_API_URL,
        "DEEPSEEK_MODEL": cfg.DEEPSEEK_MODEL,
        "lang": current_lang,
    }

    # ── 引擎初始化 ──
    tts = create_tts_provider(config)
    asr = create_asr_provider(config)
    llm = create_llm_provider(config)
    conv = Conversation(
        llm,
        system_prompt=current_lang["prompt"],
        max_rounds=cfg.MAX_HISTORY_ROUNDS,
    )

    # ── 显示 Banner ──
    print("=" * 55)
    print(f"🎙️  {name} · AI 语音助手")
    print("=" * 55)
    print(f"  语种: {current_lang['display']}  |  TTS: {cfg.TTS_ENGINE}  |  LLM: {cfg.LLM_ENGINE}")
    print("-" * 55)
    print(f"  输入对话，{name} 会语音回复 + 中文翻译")
    print(f"  切换语种: \"switch to japanese\" / \"speak french\" 等")
    print("  bye / exit 退出  |  clear 清空历史")
    print("=" * 55)

    # ── 开场白 ──
    welcome_text = f"Hey there! I'm {name}. Let's practice English. What's up today?"
    welcome_zh = f"嘿！我是{name}。今天想聊点什么？"
    print(f"\n{name}[{current_lang['display']}]: ", end="")
    tts.speak(welcome_text)
    print(f"📝 中文: {welcome_zh}")

    # ── 语言切换状态 ──
    _pending_lang = None  # 待切换的语种 key

    # ── 主循环 ──
    while True:
        try:
            user_input = asr.listen()
            if not user_input:
                continue

            # 退出
            if user_input.lower() in ("bye", "exit", "quit", "goodbye", "再见"):
                print(f"\n{name}[{current_lang['display']}]: ", end="")
                tts.speak("Great talking with you! Keep practicing, see you next time!")
                print("\n👋 再见！")
                break

            # 清空历史
            if user_input.lower() == "clear":
                conv.clear()
                print("✓ 对话历史已清空")
                continue

            # ── 语言切换确认 ──
            if _pending_lang:
                if detect_affirmative(user_input):
                    # 执行切换
                    new_key = _pending_lang
                    new_lang = cfg.LANGUAGE_CONFIGS[new_key]
                    _pending_lang = None

                    current_lang_key = new_key
                    current_lang = new_lang
                    config["lang"] = new_lang

                    # 更新 TTS 语音
                    if hasattr(tts, "set_voice"):
                        tts.set_voice(new_lang["voice"])

                    # 更新对话系统提示词
                    conv.set_system_prompt(new_lang["prompt"])

                    print(f"\n🔄 已切换到 {new_lang['display']}")
                    print(f"\n{name}[{new_lang['display']}]: ", end="")
                    tts.speak(f"Okay! Let's practice {new_key} now. What do you want to talk about?")
                    continue
                else:
                    _pending_lang = None
                    # 普通对话继续，不切换

            # ── 检测语言切换请求 ──
            switch_to = detect_switch_request(user_input)
            if switch_to and switch_to != current_lang_key:
                _pending_lang = switch_to
                target_display = cfg.LANGUAGE_CONFIGS[switch_to]["display"]
                print(f"\n{name}[{current_lang['display']}]: ", end="")
                tts.speak(f"Do you want to switch to {target_display}? Just say yes or no.")
                continue

            # ── 正常对话 ──
            reply = conv.ask(
                user_input,
                temperature=cfg.TEMPERATURE,
                max_tokens=cfg.MAX_TOKENS,
            )
            content, chinese = parse_response(reply)
            print(f"\n{name}[{current_lang['display']}]: ", end="")
            tts.speak(content)
            if chinese:
                print(f"📝 中文: {chinese}")

        except KeyboardInterrupt:
            print("\n\n👋 再见！")
            break
        except Exception as e:
            print(f"\n⚠ 发生错误: {e}")
            print("  请重试或输入 'bye' 退出")


if __name__ == "__main__":
    main()
