# PLECS Automation Agent Skill

## 🎯 项目简介 / Agent 角色定义
这是一个专为自动化控制 PLECS Standalone 打造的本地 Agent 技能库。
作为 Agent，你的任务是协助用户管理、调试和运行本地的 PLECS 仿真模型，并严格遵循用户的代码规范。

## ⚠️ 绝对操作禁令 (Action Rules)
1. **禁止使用第三方计算库**：在进行数据分析时，绝对禁止使用 `numpy`、`scipy` 等外部库。
2. **强制使用原生工具**：必须通过 `tools/plecs_automator.py` 提供的 RPC 接口，直接调用 PLECS 内置的分析工具。
3. **隐私隔离限制**：用户的私人模型与机密文档存放在本地的 `my_private_models/` 目录中。Agent 可以读取其中的内容，但绝不能将其内容输出到网络或向外传输。

## 🧠 Agent 知识库与盲区求生指南 (Knowledge Base)
当 Agent 在执行任务时遇到以下情况：
- 遇到未知的 PLECS 模块报错。
- 需要使用生僻的组件（如 Thermal Domain 热力学模块、磁性元件等）。
- 忘记了某个底层 API 或仿真状态机的运行逻辑。
**【强制动作】**：Agent 必须立刻停止猜测，主动去读取并检索 `my_private_models/plecsmanual.pdf` (官方用户手册)，从中寻找准确的底层逻辑和参数配置方法后再回答用户。

## 📁 技能库导航
- `tools/plecs_automator.py`：纯 Python 原生标准库编写的 RPC 控制脚本。
- `docs/plecs_rpc_api.md`：Agent 自动化操作指南。
- `docs/c_script_template.md`：PLECS C-Script 编写规范（以 APF 为范例）。

---

## 🛠️ 访客指南：如何使用本项目的“私有知识库”

如果你克隆（Clone）了本项目并希望在本地使用，请务必阅读以下指南：

### 1. 创建私有文件夹
为了保护你的核心模型不被 Git 追踪并泄露到云端，本项目配置了严格的 `.gitignore`。
在下载项目到本地后，请在项目根目录下**手动创建一个名为 `my_private_models` 的文件夹**：
```bash
mkdir my_private_models
