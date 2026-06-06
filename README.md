# OpenClaw AI 语言助教

基于 **DeepSeek V4 Flash + edge-tts** 的多语种 AI 语言练习伙伴。键盘输入文本，AI 用真人语音回复并附中文翻译。

她不只是老师——你可以把她调教成**朋友、恋人、同学、同事、笔友**，任何你想要的角色。所有性格和说话风格都在 `config.py` 里配置，无需改代码。

## 效果

### 正常对话

```
Alice[English]: Hey there! I'm Alice. Let's practice English. What's up today?
📝 中文: 嘿！我是爱丽丝。今天想聊点什么？

📝 You: Hi Alice, I went to the park yesterday

Alice[English]: Oh nice! What did you do at the park?
📝 中文: 哦，不错！你在公园做了什么？
```

### 切换语种

```
📝 You: switch to japanese

Alice[English]: Do you want to switch to Japanese? Just say yes or no.
📝 中文: 你想切换到日本語吗？

📝 You: 好的

🔄 已切换到 日本語

Alice[日本語]: はい、日本語で話しましょう！何について話したいですか？
📝 中文: 好的，我们用日语聊吧！你想聊什么？
```

确认切换时可以用任何语言表达同意（yes / 好的 / sure / はい / vale…），DeepSeek 会自然理解。

### 她会记住你

Alice 会跨会话记住你的信息和偏好。比如讲过什么笑话，下次不会重复。

```
📝 You: 给我讲个笑话

Alice[English]: Sure! Why don't scientists trust atoms? ...
---中文---

📝 You: 再讲一个

Alice[English]: How about this one — What do you call a fish with no eyes? A fsh!
---中文---
# 下次启动程序再要笑话，她也不会重复讲过的
```

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

Windows 用户直接安装即可。Linux/macOS 用户：edge-tts 可跨平台使用，但音频播放部分需自行适配。

### 2. 配置 API Key

编辑 `config.py`，填入你的 DeepSeek API Key：

```python
DEEPSEEK_API_KEY = "sk-your-key-here"
```

> 注册领取免费额度：https://platform.deepseek.com

### 3. 运行

```bash
python main.py                    # 默认英语
python main.py --lang japanese    # 日语模式启动
python main.py --lang french      # 法语模式启动
```

---

## 角色设定 · 把她调教成你想要的样子

Alice 可以是任何角色。核心在 `config.py` 的 `prompt` 字段，改这一句话就能改变整个性格。

### 设定示例

**朋友（默认）：**
```python
"prompt": "You are Alice, a 28-year-old American from New York — a friendly language practice assistant..."
```

**恋人 / 暧昧对象：**
```python
"prompt": "You are Alice, a 26-year-old American woman who has a crush on me. You're sweet, flirtatious, and occasionally shy. You're helping me practice English but you secretly look forward to our conversations..."
```

**严厉的老师：**
```python
"prompt": "You are Professor Alice, a strict but effective English teacher from Oxford. You push me hard, correct every mistake, and give me homework..."
```

**同龄同学：**
```python
"prompt": "You are Alice, a 20-year-old college student from California. We're classmates practicing English together. You're casual, use slang, talk about your day..."
```

**笔友：**
```python
"prompt": "You are Alice, my pen pal from New Zealand. We write to each other to improve our languages. You tell me about your life, ask about mine..."
```

**专属角色：**
直接写你想让她成为的人。年龄、性格、说话方式、你们的关系——用自然语言描述就行，DeepSeek 会理解。

### prompt 编写指南

一条好的 prompt 包含这些要素：

| 要素 | 说明 | 示例 |
|------|------|------|
| 角色身份 | 年龄、职业、来自哪里 | "a 25-year-old artist from Paris" |
| 关系定位 | 你们是什么关系 | "you are my language partner / girlfriend / classmate" |
| 性格特征 | 怎样对待你 | "sweet, patient, teasing, strict..." |
| 说话风格 | 正式/随意、用词习惯 | "use slang, be dramatic, speak formally..." |
| 规则指令 | 技术性要求 | 保留原有的规则编号（见下文） |

### ⚠️ 必须保留的规则

不管角色怎么改，`prompt` 里**必须保留**这几条技术规则（编号可以变，内容不能少）：

```
MEMORY: You can remember things about the user across sessions. ...
Rules:
...
LANGUAGE SWITCH: ... 'LANG_SWITCH:<key>' ...
Normal replies: respond in target language, then add '---' + Chinese translation.
SWITCH CONFIRMED: ... 'LANG_SWITCH:confirmed:<key>' ...
```

这些规则保证语种切换、中文翻译、记忆系统正常工作。如果你从零写 prompt，把现有配置里的规则 5/6/7（对应语言切换、翻译格式、确认切换）复制过去即可。

---

## 记忆系统

Alice 会跨会话记住你。

**工作机制：**
- 每次对话结束，她学到的信息自动保存到 `memory/user_profile.json`
- 下次启动时，记忆加载到她的脑海中
- 当她了解到值得记住的事情（你的名字、兴趣、讲过的笑话），她会用以下格式保存：
  `MEMORY_SAVE: key = value`
- 这些保存指令不会显示在对话中，也不会被语音朗读

**示例记忆文件 (`memory/user_profile.json`)：**
```json
{
  "jokes_told": "a knock-knock joke about a scarecrow, a pun about atoms",
  "user_name": "小明",
  "user_level": "intermediate",
  "likes_topic": "travel and food"
}
```

