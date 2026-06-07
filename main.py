"""
AI 语言助教 - 主程序
====================
用法:
  python main.py                    # 默认英语
  python main.py --lang japanese    # 日语模式启动
"""

import argparse
import queue
import re
import sys
import threading
import time

import config as cfg
from tutor.asr import create_asr_provider
from tutor.conversation import Conversation
from tutor.llm import create_llm_provider
from tutor.memory import MemoryManager
from tutor.tts import create_tts_provider
from tutor.utils import parse_response, split_segments

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.rule import Rule

console = Console()


class InputEngine:
    """后台线程阻塞读键，主循环无感知"""

    def __init__(self):
        self.buffer = ""
        self.cursor = 0
        self.submitted = queue.Queue()
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        try:
            import msvcrt
            while self._running:
                ch = msvcrt.getwch()
                if not self._running:
                    break
                if ch == '\r':
                    text = self.buffer.strip()
                    if text:
                        self.submitted.put(text)
                    self.buffer = ""
                    self.cursor = 0
                elif ch in ('\x7f', '\b'):
                    if self.cursor > 0:
                        self.buffer = (self.buffer[:self.cursor - 1] +
                                       self.buffer[self.cursor:])
                        self.cursor -= 1
                elif ch in ('\x00', '\xe0'):
                    second = msvcrt.getwch()
                    if second in ('K', '[D', 'OD'):
                        self.cursor = max(0, self.cursor - 1)
                    elif second in ('M', '[C', 'OC'):
                        self.cursor = min(len(self.buffer), self.cursor + 1)
                    elif second in ('G', '[H', 'OH'):
                        self.cursor = 0
                    elif second in ('O', '[F', 'OF'):
                        self.cursor = len(self.buffer)
                    elif second in ('S', '[3~'):
                        if self.cursor < len(self.buffer):
                            self.buffer = (self.buffer[:self.cursor] +
                                           self.buffer[self.cursor + 1:])
                elif ch == '\x03':
                    self.submitted.put("__CTRL_C__")
                elif ch.isprintable():
                    self.buffer = (self.buffer[:self.cursor] + ch +
                                   self.buffer[self.cursor:])
                    self.cursor += 1
        except ImportError:
            import sys
            while self._running:
                line = sys.stdin.readline()
                if not self._running:
                    break
                text = line.strip()
                if text:
                    self.submitted.put(text)

    def stop(self):
        self._running = False


# ── 工具函数 ────────────────────────────────────────

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
    return re.sub(r'[\U0001F300-\U0001FAFF\U0001F600-\U0001F64F\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF☀-⛿✀-➿⌀-⏿︀-️]', '', text)


def _script_mismatch(text: str, lang_key: str) -> bool:
    has_cjk = bool(re.search(r'[぀-ゟ゠-ヿ一-鿿]', text))
    if lang_key == "english" and has_cjk:
        return True
    if lang_key in ("japanese",) and not has_cjk:
        return True
    return False


def _build_ai_panels(segments, name, lang_display):
    panels = []
    for content, chinese in segments:
        text = content
        if chinese:
            text += f"\n\n[dim]{chinese}[/dim]"
        panels.append(Panel(
            text,
            title=f"{name} [{lang_display}]",
            border_style="cyan",
            padding=(1, 2),
        ))
    return panels


def _build_input_panel(buffer: str, cursor: int):
    display = buffer[:cursor] + "|" + buffer[cursor:]
    return Panel(
        f"You: {display}",
        border_style="dim",
        padding=(0, 2),
    )


