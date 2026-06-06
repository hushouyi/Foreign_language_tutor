"""
OpenClaw AI 语音助手 - 主程序
=============================
用法:
  python main.py                    # 默认英语
  python main.py --lang japanese    # 日语模式启动
"""

import argparse
import re
import sys

import config as cfg
from tutor.asr import create_asr_provider
from tutor.conversation import Conversation
from tutor.llm import create_llm_provider
from tutor.memory import MemoryManager
from tutor.tts import create_tts_provider
from tutor.utils import parse_response


def resolve_lang(lang_key: str):
    lang = lang_key.lower()
    if lang in cfg.LANGUAGE_CONFIGS:
        return lang, cfg.LANGUAGE_CONFIGS[lang]
    for key, val in cfg.LANGUAGE_CONFIGS.items():
        if key.startswith(lang) or lang.startswith(key):
            return key, val
    print(f"⚠ 未知语种: {lang_key}，可用: {', '.join(cfg.LANGUAGE_CONFIGS.keys())}")
    sys.exit(1)


def _strip_emoji(text: str) -> str:
    """移除 emoji 字符，避免 TTS 读出表情描述"""
    return re.sub(r'[\U0001F300-\U0001FAFF\U0001F600-\U0001F64F\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF☀-⛿✀-➿⌀-⏿︀-️]', '', text)


def _script_mismatch(text: str, lang_key: str) -> bool:
    """检测文本语言是否与当前语种不匹配（脚本级别快速检测）"""
    has_cjk = bool(re.search(r'[぀-ゟ゠-ヿ一-鿿]', text))
    if lang_key == "english" and has_cjk:
        return True
    if lang_key in ("japanese",) and not has_cjk:
        return True
    return False


