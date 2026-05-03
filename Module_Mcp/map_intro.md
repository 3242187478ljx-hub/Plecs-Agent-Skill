# PLECS MCP Server 使用说明

## 概述

PLECS MCP Server 是一个基于 Model Context Protocol (MCP) 的服务端程序，它将 PLECS 仿真软件的控制能力封装为标准化的 MCP 工具，使得 Claude Code 等 AI Agent 能够直接操作 PLECS 进行仿真、参数扫描和数据分析。

## 功能列表

| 类别 | 工具 | 说明 |
|------|------|------|
| 模型管理 | `load_plecs_model` | 加载 .plecs 模型文件 |
| | `get_model_variables` | 获取模型中所有可调参数 |
| 参数控制 | `set_parameter` | 设置单个参数 |
| | `set_parameters_batch` | 批量设置多个参数 |
| 仿真执行 | `run_simulation_async` | 异步运行仿真 |
| | `get_simulation_result` | 获取仿真结果 |
| | `cancel_simulation` | 取消正在运行的任务 |
| 参数扫描 | `scan_parameters` | 自动扫描参数范围并找最优值 |
| 数据分析 | `analyze_waveform` | 分析波形（稳态、纹波、过冲等） |
| 知识检索 | `search_knowledge` | 从手册中检索相关知识 |
| 预设管理 | `save_preset` / `load_preset` | 保存/加载参数预设 |
| | `list_presets` / `delete_preset` | 管理预设 |
| 系统管理 | `get_statistics` | 查看服务器统计信息 |
| | `clear_cache` | 清空结果缓存 |
