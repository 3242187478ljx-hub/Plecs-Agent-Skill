#!/usr/bin/env python3
"""
日志模块 for PLECS MCP Server

功能：
1. 记录所有工具调用（参数、结果、耗时）
2. 记录仿真任务生命周期
3. 支持会话管理和统计汇总
4. 自动清理过期日志

依赖安装：无需额外依赖（仅使用 Python 标准库）

使用示例：
    from logger import SimulationLogger
    
    logger = SimulationLogger(log_dir="./logs")
    
    # 记录工具调用
    logger.log_tool_call("set_parameter", {"param_name": "R_load", "value": 10.0}, "成功", True)
    
    # 记录仿真任务
    logger.log_simulation_task("task_123", "pending", {"duration": 0.01})
    logger.log_simulation_task("task_123", "completed", None, result={"voltage": 5.0})
    
    # 获取统计信息
    stats = logger.analyze_stats()
    
    # 获取优化建议
    suggestions = logger.suggest_optimizations()
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from threading import Lock
import traceback


class SimulationLogger:
    """仿真日志记录器"""
    
    # 日志文件保留天数
    DEFAULT_RETENTION_DAYS = 30
    
    # 日志格式版本
    LOG_VERSION = "2.0"
    
    def __init__(self, log_dir: str = "./logs", retention_days: int = DEFAULT_RETENTION_DAYS):
        """
        初始化日志记录器
        
        参数:
            log_dir: 日志存储目录
            retention_days: 日志保留天数
        """
        self.log_dir = Path(log_dir)
        self.retention_days = retention_days
        self.current_session_id: Optional[str] = None
        self.session_start: Optional[datetime] = None
        self._lock = Lock()
        
        # 创建日志目录
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化会话
        self._start_new_session()
        
        # 清理过期日志
        self._cleanup_old_logs()
        
        # 内存中的统计缓存
        self._stats_cache: Optional[Dict] = None
        
        print(f"✓ 日志模块已初始化 (Session: {self.current_session_id})")
    
    def _start_new_session(self):
        """开始新的会话"""
        self.current_session_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        self.session_start = datetime.now()
    
    def _get_session_file(self) -> Path:
        """获取当前会话的日志文件路径"""
        return self.log_dir / f"session_{self.current_session_id}.jsonl"
    
    def _get_meta_file(self) -> Path:
        """获取会话元数据文件路径"""
        return self.log_dir / f"session_{self.current_session_id}_meta.json"
    
    def _cleanup_old_logs(self):
        """清理过期的日志文件"""
        cutoff_time = datetime.now() - timedelta(days=self.retention_days)
        
        for log_file in self.log_dir.glob("session_*.jsonl"):
            try:
                file_mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                if file_mtime < cutoff_time:
                    log_file.unlink()
                    # 同时删除对应的元数据文件
                    meta_file = log_file.with_suffix("").with_suffix(".json") if "_meta" not in log_file.name else None
                    if meta_file and meta_file.exists():
                        meta_file.unlink()
                    print(f"✓ 已清理过期日志: {log_file.name}")
            except Exception as e:
                print(f"⚠ 清理日志文件失败 {log_file.name}: {e}")
    
    def _write_log_entry(self, entry: Dict):
        """写入日志条目（线程安全）"""
        with self._lock:
            log_file = self._get_session_file()
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    
    def _save_meta(self):
        """保存会话元数据"""
        meta = {
            "session_id": self.current_session_id,
            "started_at": self.session_start.isoformat() if self.session_start else None,
            "ended_at": datetime.now().isoformat(),
            "log_version": self.LOG_VERSION,
            "retention_days": self.retention_days
        }
        meta_file = self._get_meta_file()
        with open(meta_file, 'w', encoding='utf-8') as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)
    
    def log_tool_call(self, tool_name: str, parameters: Dict, 
                      result_summary: str, success: bool, 
                      duration_ms: float = None, error_message: str = None):
        """
        记录工具调用
        
        参数:
            tool_name: 工具名称
            parameters: 调用参数
            result_summary: 结果摘要
            success: 是否成功
            duration_ms: 执行耗时（毫秒）
            error_message: 错误信息（如果失败）
        """
        entry = {
            "type": "tool_call",
            "timestamp": datetime.now().isoformat(),
            "session_id": self.current_session_id,
            "tool": tool_name,
            "parameters": self._sanitize_parameters(parameters),
            "success": success,
            "result_summary": result_summary[:500] if result_summary else ""  # 限制摘要长度
        }
        
        if duration_ms is not None:
            entry["duration_ms"] = duration_ms
        
        if error_message:
            entry["error"] = error_message[:1000]  # 限制错误信息长度
        
        self._write_log_entry(entry)
        
        # 使缓存失效
        self._stats_cache = None
    
    def log_simulation_task(self, task_id: str, status: str, 
                            parameters: Dict = None,
                            result: Dict = None, 
                            error: str = None,
                            progress: float = None):
        """
        记录仿真任务状态变化
        
        参数:
            task_id: 任务ID
            status: 状态 (pending, running, completed, failed, cancelled)
            parameters: 任务参数
            result: 任务结果
            error: 错误信息
            progress: 进度 (0-100)
        """
        entry = {
            "type": "simulation_task",
            "timestamp": datetime.now().isoformat(),
            "session_id": self.current_session_id,
            "task_id": task_id,
            "status": status
        }
        
        if parameters:
            entry["parameters"] = self._sanitize_parameters(parameters)
        if result:
            entry["result"] = self._sanitize_result(result)
        if error:
            entry["error"] = error[:1000]
        if progress is not None:
            entry["progress"] = progress
        
        self._write_log_entry(entry)
        self._stats_cache = None
    
    def log_system_event(self, event_type: str, message: str, 
                         details: Dict = None, level: str = "INFO"):
        """
        记录系统事件
        
        参数:
            event_type: 事件类型 (startup, shutdown, config_change, error)
            message: 事件消息
            details: 详细信息
            level: 日志级别 (INFO, WARNING, ERROR)
        """
        entry = {
            "type": "system_event",
            "timestamp": datetime.now().isoformat(),
            "session_id": self.current_session_id,
            "event_type": event_type,
            "level": level,
            "message": message
        }
        
        if details:
            entry["details"] = details
        
        self._write_log_entry(entry)
    
    def _sanitize_parameters(self, params: Dict) -> Dict:
        """
        清理参数中的敏感信息
        避免记录过长的参数值
        """
        if not params:
            return {}
        
        sanitized = {}
        for key, value in params.items():
            if isinstance(value, str) and len(value) > 200:
                sanitized[key] = value[:200] + "..."
            elif isinstance(value, (list, dict)) and len(str(value)) > 500:
                sanitized[key] = f"[{type(value).__name__} with {len(str(value))} chars]"
            else:
                sanitized[key] = value
        
        return sanitized
    
    def _sanitize_result(self, result: Dict) -> Dict:
        """清理结果中的过长数据"""
        if not result:
            return {}
        
        sanitized = {}
        for key, value in result.items():
            if isinstance(value, str) and len(value) > 500:
                sanitized[key] = value[:500] + "..."
            elif isinstance(value, (list, dict)) and len(str(value)) > 1000:
                sanitized[key] = f"[{type(value).__name__} with {len(str(value))} chars]"
            else:
                sanitized[key] = value
        
        return sanitized
    
    def analyze_stats(self, session_id: str = None) -> Dict:
        """
        分析统计信息
        
        参数:
            session_id: 指定会话ID，默认当前会话
        
        返回:
            统计信息字典
        """
        # 检查缓存
        if self._stats_cache is not None:
            return self._stats_cache
        
        if session_id:
            log_file = self.log_dir / f"session_{session_id}.jsonl"
        else:
            log_file = self._get_session_file()
        
        if not log_file.exists():
            return {"error": f"日志文件不存在: {log_file.name}"}
        
        stats = {
            "session_id": session_id or self.current_session_id,
            "total_tool_calls": 0,
            "successful_tool_calls": 0,
            "failed_tool_calls": 0,
            "tool_usage": {},
            "error_counts": {},
            "total_simulations": 0,
            "simulation_status": {},
            "average_duration_ms": {},
            "session_duration_seconds": None,
            "logs_analyzed": 0
        }
        
        tool_durations = {}
        tool_call_counts = {}
        
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue
                    
                    try:
                        entry = json.loads(line)
                        stats["logs_analyzed"] += 1
                        
                        if entry.get("type") == "tool_call":
                            stats["total_tool_calls"] += 1
                            tool_name = entry.get("tool", "unknown")
                            
                            # 工具使用统计
                            stats["tool_usage"][tool_name] = stats["tool_usage"].get(tool_name, 0) + 1
                            
                            # 成功/失败统计
                            if entry.get("success"):
                                stats["successful_tool_calls"] += 1
                            else:
                                stats["failed_tool_calls"] += 1
                                error_msg = entry.get("error", "未知错误")
                                # 提取错误类型
                                error_type = error_msg[:50] if error_msg else "unknown"
                                stats["error_counts"][error_type] = stats["error_counts"].get(error_type, 0) + 1
                            
                            # 耗时统计
                            duration = entry.get("duration_ms")
                            if duration is not None:
                                if tool_name not in tool_durations:
                                    tool_durations[tool_name] = []
                                    tool_call_counts[tool_name] = 0
                                tool_durations[tool_name].append(duration)
                                tool_call_counts[tool_name] += 1
                        
                        elif entry.get("type") == "simulation_task":
                            stats["total_simulations"] += 1
                            status = entry.get("status", "unknown")
                            stats["simulation_status"][status] = stats["simulation_status"].get(status, 0) + 1
                    
                    except json.JSONDecodeError:
                        continue
            
            # 计算平均耗时
            for tool_name, durations in tool_durations.items():
                if durations:
                    avg_duration = sum(durations) / len(durations)
                    stats["average_duration_ms"][tool_name] = round(avg_duration, 2)
            
            # 计算成功率
            if stats["total_tool_calls"] > 0:
                stats["success_rate"] = round(
                    stats["successful_tool_calls"] / stats["total_tool_calls"] * 100, 2
                )
            else:
                stats["success_rate"] = 0.0
            
            # 获取会话时长
            meta_file = self.log_dir / f"session_{session_id}_meta.json" if session_id else self._get_meta_file()
            if meta_file.exists():
                try:
                    with open(meta_file, 'r') as f:
                        meta = json.load(f)
                        started = meta.get("started_at")
                        ended = meta.get("ended_at")
                        if started and ended:
                            start_time = datetime.fromisoformat(started)
                            end_time = datetime.fromisoformat(ended)
                            stats["session_duration_seconds"] = round((end_time - start_time).total_seconds(), 2)
                except:
                    pass
        
        except Exception as e:
            stats["error"] = f"分析日志失败: {e}"
        
        # 缓存结果
        self._stats_cache = stats
        return stats
    
    def suggest_optimizations(self, session_id: str = None) -> List[str]:
        """
        基于日志分析给出优化建议
        
        返回:
            优化建议列表
        """
        stats = self.analyze_stats(session_id)
        suggestions = []
        
        # 检查是否有足够的数据
        if stats.get("total_tool_calls", 0) < 10:
            suggestions.append("数据量较少（少于10次调用），建议积累更多数据后再分析优化方向")
            return suggestions
        
        # 1. 高错误率工具
        tool_usage = stats.get("tool_usage", {})
        error_counts = stats.get("error_counts", {})
        total_errors = sum(error_counts.values())
        
        if total_errors > stats.get("total_tool_calls", 1) * 0.3:
            suggestions.append(f"整体错误率较高（{stats.get('success_rate', 100)}% 成功率），建议检查 RPC 连接和参数格式")
        
        # 检查具体工具的错误率
        # 需要重新分析每个工具的错误情况
        log_file = self.log_dir / f"session_{session_id or self.current_session_id}.jsonl"
        if log_file.exists():
            tool_errors = {}
            tool_calls = {}
            
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        entry = json.loads(line)
                        if entry.get("type") == "tool_call":
                            tool = entry.get("tool", "unknown")
                            tool_calls[tool] = tool_calls.get(tool, 0) + 1
                            if not entry.get("success"):
                                tool_errors[tool] = tool_errors.get(tool, 0) + 1
                    except:
                        continue
            
            for tool, error_count in tool_errors.items():
                total = tool_calls.get(tool, 1)
                error_rate = error_count / total * 100
                if error_rate > 30 and total >= 5:
                    suggestions.append(f"工具 '{tool}' 错误率较高（{error_rate:.1f}%），建议检查该工具的调用方式和参数")
        
        # 2. 耗时过长的工具
        avg_durations = stats.get("average_duration_ms", {})
        for tool, duration in avg_durations.items():
            if duration > 5000:  # 超过5秒
                suggestions.append(f"工具 '{tool}' 平均耗时 {duration}ms，建议优化或使用异步模式")
        
        # 3. 重复的参数扫描
        if stats.get("total_simulations", 0) > 20:
            suggestions.append("检测到多次仿真任务，建议使用参数扫描批量工具以提高效率")
        
        # 4. 大量连续单参数设置
        tool_usage = stats.get("tool_usage", {})
        single_sets = tool_usage.get("set_parameter", 0)
        batch_sets = tool_usage.get("set_parameters_batch", 0)
        if single_sets > 10 and batch_sets == 0:
            suggestions.append(f"检测到 {single_sets} 次单参数设置，建议使用 set_parameters_batch 批量设置提高效率")
        
        # 5. 搜索结果为空的情况
        # 需要额外分析 search_knowledge 工具的效果
        
        if not suggestions:
            suggestions.append("当前使用情况良好，暂无优化建议")
        
        return suggestions
    
    def export_session(self, session_id: str = None, output_path: str = None) -> str:
        """
        导出会话日志
        
        参数:
            session_id: 会话ID，默认当前会话
            output_path: 输出文件路径，默认返回JSON字符串
        
        返回:
            导出的JSON字符串或文件路径
        """
        if session_id:
            log_file = self.log_dir / f"session_{session_id}.jsonl"
        else:
            log_file = self._get_session_file()
        
        if not log_file.exists():
            return json.dumps({"error": f"日志文件不存在: {log_file.name}"})
        
        logs = []
        with open(log_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    try:
                        logs.append(json.loads(line))
                    except:
                        continue
        
        export_data = {
            "exported_at": datetime.now().isoformat(),
            "session_id": session_id or self.current_session_id,
            "log_version": self.LOG_VERSION,
            "total_entries": len(logs),
            "logs": logs
        }
        
        if output_path:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            return str(output_file)
        else:
            return json.dumps(export_data, indent=2, ensure_ascii=False)
    
    def get_recent_errors(self, limit: int = 10) -> List[Dict]:
        """
        获取最近的错误记录
        
        参数:
            limit: 返回的最大记录数
        
        返回:
            错误记录列表
        """
        errors = []
        log_file = self._get_session_file()
        
        if not log_file.exists():
            return errors
        
        # 从文件末尾读取（最近的在后面）
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        for line in reversed(lines):
            if len(errors) >= limit:
                break
            
            if not line.strip():
                continue
            
            try:
                entry = json.loads(line)
                if entry.get("type") == "tool_call" and not entry.get("success"):
                    errors.append({
                        "timestamp": entry.get("timestamp"),
                        "tool": entry.get("tool"),
                        "error": entry.get("error", "未知错误"),
                        "parameters": entry.get("parameters", {})
                    })
                elif entry.get("type") == "simulation_task" and entry.get("status") == "failed":
                    errors.append({
                        "timestamp": entry.get("timestamp"),
                        "task_id": entry.get("task_id"),
                        "error": entry.get("error", "未知错误")
                    })
            except:
                continue
        
        return errors
    
    def close(self):
        """关闭日志记录器，保存元数据"""
        self._save_meta()
        print(f"✓ 日志会话已关闭: {self.current_session_id}")


# 全局日志单例（可选）
_default_logger: Optional[SimulationLogger] = None


def get_logger(log_dir: str = "./logs") -> SimulationLogger:
    """获取全局日志记录器实例（单例模式）"""
    global _default_logger
    if _default_logger is None:
        _default_logger = SimulationLogger(log_dir)
    return _default_logger


# ==================== 命令行入口 ====================

def main():
    """命令行入口，用于查看日志统计"""
    import argparse
    
    parser = argparse.ArgumentParser(description="PLECS MCP 日志分析工具")
    parser.add_argument("--log-dir", default="./logs", help="日志目录路径")
    parser.add_argument("--session", help="指定会话ID")
    parser.add_argument("--stats", action="store_true", help="显示统计信息")
    parser.add_argument("--suggest", action="store_true", help="显示优化建议")
    parser.add_argument("--errors", type=int, default=10, help="显示最近的错误记录数")
    parser.add_argument("--export", help="导出会话日志到指定文件")
    
    args = parser.parse_args()
    
    logger = SimulationLogger(log_dir=args.log_dir)
    
    if args.stats:
        stats = logger.analyze_stats(args.session)
        print(json.dumps(stats, indent=2, ensure_ascii=False))
    
    if args.suggest:
        suggestions = logger.suggest_optimizations(args.session)
        print("\n优化建议:")
        for i, s in enumerate(suggestions, 1):
            print(f"  {i}. {s}")
    
    if args.errors:
        errors = logger.get_recent_errors(args.errors)
        if errors:
            print(f"\n最近 {len(errors)} 条错误:")
            for e in errors:
                print(f"  [{e.get('timestamp', 'N/A')}] {e.get('tool', 'system')}: {e.get('error', 'unknown')[:100]}")
        else:
            print("\n暂无错误记录")
    
    if args.export:
        output = logger.export_session(args.session, args.export)
        print(f"日志已导出到: {output}")
    
    logger.close()


if __name__ == "__main__":
    import json
    main()
