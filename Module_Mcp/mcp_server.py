#!/usr/bin/env python3
"""
PLECS MCP Server - 完整增强版
支持真正的 PLECS RPC 通信、批量操作、预设管理、状态持久化
"""

import json
import asyncio
import uuid
import socket
import pickle
import hashlib
import os
import sys
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from collections import deque
import threading

# ==================== 路径与模块寻址 ====================
# 获取当前 mcp_server.py 所在目录 (module_mcp)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# 获取项目根目录
BASE_DIR = os.path.dirname(CURRENT_DIR)
# 将根目录加入系统路径，确保能跨模块导入 module_logger 和 module_rag
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

# 预设 mcp_cache 文件夹
CACHE_DIR = os.path.join(CURRENT_DIR, "mcp_cache")
os.makedirs(CACHE_DIR, exist_ok=True)
# ========================================================

# MCP 协议相关
try:
    from mcp.server import Server
    from mcp.server.models import InitializationOptions
    import mcp.server.stdio
    import mcp.types as types
except ImportError:
    print("请先安装 mcp: pip install mcp")
    exit(1)

# 可选依赖
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

try:
    from module_rag.rag_knowledge import PlecsRAG
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False

try:
    from module_logger.logger import get_logger
    LOGGER_AVAILABLE = True
except ImportError:
    LOGGER_AVAILABLE = False


@dataclass
class SimulationTask:
    """异步仿真任务数据结构"""
    task_id: str
    status: str  # pending, running, completed, failed, cancelled
    parameters: Dict[str, Any]
    result: Optional[Dict] = None
    error_message: Optional[str] = None
    created_at: datetime = None
    started_at: datetime = None
    completed_at: datetime = None
    progress: float = 0.0  # 仿真进度 0-100
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


@dataclass
class SimulationPreset:
    """仿真预设配置"""
    name: str
    description: str
    parameters: Dict[str, float]
    created_at: datetime = field(default_factory=datetime.now)
    last_used: datetime = None


