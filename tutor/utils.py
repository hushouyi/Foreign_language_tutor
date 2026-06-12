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
    text = reply.strip()

    # 预处理：移除 --- 周围多余的空行，兼容 AI 格式偏差
    text = re.sub(r'\n\s*\n---', '\n---', text)
    text = re.sub(r'---\s*\n\s*\n', '---\n', text)
    # 归一化行内 --- 分隔符（AI 有时把 "\n---\n" 写成 " --- "）
    text = re.sub(r' --- ', '\n---\n', text)

    # Pass 1: 标准格式 —— 段间有空行，每段内容 + --- + 翻译
    segments = _parse_standard(text)
    if segments:
        return segments

    # Pass 2: 容错 —— AI 把所有外文放一块再用 --- 分隔中英
    if "\n---" in text:
        parts = text.split("\n---", 1)
        content = parts[0].strip()
        chinese = parts[1].strip(" \n-").strip()
        if content:
            segments.append((content, chinese or None))
            return segments

    # Pass 3: 纯外文无翻译
    if not _is_pure_chinese(text) and text:
        segments.append((text, None))

    return segments


def _parse_standard(text: str):
    """标准解析：段间用空行分隔"""
    segments = []
    for block in text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        if "\n---" in block:
            # 一次性切分所有 ---，然后两两配对 (content, translation)
            parts = block.split("\n---")
            for i in range(0, len(parts), 2):
                content = parts[i].strip()
                if not content:
                    continue
                if i + 1 < len(parts):
                    translation = parts[i+1].strip(" \n-").strip()
                    segments.append((content, translation or None))
                else:
                    segments.append((content, None))
        else:
            stripped = block.strip("- \n")
            if _is_pure_chinese(stripped) or not stripped:
                continue
            segments.append((block, None))
    return segments


def split_segments(segments):
    """AI 只返回一段且长度 >80 时按句子拆分，确保渐进效果"""
    if not segments:
        return []
    if len(segments) >= 2:
        return segments  # 已有足够分段
    content, chinese = segments[0]
    if len(content) <= 80:
        return segments
    parts = re.split(r'(?<=[.!?])\s+', content)
    if len(parts) < 2:
        parts = re.split(r'(?<=[。！？])\s*', content)
    if len(parts) >= 2:
        mid = len(parts) // 2
        return [(" ".join(parts[:mid]), chinese),
                (" ".join(parts[mid:]), None)]
    return segments
