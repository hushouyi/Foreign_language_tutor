"""
记忆管理 - 跨会话持久化用户记忆
"""

import json
import os

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_MEMORY_FILE = os.path.join(_PROJECT_ROOT, "memory", "user_profile.json")


class MemoryManager:
    def __init__(self):
        self._memories: dict[str, str] = {}
        self._load()

    def _load(self):
        if os.path.exists(_MEMORY_FILE):
            try:
                with open(_MEMORY_FILE, "r", encoding="utf-8") as f:
                    self._memories = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._memories = {}

    def _save(self):
        os.makedirs(os.path.dirname(_MEMORY_FILE), exist_ok=True)
        with open(_MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(self._memories, f, ensure_ascii=False, indent=2)

    def get_context(self) -> str:
        """返回格式化记忆字串，注入到 system prompt。无记忆时返回空字串"""
        if not self._memories:
            return ""
        parts = [f"  {k}: {v}" for k, v in self._memories.items()]
        return (
            "[Your memory from past conversations]\n"
            + "\n".join(parts)
            + "\n[/Memory]"
        )

    def process_reply(self, reply: str) -> str:
        """提取并保存 MEMORY_SAVE: 指令，返回清除指令后的回复"""
        lines = reply.split("\n")
        clean = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("MEMORY_SAVE:"):
                content = stripped[len("MEMORY_SAVE:"):].strip()
                if "=" in content:
                    key, value = content.split("=", 1)
                    self._memories[key.strip()] = value.strip()
                    self._save()
            else:
                clean.append(line)
        return "\n".join(clean)

    def add(self, key: str, value: str):
        """手动添加/更新记忆"""
        self._memories[key.strip()] = value.strip()
        self._save()