class PlecsRPCClient:
    """真正的 PLECS RPC 客户端"""
    
    def __init__(self, host: str = "localhost", port: int = 1080, timeout: float = 30.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._socket = None
        self._lock = threading.Lock()
        
    def connect(self) -> bool:
        """建立 RPC 连接"""
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(self.timeout)
            self._socket.connect((self.host, self.port))
            return True
        except Exception as e:
            print(f"RPC 连接失败: {e}")
            return False
    
    def disconnect(self):
        """断开连接"""
        if self._socket:
            self._socket.close()
            self._socket = None
    
    def call(self, command: str, params: Dict = None) -> Dict:
        """
        调用 PLECS RPC 命令
        RPC 协议格式: JSON 命令 + 换行符
        """
        if not self._socket:
            if not self.connect():
                return {"status": "error", "message": "RPC 连接失败，请确保 PLECS Standalone 已启动且 RPC 端口已开启"}
        
        with self._lock:
            try:
                # 构建命令
                cmd = {
                    "command": command,
                    "params": params or {},
                    "id": str(uuid.uuid4())
                }
                cmd_str = json.dumps(cmd) + "\n"
                
                # 发送
                self._socket.sendall(cmd_str.encode('utf-8'))
                
                # 接收响应
                response_data = b""
                while True:
                    chunk = self._socket.recv(4096)
                    if not chunk:
                        break
                    response_data += chunk
                    if b"\n" in response_data:
                        break
                
                response = json.loads(response_data.decode('utf-8'))
                return response
                
            except socket.timeout:
                return {"status": "error", "message": f"RPC 调用超时 ({self.timeout}s)"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
    
    def is_connected(self) -> bool:
        """检查连接状态"""
        return self._socket is not None
    
    def get_model_variables_rpc(self, model_path: str) -> Dict:
        """通过 RPC 获取模型变量"""
        return self.call("get_variables", {"model_path": model_path})
    
    def set_parameter_rpc(self, param_name: str, value: float) -> Dict:
        """设置参数"""
        return self.call("set_parameter", {"name": param_name, "value": value})
    
    def set_parameters_batch_rpc(self, params: Dict[str, float]) -> Dict:
        """批量设置参数"""
        return self.call("set_parameters_batch", {"parameters": params})
    
    def simulate_rpc(self, duration: float = None, step: float = None, 
                     variables: List[str] = None) -> Dict:
        """运行仿真"""
        cmd_params = {}
        if duration:
            cmd_params["duration"] = duration
        if step:
            cmd_params["step"] = step
        if variables:
            cmd_params["variables"] = variables
        return self.call("simulate", cmd_params)
    
    def get_waveform_rpc(self, variable_name: str) -> Dict:
        """获取波形数据"""
        return self.call("get_waveform", {"variable": variable_name})
    
    def load_model_rpc(self, model_path: str) -> Dict:
        """加载模型"""
        return self.call("load_model", {"path": model_path})


class PlecsMCPEnhanced:
    """PLECS MCP 增强版服务器核心类"""
    
    def __init__(self, config_path: str = None):
        # 配置
        self.config = self._load_config(config_path)
        
        # RPC 客户端
        self.rpc_client = PlecsRPCClient(
            host=self.config.get("plecs_host", "localhost"),
            port=self.config.get("plecs_port", 1080),
            timeout=self.config.get("rpc_timeout", 30.0)
        )
        
        # 状态管理
        self.current_model_path: Optional[str] = None
        self.current_model_info: Optional[Dict] = None
        self.task_queue: Dict[str, SimulationTask] = {}
        self.task_history: deque = deque(maxlen=100)  # 保留最近100个任务
        self.presets: Dict[str, SimulationPreset] = {}
        self.result_cache: Dict[str, Dict] = {}  # 参数组合哈希 -> 结果
        self.cache_max_size = 100
        
        # 会话管理
        self.session_id = str(uuid.uuid4())
        self.session_start = datetime.now()
        
        # 初始化 RAG
        self.rag = None
        if RAG_AVAILABLE and self.config.get("rag_enabled", True):
            try:
                self.rag = PlecsRAG()
                print("✓ RAG 知识库已初始化")
            except Exception as e:
                print(f"⚠ RAG 初始化失败: {e}")
        
        # 初始化日志 (对接 module_logger 模块)
        self.logger = None
        if LOGGER_AVAILABLE and self.config.get("logging_enabled", True):
            try:
                self.logger = get_logger()
                print("✓ 日志模块已加载")
            except Exception as e:
                print(f"⚠ 日志模块加载失败: {e}")
        
        # 加载预设
        self._load_presets()
        
        # 后台任务
        self._background_tasks = set()
        
        # 统计信息
        self.stats = {
            "total_simulations": 0,
            "successful_simulations": 0,
            "failed_simulations": 0,
            "total_tokens_estimated": 0,
            "tool_calls": {}
        }
        
        print(f"✓ PLECS MCP Server 已启动 (Session: {self.session_id[:8]})")
    
    def _load_config(self, config_path: str = None) -> Dict:
        """加载配置 (文件落盘指向 cache 目录)"""
        default_config = {
            "plecs_host": "localhost",
            "plecs_port": 1080,
            "rpc_timeout": 30.0,
            "rag_enabled": True,
            "logging_enabled": True,
            "cache_enabled": True,
            "max_retries": 3,
            "retry_delay": 1.0,
            "presets_file": os.path.join(CACHE_DIR, "presets.json"),
            "state_file": os.path.join(CACHE_DIR, "session_state.pkl")
        }
        
        if config_path and Path(config_path).exists():
            with open(config_path, 'r') as f:
                user_config = json.load(f)
                default_config.update(user_config)
        
        return default_config
    
    def _load_presets(self):
        """加载预设配置"""
        presets_file = Path(self.config.get("presets_file"))
        if presets_file.exists():
            try:
                with open(presets_file, 'r') as f:
                    data = json.load(f)
                    for name, preset_data in data.items():
                        self.presets[name] = SimulationPreset(
                            name=name,
                            description=preset_data.get("description", ""),
                            parameters=preset_data["parameters"],
                            created_at=datetime.fromisoformat(preset_data["created_at"]) if "created_at" in preset_data else datetime.now()
                        )
                print(f"✓ 加载了 {len(self.presets)} 个预设配置")
            except Exception as e:
                print(f"⚠ 加载预设失败: {e}")
    
    def _save_presets(self):
        """保存预设配置"""
        presets_file = Path(self.config.get("presets_file"))
        try:
            data = {}
            for name, preset in self.presets.items():
                data[name] = {
                    "description": preset.description,
                    "parameters": preset.parameters,
                    "created_at": preset.created_at.isoformat()
                }
            with open(presets_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"⚠ 保存预设失败: {e}")
    
    def _log_tool_call(self, tool_name: str, params: Dict, success: bool, result_summary: str = ""):
        """记录工具调用日志"""
        # 更新统计
        self.stats["tool_calls"][tool_name] = self.stats["tool_calls"].get(tool_name, 0) + 1
        
        # 估算 Token 消耗（粗略）
        approx_tokens = len(json.dumps(params)) // 4 + len(result_summary) // 4
        self.stats["total_tokens_estimated"] += approx_tokens
        
        # 写入日志
        if self.logger:
            self.logger.log_tool_call(tool_name, params, result_summary, success)
    
    def _get_cache_key(self, param_name: str, value: float, target_metric: str) -> str:
        """生成缓存键"""
        key_str = f"{param_name}={value}|{target_metric}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _cache_result(self, key: str, result: Dict):
        """缓存仿真结果"""
        if not self.config.get("cache_enabled", True):
            return
        
        if len(self.result_cache) >= self.cache_max_size:
            # 删除最早的20%
            keys_to_remove = list(self.result_cache.keys())[:20]
            for k in keys_to_remove:
                del self.result_cache[k]
        
        self.result_cache[key] = {
            "result": result,
            "timestamp": datetime.now().isoformat()
        }
    
    def _get_cached_result(self, key: str) -> Optional[Dict]:
        """获取缓存结果"""
        if not self.config.get("cache_enabled", True):
            return None
        
        cached = self.result_cache.get(key)
        if cached:
            return cached["result"]
        return None
    
    # ==================== 核心工具方法 ====================
    
    async def ensure_rpc_connection(self) -> Tuple[bool, str]:
        """确保 RPC 连接可用"""
        if not self.rpc_client.is_connected():
            if not self.rpc_client.connect():
                return False, "无法连接到 PLECS Standalone，请确保：\n1. PLECS Standalone 已启动\n2. Preferences -> General -> RPC interface port 已勾选并设置为 1080"
        return True, ""
    
    async def load_plecs_model(self, model_path: str) -> Dict:
        """加载 PLECS 模型"""
        # 检查连接
        ok, msg = await self.ensure_rpc_connection()
        if not ok:
            return {"status": "error", "message": msg}
        
        if not Path(model_path).exists():
            return {"status": "error", "message": f"模型文件不存在: {model_path}"}
        
        # 尝试加载，带重试
        last_error = None
        for attempt in range(self.config.get("max_retries", 3)):
            result = self.rpc_client.load_model_rpc(model_path)
            if result.get("status") == "success":
                self.current_model_path = model_path
                self.current_model_info = {
                    "path": model_path,
                    "loaded_at": datetime.now().isoformat(),
                    "name": Path(model_path).stem
                }
                return {"status": "success", "message": f"已加载模型: {model_path}", "model_info": self.current_model_info}
            last_error = result.get("message", "未知错误")
            if attempt < self.config.get("max_retries", 3) - 1:
                await asyncio.sleep(self.config.get("retry_delay", 1.0))
        
        return {"status": "error", "message": f"加载模型失败: {last_error}"}
    
    async def get_model_variables(self, model_path: str = None, refresh: bool = False) -> Dict:
        """获取模型中所有可调参数"""
        path = model_path or self.current_model_path
        if not path:
            return {"status": "error", "message": "未加载模型，请先调用 load_plecs_model"}
        
        ok, msg = await self.ensure_rpc_connection()
        if not ok:
            return {"status": "error", "message": msg}
        
        result = self.rpc_client.get_model_variables_rpc(path)
        
        if result.get("status") == "success":
            # 格式化返回值
            variables = result.get("variables", [])
            return {
                "status": "success",
                "variables": variables,
                "count": len(variables),
                "model": path
            }
        
        return {"status": "error", "message": result.get("message", "获取变量失败")}
    
    async def set_parameter(self, param_name: str, value: float, verify: bool = True) -> Dict:
        """设置单个参数值"""
        if not self.current_model_path:
            return {"status": "error", "message": "未加载模型，请先调用 load_plecs_model"}
        
        ok, msg = await self.ensure_rpc_connection()
        if not ok:
            return {"status": "error", "message": msg}
        
        result = self.rpc_client.set_parameter_rpc(param_name, value)
        
        if result.get("status") == "success":
            # 如果需要验证，读取回来确认
            verified_value = None
            if verify:
                verify_result = await self.get_model_variables()
                if verify_result.get("status") == "success":
                    for var in verify_result.get("variables", []):
                        if var.get("name") == param_name:
                            verified_value = var.get("current")
            
            return {
                "status": "success",
                "parameter": param_name,
                "set_value": value,
                "verified_value": verified_value,
                "match": verified_value is None or abs(verified_value - value) < 1e-6
            }
        
        return {"status": "error", "message": result.get("message", "设置参数失败")}
    
    async def set_parameters_batch(self, parameters: Dict[str, float]) -> Dict:
        """批量设置多个参数"""
        if not self.current_model_path:
            return {"status": "error", "message": "未加载模型，请先调用 load_plecs_model"}
        
        ok, msg = await self.ensure_rpc_connection()
        if not ok:
            return {"status": "error", "message": msg}
        
        results = []
        for param_name, value in parameters.items():
            result = await self.set_parameter(param_name, value, verify=False)
            results.append({
                "parameter": param_name,
                "value": value,
                "success": result.get("status") == "success",
                "error": result.get("message") if result.get("status") != "success" else None
            })
        
        success_count = sum(1 for r in results if r["success"])
        
        return {
            "status": "success" if success_count == len(parameters) else "partial",
            "total": len(parameters),
            "success_count": success_count,
            "results": results
        }
    
    async def run_simulation_async(self, duration: float = None, step: float = None,
                                   variables: List[str] = None, callback_url: str = None) -> Dict:
        """
        异步运行仿真，立即返回 task_id
        """
        if not self.current_model_path:
            return {"status": "error", "message": "未加载模型，请先调用 load_plecs_model"}
        
        ok, msg = await self.ensure_rpc_connection()
        if not ok:
            return {"status": "error", "message": msg}
        
        task_id = str(uuid.uuid4())
        task = SimulationTask(
            task_id=task_id,
            status="pending",
            parameters={
                "duration": duration,
                "step": step,
                "variables": variables,
                "callback_url": callback_url
            }
        )
        self.task_queue[task_id] = task
        self.stats["total_simulations"] += 1
        
        # 启动后台仿真任务
        background_task = asyncio.create_task(self._execute_simulation(task_id, duration, step, variables))
        self._background_tasks.add(background_task)
        background_task.add_done_callback(self._background_tasks.discard)
        
        return {
            "status": "pending",
            "task_id": task_id,
            "message": "仿真已提交，请使用 get_simulation_result 查询结果"
        }
    
    async def _execute_simulation(self, task_id: str, duration: float, step: float, variables: List[str]):
        """后台执行仿真"""
        task = self.task_queue[task_id]
        task.status = "running"
        task.started_at = datetime.now()
        
        try:
            # 执行仿真
            result = self.rpc_client.simulate_rpc(duration, step, variables)
            
            if result.get("status") == "success":
                task.status = "completed"
                task.result = result.get("results", {})
                self.stats["successful_simulations"] += 1
            else:
                task.status = "failed"
                task.error_message = result.get("message", "仿真失败")
                self.stats["failed_simulations"] += 1
            
            task.completed_at = datetime.now()
            
            # 记录历史
            self.task_history.append({
                "task_id": task_id,
                "params": asdict(task.parameters),
                "status": task.status,
                "duration_ms": (task.completed_at - task.started_at).total_seconds() * 1000 if task.completed_at and task.started_at else 0
            })
            
        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)
            task.completed_at = datetime.now()
            self.stats["failed_simulations"] += 1
    
    async def get_simulation_result(self, task_id: str, wait: bool = False, timeout: float = 60.0) -> Dict:
        """获取异步仿真结果"""
        task = self.task_queue.get(task_id)
        if not task:
            return {"status": "error", "message": f"任务不存在: {task_id}"}
        
        # 如果需要等待完成
        if wait and task.status in ["pending", "running"]:
            start = datetime.now()
            while task.status in ["pending", "running"]:
                if (datetime.now() - start).total_seconds() > timeout:
                    return {
                        "task_id": task_id,
                        "status": task.status,
                        "progress": task.progress,
                        "message": f"等待超时 ({timeout}s)，请稍后再次查询"
                    }
                await asyncio.sleep(0.5)
        
        response = {
            "task_id": task_id,
            "status": task.status,
            "progress": task.progress
        }
        
        if task.status == "completed":
            response["result"] = task.result
        elif task.status == "failed":
            response["error"] = task.error_message
        
        return response
    
    async def scan_parameters(self, param_name: str, start: float, end: float,
                              steps: int, target_metric: str, minimize: bool = True,
                              parallel: bool = False) -> Dict:
        """
        服务端参数扫描
        支持串行和并行两种模式
        """
        if not self.current_model_path:
            return {"status": "error", "message": "未加载模型，请先调用 load_plecs_model"}
        
        step_size = (end - start) / steps
        param_values = [start + i * step_size for i in range(steps + 1)]
        
        # 检查缓存
        cached_results = []
        uncached_values = []
        for value in param_values:
            cache_key = self._get_cache_key(param_name, value, target_metric)
            cached = self._get_cached_result(cache_key)
            if cached:
                cached_results.append({
                    "value": value,
                    target_metric: cached.get(target_metric),
                    "cached": True
                })
            else:
                uncached_values.append(value)
        
        # 扫描未缓存的值
        if uncached_values:
            if parallel:
                # 并行执行（注意：PLECS RPC 可能不支持并发）
                tasks = []
                for value in uncached_values:
                    # 设置参数
                    set_result = await self.set_parameter(param_name, value)
                    if set_result.get("status") != "success":
                        continue
                    # 运行仿真
                    sim_result = await self.run_simulation_async()
                    if sim_result.get("status") == "pending":
                        tasks.append((value, sim_result["task_id"]))
                
                # 等待所有完成
                scan_results = []
                for value, task_id in tasks:
                    result = await self.get_simulation_result(task_id, wait=True)
                    metric_value = result.get("result", {}).get(target_metric) if result.get("status") == "completed" else None
                    scan_results.append({
                        "value": value,
                        target_metric: metric_value,
                        "status": result.get("status")
                    })
                    
                    # 缓存结果
                    if metric_value is not None:
                        cache_key = self._get_cache_key(param_name, value, target_metric)
                        self._cache_result(cache_key, {target_metric: metric_value})
            else:
                # 串行执行
                scan_results = []
                for value in uncached_values:
                    # 设置参数
                    set_result = await self.set_parameter(param_name, value)
                    if set_result.get("status") != "success":
                        scan_results.append({
                            "value": value,
                            target_metric: None,
                            "status": "failed",
                            "error": set_result.get("message")
                        })
                        continue
                    
                    # 运行仿真
                    sim_result = await self.run_simulation_async()
                    if sim_result.get("status") != "pending":
                        scan_results.append({
                            "value": value,
                            target_metric: None,
                            "status": "failed",
                            "error": sim_result.get("message")
                        })
                        continue
                    
                    result = await self.get_simulation_result(sim_result["task_id"], wait=True)
                    metric_value = result.get("result", {}).get(target_metric) if result.get("status") == "completed" else None
                    scan_results.append({
                        "value": value,
                        target_metric: metric_value,
                        "status": result.get("status")
                    })
                    
                    # 缓存结果
                    if metric_value is not None:
                        cache_key = self._get_cache_key(param_name, value, target_metric)
                        self._cache_result(cache_key, {target_metric: metric_value})
        else:
            scan_results = []
        
        # 合并缓存和扫描结果
        all_results = cached_results + scan_results
        all_results.sort(key=lambda x: x["value"])
        
        # 找出最优值
        valid_results = [r for r in all_results if r.get(target_metric) is not None]
        if not valid_results:
            return {"status": "error", "message": "没有成功的仿真结果"}
        
        if minimize:
            optimal = min(valid_results, key=lambda x: x[target_metric])
        else:
            optimal = max(valid_results, key=lambda x: x[target_metric])
        
        return {
            "status": "success",
            "param_name": param_name,
            "scan_range": {"start": start, "end": end, "steps": steps},
            "results": all_results,
            "optimal": {
                "value": optimal["value"],
                f"{target_metric}": optimal[target_metric]
            },
            "cached_count": len(cached_results),
            "scanned_count": len(scan_results)
        }
    
    async def analyze_waveform(self, variable_name: str, metrics: List[str] = None,
                               time_range: Tuple[float, float] = None) -> Dict:
        """
        分析仿真波形
        支持指标: steady_state, ripple_pp, thd, fft, rise_time, overshoot, settling_time
        """
        if metrics is None:
            metrics = ["steady_state", "ripple_pp"]
        
        ok, msg = await self.ensure_rpc_connection()
        if not ok:
            return {"status": "error", "message": msg}
        
        # 获取波形数据
        waveform_result = self.rpc_client.get_waveform_rpc(variable_name)
        
        if waveform_result.get("status") != "success":
            return {"status": "error", "message": f"获取波形失败: {waveform_result.get('message')}"}
        
        waveform_data = waveform_result.get("data", [])
        time_data = waveform_result.get("time", [])
        
        if not waveform_data:
            return {"status": "error", "message": f"变量 {variable_name} 无数据"}
        
        analysis_results = {}
        
        for metric in metrics:
            if metric == "steady_state":
                # 稳态值：取最后 20% 数据的平均值
                steady_start = int(len(waveform_data) * 0.8)
                steady_values = waveform_data[steady_start:]
                analysis_results[metric] = sum(steady_values) / len(steady_values) if steady_values else None
            
            elif metric == "ripple_pp":
                # 纹波峰峰值
                analysis_results[metric] = max(waveform_data) - min(waveform_data)
            
            elif metric == "overshoot" and time_range:
                # 过冲：需要设定目标值
                target = time_range[1] if len(time_range) > 1 else None
                if target:
                    max_val = max(waveform_data)
                    analysis_results[metric] = ((max_val - target) / target) * 100 if target != 0 else None
            
            elif metric == "rise_time" and time_range:
                # 上升时间：10% 到 90%
                target = time_range[1] if len(time_range) > 1 else None
                if target and time_data:
                    min_val = min(waveform_data)
                    target_range = target - min_val
                    if target_range != 0:
                        threshold_10 = min_val + 0.1 * target_range
                        threshold_90 = min_val + 0.9 * target_range
                        # 查找时间点
                        time_10 = None
                        time_90 = None
                        for i, val in enumerate(waveform_data):
                            if time_10 is None and val >= threshold_10:
                                time_10 = time_data[i]
                            if time_90 is None and val >= threshold_90:
                                time_90 = time_data[i]
                            if time_10 and time_90:
                                break
                        if time_10 and time_90:
                            analysis_results[metric] = time_90 - time_10
        
        return {
            "status": "success",
            "variable": variable_name,
            "metrics": analysis_results,
            "data_points": len(waveform_data)
        }
    
    async def search_knowledge(self, query: str, top_k: int = 3) -> Dict:
        """检索知识库（RAG）"""
        if not RAG_AVAILABLE or not self.rag:
            # 提供本地手册路径作为备选
            manual_path = Path("Reference/plecsmanual.pdf")
            if manual_path.exists():
                return {
                    "status": "fallback",
                    "message": f"RAG 未初始化，请手动查阅 {manual_path} 中关于 '{query}' 的内容",
                    "manual_path": str(manual_path)
                }
            return {
                "status": "error",
                "message": "RAG 知识库未初始化，请先运行: python -c 'from rag_knowledge import PlecsRAG; rag = PlecsRAG(); rag.index_documents([\"Reference/plecsmanual.pdf\"])'"
            }
        
        try:
            results = self.rag.search(query, top_k)
            return {
                "status": "success",
                "query": query,
                "results": results,
                "total_found": len(results)
            }
        except Exception as e:
            return {"status": "error", "message": f"检索失败: {e}"}
    
    async def save_preset(self, name: str, description: str, parameters: Dict[str, float]) -> Dict:
        """保存当前参数组合为预设"""
        if not parameters:
            return {"status": "error", "message": "参数不能为空"}
        
        preset = SimulationPreset(
            name=name,
            description=description,
            parameters=parameters
        )
        self.presets[name] = preset
        self._save_presets()
        
        return {
            "status": "success",
            "message": f"已保存预设: {name}",
            "preset": {
                "name": name,
                "description": description,
                "parameters": parameters,
                "parameter_count": len(parameters)
            }
        }
    
    async def load_preset(self, name: str) -> Dict:
        """加载预设参数"""
        preset = self.presets.get(name)
        if not preset:
            return {"status": "error", "message": f"预设不存在: {name}"}
        
        # 应用预设参数
        result = await self.set_parameters_batch(preset.parameters)
        
        # 更新最后使用时间
        preset.last_used = datetime.now()
        self._save_presets()
        
        return {
            "status": "success",
            "preset_name": name,
            "description": preset.description,
            "parameters": preset.parameters,
            "apply_result": result
        }
    
    async def list_presets(self) -> Dict:
        """列出所有预设"""
        presets_info = []
        for name, preset in self.presets.items():
            presets_info.append({
                "name": name,
                "description": preset.description,
                "parameter_count": len(preset.parameters),
                "created_at": preset.created_at.isoformat(),
                "last_used": preset.last_used.isoformat() if preset.last_used else None
            })
        
        return {
            "status": "success",
            "count": len(presets_info),
            "presets": presets_info
        }
    
    async def delete_preset(self, name: str) -> Dict:
        """删除预设"""
        if name not in self.presets:
            return {"status": "error", "message": f"预设不存在: {name}"}
        
        del self.presets[name]
        self._save_presets()
        
        return {"status": "success", "message": f"已删除预设: {name}"}
    
    async def get_statistics(self) -> Dict:
        """获取统计信息"""
        return {
            "status": "success",
            "session": {
                "session_id": self.session_id,
                "started_at": self.session_start.isoformat(),
                "uptime_seconds": (datetime.now() - self.session_start).total_seconds()
            },
            "simulations": {
                "total": self.stats["total_simulations"],
                "successful": self.stats["successful_simulations"],
                "failed": self.stats["failed_simulations"],
                "success_rate": (self.stats["successful_simulations"] / self.stats["total_simulations"] * 100) if self.stats["total_simulations"] > 0 else 0
            },
            "cache": {
                "size": len(self.result_cache),
                "max_size": self.cache_max_size
            },
            "presets": {
                "count": len(self.presets)
            },
            "estimated_tokens": self.stats["total_tokens_estimated"],
            "tool_calls": self.stats["tool_calls"]
        }
    
    async def cancel_simulation(self, task_id: str) -> Dict:
        """取消正在运行的仿真"""
        task = self.task_queue.get(task_id)
        if not task:
            return {"status": "error", "message": f"任务不存在: {task_id}"}
        
        if task.status not in ["pending", "running"]:
            return {"status": "error", "message": f"任务状态为 {task.status}，无法取消"}
        
        task.status = "cancelled"
        task.completed_at = datetime.now()
        
        return {"status": "success", "message": f"已取消任务: {task_id}"}
    
    async def clear_cache(self) -> Dict:
        """清空结果缓存"""
        cache_size = len(self.result_cache)
        self.result_cache.clear()
        return {"status": "success", "message": f"已清空 {cache_size} 条缓存"}


# ==================== MCP 服务器初始化 ====================

app = Server("plecs-mcp-server-v2")
plecs_service = PlecsMCPEnhanced()


@app.list_tools()
async def handle_list_tools() -> List[types.Tool]:
    """列出所有可用工具"""
    return [
        types.Tool(
            name="load_plecs_model",
            description="加载 PLECS 模型文件",
            inputSchema={
                "type": "object",
                "properties": {
                    "model_path": {"type": "string", "description": ".plecs 文件的绝对路径"}
                },
                "required": ["model_path"]
            }
        ),
        types.Tool(
            name="get_model_variables",
            description="获取当前模型中所有可调参数及其当前值、类型和有效范围",
            inputSchema={
                "type": "object",
                "properties": {
                    "model_path": {"type": "string", "description": "可选，模型路径"},
                    "refresh": {"type": "boolean", "description": "是否强制刷新"}
                }
            }
        ),
        types.Tool(
            name="set_parameter",
            description="设置单个模型参数的数值",
            inputSchema={
                "type": "object",
                "properties": {
                    "param_name": {"type": "string", "description": "参数名称"},
                    "value": {"type": "number", "description": "参数值"},
                    "verify": {"type": "boolean", "description": "是否验证设置成功", "default": True}
                },
                "required": ["param_name", "value"]
            }
        ),
        types.Tool(
            name="set_parameters_batch",
            description="批量设置多个参数",
            inputSchema={
                "type": "object",
                "properties": {
                    "parameters": {"type": "object", "description": "参数名:值 的字典"}
                },
                "required": ["parameters"]
            }
        ),
        types.Tool(
            name="run_simulation_async",
            description="异步运行仿真，立即返回任务ID，不阻塞对话",
            inputSchema={
                "type": "object",
                "properties": {
                    "duration": {"type": "number", "description": "仿真时长"},
                    "step": {"type": "number", "description": "仿真步长"},
                    "variables": {"type": "array", "items": {"type": "string"}, "description": "需要记录的变量"}
                }
            }
        ),
        types.Tool(
            name="get_simulation_result",
            description="根据任务ID获取异步仿真的结果或状态",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "仿真任务ID"},
                    "wait": {"type": "boolean", "description": "是否等待完成", "default": False},
                    "timeout": {"type": "number", "description": "等待超时时间（秒）", "default": 60.0}
                },
                "required": ["task_id"]
            }
        ),
        types.Tool(
            name="scan_parameters",
            description="服务端执行参数扫描，一次性完成多组仿真并返回最优结果",
            inputSchema={
                "type": "object",
                "properties": {
                    "param_name": {"type": "string", "description": "要扫描的参数名称"},
                    "start": {"type": "number", "description": "扫描起始值"},
                    "end": {"type": "number", "description": "扫描结束值"},
                    "steps": {"type": "integer", "description": "步数"},
                    "target_metric": {"type": "string", "description": "目标指标名称"},
                    "minimize": {"type": "boolean", "description": "是否最小化目标指标", "default": True},
                    "parallel": {"type": "boolean", "description": "是否并行执行", "default": False}
                },
                "required": ["param_name", "start", "end", "steps", "target_metric"]
            }
        ),
        types.Tool(
            name="analyze_waveform",
            description="分析仿真波形，支持稳态值、纹波、THD、上升时间、过冲等多种指标",
            inputSchema={
                "type": "object",
                "properties": {
                    "variable_name": {"type": "string", "description": "要分析的变量名称"},
                    "metrics": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "指标列表: steady_state, ripple_pp, overshoot, rise_time, settling_time"
                    },
                    "time_range": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "[start, end] 时间范围，用于指标计算"
                    }
                },
                "required": ["variable_name"]
            }
        ),
        types.Tool(
            name="search_knowledge",
            description="从 PLECS 手册和历史经验库中检索相关知识",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"},
                    "top_k": {"type": "integer", "description": "返回结果数量", "default": 3}
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="save_preset",
            description="保存当前参数组合为预设配置",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "预设名称"},
                    "description": {"type": "string", "description": "预设描述"},
                    "parameters": {"type": "object", "description": "参数名:值的字典"}
                },
                "required": ["name", "parameters"]
            }
        ),
        types.Tool(
            name="load_preset",
            description="加载预设参数组合",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "预设名称"}
                },
                "required": ["name"]
            }
        ),
        types.Tool(
            name="list_presets",
            description="列出所有预设配置",
            inputSchema={"type": "object", "properties": {}}
        ),
        types.Tool(
            name="delete_preset",
            description="删除指定的预设配置",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "预设名称"}
                },
                "required": ["name"]
            }
        ),
        types.Tool(
            name="get_statistics",
            description="获取服务器统计信息",
            inputSchema={"type": "object", "properties": {}}
        ),
        types.Tool(
            name="cancel_simulation",
            description="取消正在运行的仿真任务",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "任务ID"}
                },
                "required": ["task_id"]
            }
        ),
        types.Tool(
            name="clear_cache",
            description="清空仿真结果缓存",
            inputSchema={"type": "object", "properties": {}}
        )
    ]


