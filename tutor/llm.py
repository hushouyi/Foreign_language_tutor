"""
LLM 引擎 - 大语言模型调用抽象与实现
"""

import abc
import json

import requests


class LLMProvider(abc.ABC):
    @abc.abstractmethod
    def chat(self, history: list) -> str:
        ...


class DeepSeekProvider(LLMProvider):
    def __init__(self, api_key: str, api_url: str, model: str, timeout: int = 30):
        self.api_key = api_key
        self.api_url = api_url
        self.model = model
        self.timeout = timeout

    def chat(self, history: list, temperature: float = 0.7, max_tokens: int = 300) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": history,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        resp = requests.post(self.api_url, headers=headers,
                             json=payload, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


def create_llm_provider(config: dict) -> LLMProvider:
    engine = config["LLM_ENGINE"]
    if engine == "deepseek":
        return DeepSeekProvider(
            api_key=config["DEEPSEEK_API_KEY"],
            api_url=config["DEEPSEEK_API_URL"],
            model=config["DEEPSEEK_MODEL"],
            timeout=config.get("API_TIMEOUT", 30),
        )
    else:
        raise ValueError(f"未知 LLM_ENGINE: {engine}")
