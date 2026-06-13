"""
搜索决策与执行 — SearchBroker
==============================

让 AI 自己判断是否需要搜索，像 Claude 一样理解语义。

用法:
    broker = SearchBroker(llm, search_provider, "Alice", "English")
    should_search, query = broker.decide(user_text, conv_history)
    if should_search:
        context = broker.search(query)
        if context:
            conv.history.append({"role": "system", "content": context})
"""

import config as cfg


class SearchBroker:
    """搜索决策与执行。"""

    def __init__(self, llm, search_provider, char_name: str, lang_display: str):
        self.llm = llm
        self.provider = search_provider
        self.char_name = char_name
        self.lang_display = lang_display

    def decide(self, user_text: str, recent_history: list[dict]) -> tuple[bool, str]:
        """判断是否需要搜索。

        返回:
            (True, query)  — 需要搜索，query 是提取的搜索关键词
            (False, _)     — 不需要搜索
        """
        decision_prompt = cfg.SEARCH_DECISION_PROMPT.format(
            name=self.char_name,
            lang=self.lang_display,
        )
        messages = [{"role": "system", "content": decision_prompt}]
        # 只传最近 user 消息做上下文（避免 assistant 回复的格式规则干扰）
        recent_users = [m for m in recent_history[-3:] if m.get("role") == "user"][-1:]
        messages.extend(recent_users)
        messages.append({"role": "user", "content": user_text})

        try:
            decision = self.llm.chat(messages, max_tokens=50, temperature=0.1)
            decision = (decision or "").strip()
            if decision.startswith("SEARCH_NEEDED:"):
                query = decision[len("SEARCH_NEEDED:"):].strip() or user_text
                return True, query
            return False, decision
        except Exception as e:
            print(f"[search] 决策错误: {e}")
            return False, ""

    def search(self, query: str) -> tuple[str | None, int]:
        """执行搜索。

        返回:
            (formatted_context, result_count)
            context 为 None 表示无结果或失败。
        """
        if not self.provider:
            return None, 0
        try:
            results = self.provider.search(query)
        except Exception as e:
            print(f"[search] 搜索异常: {e}")
            return None, 0

        if not results:
            return None, 0

        lines = [
            "【网络搜索结果 — 请优先使用以下信息回答用户】",
            "以下是刚刚从互联网搜索到的实时信息。",
            "请基于这些内容回答用户的问题，用自然的方式融入你的回复中。",
            "如果搜索结果不相关或不可靠，直接忽略即可，不用提及。\n",
        ]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r['title']}")
            lines.append(f"   {r['url']}")
            if r.get("content"):
                lines.append(f"   {r['content']}")
            lines.append("")

        return "\n".join(lines), len(results)
