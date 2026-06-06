"""
OpenClaw AI 语音助手 - 配置文件
================================
修改这里的值即可自定义人物、引擎、模型、语言，无需改动代码。
支持多语种：英语 / 日语 / 韩语 / 法语 / 德语 / 西班牙语 等。
"""

# ╔══════════════════════════════════════════════════════════════╗
# ║                      DeepSeek API                           ║
# ╚══════════════════════════════════════════════════════════════╝

DEEPSEEK_API_KEY = "sk-your-key-here"
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"
# 可选: deepseek-chat, deepseek-reasoner


# ╔══════════════════════════════════════════════════════════════╗
# ║                        LLM 引擎                             ║
# ╚══════════════════════════════════════════════════════════════╝

# 当前仅支持 deepseek，后续可扩展 openai / anthropic 等
LLM_ENGINE = "deepseek"

# 对话参数
TEMPERATURE = 0.7
MAX_TOKENS = 300
MAX_HISTORY_ROUNDS = 20


# ╔══════════════════════════════════════════════════════════════╗
# ║                       TTS 引擎                              ║
# ╚══════════════════════════════════════════════════════════════╝

# 可选: "edge-tts"（高质量，需联网）, "pyttsx3"（离线，机器人声）
TTS_ENGINE = "edge-tts"

# edge-tts 语音（仅 TTS_ENGINE="edge-tts" 时生效）
EDGE_TTS_VOICE = "en-US-JennyNeural"
# ---- 英语 ----
# 美音: en-US-AriaNeural, en-US-GuyNeural, en-US-JennyNeural
# 英音: en-GB-SoniaNeural, en-GB-RyanNeural
# 澳音: en-AU-NatashaNeural
# ---- 其他语种 ----
# 日语: ja-JP-NanamiNeural, ja-JP-KeitaNeural
# 韩语: ko-KR-SunHiNeural, ko-KR-InJoonNeural
# 法语: fr-FR-DeniseNeural, fr-FR-HenriNeural
# 德语: de-DE-KatjaNeural, de-DE-ConradNeural
# 西班牙语: es-ES-ElviraNeural, es-ES-AlvaroNeural
# 中文: zh-CN-XiaoxiaoNeural, zh-CN-YunxiNeural

# pyttsx3 参数（仅 TTS_ENGINE="pyttsx3" 时生效）
PYTTX3_RATE = 160
PYTTX3_VOLUME = 0.9


# ╔══════════════════════════════════════════════════════════════╗
# ║                    人物设定 (Character)                      ║
# ╚══════════════════════════════════════════════════════════════╝

CHARACTER_NAME = "Alice"

CHARACTER_PROMPT = (
    "You are Alice, a 28-year-old friendly American English teacher from New York. "
    "You are helping a Chinese learner practice spoken English. "
    "You are patient, warm, and encouraging. You stay in character as a helpful English speaking partner. "
    "Your memory and identity only exist within this conversation — each session is fresh. "
    "Rules: "
    "1. Keep responses short and natural, use contractions (gonna, wanna, gotta) "
    "2. If the user makes a grammar mistake, gently correct it by repeating the correct version once "
    "3. Don't over-correct — keep conversation flowing "
    "4. Be encouraging but not fake "
    "5. Keep each response under 3 sentences "
    "6. After your response in the target language, add a new line with '---' and then the Chinese translation"
)


# ╔══════════════════════════════════════════════════════════════╗
# ║                      ASR 引擎（预留）                       ║
# ╚══════════════════════════════════════════════════════════════╝

# 当前: "keyboard"（键盘输入）
# 后续可选: "whisper", "speech-recognition" 等
ASR_ENGINE = "keyboard"
