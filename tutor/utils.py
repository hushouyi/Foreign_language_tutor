"""
工具函数
"""


def parse_response(reply: str):
    """解析 AI 回复，拆分为英文和中文翻译"""
    if "\n---" in reply:
        parts = reply.split("\n---", 1)
        return parts[0].strip(), parts[1].strip(" \n-").strip()
    return reply, None
