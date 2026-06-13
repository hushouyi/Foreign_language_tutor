"""
服务状态检测
===========
检测本地 Docker 容器中的服务是否在运行。
"""
import urllib.request
import json
import config as cfg


def _http_get(url: str, timeout: int = 3) -> dict | None:
    """尝试 GET 请求，成功返回响应 JSON，失败返回 None"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "X-Forwarded-For": "127.0.0.1"})
        resp = urllib.request.urlopen(req, timeout=timeout)
        ctype = resp.headers.get("Content-Type", "")
        body = resp.read().decode("utf-8", errors="replace")
        if "json" in ctype:
            return json.loads(body)
        return {"raw": body[:200]}
    except Exception:
        return None


def detect_ollama() -> dict:
    """检测 Ollama 服务状态，返回 {"status": "running"|"stopped", "models": [...]}"""
    data = _http_get(f"{cfg.OLLAMA_API_URL}/api/tags")
    if data is None:
        return {"status": "stopped", "models": []}
    models = [m.get("name", "?") for m in data.get("models", [])]
    return {"status": "running", "models": models}


def detect_searxng() -> dict:
    """检测 SearXNG 服务状态"""
    data = _http_get(f"{cfg.SEARXNG_API_URL}/search?q=health&format=json")
    if data is None:
        return {"status": "stopped"}
    return {"status": "running"}


def detect_all() -> dict:
    """检测所有本地服务，返回完整状态字典"""
    return {
        "ollama": detect_ollama(),
        "searxng": detect_searxng(),
    }
