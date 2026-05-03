# 📚 PLECS RAG 知识检索模块

## 概述

PLECS RAG (Retrieval-Augmented Generation) 是为本系统提供的外部大脑。通过本地化运行的文本嵌入模型（`sentence-transformers`）和向量数据库（`ChromaDB`），它可以将庞大的 PLECS 官方 PDF 手册转化为 Agent 可以毫秒级检索的知识库。当 Agent 遇到 C-Script 编译错误或未知的模块用法时，将自动调用本模块查阅文档，从而从根本上消除 LLM 在私有工业软件领域的“代码幻觉”。

## 目录结构

* `rag_knowledge.py`: RAG 的核心引擎代码。负责文档切片、Embedding 向量化映射以及 Cosine 相似度检索。
* `chroma_db/`: (自动生成) 用于存放持久化的 ChromaDB 本地向量数据库。**该目录已被配置为忽略，防止由于体积过大推送到 Git 远程仓库。**

## 数据安全原则：绝对只读

为了保护你的核心参考资料：
1. 本模块对项目根目录下的 `Reference/` 目录进行**完全只读**访问。
2. 切片后的知识向量被物理隔离并存储在 `module_rag/chroma_db/` 中。
3. 系统内置了严格的 `_validate_file_access` 逻辑，即使 Agent 下达了错误的篡改指令，本模块也会拦截并拒绝执行任何涉及原文档的写入操作。

## 核心特性

| 特性 | 描述 |
|------|------|
| **安全分块算法** | 采用基于段落 (`\n\n`) 的切片策略配合 `chunk_overlap`，在防止 PDF 断句撕裂的同时保留了技术手册的上下文语义。 |
| **增量索引机制** | 记录文件 Hash 值。当调用 `index` 时，如果手册未发生变更，则直接跳过，防止重复计算浪费算力。 |
| **开箱即用** | 无需调用 OpenAI 等在线 API。完全在本地计算 Embedding 向量，确保内部工程数据的绝对私密。 |
| **优雅降级** | 如果用户未安装 RAG 依赖或未初始化数据库，`mcp_server.py` 会捕获异常，并提示 Agent 手动查阅本地文件的路径。 |

## CLI 命令行管理

你可以直接进入项目目录并在终端执行该模块，以管理知识库：

```bash
# 1. 首次初始化 / 增量构建向量数据库（默认读取项目根目录的 Reference/plecsmanual.pdf）
python -m module_rag.rag_knowledge index

# 2. 手动测试检索效果，检查知识库质量
python -m module_rag.rag_knowledge search --query "如何编写 C-Script" --top-k 3

# 3. 查看当前知识库统计信息（切片总数、来源文件）
python -m module_rag.rag_knowledge stats

# 4. （危险）清空当前知识库并重置
python -m module_rag.rag_knowledge clear
```

## 注意事项

请确保项目根目录下存在 `Reference/` 文件夹，且内部放置了你的 `plecsmanual.pdf`，否则 RAG 模块将在初始化阶段报错退出。同时，记得在根目录的 `.gitignore` 中加入 `module_rag/chroma_db/`。
