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

如果你克隆（Clone）了本项目并希望在本地使用，请按以下步骤将本技能“植入”你的 Agent 大脑：

### 1. 环境与软件准备
- 确保已安装 Python 3.1x，并安装 MCP 官方依赖库（需要3.10以上）：
  ```bash
  pip install mcp
  ```
- **开启 PLECS 控制通道 (必做)**：打开 PLECS Standalone -> 菜单栏 `Preferences` -> `General` 选项卡 -> 勾选 `RPC interface port` 并将其设置为 `1080`。

### 2. 接入 Claude Code (MCP 挂载)
在你的终端中执行以下命令（请将路径替换为你克隆本项目的绝对路径）：
```bash
claude mcp add plecs-skill python /你的绝对路径/Plecs-Agent-Skill/mcp_server.py
```
挂载成功后，Claude 将永久获得操作 PLECS 的原生工具。

### 3. 创建你的“私密机房”
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
