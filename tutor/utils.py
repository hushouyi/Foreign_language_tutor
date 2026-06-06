"""
工具函数
"""

import re


# 纯中文检测：包含 CJK 字符但几乎没有拉丁字母
_CJK_PATTERN = re.compile(r'[一-鿿　-〿＀-￯]')
_LATIN_PATTERN = re.compile(r'[a-zA-Z0-9]')


def _is_pure_chinese(text: str) -> bool:
    """判断文本是否纯中文（含 CJK，无拉丁字母）"""
    return bool(_CJK_PATTERN.search(text)) and not _LATIN_PATTERN.search(text)


def parse_response(reply: str):
    """解析 AI 多段回复，返回 [(英文段, 中文翻译), ...]"""
    segments = []
    for block in reply.strip().split("\n\n"):
        block = block.strip()
        if not block:
            continue
        if "\n---" in block:
            parts = block.split("\n---", 1)
            content = parts[0].strip()
            chinese = parts[1].strip(" \n-").strip()
            if content:
                segments.append((content, chinese or None))
        else:
            # 跳过纯中文或纯分隔符的孤立段
            stripped = block.strip("- \n")
            if _is_pure_chinese(stripped) or not stripped:
                continue
            segments.append((block, None))
    return segments