# ── 主流程 ──────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="AI 语言助教")
    parser.add_argument("--lang", default=cfg.LANGUAGE,
                        help=f"语种: {', '.join(cfg.LANGUAGE_CONFIGS.keys())} (默认: {cfg.LANGUAGE})")
    args = parser.parse_args()

    current_lang_key, current_lang = resolve_lang(args.lang)
    name = cfg.CHARACTER_NAME

    config = {
        "TTS_ENGINE": cfg.TTS_ENGINE, "PYTTX3_RATE": 160,
        "PYTTX3_VOLUME": 0.9, "ASR_ENGINE": cfg.ASR_ENGINE,
        "LLM_ENGINE": cfg.LLM_ENGINE, "DEEPSEEK_API_KEY": cfg.DEEPSEEK_API_KEY,
        "DEEPSEEK_API_URL": cfg.DEEPSEEK_API_URL,
        "DEEPSEEK_MODEL": cfg.DEEPSEEK_MODEL, "lang": current_lang,
        "API_TIMEOUT": cfg.API_TIMEOUT,
    }

    tts = create_tts_provider(config)
    asr = create_asr_provider(config)
    llm = create_llm_provider(config)
    memory = MemoryManager()
    memory.on_session_start()
    conv = Conversation(llm, system_prompt=current_lang["prompt"],
                        max_rounds=cfg.MAX_HISTORY_ROUNDS)
    memory_ctx = memory.get_context()
    if memory_ctx:
        conv.history.append({"role": "system", "content": memory_ctx})

    # ── 横幅（仅打印一次，在 Live 上方）──
    console.print(f"[bold]{name} - AI 语言助教 [{current_lang['display']}][/bold]")
    console.print("[dim]输入对话，Alice 会语音回复 + 中文翻译[/dim]")
    console.print("[dim]切换 / 退出 / 清空: switch to japanese / bye / clear[/dim]")

    # ── 获取欢迎词 ──
    conv.history.append({
        "role": "system",
        "content": "Greet the user warmly but concisely — 1-2 sentences, friendly tone, "
                   "under 25 words total. Show warmth but keep it brief. "
                   "Be creative each time. Follow the normal reply format (with full Chinese translation)."
    })
    welcome_reply = llm.chat(conv.history, temperature=cfg.TEMPERATURE, max_tokens=600)
    conv.history.pop()
    welcome_reply = memory.process_reply(welcome_reply)
    welcome_segments = split_segments(parse_response(welcome_reply))

    # ── 状态 ──
    display_items = []  # Rich renderables

    pending_api = False
    api_response = None
    api_lock = threading.Lock()
    pending_question = None  # 用户在等待时发的新消息（覆盖旧请求）
    speaking = False         # AI 正在朗读中

    # 渐进式显示
    progressive_segments = None   # 当前正在逐段显示的段落
    progressive_events = []       # 每段一个 Event，TTS 线程播前设置
    progressive_name = name
    progressive_lang = current_lang['display']

    # 欢迎词用渐进显示
    if welcome_segments:
        speaking = True
        progressive_segments = welcome_segments
        progressive_events = [threading.Event() for _ in welcome_segments]
        progressive_events[0].set()
        progressive_name = name
        progressive_lang = current_lang['display']
        def _on_before_welcome(idx):
            if idx < len(progressive_events):
                progressive_events[idx].set()
        threading.Thread(
            target=tts.speak_segments,
            args=(welcome_segments, _on_before_welcome),
            daemon=True
        ).start()

    input_eng = InputEngine()
    running = True

    def _api_call(user_text):
        nonlocal pending_api, api_response, pending_question
        try:
            reminder = ("\n\nIMPORTANT FORMAT: Split your reply into segments. "
                        "Each segment = text + newline + '---' + newline + Chinese translation. "
                        "EVERY segment MUST have Chinese translation!")
            reply = conv.ask(user_text + reminder, temperature=cfg.TEMPERATURE,
                             max_tokens=cfg.MAX_TOKENS)
            reply = memory.process_reply(reply)
        except Exception as e:
            reply = f"ERROR:{e}"

        with api_lock:
            if pending_question:
                # 用户有新问题，丢弃当前回复，用新问题重启
                new_text = pending_question
                pending_question = None
                threading.Thread(target=_api_call, args=(new_text,), daemon=True).start()
            else:
                api_response = reply
                pending_api = False

    # ── Live ──
    try:
        with Live(console=console, refresh_per_second=30, screen=False) as live:
            while running:
                # 1) 检查提交
                try:
                    user_text = input_eng.submitted.get_nowait()
                except queue.Empty:
                    user_text = None

                if user_text == "__CTRL_C__":
                    break

                if user_text:
                    if user_text.lower() in ("bye", "exit", "quit", "goodbye", "再见"):
                        tts.speak("Great talking with you! Keep practicing, see you next time!")
                        display_items.append(Panel(
                            "Great talking with you! Keep practicing, see you next time!",
                            title=f"{name} [{current_lang['display']}]",
                            border_style="cyan", padding=(1, 2),
                        ))
                        live.update(Group(*display_items, _build_input_panel("", 0)))
                        time.sleep(1.5)
                        break

                    if user_text.lower() == "clear":
                        conv.clear()
                        display_items.clear()
                        progressive_segments = None
                        continue

                    display_items.append(Panel(
                        user_text, title="You",
                        border_style="yellow", padding=(1, 2),
                    ))

                    tts.cancel()  # 取消之前的 TTS，防止重叠
                    speaking = False  # 关闭旧的 speaking 状态

                    with api_lock:
                        if pending_api:
                            # AI 正忙，存为待处理（覆盖旧待处理）
                            pending_question = user_text
                        else:
                            pending_api = True
                            api_response = None
                            threading.Thread(target=_api_call, args=(user_text,), daemon=True).start()

                # 3) 检查 API 返回
                with api_lock:
                    if api_response is not None:
                        reply = api_response
                        api_response = None

                        if reply.startswith("LANG_SWITCH:"):
                            lines = reply.split("\n", 1)
                            header = lines[0].replace("LANG_SWITCH:", "").strip()
                            is_confirmed = header.startswith("confirmed:")
                            target_key = header[10:].strip() if is_confirmed else header

                            if target_key not in cfg.LANGUAGE_CONFIGS or target_key == current_lang_key:
                                conv.history = [m for m in conv.history
                                                if not m["content"].startswith("LANG_SWITCH:")]
                                continue

                            rest = lines[1] if len(lines) > 1 else ""

                            if not is_confirmed:
                                # 用固定话术，不用 AI 生成的内容
                                target_name = current_lang.get("names", {}).get(target_key, target_key)
                                confirm_text = current_lang["confirm_switch"].format(lang=target_name)
                                confirm_cn = current_lang.get("confirm_switch_cn", "").format(
                                    lang=cfg.LANG_NAMES_CN.get(target_key, target_key))
                                segments = split_segments(parse_response(
                                    confirm_text + "\n---\n" + confirm_cn))
                                if segments:
                                    speaking = True
                                    progressive_segments = segments
                                    progressive_events = [threading.Event() for _ in segments]
                                    progressive_events[0].set()
                                    progressive_name = name
                                    progressive_lang = current_lang['display']
                                    def _on_before(idx):
                                        if idx < len(progressive_events):
                                            progressive_events[idx].set()
                                    threading.Thread(
                                        target=tts.speak_segments,
                                        args=(segments, _on_before),
                                        daemon=True
                                    ).start()
                                continue

                            # confirmed: 执行切换 + 渐进显示
                            new_lang = cfg.LANGUAGE_CONFIGS[target_key]
                            current_lang_key = target_key
                            current_lang = new_lang
                            config["lang"] = new_lang
                            if hasattr(tts, "set_voice"):
                                tts.set_voice(new_lang["voice"])
                            conv.set_system_prompt(new_lang["prompt"])
                            if rest.strip():
                                switch_seg = split_segments(parse_response(rest))
                                if switch_seg:
                                    speaking = True
                                    progressive_segments = switch_seg
                                    progressive_events = [threading.Event() for _ in switch_seg]
                                    progressive_events[0].set()
                                    progressive_name = name
                                    progressive_lang = new_lang['display']
                                    def _on_before_sw(idx):
                                        if idx < len(progressive_events):
                                            progressive_events[idx].set()
                                    threading.Thread(
                                        target=tts.speak_segments,
                                        args=(switch_seg, _on_before_sw),
                                        daemon=True
                                    ).start()
                                    has_any_cn = any(cn for _, cn in switch_seg)
                                    if not has_any_cn:
                                        display_items.append(
                                            Panel("[yellow]提示: AI 回复缺少中文翻译，已自动调整[/yellow]",
                                                  border_style="dim", padding=(0, 1)))
                            continue

                        if reply.startswith("ERROR:"):
                            display_items.append(Panel(
                                f"[red]错误: {reply[6:]}[/red]",
                                border_style="red", padding=(0, 1),
                            ))
                            continue

                        segments = split_segments(parse_response(reply))
                        if not segments:
                            continue
                        speaking = True
                        progressive_segments = segments
                        progressive_events = [threading.Event() for _ in segments]
                        progressive_events[0].set()  # 第一段立即显示
                        progressive_name = name
                        progressive_lang = current_lang['display']
                        # 逐段播放：播前设置对应 Event
                        def _on_before(idx):
                            if idx < len(progressive_events):
                                progressive_events[idx].set()
                        threading.Thread(
                            target=tts.speak_segments,
                            args=(segments, _on_before),
                            daemon=True
                        ).start()
                        if _script_mismatch(segments[0][0], current_lang_key):
                            display_items.append(
                                Panel("[yellow]提示: AI 用了其他语言回复[/yellow]",
                                      border_style="dim", padding=(0, 1)))
                        has_any_cn = any(cn for _, cn in segments)
                        if not has_any_cn:
                            display_items.append(
                                Panel("[yellow]提示: AI 回复缺少中文翻译，已自动调整[/yellow]",
                                      border_style="dim", padding=(0, 1)))

                # 4) 处理渐进式显示（Event 驱动）
                if progressive_segments is not None:
                    reveal = sum(1 for e in progressive_events if e.is_set())
                    progressive_items = []
                    if reveal > 0:
                        for i in range(reveal):
                            content, chinese = progressive_segments[i]
                            text = content
                            if chinese:
                                text += f"\n\n[dim]{chinese}[/dim]"
                            progressive_items.append(Panel(
                                text,
                                title=f"{progressive_name} [{progressive_lang}]",
                                border_style="cyan",
                                padding=(1, 2),
                            ))
                    # 全部揭示完 → 转成永久内容
                    if reveal >= len(progressive_segments):
                        display_items.extend(_build_ai_panels(
                            progressive_segments, progressive_name, progressive_lang))
                        progressive_segments = None
                        speaking = False

                # 5) 构建完整渲染
                # 限制显示面板数量，确保输入框始终可见
                MAX_ITEMS = 10
                items = list(display_items[-MAX_ITEMS:]) if len(display_items) > MAX_ITEMS else list(display_items)
                if progressive_segments is not None:
                    items.extend(progressive_items)
                buffer, cursor = input_eng.buffer, input_eng.cursor
                # 状态栏（在输入框上方）
                if pending_api:
                    items.append(Panel("Alice thinking...",
                                      border_style="dim", padding=(0, 1)))
                elif speaking and progressive_segments is not None and progressive_events:
                    r = sum(1 for e in progressive_events if e.is_set())
                    t = len(progressive_segments)
                    items.append(Panel(f"Alice speaking... [{r}/{t}]",
                                      border_style="dim", padding=(0, 1)))
                items.append(_build_input_panel(buffer, cursor))

                live.update(Group(*items))
                time.sleep(0.03)
    except KeyboardInterrupt:
        pass

    console.print("[green]Bye![/green]")
    tts.cancel()


if __name__ == "__main__":
    main()
