# 🎙️ OpenClaw AI 语音助手

基于 **DeepSeek + edge-tts** 的多语种 AI 语音对话工具。键盘输入文本，AI 用真人语音回复并附中文翻译。

支持英语 / 日语 / 韩语 / 法语 / 德语 / 西班牙语 等多语种对话，只需修改配置文件即可切换语言和角色。

## 效果

```
🎙️ Alice: Hey there! I'm Alice. Let's practice English. What's up today?

📝 You: Hi Alice, I went to the park yesterday

🎙️ Alice: Oh nice! What did you do at the park?

📝 中文: 哦，不错！你在公园做了什么？
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

> **Windows 用户**：直接安装即可，底层音频播放使用系统自带组件。
>
> **Linux/macOS 用户**：edge-tts 可跨平台使用，但音频播放部分需自行适配（当前基于 PowerShell SoundPlayer）。

### 2. 配置 API Key

编辑 `config.py`，填入你的 DeepSeek API Key：

```python
DEEPSEEK_API_KEY = "sk-your-key-here"
```

> 💡 注册领取免费额度：https://platform.deepseek.com

### 3. 运行

```bash
python main.py
```

输入 `bye` 或 `exit` 退出，`clear` 清空对话历史。

## 多语种切换

改 `config.py` 里的 **语音** 和 **人物 prompt** 即可切换语种。

### 日语示例

```python
EDGE_TTS_VOICE = "ja-JP-NanamiNeural"

CHARACTER_PROMPT = (
    "あなたは佐藤さんです。日本語を勉強している中国人学習者を助けています。"
    "毎回の返事の最後に「---」を入れて、その後に中国語の翻訳を追加してください。"
    ...
)
```

### 法语示例

```python
EDGE_TTS_VOICE = "fr-FR-DeniseNeural"

CHARACTER_PROMPT = (
    "You are Sophie, a friendly French teacher from Paris. "
    "You are helping a Chinese learner practice French. "
    ...
)
```

## 自定义

所有配置集中在 [`config.py`](config.py)，无需修改代码：

| 配置项 | 说明 |
|--------|------|
| `CHARACTER_NAME` | AI 角色名字 |
| `CHARACTER_PROMPT` | 完整人物设定（语言、性格、行为规则） |
| `TTS_ENGINE` | 语音引擎：`edge-tts`（推荐）或 `pyttsx3` |
| `EDGE_TTS_VOICE` | 微软神经语音（支持 50+ 语种） |
| `DEEPSEEK_MODEL` | 模型：`deepseek-chat` / `deepseek-reasoner` |
| `LLM_ENGINE` | 预留字段，后续支持 OpenAI / Anthropic |

## 项目结构

```
├── main.py              # 入口 (python main.py)
├── config.py            # 配置（角色、引擎、模型、语种）
├── requirements.txt     # Python 依赖
├── .gitignore
├── README.md
└── tutor/               # 核心模块
    ├── tts.py           # TTS 引擎（edge-tts / pyttsx3）
    ├── asr.py           # ASR 引擎（当前键盘，预留 MIC）
    ├── llm.py           # LLM 引擎（当前 DeepSeek）
    ├── conversation.py  # 对话历史管理
    └── utils.py         # 工具函数
```

## 扩展计划

- [ ] 麦克风语音输入（Whisper / speech-recognition）
- [ ] 更多 LLM 支持（OpenAI、Claude、本地模型）
- [ ] 对话记录保存与导出
- [ ] 非 Windows 音频播放适配
- [ ] Web / GUI 界面

## 许可

MIT
