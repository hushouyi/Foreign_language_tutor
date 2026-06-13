"""
语言切换协议处理 — LANG_SWITCH:
================================

处理 AI 回复中的 LANG_SWITCH: 协议。

协议格式:
    未确认: LANG_SWITCH:english
    已确认: LANG_SWITCH:confirmed:english
"""

import config as cfg
from tutor.utils import parse_response, split_segments


def parse_switch_header(reply: str, current_key: str = "") -> dict:
    """解析 LANG_SWITCH: 头部。

    参数:
        reply: AI 回复文本
        current_key: 当前语种 key，传入后会自动校验合法性

    返回:
        is_valid: bool  — 目标语种是否存在且不同于当前
        is_confirmed: bool
        target_key: str
        rest: str  — 头部后的内容
    """
    lines = reply.split("\n", 1)
    header = lines[0].replace("LANG_SWITCH:", "").strip()
    is_confirmed = header.startswith("confirmed:")
    target_key = header[10:].strip() if is_confirmed else header
    rest = lines[1] if len(lines) > 1 else ""
    is_valid = validate_switch(target_key, current_key) if current_key else False
    return {"is_valid": is_valid, "is_confirmed": is_confirmed,
            "target_key": target_key, "rest": rest}


def validate_switch(target_key: str, current_key: str) -> bool:
    """验证切换是否合法（目标语种存在且不同于当前）。"""
    return target_key in cfg.LANGUAGE_CONFIGS and target_key != current_key


def build_confirm_segments(target_key: str, current_lang: dict) -> list:
    """构造未确认时的确认询问回复。"""
    target_name = current_lang.get("names", {}).get(target_key, target_key)
    confirm_text = current_lang["confirm_switch"].format(lang=target_name)
    confirm_cn = current_lang.get("confirm_switch_cn", "").format(
        lang=cfg.LANG_NAMES_CN.get(target_key, target_key))
    return split_segments(parse_response(confirm_text + "\n---\n" + confirm_cn))


def execute_switch(target_key: str, tts, conv) -> dict:
    """执行语言切换。

    返回:
        lang_key: str
        lang_config: dict
        display: str
    """
    new_lang = cfg.LANGUAGE_CONFIGS[target_key]
    if hasattr(tts, "set_voice"):
        try:
            tts.set_voice(new_lang["voice"])
        except Exception:
            pass
    conv.set_system_prompt(new_lang["prompt"])
    return {"lang_key": target_key, "lang_config": new_lang,
            "display": new_lang["display"]}


def build_switch_segments(rest: str) -> list:
    """从切换确认后的回复内容构造段。"""
    if not rest.strip():
        return []
    return split_segments(parse_response(rest))
