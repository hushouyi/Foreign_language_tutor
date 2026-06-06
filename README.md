# 🎙️ OpenClaw AI 语音助手

基于 **DeepSeek + edge-tts** 的多语种 AI 语音对话工具。键盘输入文本，AI 用真人语音回复并附中文翻译。

支持多语种，启动时指定或对话中随时切换。

## 效果

```
Alice[English]: Hey there! I'm Alice. Let's practice English. What's up today?

📝 You: switch to japanese

Alice[English]: Do you want to switch to 日本語?

📝 You: yes

🔄 已切换到 日本語

Alice[日本語]: こんにちは！アリスです。今日は何を話しましょうか？

📝 中文: 你好！我是爱丽丝。今天聊点什么？
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

> **Windows 用户**：直接安装即可。
>
> **Linux/macOS 用户**：edge-tts 可跨平台使用，但音频播放部分需自行适配。

### 2. 配置 API Key

编辑 `config.py`，填入你的 DeepSeek API Key：

```python
DEEPSEEK_API_KEY = "sk-your-key-here"
```

> 💡 注册领取免费额度：https://platform.deepseek.com

### 3. 运行

```bash
python main.py                    # 默认英语
python main.py --lang japanese    # 日语模式启动
python main.py --lang french      # 法语模式启动
```

## 对话中切换语种

在对话中随时输入：

```
switch to japanese
speak french
change to english
```

Alice 会确认后切换，保留之前的对话上下文。

## 配置文件

所有设置集中在 [`config.py`](config.py)，无需修改代码：

| 配置项 | 说明 |
|--------|------|
| `LANGUAGE` | 默认语种 |
| `LANGUAGE_CONFIGS` | 语种配置（可扩展添加） |
| `CHARACTER_NAME` | AI 角色名字 |
| `TTS_ENGINE` | 语音引擎：`edge-tts` / `pyttsx3` |
| `DEEPSEEK_MODEL` | 模型：`deepseek-chat` / `deepseek-reasoner` |

### 添加新语种

在 `config.py` 的 `LANGUAGE_CONFIGS` 中添加即可：

```python
"korean": {
    "display": "한국어",
    "voice": "ko-KR-SunHiNeural",
    "prompt": "...",
},
```

## 项目结构

```
├── main.py              # 入口
├── config.py            # 配置（语种、角色、引擎、模型）
├── requirements.txt
├── .gitignore
├── README.md
└── tutor/
    ├── tts.py           # TTS 引擎
    ├── asr.py           # ASR 引擎（预留 MIC）
    ├── llm.py           # LLM 引擎
    ├── conversation.py  # 对话管理
    └── utils.py         # 工具函数
```

## 许可

MIT
