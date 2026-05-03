#!/usr/bin/env python3
"""
RAG 知识检索模块 for PLECS MCP Server

功能：
1. 将 PLECS 官方手册 PDF 分块并向量化（只读模式，不修改原始文件）
2. 支持语义检索，根据用户问题找到最相关的内容
3. 支持多文档索引（手册 + FAQ + 最佳实践）
4. 本地运行，不依赖外部 API
"""

import json
import hashlib
import os
import sys
from typing import List, Dict, Optional, Tuple
from pathlib import Path

# ==================== 路径自动寻址 ====================
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(CURRENT_DIR)

# 将向量数据库统一存放在本模块的 chroma_db 子目录
DEFAULT_PERSIST_DIR = os.path.join(CURRENT_DIR, "chroma_db")
# 定位项目根目录下的 Reference 文件夹
DEFAULT_REFERENCE_DIR = os.path.join(BASE_DIR, "Reference")

if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)
# ======================================================

# 可选依赖导入（带友好提示）
try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False
    print("警告: PyPDF2 未安装，请运行: pip install PyPDF2")

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMER_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMER_AVAILABLE = False
    print("警告: sentence-transformers 未安装，请运行: pip install sentence-transformers")

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    print("警告: chromadb 未安装，请运行: pip install chromadb")


