# PLECS MCP Logger 模块说明

## 概述

PLECS MCP Logger 是专为本仿真系统设计的结构化日志与分析模块。它采用 JSONL 格式实现会话级（Session）的日志隔离，不仅能够自动记录 Agent 的工具调用、参数修改和仿真状态流转，还内置了执行耗时统计、错误率分析以及基于历史数据的自动化调优建议功能。

## 目录结构

* `logger.py`: 日志生成与分析器的核心脚本，支持以单例模式集成到主服务中，同时也支持直接通过命令行运行。
* `logs/`: 自动生成的目录（受 `.gitignore` 保护）。按时间戳和会话 ID 独立存储 `.jsonl` 日志文件及其对应的 `_meta.json` 元数据配置文件。

## 功能列表

本模块提供了以下核心日志记录与分析接口：

| 类别 | 核心方法/功能 | 说明 |
|------|---------------|------|
| **行为记录** | `log_tool_call` | 记录任意工具调用的详细信息（含参数截断脱敏、执行耗时、成功/失败状态）。 |
| | `log_simulation_task` | 记录耗时仿真任务的生命周期节点（pending, running, completed, failed）。 |
| | `log_system_event` | 记录底层系统级事件（如服务启动、RPC 连接断开、全局配置变更等）。 |
| **数据分析** | `analyze_stats` | 计算指定会话内所有工具的调用次数、平均耗时、报错频率及成功率。 |
| | `suggest_optimizations` | 基于统计数据自动生成诊断建议（如：识别高频报错工具、建议批量扫描替代单次循环等）。 |
| **查询检索** | `get_recent_errors` | 快速提取当前会话或历史文件末尾的 N 条报错记录，辅助 Agent 进行快速失败复盘。 |
| **持久化** | `export_session` | 将当前隔离的 `.jsonl` 碎片化日志合并导出为标准的 `.json` 报告文件。 |

## 数据脱敏与安全设计

1. **自动截断机制 (`_sanitize_parameters` / `_sanitize_result`)**：为了防止单条日志体积爆炸导致内存溢出，当检测到过长的字符串（>200 字符）或庞大的波形数据结构（如超过 500 长度的 list/dict）时，系统会自动对其进行截断缩略（如：`[list with 1500 chars]`）。
2. **生命周期管理 (`_cleanup_old_logs`)**：每次初始化新的日志会话时，系统会自动扫描 `logs/` 目录，并静默清理超过设定保留天数（默认 30 天）的陈旧日志，防止磁盘空间耗尽。

## 命令行分析工具 (CLI)

除了作为依赖库被 `mcp_server.py` 引入外，本模块亦可作为独立分析工具在终端直接执行，方便人类开发者快速复盘 Agent 的表现：

```bash
# 查看默认会话的全面统计信息与分析建议
python -m module_logger.logger --stats --suggest

# 查看最近的 5 条致命错误报错详情
python -m module_logger.logger --errors 5

# 分析指定的历史会话，并生成离线报告
python -m module_logger.logger --session 20260503_153000 --stats --export ./report.json
```
