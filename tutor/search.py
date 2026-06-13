"""
搜索引擎 — 联网搜索抽象与实现
=============================

用法:
    # SEARXNG_API_URL 从 local_config.py 传入
    provider = create_search_provider({"SEARCH_ENGINE": "searxng", "SEARXNG_API_URL": SEARXNG_API_URL})
    results = provider.search("今天天气")
    # → [{"title": ..., "url": ..., "content": ...}, ...]
"""

import abc
import json
import logging
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)


class SearchProvider(abc.ABC):
    """联网搜索抽象基类"""

    @abc.abstractmethod
    def search(self, query: str, max_results: int = 5) -> list[dict]:
        """执行搜索，返回结果列表。

        每条结果包含:
            title (str):   标题
            url   (str):   链接
            content (str): 摘要/片段
        """
        ...


class SearXNGProvider(SearchProvider):
    """SearXNG 元搜索引擎（Docker 容器）"""

    def __init__(self, base_url: str, timeout: int = 10):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def search(self, query: str, max_results: int = 5) -> list[dict]:
        """通过 SearXNG JSON API 搜索，返回结构化结果。"""
        if not query.strip():
            return []

        encoded = urllib.parse.quote(query)
        url = f"{self.base_url}/search?q={encoded}&format=json&language=all"

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; AITutor/1.0)", "X-Forwarded-For": "127.0.0.1"},
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))

            raw_results = data.get("results", [])
            if not raw_results:
                logger.info("[search] 0 results for q=%s", query)
                return []

            results = []
            for r in raw_results[:max_results]:
                title = (r.get("title") or "").strip()
                content = (r.get("content") or "").strip()
                url_val = (r.get("url") or "").strip()
                if title or content:
                    results.append({
                        "title": title,
                        "url": url_val,
                        "content": content,
                    })

            logger.info("[search] %s → %d results", query, len(results))
            return results

        except urllib.error.URLError as e:
            logger.warning("[search] SearXNG 连接失败: %s", e)
            return []
        except json.JSONDecodeError as e:
            logger.warning("[search] SearXNG 返回非 JSON: %s", e)
            return []
        except Exception as e:
            logger.warning("[search] 搜索异常: %s", e)
            return []


def create_search_provider(config: dict) -> SearchProvider | None:
    """工厂函数，根据配置创建搜索 provider。

    配置项:
        SEARCH_ENGINE: "searxng" | "disabled"
        SEARXNG_API_URL: SearXNG 服务地址（search engine=searxng 时必须提供）
    """
    engine = config.get("SEARCH_ENGINE", "disabled")
    if engine == "searxng":
        base_url = config.get("SEARXNG_API_URL")
        if not base_url:
            raise ValueError("SEARXNG_API_URL 必须提供")
        return SearXNGProvider(base_url=base_url)
    return None
