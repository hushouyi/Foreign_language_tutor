"""
对话管理器 - 管理对话历史和调用 LLM
"""


class Conversation:
    def __init__(self, llm, system_prompt: str, max_rounds: int = 20):
        self.llm = llm
        self.max_rounds = max_rounds
        self.history = [{"role": "system", "content": system_prompt}]

    def ask(self, user_text: str, **kwargs) -> str:
        self.history.append({"role": "user", "content": user_text})
        reply = self.llm.chat(self.history, **kwargs)
        self.history.append({"role": "assistant", "content": reply})

        # 截断历史，防止超长
        limit = 1 + self.max_rounds * 2  # 1 system + N 轮对话
        if len(self.history) > limit:
            self.history[:] = [self.history[0]] + self.history[-self.max_rounds * 2:]

        return reply

    def clear(self):
        self.history[:] = [self.history[0]]