def main():
    # ── 命令行参数 ──
    parser = argparse.ArgumentParser(description="OpenClaw AI 语音助手")
    parser.add_argument("--lang", default=cfg.LANGUAGE,
                        help=f"语种: {', '.join(cfg.LANGUAGE_CONFIGS.keys())} (默认: {cfg.LANGUAGE})")
    args = parser.parse_args()

    current_lang_key, current_lang = resolve_lang(args.lang)
    name = cfg.CHARACTER_NAME

    # ── 引擎配置 ──
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
    memory = MemoryManager()
    conv = Conversation(
        llm,
        system_prompt=current_lang["prompt"],
        max_rounds=cfg.MAX_HISTORY_ROUNDS,
    )
    memory_ctx = memory.get_context()
    if memory_ctx:
        conv.history.append({"role": "system", "content": memory_ctx})

    # ── Banner ──
    print("=" * 55)
    print(f"  {name} · AI 语言助教")
    print("=" * 55)
    print(f"  语种: {current_lang['display']}  |  TTS: {cfg.TTS_ENGINE}  |  LLM: {cfg.LLM_ENGINE}")
    print("-" * 55)
    print(f"  输入对话，{name} 会语音回复 + 中文翻译")
    print("  切换语种: \"说日语\" / \"speak French\" / \"switch to spanish\" 等")
    print("  bye / exit 退出  |  clear 清空历史")
    print("=" * 55)

    # ── 开场白 ──
    welcome_text = current_lang["hello"]
    welcome_zh = current_lang["hello_zh"]
    print(f"\n{name}[{current_lang['display']}]: {welcome_text}")
    tts.speak(_strip_emoji(welcome_text))
    print(f"📝 中文: {welcome_zh}")

    # ── 主循环 ──
    while True:
        try:
            user_input = asr.listen()
            if not user_input:
                continue

            # 退出
            if user_input.lower() in ("bye", "exit", "quit", "goodbye", "再见"):
                farewell_text = "Great talking with you! Keep practicing, see you next time!"
                print(f"\n{name}[{current_lang['display']}]: {farewell_text}")
                tts.speak(_strip_emoji(farewell_text))
                print("\n👋 再见！")
                break

            # 清空历史
            if user_input.lower() == "clear":
                conv.clear()
                print("✓ 对话历史已清空")
                continue

            # ── 检测语言切换请求（LANG_SWITCH:xxx 前缀）──
            reply = conv.ask(
                user_input,
                temperature=cfg.TEMPERATURE,
                max_tokens=cfg.MAX_TOKENS,
            )
            reply = memory.process_reply(reply)

            if reply.startswith("LANG_SWITCH:"):
                lines = reply.split("\n", 1)
                target_key = lines[0].replace("LANG_SWITCH:", "").strip()

                if target_key in cfg.LANGUAGE_CONFIGS and target_key != current_lang_key:
                    # 显示 AI 的确认问题（LANG_SWITCH: 之后的内容）
                    if len(lines) > 1 and lines[1].strip():
                        question = lines[1].strip()
                        print(f"\n{name}[{current_lang['display']}]: {question}")
                        tts.speak(_strip_emoji(question))

                    # 等用户回复 → 交给 AI 自然理解
                    user_confirm = asr.listen()
                    if not user_confirm:
                        continue

                    confirm_reply = conv.ask(
                        user_confirm,
                        temperature=cfg.TEMPERATURE,
                        max_tokens=cfg.MAX_TOKENS,
                    )
                    confirm_reply = memory.process_reply(confirm_reply)

                    # AI 以 LANG_SWITCH:confirmed: 开头表示确认切换
                    if confirm_reply.startswith("LANG_SWITCH:confirmed:"):
                        confirmed_key = confirm_reply.split("\n", 1)[0].replace("LANG_SWITCH:confirmed:", "").strip()
                        if confirmed_key in cfg.LANGUAGE_CONFIGS and confirmed_key != current_lang_key:
                            new_lang = cfg.LANGUAGE_CONFIGS[confirmed_key]
                            current_lang_key = confirmed_key
                            current_lang = new_lang
                            config["lang"] = new_lang

                            if hasattr(tts, "set_voice"):
                                tts.set_voice(new_lang["voice"])
                            conv.set_system_prompt(new_lang["prompt"])

                            # 显示 AI 的欢迎回复（去掉确认前缀）
                            rest = confirm_reply.split("\n", 1)[1] if "\n" in confirm_reply else ""
                            content, chinese = parse_response(rest)
                            print(f"\n🔄 已切换到 {new_lang['display']}")
                            print(f"\n{name}[{new_lang['display']}]: {content}")
                            tts.speak(_strip_emoji(content))
                            if chinese:
                                print(f"📝 中文: {chinese}")
                            continue
                        # 无效的确认 key，当作普通回复处理

                    # AI 未确认切换 → 正常显示回复
                    content, chinese = parse_response(confirm_reply)
                    print(f"\n{name}[{current_lang['display']}]: {content}")
                    tts.speak(_strip_emoji(content))
                    if chinese:
                        print(f"📝 中文: {chinese}")
                    # 清除对话历史中的 LANG_SWITCH 痕迹，保持语种一致
                    conv.history = [m for m in conv.history
                                    if not m["content"].startswith("LANG_SWITCH:")]
                    conv.history.append({
                        "role": "system",
                        "content": "[Language switch declined. Continue in current language.]"
                    })
                continue

            # ── 正常回复解析（非 LANG_SWITCH）──
            content, chinese = parse_response(reply)
            print(f"\n{name}[{current_lang['display']}]: {content}")
            ok = tts.speak(_strip_emoji(content))
            if chinese:
                print(f"📝 中文: {chinese}")
            if not ok and _script_mismatch(content, current_lang_key):
                print(f"💡 AI 似乎用了其他语言回复。需要切换语种的话，可以说 \"switch to japanese\" 或 \"说英语\" 等")

        except KeyboardInterrupt:
            print("\n\n👋 再见！")
            break
        except Exception as e:
            print(f"\n⚠ 发生错误: {e}")
            print("  请重试或输入 'bye' 退出")


if __name__ == "__main__":
    main()
