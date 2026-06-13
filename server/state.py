"""
共享状态 — 服务器全局可变状态
=============================
所有模块通过 from .state import chat_flow 获取状态引用。
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tutor.chat_flow import ChatFlow
    from tutor.audio_cache import AudioCache
    from tutor.search import SearchProvider

# ── 全局可变状态 ──────────────────────────────
chat_flow: 'ChatFlow | None' = None
audio_cache: 'AudioCache | None' = None
current_llm_engine: str = "deepseek"
current_search_engine: str = "disabled"
current_silence_timeout: int = 3
search_provider: 'SearchProvider | None' = None


def set_state(**kwargs):
    """批量更新状态变量。"""
    for key, value in kwargs.items():
        if key in globals():
            globals()[key] = value


def init_audio_cache(max_size=200):
    """惰性初始化音频缓存。"""
    global audio_cache
    if audio_cache is None:
        from tutor.audio_cache import AudioCache
        audio_cache = AudioCache(max_size=max_size)
