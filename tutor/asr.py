"""
ASR 引擎 - 语音/输入识别抽象与实现（预留 MIC 扩展）
"""

import abc


class ASRProvider(abc.ABC):
    @abc.abstractmethod
    def listen(self) -> str:
        ...

    @property
    @abc.abstractmethod
    def name(self) -> str:
        ...


class KeyboardInputProvider(ASRProvider):
    def listen(self) -> str:
        return input("You: ").strip()

    @property
    def name(self) -> str:
        return "键盘输入"


def create_asr_provider(config: dict) -> ASRProvider:
    engine = config["ASR_ENGINE"]
    if engine == "keyboard":
        return KeyboardInputProvider()
    else:
        raise ValueError(f"未知 ASR_ENGINE: {engine}")
