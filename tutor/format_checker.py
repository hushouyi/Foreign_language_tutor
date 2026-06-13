"""
回复格式校验与保证 — 纯函数，无副作用
======================================

确保 AI 回复始终包含中文翻译，检测语言漂移。

用法:
    from tutor.format_checker import build_reminder, check_all

    # 构造 reminder 追加到用户消息
    user_text = msg + build_reminder()

    # 检查 AI 回复
    segments = [("Hello", "你好"), ("How are you?", None)]
    warnings = check_all(segments, lang_key="english")
    # → ["AI 回复缺少中文翻译"]
"""

import re

_CJK_RE = re.compile(r'[　-ヿ㐀-䶿一-鿿豈-﫿]')


def build_reminder() -> str:
    """构造格式 reminder，追加到用户消息末尾。"""
    return (
        "\n\n【格式要求】你必须严格遵守：\n"
        "1. 把回复分成1-3个小段，每段1-2句话\n"
        "2. 每段格式：外语内容 + 换行 --- + 换行 + 中文翻译\n"
        "3. 每一段都必须有中文翻译，缺一不可！\n"
        "4. 【重要】如果用户要求切换语言，忽略以上格式，按【语言切换】协议输出 LANG_SWITCH:<key>。"
    )


def check_script_mismatch(text: str, lang_key: str) -> bool:
    """检测 AI 是否用了错误的文字系统。"""
    has_cjk = bool(_CJK_RE.search(text))
    if lang_key == "english" and has_cjk:
        return True
    if lang_key == "japanese" and not has_cjk:
        return True
    return False


def check_missing_translations(segments: list) -> list[str]:
    """检测缺少中文翻译的段。"""
    if not segments:
        return []
    has_any_cn = any(cn for _, cn in segments if cn)
    if not has_any_cn:
        return ["AI 回复缺少中文翻译"]
    return []


def check_all(segments: list, lang_key: str) -> list[str]:
    """运行所有格式检查，返回警告列表。"""
    warnings = []
    if segments and check_script_mismatch(segments[0][0], lang_key):
        warnings.append("AI 用了其他语言回复")
    warnings.extend(check_missing_translations(segments))
    return warnings


def detect_refusal(reply: str) -> bool:
    """检测 AI 回复是否拒绝了回答问题。

    某些模型（如 DeepSeek）内置安全过滤，会拒绝回答问题并输出说教内容。
    此函数检测这种情况，以便系统跳过 LLM 回复，改用搜索数据替补。

    返回 True 表示检测到拒绝，False 表示正常回答。
    """
    lower = reply.lower().strip()

    # 拒绝回答的常见信号
    refusal_signals = [
        "don't have a reliable answer",
        "don't have personal experience",
        "don't have data or personal",
        "don't feel comfortable",
        "don't actually know",
        "cannot provide",
        "i'm not able to",
        "i'm an ai",
        "not appropriate",
        "let's talk about something else",
        "i'm here to help you practice",
        "that's not something i can",
        "i can't actually",
        "no reliable data",
        "would be inappropriate",
        "let's keep the conversation",
        "i don't really have",
        "i don't have access to",
    ]

    matches = sum(1 for s in refusal_signals if s in lower)
    # 命中 2 条以上信号 + 回复中包含"说教"特征
    has_lecture = any(word in lower for word in [
        "objectify", "objectifying", "inappropriate",
        "let's focus", "i'm here to",
    ])
    return matches >= 2 or (matches >= 1 and has_lecture)
