# PLECS MCP Agent Skill

## 🎯 项目简介
这是一个基于前沿 MCP (Model Context Protocol) 协议打造的 PLECS Standalone 自动化控制服务。
通过将本服务接入 Claude Code，Agent 将原生具备加载模型、修改参数、运行仿真和分析数据的能力。告别繁琐的终端命令，实现大语言模型与仿真软件的“意念直连”。

## 📁 极简架构导航
- `mcp_server.py`：核心 MCP 服务端脚本（负责将 PLECS RPC 接口注册为 Claude 原生工具）。
- `docs/c_script_template.md`：PLECS C-Script 编写规范（防幻觉模板，强制 Agent 输出高质量控制代码）。
- `Reference/`：公共参考资料库（建议放入官方 `plecsmanual.pdf` 供 Agent 随时查阅）。
- `my_private_models/`：本地私密模型保险箱（受 `.gitignore` 保护，存放你的核心工程文件，绝不上传云端）。

---

## 🚀 访客指南：如何安装与挂载本技能

为了保障底层环境的绝对干净，并确保 Claude 的内置服务不崩溃，请严格按照以下标准化流程将本技能“植入”你的 Agent 大脑：

### 1. 环境与底层依赖准备
除了必须开启的仿真软件接口外，你需要确保系统底层组件的完整：
- **开启 PLECS 控制通道 (必做)**：打开 PLECS Standalone -> 菜单栏 `Preferences` -> `General` 选项卡 -> 勾选 `RPC interface port` 并将其设置为 `1080`。
- **配置 Claude 底层环境 (重要)**：Claude Code 自身的部分内置模块（如历史记忆）强依赖于 `Node.js` 和 `Bun`。若你使用 macOS，强烈建议通过 Homebrew 提前装好它们以防报错：
  ```bash
  brew install node
  brew install bun
  ```

### 2. 创建独立运行环境与安装依赖
为了不污染系统的全局 Python，且防止后续 Agent 找不到 `mcp` 库，**本工程建议使用虚拟环境**。请在项目根目录下依次执行：
```bash
# 1. 创建名为 .venv 的虚拟环境 (需 Python 3.10+)
python3 -m venv .venv

# 2. 激活虚拟环境 (Windows 用户请使用 .venv\Scripts\activate)
source .venv/bin/activate

# 3. 安装mcp包
pip install mcp
```

### 3. 接入 Claude Code (绝对路径挂载)
由于 Claude 在底层调用时不会自动识别你的虚拟环境，**必须**使用虚拟环境内部 Python 的绝对路径来进行“挂载”。

在你的终端中执行以下命令（⚠️ **务必将 `/你的绝对路径/` 替换为你本机的实际路径**）：
```bash
claude mcp add plecs-skill /你的绝对路径/Plecs-Agent-Skill/.venv/bin/python /你的绝对路径/Plecs-Agent-Skill/mcp_server.py
```
*💡 原理解析：执行此命令后，终端会提示 `Added stdio MCP server...` 并修改本地的 `~/.claude.json` 配置文件。这意味着该技能的专属神经元已经被系统级写入 Claude 的主板。*

**⚠️ 注意：挂载成功后，请输入 `/exit` 退出当前会话，并重新运行 `claude` 重启以使配置生效！**

### 4. 创建你的“私密机房”
为了保护你的核心研究成果（如复杂的 APF 控制系统或 Buck 变换器闭环模型），请在本项目根目录下手动创建私有文件夹：
```bash
mkdir my_private_models
```
将你的 `.plecs` 文件放入其中，Agent 即可安全地进行读取和调试。

---

## 🧠 Agent 核心工作准则 (System Prompt)

**致读取本仓库的 AI Agent：当用户要求你调试或运行 PLECS 模型时，你必须严格遵守以下准则：**

1. **原生工具优先**：你已经通过 MCP 挂载了 `load_plecs_model`, `simulate_plecs_model`, `analyze_plecs_model` 和 `update_plecs_parameter` 等原生工具。**绝对不要**尝试在终端手写 python 脚本去控制软件，请直接调用你的原生能力。
2. **纯净数据分析**：禁止使用 `numpy`/`scipy` 等外部科学库进行数据处理，必须调用 `analyze_plecs_model` 获取官方底层的稳态或频域高精度数据。
3. **盲区求生本能**：遇到不熟悉的 PLECS 模块报错，或忘记了底层 API 与状态机的运行逻辑时，**必须立刻停止猜测**，主动读取本地 `Reference/plecsmanual.pdf` 寻找准确答案。
4. **捍卫代码规范**：在编写或修改任何 C-Script 控制代码前，务必先查阅 `docs/c_script_template.md` 熟悉开发者的代码风格。
