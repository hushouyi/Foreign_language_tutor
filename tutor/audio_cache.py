"""
有上限的音频缓存 — 线程安全，FIFO 淘汰
========================================

用法:
    cache = AudioCache(max_size=200)
    cache.put(uuid, wav_bytes)
    data = cache.get(uuid)  # → bytes | None
"""

import threading
from collections import OrderedDict


class AudioCache:
    """线程安全的音频字节缓存，超过 max_size 时淘汰最旧条目。"""

    def __init__(self, max_size: int = 200):
        self.max_size = max_size
        self._cache: OrderedDict[str, bytes] = OrderedDict()
        self._lock = threading.Lock()

    def put(self, uid: str, data: bytes):
        """存入音频字节。如果缓存已满，淘汰最旧条目。"""
        with self._lock:
            self._cache[uid] = data
            while len(self._cache) > self.max_size:
                self._cache.popitem(last=False)

    def get(self, uid: str) -> bytes | None:
        """获取音频字节，不存在返回 None。"""
        with self._lock:
            return self._cache.get(uid)

    def clear(self):
        """清空缓存。"""
        with self._lock:
            self._cache.clear()

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._cache)
