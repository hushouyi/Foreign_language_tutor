"""
OpenClaw 英语陪练 - 主程序
=========================
用法: python main.py
"""

import config as cfg
from tutor.asr import create_asr_provider
from tutor.conversation import Conversation
from tutor.llm import create_llm_provider
from tutor.tts import create_tts_provider
from tutor.utils import parse_response


def print_banner():
    name = cfg.CHARACTER_NAME
    print("=" * 55)
    print(f"🎙️  {name} · AI 语音助手")
    print("=" * 55)
    print(f"  TTS: {cfg.TTS_ENGINE}  |  LLM: {cfg.LLM_ENGINE}  |  输入: {cfg.ASR_ENGINE}")
    print("-" * 55)
    print(f"  输入对话，{name} 会语音回复 + 中文翻译")
    print("  bye / exit 退出  |  clear 清空历史")
    print("=" * 55)


def main():
    print_banner()

    config = {
        "TTS_ENGINE": cfg.TTS_ENGINE,
        "EDGE_TTS_VOICE": cfg.EDGE_TTS_VOICE,
        "PYTTX3_RATE": cfg.PYTTX3_RATE,
        "PYTTX3_VOLUME": cfg.PYTTX3_VOLUME,
        "ASR_ENGINE": cfg.ASR_ENGINE,
        "LLM_ENGINE": cfg.LLM_ENGINE,
        "DEEPSEEK_API_KEY": cfg.DEEPSEEK_API_KEY,
        "DEEPSEEK_API_URL": cfg.DEEPSEEK_API_URL,
        "DEEPSEEK_MODEL": cfg.DEEPSEEK_MODEL,
    }

    tts = create_tts_provider(config)
    asr = create_asr_provider(config)
    llm = create_llm_provider(config)
    conv = Conversation(
        llm,
        system_prompt=cfg.CHARACTER_PROMPT,
        max_rounds=cfg.MAX_HISTORY_ROUNDS,
    )

    tts.speak(f"Hey there! I'm {cfg.CHARACTER_NAME}. Let's practice English. What's up today?")

    while True:
        try:
            user_input = asr.listen()
            if not user_input:
                continue

            if user_input.lower() in ("bye", "exit", "quit", "goodbye"):
                tts.speak(f"Great talking with you! Keep practicing, see you next time!")
                print("\n👋 再见！")
                break

            if user_input.lower() == "clear":
                conv.clear()
                print("✓ 对话历史已清空")
                continue

            reply = conv.ask(
                user_input,
                temperature=cfg.TEMPERATURE,
                max_tokens=cfg.MAX_TOKENS,
            )
            english, chinese = parse_response(reply)
            tts.speak(english)
            if chinese:
                print(f"📝 中文: {chinese}")

        except KeyboardInterrupt:
            print("\n\n👋 再见！")
            break
        except Exception as e:
            print(f"\n⚠ 发生错误: {e}")
            print("  请重试或输入 'bye' 退出")


if __name__ == "__main__":
    main()
