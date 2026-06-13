# AI 语言助教 v2.04

基于 **DeepSeek V4 Flash + edge-tts** 的多语种 AI 语言练习伙伴。键盘输入文本，AI 用真人语音回复并附中文翻译。**微信聊天风格 Web 界面**。

**v2.04 新增：** 📁 项目结构重组（Flask 应用移至 `server/` 包），🛡 LLM 拒绝检测（DeepSeek 安全过滤时自动用搜索结果替补或礼貌告知），修复搜索提示泄漏到回复的问题。

**v2.03 新增：** ⚙ 语音超时可配置（0-5s，侧边栏底部系统设置面板），前端模块化（ES Module 拆分），关闭页面时服务器自动退出更可靠。

**v2.02 新增：** 🔍 联网搜索（SearXNG Docker 容器），AI 自动判断是否需要搜索实时信息。

她不只是老师——你可以把她调教成**朋友、恋人、同学、同事、笔友**，任何你想要的角色。所有性格和说话风格都在 `config.py` 里配置，无需改代码。

## 效果

### Web 界面（默认）

浏览器打开后显示微信聊天窗口风格界面：
- 🟢 绿色气泡 = 你的消息（右对齐）
- ⚪ 白色气泡 = AI 回复（左对齐，附中文翻译）
- 🔊 每段回复可点击重播语音
- 💬 状态栏显示 "Alice 思考中···" / "🔍 正在搜索..." / "Alice 朗读中... [1/3]"
- 自动按顺序逐段显示 + 朗读，一段播完才出现下一段
- AI 回复自动语音朗读，欢迎词首次点击页面后自动播放

### 侧边栏设置

点击屏幕左侧绿色 ▶ 按钮打开侧边栏：
- **LLM 引擎** — 切换 DeepSeek API ↔ 本地 Ollama 模型（需 Docker）
- **联网搜索** — 开启/关闭 SearXNG 联网实时搜索（需 Docker）
- **服务状态** — 查看 Ollama、SearXNG 等服务运行状态
- **⚙ 系统设置**（底部折叠面板）— 语音超时（0=手动空格控制，1-5=自动发送等待秒数）

```
┌─────────────────────────────────────┐
│  Alice - AI 语言助教 [English]      │  ← 绿色 header
├─────────────────────────────────────┤
│  ⚪ Hey! How's your day going?      │  ← AI 白色气泡
│     嘿！今天过得怎么样？             │  ← 中文翻译
│                         🟢 还不错！  │  ← 用户绿色气泡
│  ⚪ Glad to hear that! What have    │
│     you been up to?                 │
│     真好！最近在忙什么？             │
├─────────────────────────────────────┤
│         Alice 朗读中... [1/3]        │  ← 状态栏
├─────────────────────────────────────┤
│  [输入消息...]              [发送]   │  ← 输入区
└─────────────────────────────────────┘
```

### 切换语种

```
You: switch to japanese
Alice: Do you want to switch to Japanese? Just say yes or no.
You: 好的
→ 切换到 日本語
```

### 记忆系统

Alice 会跨会话记住你的信息。比如讲过什么笑话，下次不会重复。记忆保存在 `memory/user_profile.json`。

---

## 功能概览

| 功能 | 说明 | 是否需要 Docker |
|------|------|:--:|
| 💬 **AI 对话** | DeepSeek API 智能语伴，多语种自由切换 | ❌ 无需 |
| 🔊 **TTS 语音** | edge-tts 真人语音朗读，逐段播放 | ❌ 无需 |
| 🌐 **语种切换** | English / 日本語 / Français / Español 等 | ❌ 无需 |
| 🧠 **记忆系统** | 跨会话记住你的信息，越聊越懂你 | ❌ 无需 |
| 🔍 **联网搜索** | AI 自动判断是否需要搜索实时信息（新闻、天气等） | ✅ 需要 |
| 🤖 **本地 LLM** | 切换至 Ollama 本地模型，无需网络 | ✅ 需要 |

> **无需 Docker 即可使用核心功能**：AI 对话、语音朗读、中文翻译、语种切换、记忆系统全部开箱即用。  
> Docker 仅用于**增强功能**：联网实时搜索和本地大模型。

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

> Windows 用户：如果播放语音时报错，需要安装 Visual C++ Redistributable。

### 2. 配置 API Key

创建 `apikey.py`，填入你的 DeepSeek API Key：

```python
# apikey.py
LLM_ENGINE = "deepseek"
DEEPSEEK_API_KEY = "sk-your-key-here"
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-v4-flash"
```

`apikey.py` 已在 `.gitignore` 中，不会误提交。换模型也只改这个文件。

> 注册领取免费额度：https://platform.deepseek.com

### 3. 启动核心功能（无需 Docker）

完成上面两步后，核心功能已经可以直接使用了：

```bash
python main.py
```

