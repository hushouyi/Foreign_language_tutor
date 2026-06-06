"""
AI 语言助教 - 主程序
====================
用法:
  python main.py                    # 默认英语
  python main.py --lang japanese    # 日语模式启动
"""

import argparse
import re
import sys
import threading

import config as cfg
from tutor.asr import create_asr_provider
from tutor.conversation import Conversation
from tutor.llm import create_llm_provider
from tutor.memory import MemoryManager
from tutor.tts import create_tts_provider
from tutor.utils import parse_response

from rich.console import Console
from rich.panel import Panel

console = Console()


def resolve_lang(lang_key: str):
    lang = lang_key.lower()
    if lang in cfg.LANGUAGE_CONFIGS:
        return lang, cfg.LANGUAGE_CONFIGS[lang]
    for key, val in cfg.LANGUAGE_CONFIGS.items():
        if key.startswith(lang) or lang.startswith(key):
            return key, val
    console.print(f"[red]未知语种: {lang_key}，可用: {', '.join(cfg.LANGUAGE_CONFIGS.keys())}[/red]")
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




def _display_ai(segments, name, lang_display, tts):
    """一次性显示所有段落 + 后台 TTS 播放。不阻塞输入。"""
    if not segments:
        return

    for content, chinese in segments:
        text = content
        if chinese:
            text += f"\n\n[dim][中文] {chinese}[/dim]"
        console.print(Panel(
            text,
            title=f"{name} [{lang_display}]",
            border_style="cyan",
            padding=(1, 2),
        ))

    full_text = _strip_emoji(" ".join(c for c, _ in segments))
    if full_text.strip():
        tts.cancel()
        threading.Thread(target=tts.speak, args=(full_text,), daemon=True).start()
        console.print("[dim]   speaking...[/dim]")


def main():
    # ── 命令行参数 ──
    parser = argparse.ArgumentParser(description="AI 语言助教")
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
    memory.on_session_start()
    conv = Conversation(
        llm,
        system_prompt=current_lang["prompt"],
        max_rounds=cfg.MAX_HISTORY_ROUNDS,
    )
    memory_ctx = memory.get_context()
    if memory_ctx:
        conv.history.append({"role": "system", "content": memory_ctx})

    # ── Banner ──
    console.print("=" * 52)
    console.print(f"  {name} - AI 语言助教")
    console.print("=" * 52)
    console.print(f"  [cyan]语种: {current_lang['display']}[/cyan]  |  TTS: {cfg.TTS_ENGINE}  |  LLM: {cfg.LLM_ENGINE}")
    console.print("-" * 52)
    console.print("  输入对话，Alice 会语音回复 + 中文翻译")
    console.print('  切换语种: "说日语" / "speak French" / "switch to spanish" 等')
    console.print("  bye / exit 退出  |  clear 清空历史")
    console.print("=" * 52)

    # ── 动态开场白（AI 生成，每次不同）──
    console.print("─" * 52)
    conv.history.append({
        "role": "system",
        "content": "Greet the user warmly but concisely — 1-2 sentences, friendly tone, "
                   "under 25 words total. Show warmth but keep it brief. "
                   "Be creative each time. Follow the normal reply format (with full Chinese translation)."
    })
    with console.status("[cyan]Alice thinking...", spinner="dots"):
        welcome_reply = llm.chat(conv.history, temperature=cfg.TEMPERATURE, max_tokens=600)
    conv.history.pop()
    welcome_reply = memory.process_reply(welcome_reply)
    segments = parse_response(welcome_reply)
    _display_ai(segments, name, current_lang['display'], tts)

    # ── 主循环 ──
    while True:
        try:
            console.print("─" * 52)  # 输入区上框
            user_input = asr.listen()
            console.print("─" * 52)  # 输入区下框
            if not user_input:
                continue

            # 正常对话发言加框显示（bye/clear 等命令不处理）
            is_chat = user_input.lower() not in ("bye", "exit", "quit", "goodbye", "再见", "clear")
            if is_chat:
                console.print(Panel(
                    user_input,
                    title="You",
                    border_style="yellow",
                    padding=(1, 2),
                ))

            # 退出
            if user_input.lower() in ("bye", "exit", "quit", "goodbye", "再见"):
                farewell_text = "Great talking with you! Keep practicing, see you next time!"
                console.print(Panel(
                    farewell_text,
                    title=f"{name} [{current_lang['display']}]",
                    border_style="cyan",
                    padding=(1, 2),
                ))
                tts.speak(_strip_emoji(farewell_text))
                console.print("[green]Bye![/green]")
                break

            # 清空历史
            if user_input.lower() == "clear":
                conv.clear()
                console.print("[green]对话历史已清空[/green]")
                continue

            # ── AI 生成回复 ──
            console.print("─" * 52)  # 分隔线
            with console.status("[cyan]Alice thinking...", spinner="dots"):
                reply = conv.ask(
                    user_input,
                    temperature=cfg.TEMPERATURE,
                    max_tokens=cfg.MAX_TOKENS,
                )
                reply = memory.process_reply(reply)

            # ── 检测语言切换请求（LANG_SWITCH:xxx 前缀）──
            if reply.startswith("LANG_SWITCH:"):
                lines = reply.split("\n", 1)
                target_key = lines[0].replace("LANG_SWITCH:", "").strip()

                if target_key in cfg.LANGUAGE_CONFIGS and target_key != current_lang_key:
                    # 显示 AI 的确认问题（LANG_SWITCH: 之后的内容）
                    if len(lines) > 1 and lines[1].strip():
                        q_text = lines[1].strip()
                        console.print(Panel(
                            q_text,
                            title=f"{name} [{current_lang['display']}]",
                            border_style="cyan",
                            padding=(1, 2),
                        ))
                        # TTS 只读外语部分，不读中文翻译
                        q_segments = parse_response(q_text)
                        q_tts = " ".join(c for c, _ in q_segments)
                        if q_tts.strip():
                            tts.speak(_strip_emoji(q_tts))

                    # 等用户回复
                    console.print("─" * 52)  # 输入区上框
                    user_confirm = asr.listen()
                    console.print("─" * 52)  # 输入区下框
                    if not user_confirm:
                        continue

                    with console.status("[cyan]Alice thinking...", spinner="dots"):
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
                            switch_segments = parse_response(rest)
                            if switch_segments:
                                console.print(f"\n[green]切换 -> {new_lang['display']}[/green]")
                                _display_ai(switch_segments, name, new_lang['display'], tts)
                            continue

                    # AI 未确认切换
                    decline_segments = parse_response(confirm_reply)
                    if decline_segments:
                        _display_ai(decline_segments, name, current_lang['display'], tts)
                    # 清除对话历史中的 LANG_SWITCH 痕迹，保持语种一致
                    conv.history = [m for m in conv.history
                                    if not m["content"].startswith("LANG_SWITCH:")]
                    conv.history.append({
                        "role": "system",
                        "content": "[Language switch declined. Continue in current language.]"
                    })
                continue

            # ── 正常回复解析（非 LANG_SWITCH）──
            segments = parse_response(reply)
            if not segments:
                continue

            _display_ai(segments, name, current_lang['display'], tts)

            if _script_mismatch(segments[0][0], current_lang_key):
                console.print("[yellow]提示: AI 似乎用了其他语言回复，可以说 \"switch to japanese\" 切换语种[/yellow]")

        except KeyboardInterrupt:
            console.print("\n[green]Bye![/green]")
            break
        except Exception as e:
            console.print(f"\n[red]错误: {e}[/red]")
            console.print("  请重试或输入 'bye' 退出")


if __name__ == "__main__":
    main()
