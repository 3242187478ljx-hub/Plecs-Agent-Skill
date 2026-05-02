# PLECS Automation Agent Skill

## 🎯 项目简介 / Agent 角色定义
这是一个专为自动化控制 PLECS Standalone 打造的本地 Agent 技能库。
作为 Agent，你的任务是协助用户管理、调试和运行本地的 PLECS 仿真模型，并严格遵循用户的代码规范。

## ⚠️ 绝对操作禁令 (Action Rules)
1. **禁止使用第三方计算库**：在进行数据分析时，绝对禁止使用 `numpy`、`scipy` 等外部库。
2. **强制使用原生工具**：必须通过 `tools/plecs_automator.py` 提供的 RPC 接口，直接调用 PLECS 内置的分析工具。
3. **数据安全与隔离机制**：用户的私人模型与代码存放在本地受 Git 保护的 `my_private_models/` 目录中，Agent 绝不能将其内容输出到网络；公开的官方参考文件存放于 `Reference/` 目录中。

## 🧠 Agent 知识库与盲区求生指南 (Knowledge Base)
当 Agent 在执行任务时遇到以下情况：
- 遇到未知的 PLECS 模块报错。
- 需要使用生僻的组件（如 Thermal Domain 热力学模块、磁性元件等）。
- 忘记了某个底层 API 或仿真状态机的运行逻辑。

**【强制动作】**：Agent 必须立刻停止猜测，主动去读取并检索 `Reference/plecsmanual.pdf` (官方用户手册)，从中寻找准确的底层逻辑和参数配置方法后再回答用户。

## 📁 技能库导航
- `Reference/`：公共参考资料库，包含官方用户手册等公开可下载资料。
- `tools/plecs_automator.py`：纯 Python 原生标准库编写的 RPC 控制脚本。
- `docs/plecs_rpc_api.md`：Agent 自动化操作指南。
- `docs/c_script_template.md`：PLECS C-Script 编写规范（以 APF 为范例）。

---

## 🛠️ 访客指南：如何使用本项目的本地 Agent 架构

如果你克隆（Clone）了本项目并希望在本地驱动你的大语言模型（如 Claude Code），请遵循以下指南：

### 1. 配置 PLECS RPC 接口 (必做)
为了让 Agent 能够接管仿真软件，你必须手动开启 PLECS 的通信端口：
- 打开 PLECS Standalone。
- 进入菜单 **File** -> **Preferences** (Mac 用户为 **PLECS** -> **Preferences**)。
- 在 **General** 选项卡中，勾选 **RPC interface port** 并将其设置为 `1080`。
- 点击 **OK** 确保配置生效。

### 2. 完善公共参考库
本项目自带 `Reference/` 文件夹，里面预置了如 `plecsmanual.pdf` 等官方文档。当 Agent 遇到专业盲区时，会自动查阅该目录下的文件，极大程度减少 AI 的幻觉。

### 3. 创建你的私有模型文件夹 (极其重要)
为了保护你的核心模型、未开源代码或个人实验数据不被 Git 追踪并泄露到云端，本项目配置了严格的 `.gitignore`。
在下载项目到本地后，请在项目根目录下**手动创建一个名为 `my_private_models` 的文件夹**：

```bash
mkdir my_private_models
```

它是你本地 Agent 的“机密外脑”。你应该往里面放入：
* **你的成品仿真文件 (`.plecs`)**：当 Agent 为你编写新代码时，会去这里参考你的历史成品，完美复刻你的代码习惯和工程规范。
* **个人实验数据/报告**：任何你不希望开源，但希望 Agent 帮你分析的数据。