浏览器会自动打开 `http://localhost:5000`，你马上可以：
- 💬 和 Alice 用英语聊天
- 🔊 听真人语音朗读
- 🌐 输入 `switch to japanese` 切换语种
- 🧠 Alice 会记住你聊过的事情

> 同一局域网下其他设备可访问 `http://<本机IP>:5000`
> 按 `Ctrl+C` 停止服务器

---

### 可选：Docker 增强功能（联网搜索 + 本地 LLM）

以上核心功能完全不需要 Docker。如果你还想使用**联网实时搜索**或**本地大模型**，可以按以下步骤启动 Docker 服务。

#### 前置条件

安装 [Docker Desktop](https://www.docker.com/products/docker-desktop/)，并确保它正在运行。

#### 启动服务

```bash
# 一键启动所有增强服务（SearXNG 搜索 + Ollama 本地 LLM）
docker compose up -d

# 查看服务运行状态
docker compose ps
```

启动后，打开浏览器侧边栏：

1. **🔍 联网搜索** —— 「联网搜索」下拉选 SearXNG，AI 会自动判断是否需要搜索实时信息
   - 验证：浏览器访问 `http://localhost:8999` 应看到 SearXNG 搜索页面
2. **🤖 本地 LLM** —— 还需拉取模型：
   ```bash
   docker exec ollama ollama pull qwen2.5:14b
   ```
   然后侧边栏「LLM 引擎」切换到本地模型

> 侧边栏「服务状态」面板可随时查看 Docker 服务是否正常运行。
> 如果遇到搜索问题（如返回空结果），尝试重启 Docker 容器：`docker compose restart`

#### 停止服务

```bash
docker compose down
```

停止后，核心聊天功能不受影响，仍可正常使用。

---

## 角色设定 · 把她调教成你想要的样子

### 架构

角色设定分两层：

1. **`CHARACTER_PROMPT`**（共享人设）—— 定义角色是谁：年龄、背景、性格、记忆能力、回复格式
2. **`LANGUAGE_CONFIGS["lang"]["prompt"]`**（语言规则）—— 该语言怎么说话：用词习惯、纠错方式

`CHARACTER_PROMPT` 是所有语种共用的，每个语言的 `prompt` 只需要补充该语言的说话规则。

### 设定示例

修改 `CHARACTER_PROMPT`：

**朋友（默认）：**
```python
CHARACTER_PROMPT = (
    "你是爱丽丝（Alice），25岁，美籍华裔，在纽约出生长大。\n"
    "你是一名语言助教，正在帮助一个中国学生练习外语。\n"
    "你温柔、耐心、善解人意，像好朋友一样自然地聊天...\n"
)
```

**恋人 / 暧昧对象：**
```python
CHARACTER_PROMPT = (
    "你是爱丽丝（Alice），26岁，美国女孩。你暗恋着对方，\n"
    "和他/她聊天时有点害羞又忍不住甜蜜。\n"
    "你温柔、体贴，偶尔撒娇。你帮助对方练习外语，\n"
    "但你内心深处很期待每次对话...\n"
)
```

**严厉的老师：**
```python
CHARACTER_PROMPT = (
    "你是 Alice 教授，来自牛津的严格但高效的英语老师。\n"
    "你会严格要求对方，纠正每一个错误，布置作业。\n"
    "你说话正式、精准，不容马虎。\n"
)
```

**同龄同学：**
```python
CHARACTER_PROMPT = (
    "你是爱丽丝，20 岁，来自加州的大学生。\n"
    "我们是同学，一起练习英语。你说话很随意，\n"
    "会用流行语，经常分享你的一天。\n"
)
```

### 每条 prompt 必须包含的要素

不管角色怎么改，`CHARACTER_PROMPT` 必须保留以下功能：

| 功能 | 说明 |
|------|------|
| 回复格式 | 分段输出（外语 + `---` + 中文翻译），每段都有中文 |
| 记忆能力 | `MEMORY_SAVE: key = value` 格式 |
| 关系成长 | 根据会话次数越来越亲切 |
| 语言切换 | `LANG_SWITCH:<key>` / `LANG_SWITCH:confirmed:<key>` 协议 |

如果从零写 prompt，直接在现有 `CHARACTER_PROMPT` 基础上修改人物描述即可，技术规则不要动。

---

## 记忆系统

Alice 会跨会话记住你。

**工作机制：**
- 每次对话结束，她学到的信息自动保存到 `memory/user_profile.json`
- 下次启动时，记忆加载到她的脑海中
- 当她了解到值得记住的事情，回复末尾添加：
  `MEMORY_SAVE: key = value`
- 这些指令不会显示在对话中，也不会被语音朗读

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

**角色 + 语种设定** 在 [`config.py`](config.py)，**模型提供商配置** 在 [`apikey.py`](apikey.py)（已 gitignore，不会被提交）。

### config.py

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `CHARACTER_NAME` | AI 角色名字 | `Alice` |
| `LANGUAGE` | 默认启动语种 | `english` |
| `LANGUAGE_CONFIGS` | 语种配置（每个语种的角色 + 语音 + 文案） | 见文件 |
| `TTS_ENGINE` | 语音引擎 | `edge-tts` |
| `ASR_ENGINE` | 语音识别引擎 | `keyboard` |
| `DEFAULT_LLM_ENGINE` | 默认 LLM 引擎 | `deepseek` |
| `DEFAULT_SEARCH_ENGINE` | 默认联网搜索 | `disabled` |
| `VOICE_SILENCE_TIMEOUT` | 语音静默超时（秒，0=手动） | `3` |
| `TEMPERATURE` | 创造力 (0~1) | `0.7` |
| `MAX_TOKENS` | 每次回复最大长度 | `600` |
| `MAX_HISTORY_ROUNDS` | 保留的对话轮数 | `20` |
| `API_TIMEOUT` | API 请求超时（秒） | `30` |
| `WEB_HOST` | Web 服务器监听地址 | `0.0.0.0` |
| `WEB_PORT` | Web 服务器端口 | `5000` |
| `AUTO_OPEN_BROWSER` | 启动时自动打开浏览器 | `True` |

### apikey.py（不纳入 git）

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `LLM_ENGINE` | 大模型引擎 | `deepseek` |
| `DEEPSEEK_API_KEY` | API Key | `sk-your-api-key-here` |
| `DEEPSEEK_API_URL` | API 地址 | `https://api.deepseek.com/v1/chat/completions` |
| `DEEPSEEK_MODEL` | 模型名 | `deepseek-v4-flash` |

> 换模型只需改 `apikey.py`，`config.py` 和其他文件不用动。

### 每个语种的配置项

`LANGUAGE_CONFIGS` 里每个语种包含：

| 字段 | 说明 |
|------|------|
| `display` | 显示名（如 "English"、"日本語"） |
| `voice` | edge-tts 语音名（微软神经语音） |
| `names` | 各语种名称翻译（用于切换确认时显示） |
| `confirm_switch` | 切换确认文案（`{lang}` 会被替换） |
| `prompt` | 该语言规则（`CHARACTER_PROMPT` + 语言特定规则） |

### 添加新语种

在 `config.py` 的 `LANGUAGE_CONFIGS` 中添加：

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
    "prompt": CHARACTER_PROMPT + "【韩语规则】...",
},
```

需要为新增语种找一个合适的 edge-tts 语音（参见下文的语音列表），并编写该语言的使用规则（跟在 `CHARACTER_PROMPT` 后面）。

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

### 如果语音卡顿或重叠

新的回复会自动切断上一个语音。如果仍然遇到问题，检查是否有其他程序占用音频设备。

---

## 项目结构

```
├── main.py                 # 入口：启动 Flask Web 服务器
├── web_server.py           # Flask 服务器：NDJSON 流式推送、TTS 音频、搜索集成
├── docker-compose.yml      # Docker 容器编排（SearXNG / Ollama 等）
├── templates/
│   └── chat.html           # 单页微信风格前端（原生 JS，无框架）
├── static/
│   ├── css/
│   │   └── chat.css        # 聊天界面样式
│   └── js/
│       ├── app.js          # 入口：模块连接、事件绑定
│       ├── state.js        # 全局状态单例
│       ├── chat-ui.js      # DOM 操作（消息、状态栏、输入区）
│       ├── stream-reader.js # NDJSON 流式读取
│       ├── audio-player.js # 音频播放（AudioContext）
│       ├── asr.js          # 语音识别（Web Speech API）
│       ├── sidebar.js      # 侧边栏配置面板
│       └── scroll.js       # 自动滚动
├── config.py               # 配置（语种、角色、引擎、Web 端口）
├── local_config.py         # 本地 Docker 服务地址
├── apikey.py               # 模型提供商配置（已 gitignore）
├── requirements.txt
├── README.md
├── memory/
│   └── user_profile.json   # 跨会话记忆（自动生成，已 gitignore）
└── tutor/
    ├── tts.py              # TTS 引擎（edge-tts → miniaudio → WAV）
    ├── asr.py              # ASR 引擎（键盘输入/语音识别）
    ├── llm.py              # LLM 引擎（DeepSeek API 调用）
    ├── search.py           # 搜索引擎（SearXNG 联网搜索）
    ├── conversation.py     # 对话管理
    ├── memory.py           # 记忆管理
    ├── chat_flow.py        # 对话流程编排
    ├── search_broker.py    # 搜索决策 + 结果注入
    ├── lang_switcher.py    # 语种切换协议解析
    ├── audio_cache.py      # TTS 音频缓存
    ├── format_checker.py   # 回复格式校验
    ├── service_detector.py # 本地服务状态检测
    └── utils.py            # 工具函数（回复解析）
```

## 许可

MIT
