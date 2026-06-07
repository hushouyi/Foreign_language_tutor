"""
记忆管理 - 跨会话持久化用户记忆
"""

import json
import os
from datetime import datetime

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

    def on_session_start(self):
        """每次启动时调用：记录首次日期、递增会话次数"""
        today = datetime.now().strftime("%Y-%m-%d")
        if "first_seen" not in self._memories:
            self._memories["first_seen"] = today
        session_count = int(self._memories.get("session_count", 0))
        self._memories["session_count"] = str(session_count + 1)
        self._save()

    def get_context(self) -> str:
        """返回格式化记忆 + 关系信息，注入到 system prompt"""
        parts = []
        # 用户记忆
        for k, v in self._memories.items():
            if k in ("first_seen", "session_count"):
                continue
            parts.append(f"  {k}: {v}")

        # 关系信息
        session_count = int(self._memories.get("session_count", 0))
        first_seen = self._memories.get("first_seen", "today")
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        hour = now.hour
        if hour < 6:
            time_desc = "深夜"
        elif hour < 12:
            time_desc = "上午"
        elif hour < 14:
            time_desc = "中午"
        elif hour < 18:
            time_desc = "下午"
        else:
            time_desc = "晚上"

        lines = [
            f"[Memory]  Today: {today} ({time_desc}). "
            f"You first met this user on: {first_seen}. "
            f"This is session #{session_count}. "
            f"Relationship: the more you chat, the closer and warmer you become.",
            "",
            "【格式提醒 - 每次回复必须遵守】",
            "你必须把回复分成小段，每段1-2句话。",
            "每段格式：外语内容（换行）---（换行）中文翻译",
            "段与段之间用空行隔开。",
            "每一段都必须有中文翻译！决不能只有外语没有中文。",
        ]
        if parts:
            lines.append("Facts you remember:")
            lines.extend(parts)
        return "\n".join(lines)

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