**清除记忆：** 直接删除 `memory/user_profile.json` 文件即可。

---

## 对话中切换语种

随时输入：

```
switch to japanese
speak french
change to english
说日语
切换到西班牙语
```

Alice 会用当前语言确认，你同意后切换。切换后保留之前的对话上下文。

支持所有配置的语种：english / japanese / french / spanish。

---

## 配置文件

所有设置集中在 [`config.py`](config.py)，无需修改代码：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `CHARACTER_NAME` | AI 角色名字 | `Alice` |
| `LANGUAGE` | 默认启动语种 | `english` |
| `LANGUAGE_CONFIGS` | 语种配置（每个语种的角色 + 语音 + 文案） | 见文件 |
| `TTS_ENGINE` | 语音引擎 | `edge-tts` |
| `ASR_ENGINE` | 语音识别引擎 | `keyboard` |
| `LLM_ENGINE` | 大模型引擎 | `deepseek` |
| `DEEPSEEK_MODEL` | DeepSeek 模型名 | `deepseek-v4-flash` |
| `TEMPERATURE` | 创造力 (0~1) | `0.7` |
| `MAX_TOKENS` | 每次回复最大长度 | `300` |
| `MAX_HISTORY_ROUNDS` | 保留的对话轮数 | `20` |

### 每个语种的配置项

`LANGUAGE_CONFIGS` 里每个语种包含：

| 字段 | 说明 |
|------|------|
| `display` | 显示名（如 "English"、"日本語"） |
| `voice` | edge-tts 语音名（微软神经语音） |
| `names` | 各语种名称翻译 |
| `confirm_switch` | 切换确认文案（`{lang}` 会被替换） |
| `hello` | 启动问候语 |
| `hello_zh` | 问候语的中文翻译 |
| `switched` | 切换成功后的欢迎语 |
| `switched_zh` | 欢迎语的中文翻译 |
| `prompt` | 角色设定 + 规则（修改这里改变性格） |

### 添加新语种

在 `config.py` 的 `LANGUAGE_CONFIGS` 中添加即可：

```python
"korean": {
    "display": "한국어",
    "voice": "ko-KR-SunHiNeural",
    "names": {
        "english": "영어", "japanese": "일본어",
        "french": "프랑스어", "spanish": "스페인어",
        "korean": "한국어"
    },
    "confirm_switch": "{lang}(으)로 전환할까요? 예 또는 아니요로 답해주세요.",
    "hello": "안녕하세요! 앨리스입니다. 한국어 연습을 시작해볼까요? 오늘은 무엇에 대해 이야기하고 싶으신가요?",
    "hello_zh": "你好！我是爱丽丝。我们来练习韩语吧。你想聊什么？",
    "switched": "좋아요! 이제 한국어로 이야기해요. 무슨 이야기를 하고 싶으신가요?",
    "switched_zh": "好的！我们现在开始练习韩语吧。你想聊什么？",
    "prompt": "...角色设定和规则..."
},
```

需要为新增语种找一个合适的 edge-tts 语音（参见下文的语音列表），并按照现有模板编写 prompt（含角色设定 + 语言切换规则 + 记忆指令）。

### 可用的 edge-tts 语音

```
英语:    en-US-JennyNeural, en-GB-SoniaNeural, en-AU-NatashaNeural
日语:    ja-JP-NanamiNeural
法语:    fr-FR-DeniseNeural, fr-CA-SylvieNeural
西班牙语: es-ES-ElviraNeural, es-MX-DaliaNeural
韩语:    ko-KR-SunHiNeural, ko-KR-InJoonNeural
中文:    zh-CN-XiaoxiaoNeural, zh-CN-YunxiNeural
德语:    de-DE-KatjaNeural, de-DE-ConradNeural
俄语:    ru-RU-SvetlanaNeural
葡萄牙语: pt-BR-FranciscaNeural
意大利语: it-IT-ElsaNeural
阿拉伯语: ar-SA-ZariyahNeural
```

> 完整列表：https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=tts

---

## 小技巧

### 每个语种可以设定不同的角色

英语是朋友、日语是恋人、法语是严厉的老师——每个语种独立配置 `prompt`，切换语种时角色也一起切换。

### 温度调得越高越"疯"

`TEMPERATURE = 0.7` 比较平衡。调到 `0.9` 以上会更随机、更有创意；调到 `0.3` 会更稳定、更可预测。

### 记忆是跨语种共享的

Alice 在英语模式下记住的东西，切换到日语时她也记得。因为所有记忆存在同一个 `user_profile.json`。

### 调试模式

如果想知道她记住了什么，直接问她："你还记得我什么？" 她会读取脑海中的记忆回复你。

---

## 项目结构

```
├── main.py                 # 入口
├── config.py               # 配置（语种、角色、引擎、模型）
├── requirements.txt
├── README.md
├── memory/
│   └── user_profile.json   # 跨会话记忆（自动生成）
└── tutor/
    ├── tts.py              # TTS 引擎（语音合成）
    ├── asr.py              # ASR 引擎（语音识别）
    ├── llm.py              # LLM 引擎（模型调用）
    ├── conversation.py     # 对话管理
    ├── memory.py           # 记忆管理
    └── utils.py            # 工具函数
```

## 许可

MIT
