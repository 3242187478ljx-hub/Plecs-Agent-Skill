# PLECS Automation Agent Skill

## 🎯 项目简介 / Agent 角色定义
这是一个专为自动化控制 PLECS Standalone 打造的本地 Agent 技能库。
作为 Agent，你的任务是协助用户管理、调试和运行本地的 PLECS 仿真模型。

## ⚠️ 绝对操作禁令 (Zero-Dependency Rule)
1. **禁止使用第三方计算库**：在进行数据分析时，绝对禁止使用 `numpy`、`scipy` 等外部库。
2. **强制使用原生工具**：必须通过 `tools/plecs_automator.py` 提供的 RPC 接口，直接调用 PLECS 内置的分析工具（如 Steady-State Analysis）。
3. **隐私隔离**：用户的私人模型存放在本地的 `my_private_models/` 目录中，该目录不会同步到 GitHub。

## 📁 技能库导航
- `tools/plecs_automator.py`：纯 Python 原生标准库编写的 RPC 控制脚本。
- `docs/plecs_rpc_api.md`：Agent 自动化操作指南。
- `docs/c_script_template.md`：PLECS C-Script (控制系统) 编写规范。