class PlecsRAG:
    """
    PLECS 知识检索增强生成系统
    使用本地向量数据库实现语义检索
    """
    
    # Reference 目录路径（官方文档存放位置，只读）
    REFERENCE_DIR = Path(DEFAULT_REFERENCE_DIR)
    
    def __init__(self, 
                 persist_path: str = DEFAULT_PERSIST_DIR,
                 embedding_model: str = "all-MiniLM-L6-v2",
                 chunk_size: int = 1000,
                 chunk_overlap: int = 200):
        """初始化 RAG 系统"""
        # 检查依赖
        if not all([PYPDF2_AVAILABLE, SENTENCE_TRANSFORMER_AVAILABLE, CHROMADB_AVAILABLE]):
            raise ImportError(
                "请安装所有依赖: pip install chromadb sentence-transformers PyPDF2"
            )
        
        self.persist_path = Path(persist_path)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # 创建持久化目录
        self.persist_path.mkdir(parents=True, exist_ok=True)
        
        # 初始化嵌入模型
        print(f"正在加载嵌入模型: {embedding_model}...")
        self.embedder = SentenceTransformer(embedding_model)
        print("✓ 嵌入模型加载完成")
        
        # 初始化 ChromaDB 客户端（持久化模式）
        self.client = chromadb.Client(Settings(
            persist_directory=str(self.persist_path),
            anonymized_telemetry=False
        ))
        
        # 获取或创建 collection
        self.collection_name = "plecs_documents"
        try:
            self.collection = self.client.get_collection(self.collection_name)
            print(f"✓ 连接到已有知识库，包含 {self.collection.count()} 个文档块")
        except Exception:
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            print("✓ 创建新的知识库")
        
        # 已索引文件记录
        self.indexed_files = self._load_indexed_files()
    
    def _load_indexed_files(self) -> Dict[str, Dict]:
        record_file = self.persist_path / "indexed_files.json"
        if record_file.exists():
            try:
                with open(record_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}
    
    def _save_indexed_files(self):
        record_file = self.persist_path / "indexed_files.json"
        with open(record_file, 'w') as f:
            json.dump(self.indexed_files, f, indent=2)
    
    def _get_file_hash(self, file_path: Path) -> str:
        hasher = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    
    def _is_reference_file(self, file_path: str) -> bool:
        return str(Path(file_path).absolute()).startswith(str(self.REFERENCE_DIR.absolute()))
    
    def _validate_file_access(self, file_path: str) -> Tuple[bool, str]:
        path = Path(file_path)
        if not path.exists():
            return False, f"文件不存在: {file_path}"
        
        if self._is_reference_file(file_path):
            if path.is_file():
                if not os.access(file_path, os.R_OK):
                    return False, f"文件不可读: {file_path}"
                return True, ""
            else:
                return False, f"路径不是文件: {file_path}"
        return True, ""
    
    def _safe_extract_pdf_text(self, pdf_path: Path) -> List[Tuple[int, str]]:
        pages_text = []
        try:
            with open(pdf_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page_num, page in enumerate(reader.pages, start=1):
                    try:
                        text = page.extract_text()
                        if text:
                            pages_text.append((page_num, text))
                    except Exception as e:
                        print(f"⚠ 提取第 {page_num} 页文本时出错: {e}")
                        continue
        except Exception as e:
            print(f"⚠ 读取 PDF 文件失败: {e}")
        return pages_text
    
    def _chunk_pdf(self, pdf_path: str) -> List[Dict]:
        path = Path(pdf_path)
        chunks = []
        chunk_id = 0
        pages_text = self._safe_extract_pdf_text(path)
        
        for page_num, text in pages_text:
            if not text.strip(): continue
            paragraphs = text.split('\n\n')
            current_chunk = ""
            
            for para in paragraphs:
                para = para.strip()
                if not para: continue
                if len(current_chunk) + len(para) < self.chunk_size:
                    if current_chunk:
                        current_chunk += "\n\n" + para
                    else:
                        current_chunk = para
                else:
                    if current_chunk:
                        chunks.append({
                            "id": f"chunk_{chunk_id}",
                            "text": current_chunk.strip(),
                            "page": page_num,
                            "source": str(pdf_path)
                        })
                        chunk_id += 1
                    
                    if self.chunk_overlap > 0 and current_chunk:
                        overlap_text = current_chunk[-self.chunk_overlap:]
                        current_chunk = overlap_text + "\n\n" + para
                    else:
                        current_chunk = para
            
            if current_chunk:
                chunks.append({
                    "id": f"chunk_{chunk_id}",
                    "text": current_chunk.strip(),
                    "page": page_num,
                    "source": str(pdf_path)
                })
                chunk_id += 1
        return chunks
    
    def _chunk_text_file(self, file_path: str) -> List[Dict]:
        chunks = []
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            print(f"⚠ 读取文本文件失败: {e}")
            return []
        
        paragraphs = content.split('\n\n')
        current_chunk = ""
        chunk_id = 0
        
        for para in paragraphs:
            para = para.strip()
            if not para: continue
            
            if len(current_chunk) + len(para) < self.chunk_size:
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para
            else:
                if current_chunk:
                    chunks.append({
                        "id": f"chunk_{chunk_id}",
                        "text": current_chunk.strip(),
                        "page": 0,
                        "source": str(file_path)
                    })
                    chunk_id += 1
                
                if self.chunk_overlap > 0 and current_chunk:
                    overlap_text = current_chunk[-self.chunk_overlap:]
                    current_chunk = overlap_text + "\n\n" + para
                else:
                    current_chunk = para
        
        if current_chunk:
            chunks.append({
                "id": f"chunk_{chunk_id}",
                "text": current_chunk.strip(),
                "page": 0,
                "source": str(file_path)
            })
        return chunks
    
    def index_documents(self, file_paths: List[str], force_reindex: bool = False) -> Dict:
        all_chunks = []
        skipped_count = 0
        failed_count = 0
        new_count = 0
        
        for file_path in file_paths:
            allowed, error_msg = self._validate_file_access(file_path)
            if not allowed:
                print(f"⚠ {error_msg}")
                failed_count += 1
                continue
            
            path = Path(file_path)
            file_hash = self._get_file_hash(path)
            record_key = str(path.absolute())
            if not force_reindex and record_key in self.indexed_files:
                if self.indexed_files[record_key].get("hash") == file_hash:
                    print(f"⏭ 文件未变更，跳过: {file_path}")
                    skipped_count += 1
                    continue
            
            file_ext = path.suffix.lower()
            if file_ext == '.pdf':
                chunks = self._chunk_pdf(file_path)
            elif file_ext in ['.txt', '.md']:
                chunks = self._chunk_text_file(file_path)
            else:
                print(f"⚠ 不支持的文件类型: {file_ext}，跳过: {file_path}")
                failed_count += 1
                continue
            
            if chunks:
                all_chunks.extend(chunks)
                self.indexed_files[record_key] = {
                    "hash": file_hash,
                    "source": file_path,
                    "chunk_count": len(chunks),
                    "indexed_at": self._get_timestamp()
                }
                new_count += 1
                print(f"✓ 索引 {len(chunks)} 个块: {file_path}")
            else:
                print(f"⚠ 未能从文件中提取有效内容: {file_path}")
                failed_count += 1
        
        if not all_chunks:
            return {
                "status": "success",
                "total_chunks": 0,
                "new_files": new_count,
                "skipped_files": skipped_count,
                "failed_files": failed_count,
                "message": "没有需要索引的新内容"
            }
        
        print(f"正在生成嵌入向量（共 {len(all_chunks)} 个块）...")
        texts = [chunk["text"] for chunk in all_chunks]
        embeddings = self.embedder.encode(texts, show_progress_bar=True).tolist()
        
        ids = [f"{chunk['source']}_{chunk['page']}_{i}" for i, chunk in enumerate(all_chunks)]
        metadatas = [
            {"page": chunk["page"], "source": chunk["source"]} for chunk in all_chunks
        ]
        
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas
        )
        
        self._save_indexed_files()
        print(f"✓ 索引完成！共 {len(all_chunks)} 个文档块")
        
        return {
            "status": "success",
            "total_chunks": len(all_chunks),
            "new_files": new_count,
            "skipped_files": skipped_count,
            "failed_files": failed_count,
            "files_processed": [f for f in file_paths if Path(f).exists()]
        }
    
    def _get_timestamp(self) -> str:
        from datetime import datetime
        return datetime.now().isoformat()
    
    def search(self, query: str, top_k: int = 3, min_relevance: float = 0.3) -> List[Dict]:
        if self.collection.count() == 0:
            return []
        
        query_embedding = self.embedder.encode([query]).tolist()
        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=top_k,
            include=["documents", "metadatas", "distances"]
        )
        
        formatted_results = []
        for i in range(len(results['documents'][0])):
            distance = results['distances'][0][i]
            relevance = 1 - distance
            if relevance < min_relevance:
                continue
            
            formatted_results.append({
                "content": results['documents'][0][i],
                "page": results['metadatas'][0][i]['page'],
                "source": results['metadatas'][0][i]['source'],
                "relevance_score": round(relevance, 4)
            })
        
        return formatted_results
    
    def search_with_context(self, query: str, top_k: int = 3, context_chars: int = 500) -> Dict:
        results = self.search(query, top_k)
        context_parts = []
        sources = []
        
        for r in results:
            content = r['content']
            if len(content) > context_chars:
                content = content[:context_chars] + "..."
            context_parts.append(content)
            sources.append({
                "source": r['source'],
                "page": r['page'],
                "relevance": r['relevance_score']
            })
        
        combined_context = "\n\n---\n\n".join(context_parts)
        return {
            "query": query,
            "found": len(results) > 0,
            "context": combined_context,
            "sources": sources,
            "raw_results": results
        }
    
    def get_stats(self) -> Dict:
        return {
            "total_chunks": self.collection.count(),
            "collection_name": self.collection_name,
            "persist_path": str(self.persist_path),
            "reference_dir": str(self.REFERENCE_DIR),
            "indexed_files": len(self.indexed_files),
            "files_detail": list(self.indexed_files.keys())
        }
    
    def list_reference_files(self) -> List[str]:
        if not self.REFERENCE_DIR.exists():
            return []
        reference_files = []
        for ext in ['*.pdf', '*.txt', '*.md']:
            reference_files.extend(self.REFERENCE_DIR.glob(ext))
        return [str(f.absolute()) for f in reference_files]
    
    def delete_collection(self):
        confirm = input("确认清空整个知识库？(y/N): ")
        if confirm.lower() != 'y':
            print("操作已取消")
            return
        try:
            self.client.delete_collection(self.collection_name)
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            self.indexed_files = {}
            self._save_indexed_files()
            print("✓ 知识库已清空")
        except Exception as e:
            print(f"⚠ 删除失败: {e}")


