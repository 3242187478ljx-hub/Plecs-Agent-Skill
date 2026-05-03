# 🔌 PLECS MCP Server 模块说明

## 概述

PLECS MCP Server 是本项目的核心服务端程序。它基于 Model Context Protocol (MCP)，将 PLECS Standalone 仿真软件底层的 RPC 控制能力封装为标准化的智能工具。通过本模块，Claude Code 等 AI Agent 能够原生、安全地操作 PLECS，执行包括模型加载、参数整定、异步仿真、批量扫描和自动化数据分析在内的高级任务。

## 目录结构

* `mcp_server.py`: 核心服务端脚本。负责启动 MCP 服务、建立与 PLECS 的 RPC 通道，并注册所有可用的 Tools。
* `mcp_cache/`: 临时存储目录（受 `.gitignore` 保护）。用于暂存正在运行的异步仿真状态、参数预设配置文件（Presets）以及导出的波形分析缓存。

## 核心功能列表

本模块为 Agent 注册了以下原生能力（Tools）：

| 类别 | 工具名称 | 功能说明 | 适用场景 |
|------|----------|----------|----------|
| **模型管理** | `load_plecs_model` | 加载 `.plecs` 模型文件 | 初始化仿真环境，必须优先执行 |
| | `get_model_variables` | 获取模型中所有可调参数及其路径 | 修改参数前的先决探索步骤 |
| **参数控制** | `set_parameter` | 修改指定的单一参数值 | 精确微调单一元件或控制环变量 |
| | `set_parameters_batch` | 批量修改多个参数 | 多变量协同整定，减少通信开销 |
| **仿真执行** | `run_simulation_async` | 发起非阻塞式的异步仿真，返回 Task ID | 执行耗时较长（>2秒）的复杂仿真 |
| | `get_simulation_result` | 轮询并获取异步仿真结果 | 配合 `run_simulation_async` 获取波形 |
| | `cancel_simulation` | 中止正在运行的仿真任务 | 发现参数设置错误时及时止损 |
| **高级分析** | `scan_parameters` | 自动化参数扫描，寻找特定指标最优值 | 寻找最佳 PID 系数或最佳效率点 |
| | `analyze_waveform` | 自动提取稳态值、纹波峰峰值、过冲等指标 | 替代外部数学库（如 numpy）进行结果评估 |
| **知识检索** | `search_knowledge` | 桥接 RAG 模块，检索 PLECS 官方手册 | 解决 C-Script 编译报错、查阅模块用法 |
| **预设管理** | `save_preset` / `load_preset` | 将当前参数组合保存为预设/加载历史预设 | 保存多组较优的实验工况 |
| | `list_presets` / `delete_preset` | 列出所有已保存预设/删除无用预设 | 环境清理与状态回溯 |
| **系统管理** | `get_statistics` | 查看服务端当前的仿真统计与健康状态 | 监控任务积压情况与内存占用 |
| | `clear_cache` | 清空服务端的历史仿真结果缓存 | 释放磁盘空间与内存，重置环境 |

## 安全与架构机制

1. **强隔离机制**：为防止 Agent 随意篡改主机文件，`load_plecs_model` 仅被允许读取特定的安全目录下的 `.plecs` 文件。
2. **防崩溃处理**：所有 RPC 请求均被 `try-except` 块严格包裹，底层通信超时或异常会转换为友好的 JSON 返回值，防止服务端主进程（StdIO）崩溃。
3. **跨模块联动**：本模块在启动时会自动将项目根目录拉入 `sys.path`，以实现与 `module_logger` (仿真追踪) 和 `module_rag` (手册检索) 的无缝协同。
4. **会话缓存机制**：启用了自动过期清理的 `result_cache`，大幅度提升了对历史相似查询（如重复的参数组合评估）的响应速度。
