"""
聊天流程编排器 — 协调各模块，生成 NDJSON 事件流
==================================================

ChatFlow 是核心编排器，不包含业务逻辑，只负责协调各模块。
每个模块只做一件事，互不影响。
"""

import json
import threading
import uuid
from typing import Generator

import config as cfg
from tutor import lang_switcher
from tutor.format_checker import build_reminder, check_all
from tutor.search_broker import SearchBroker
from tutor.utils import parse_response, split_segments


class ChatFlow:
    """聊天流程编排器。"""

    def __init__(self, llm, tts, conv, memory, audio_cache, search_provider=None):
        self.llm = llm
        self.tts = tts
        self.conv = conv
        self.memory = memory
        self.audio_cache = audio_cache

        # 搜索（可能为 None）
        self.search_broker = None
        if search_provider:
            self.search_broker = SearchBroker(
                llm=llm,
                search_provider=search_provider,
                char_name=cfg.CHARACTER_NAME,
                lang_display="English",
            )
        self.search_engine = cfg.DEFAULT_SEARCH_ENGINE
        self._search_cap_injected = False
        self._inject_search_capability()

        # 语种运行时状态
        self.lang_key = "english"
        self.lang_config = cfg.LANGUAGE_CONFIGS["english"]

        # 欢迎词缓存
        self._welcome_data = None
        self._welcome_lock = threading.Lock()

    def set_search_engine(self, engine: str):
        """运行时切换搜索引擎。"""
        self.search_engine = engine
        if engine == "searxng" and not self._search_cap_injected:
            self._inject_search_capability()

    def _inject_search_capability(self):
        """向系统提示注入搜索能力说明，让 LLM 知道它会收到搜索结果。"""
        if not self.search_broker:
            return
        if self._search_cap_injected:
            return
        self.conv.history.insert(1, {
            "role": "system",
            "content": cfg.SEARCH_CAPABILITY_PROMPT,
        })
        self._search_cap_injected = True

    def set_language(self, key: str, config: dict):
        """运行时切换语种。"""
        self.lang_key = key
        self.lang_config = config
        if self.search_broker:
            self.search_broker.lang_display = config.get("display", "English")

    # ── 流程 ──────────────────────────────────────

    def process(self, user_text: str) -> Generator[str, None, None]:
        """处理一条用户消息，产生 NDJSON 事件字符串序列。"""
        # ── 0. 系统命令 ──
        cmd = user_text.lower()
        if cmd in ("clear",):
            self.conv.clear()
            yield self._event("cleared")
            yield self._event("done")
            return

        if cmd in ("bye", "exit", "quit", "goodbye", "再见"):
            yield self._event("status", status="goodbye")
            yield self._event("done")
            return

        # ── 1. 思考中 ──
        yield self._event("status", status="thinking")

        # ── 2. 搜索决策 ──
        search_context = None
        if self.search_engine == "searxng" and self.search_broker:
            should_search, query = self.search_broker.decide(
                user_text, self.conv.history,
            )
            if should_search:
                yield self._event("status", status="searching", query=query)
                context, count = self.search_broker.search(query)
                if context:
                    search_context = context
                    yield self._event("status", status="search_results",
                                      count=count, query=query)
                    self.conv.history.append({
                        "role": "system", "content": search_context,
                    })
                else:
                    yield self._event("status", status="thinking")

        # ── 3. 调用 LLM ──
        try:
            reply = self.conv.ask(
                user_text + build_reminder(),
                temperature=cfg.TEMPERATURE,
                max_tokens=cfg.MAX_TOKENS,
            )
        except Exception as e:
            self._rollback_search(search_context)
            yield self._event("error", message=str(e))
            yield self._event("done")
            return

        reply = self.memory.process_reply(reply)

        # ── 4. LANG_SWITCH 协议 ──
        if reply.startswith("LANG_SWITCH:"):
            yield from self._handle_switch(reply)
            return

        # ── 5. 错误 ──
        if reply.startswith("ERROR:"):
            yield self._event("error", message=reply[6:])
            yield self._event("done")
            return

        # ── 6. 正常回复 ──
        yield from self._emit_reply(reply)

    # ── 内部方法 ──────────────────────────────────

    def _handle_switch(self, reply: str) -> Generator[str, None, None]:
        """处理 LANG_SWITCH 协议。"""
        parsed = lang_switcher.parse_switch_header(reply, current_key=self.lang_key)

        if not parsed["is_valid"]:
            yield self._event("done")
            return

        is_confirmed = parsed["is_confirmed"]
        target_key = parsed["target_key"]
        rest = parsed["rest"]

        if not is_confirmed:
            segments = lang_switcher.build_confirm_segments(target_key, self.lang_config)
            for i, (content, translation) in enumerate(segments):
                yield self._event("segment", index=i, content=content, translation=translation)
                yield from self._gen_audio(content, i)
            yield self._event("done")
            return

        # 确认切换
        state = lang_switcher.execute_switch(target_key, self.tts, self.conv)
        self.lang_key = state["lang_key"]
        self.lang_config = state["lang_config"]

        yield self._event("lang_switch", lang_key=target_key, display=state["display"])

        segments = lang_switcher.build_switch_segments(rest)
        for i, (content, translation) in enumerate(segments):
            yield self._event("segment", index=i, content=content, translation=translation)
            yield from self._gen_audio(content, i)

        for warning in check_all(segments, self.lang_key):
            yield self._event("warning", message=warning)

        yield self._event("done")

    def _emit_reply(self, reply: str) -> Generator[str, None, None]:
        """解析回复并产生段事件。"""
        segments = split_segments(parse_response(reply))
        if not segments:
            yield self._event("done")
            return

        for i, (content, translation) in enumerate(segments):
            yield self._event("segment", index=i, content=content, translation=translation)
            yield from self._gen_audio(content, i)

        for warning in check_all(segments, self.lang_key):
            yield self._event("warning", message=warning)

        yield self._event("done")

    def _gen_audio(self, text: str, index: int) -> Generator[str, None, None]:
        """生成音频并产生 audio 事件。"""
        if not self.tts:
            return
        try:
            wav = self.tts._generate_wav_bytes(text)
            uid = str(uuid.uuid4())
            self.audio_cache.put(uid, wav)
            yield self._event("audio", index=index, url=f"/api/audio/{uid}")
        except Exception:
            yield self._event("audio", index=index, url=None)

    def _rollback_search(self, search_context: str | None):
        """LLM 出错时回滚搜索注入。"""
        if search_context and self.conv.history:
            last = self.conv.history[-1]
            if last.get("role") == "system" and last.get("content") == search_context:
                self.conv.history.pop()

    def generate_welcome(self) -> dict:
        """生成欢迎词（缓存，仅首次调用时真正生成）。"""
        if self._welcome_data is not None:
            return self._welcome_data

        with self._welcome_lock:
            if self._welcome_data is not None:
                return self._welcome_data

            self.conv.history.append({
                "role": "system",
                "content": (
                    "Greet the user warmly but concisely — 1-2 sentences, friendly tone, "
                    "under 25 words total. Show warmth but keep it brief. "
                    "Be creative each time. Follow the normal reply format."
                ),
            })
            try:
                reply = self.llm.chat(self.conv.history,
                                      temperature=cfg.TEMPERATURE, max_tokens=600)
            except Exception:
                reply = ("Hi there! Ready to practice today?\n"
                         "---\n嗨！准备好今天的练习了吗？")
            self.conv.history.pop()
            reply = self.memory.process_reply(reply)
            segments = split_segments(parse_response(reply))

            result_segments = []
            audio_infos = []
            for idx, (content, translation) in enumerate(segments):
                result_segments.append({
                    "content": content, "translation": translation,
                })
                uid = None
                if self.tts:
                    try:
                        wav = self.tts._generate_wav_bytes(content)
                        uid = str(uuid.uuid4())
                        self.audio_cache.put(uid, wav)
                    except Exception:
                        pass
                audio_infos.append({
                    "index": idx,
                    "url": f"/api/audio/{uid}" if uid else None,
                })

            self._welcome_data = {
                "segments": result_segments, "audio_urls": audio_infos,
            }
            return self._welcome_data

    @staticmethod
    def _event(event_type: str, **data) -> str:
        return json.dumps({"type": event_type, **data}, ensure_ascii=False) + "\n"
