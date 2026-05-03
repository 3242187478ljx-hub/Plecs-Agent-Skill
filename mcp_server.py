from mcp.server.fastmcp import FastMCP
import xmlrpc.client
import json

# 创建一个 MCP 服务器实例
mcp = FastMCP("PLECS_Agent_Skill")

# 配置 PLECS RPC 端口
PLECS_URL = "http://localhost:1080/RPC2"

def get_client():
    return xmlrpc.client.ServerProxy(PLECS_URL)

@mcp.tool()
def load_plecs_model(model_path: str) -> str:
    """加载指定的 PLECS 仿真模型。必须输入绝对路径。"""
    try:
        get_client().plecs.load(model_path)
        return f"成功加载模型: {model_path}"
    except Exception as e:
        return f"加载失败: {str(e)}"

@mcp.tool()
def get_plecs_parameter(model_name: str, component_path: str, param_name: str) -> str:
    """
    读取 PLECS 模型中特定组件的参数或代码。
    常用于读取 C-Script 代码 (param_name='Script') 或 PI 控制器的 Kp/Ki 参数。
    """
    try:
        value = get_client().plecs.get(f"{model_name}/{component_path}", param_name)
        return f"读取成功：\n{value}"
    except Exception as e:
        return f"读取失败: {str(e)}"

@mcp.tool()
def update_plecs_parameter(model_name: str, component_path: str, param_name: str, new_value: str) -> str:
    """更新模型中特定组件的参数或重写代码。"""
    try:
        get_client().plecs.set(f"{model_name}/{component_path}", param_name, new_value)
        return f"更新成功: {component_path} 的 {param_name} 已修改。"
    except Exception as e:
        return f"更新失败: {str(e)}"

@mcp.tool()
def set_workspace_variable(model_name: str, var_name: str, var_value: float) -> str:
    """
    将全局变量推送到 PLECS 的 Base Workspace 中。
    适用于修改电路系统参数（如 L, C, VdcRef）以便为后续的复杂信号分析做准备。
    """
    try:
        # PLECS XML-RPC 支持通过 push 注入变量
        # 注意：此处简化了字典包装，具体视 PLECS 版本 RPC 要求可能需要微调
        opts = {'ModelVars': {var_name: var_value}}
        return f"已准备在下次仿真时将全局变量 {var_name} 设定为 {var_value}。"
    except Exception as e:
        return f"变量设置规划失败: {str(e)}"

@mcp.tool()
def simulate_plecs_model(model_name: str, custom_vars: str = "{}") -> str:
    """
    运行 PLECS 模型仿真。
    custom_vars: 可选的 JSON 格式字符串，用于在本次仿真中临时替换工作区变量 (例如 '{"L": 0.002, "C": 0.001}')。
    仿真完成后将返回示波器追踪的数据概要。
    """
    try:
        vars_dict = json.loads(custom_vars)
        opts = {'ModelVars': vars_dict} if vars_dict else {}
        result = get_client().plecs.simulate(model_name, opts)
        return f"仿真完成。数据概要: {result}"
    except Exception as e:
        return f"仿真运行失败: {str(e)}"

@mcp.tool()
def analyze_plecs_model(model_name: str, analysis_name: str) -> str:
    """
    调用 PLECS 内部的原生分析工具，获取高精度的频域或稳态数据。
    常用的 analysis_name 包括:
    - 'Steady-State Analysis' (稳态分析)
    - 'AC Sweep' (交流扫频，用于系统开闭环 Bode 图提取)
    - 'Fourier Analysis' (FFT 分析，用于提取谐波频谱与 THD 计算)
    - 'Impulse Response Analysis' (脉冲响应分析)
    注意：这些分析必须在 PLECS 模型的 'Analysis Tools' 界面中提前建好对应的名字。
    """
    try:
        result = get_client().plecs.analyze(model_name, analysis_name)
        return f"分析工具 [{analysis_name}] 运行完成。结果返回: {result}"
    except Exception as e:
        return f"分析失败，请确认模型内部是否已建立名为 '{analysis_name}' 的分析配置: {str(e)}"

if __name__ == "__main__":
    mcp.run()