def main():
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(
        description="PLECS RAG 知识库管理工具",
        epilog="注意：本工具以只读方式访问 Reference/ 目录下的官方文档，不会修改任何原始文件"
    )
    parser.add_argument("command", choices=["index", "search", "stats", "list-ref", "clear"],
                        help="操作命令")
    parser.add_argument("--files", nargs="+", help="要索引的文件路径")
    parser.add_argument("--query", help="搜索查询")
    parser.add_argument("--top-k", type=int, default=3, help="返回结果数量")
    parser.add_argument("--force", action="store_true", help="强制重新索引")
    
    args = parser.parse_args()
    
    # 获取指向项目根目录下的 Reference 默认手册路径
    default_manual = os.path.join(DEFAULT_REFERENCE_DIR, "plecsmanual.pdf")
    
    try:
        rag = PlecsRAG()
    except ImportError as e:
        print(f"错误: {e}")
        print("请先安装依赖: pip install chromadb sentence-transformers PyPDF2")
        sys.exit(1)
    
    if args.command == "index":
        if args.files:
            files = args.files
        else:
            if Path(default_manual).exists():
                files = [default_manual]
                print(f"使用默认手册: {default_manual}")
            else:
                print(f"未找到默认手册: {default_manual}")
                print("请将 PLECS 官方手册放入根目录的 Reference/ 文件夹中")
                sys.exit(1)
        
        result = rag.index_documents(files, force_reindex=args.force)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    elif args.command == "search":
        if not args.query:
            print("请提供搜索查询: --query '你的问题'")
            sys.exit(1)
        results = rag.search(args.query, top_k=args.top_k)
        if not results:
            print("未找到相关内容")
        else:
            print(f"\n搜索: {args.query}\n")
            for i, r in enumerate(results, 1):
                source_name = Path(r['source']).name
                page_info = f"第 {r['page']} 页" if r['page'] > 0 else ""
                print(f"[{i}] 相关度: {r['relevance_score']:.3f} | 来源: {source_name} {page_info}")
                print(f"    {r['content'][:300]}...")
                print()
    
    elif args.command == "stats":
        stats = rag.get_stats()
        print(json.dumps(stats, indent=2, ensure_ascii=False))
    
    elif args.command == "list-ref":
        files = rag.list_reference_files()
        if not files:
            print("Reference/ 目录下未找到任何文档")
        else:
            print(f"Reference/ 目录下的官方文档（只读）:")
            for f in files:
                print(f"  - {Path(f).name}")
    
    elif args.command == "clear":
        rag.delete_collection()

if __name__ == "__main__":
    main()
