"""
对话管理器 - 管理对话历史和调用 LLM
"""


class Conversation:
    def __init__(self, llm, system_prompt: str, max_rounds: int = 20):
        self.llm = llm
        self.max_rounds = max_rounds
        self.system_prompt = system_prompt
        self.history = [{"role": "system", "content": system_prompt}]

    def set_system_prompt(self, prompt: str):
        """运行时切换系统提示词（用于切换语种）"""
        self.system_prompt = prompt
        # 在历史中追加一条语言切换说明，保留之前的对话
        self.history.append({
            "role": "system",
            "content": f"[Language switch] From now on, use the new language rules below:\n{prompt}",
        })

    def ask(self, user_text: str, **kwargs) -> str:
        self.history.append({"role": "user", "content": user_text})
        reply = self.llm.chat(self.history, **kwargs)
        self.history.append({"role": "assistant", "content": reply})

        limit = 1 + self.max_rounds * 2
        if len(self.history) > limit:
            self.history[:] = [self.history[0]] + self.history[-self.max_rounds * 2:]

        return reply

    def clear(self):
        self.history[:] = [self.history[0]]