@app.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> List[types.TextContent]:
    """处理工具调用"""
    result = None
    
    try:
        # 工具分发
        if name == "load_plecs_model":
            result = await plecs_service.load_plecs_model(arguments["model_path"])
        elif name == "get_model_variables":
            result = await plecs_service.get_model_variables(
                arguments.get("model_path"),
                arguments.get("refresh", False)
            )
        elif name == "set_parameter":
            result = await plecs_service.set_parameter(
                arguments["param_name"],
                arguments["value"],
                arguments.get("verify", True)
            )
        elif name == "set_parameters_batch":
            result = await plecs_service.set_parameters_batch(arguments["parameters"])
        elif name == "run_simulation_async":
            result = await plecs_service.run_simulation_async(
                arguments.get("duration"),
                arguments.get("step"),
                arguments.get("variables")
            )
        elif name == "get_simulation_result":
            result = await plecs_service.get_simulation_result(
                arguments["task_id"],
                arguments.get("wait", False),
                arguments.get("timeout", 60.0)
            )
        elif name == "scan_parameters":
            result = await plecs_service.scan_parameters(
                arguments["param_name"],
                arguments["start"],
                arguments["end"],
                arguments["steps"],
                arguments["target_metric"],
                arguments.get("minimize", True),
                arguments.get("parallel", False)
            )
        elif name == "analyze_waveform":
            result = await plecs_service.analyze_waveform(
                arguments["variable_name"],
                arguments.get("metrics"),
                arguments.get("time_range")
            )
        elif name == "search_knowledge":
            result = await plecs_service.search_knowledge(
                arguments["query"],
                arguments.get("top_k", 3)
            )
        elif name == "save_preset":
            result = await plecs_service.save_preset(
                arguments["name"],
                arguments.get("description", ""),
                arguments["parameters"]
            )
        elif name == "load_preset":
            result = await plecs_service.load_preset(arguments["name"])
        elif name == "list_presets":
            result = await plecs_service.list_presets()
        elif name == "delete_preset":
            result = await plecs_service.delete_preset(arguments["name"])
        elif name == "get_statistics":
            result = await plecs_service.get_statistics()
        elif name == "cancel_simulation":
            result = await plecs_service.cancel_simulation(arguments["task_id"])
        elif name == "clear_cache":
            result = await plecs_service.clear_cache()
        else:
            result = {"status": "error", "message": f"未知工具: {name}"}
        
        # 记录日志
        plecs_service._log_tool_call(name, arguments, result.get("status") == "success", str(result)[:200])
        
    except Exception as e:
        result = {"status": "error", "message": str(e)}
        plecs_service._log_tool_call(name, arguments, False, str(e))
    
    return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]


async def main():
    """主函数"""
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="plecs-mcp-server-v2",
                server_version="2.0.0"
            )
        )


if __name__ == "__main__":
    asyncio.run(main())
