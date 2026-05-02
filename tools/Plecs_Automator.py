from mcp.server.fastmcp import FastMCP
import xmlrpc.client

# 创建一个 MCP 服务器实例
mcp = FastMCP("PLECS_Agent_Skill")

# 配置 PLECS RPC 端口
PLECS_URL = "http://localhost:1080/RPC2"

def get_client():
    return xmlrpc.client.ServerProxy(PLECS_URL)

# =====================================================================
# 下面使用 @mcp.tool() 装饰器，直接把这些函数变成 Claude 原生支持的工具
# Claude 会自动读取函数下方的文档字符串 (Docstring) 来知道什么时候该用它
# =====================================================================

@mcp.tool()
def load_plecs_model(model_path: str) -> str:
    """
    加载指定的 PLECS 仿真模型。
    当你需要调试一个未打开的 .plecs 文件时，首先调用此工具。
    参数: model_path - 模型的绝对路径。
    """
    try:
        get_client().plecs.load(model_path)
        return f"成功加载模型: {model_path}"
    except Exception as e:
        return f"加载失败: {str(e)}"

@mcp.tool()
def simulate_plecs_model(model_name: str) -> str:
    """
    运行 PLECS 模型的常规仿真。
    参数: model_name - 模型名称 (不含 .plecs 后缀)。
    """
    try:
        result = get_client().plecs.simulate(model_name)
        return f"仿真完成。返回概要数据: {result}"
    except Exception as e:
        return f"仿真运行失败: {str(e)}"

@mcp.tool()
def analyze_plecs_model(model_name: str, analysis_name: str = "Steady-State Analysis") -> str:
    """
    调用 PLECS 内部的原生分析工具 (如稳态分析 Steady-State Analysis)。
    这能直接返回高精度的分析数据，避免使用外部计算库。
    """
    try:
        result = get_client().plecs.analyze(model_name, analysis_name)
        return f"分析完成。结果: {result}"
    except Exception as e:
        return f"分析失败: {str(e)}"

@mcp.tool()
def update_plecs_parameter(model_name: str, component_path: str, param_name: str, new_value: str) -> str:
    """
    修改 PLECS 模型中的组件参数或 C-Script 代码。
    参数:
    - component_path: 组件在模型中的路径 (如 'Circuit/PI Controller')
    - param_name: 参数名称 (如果是 C-Script 通常为 'Script' 或 'StartFcn', 'OutputFcn')
    - new_value: 新的参数值或代码字符串。
    """
    try:
        get_client().plecs.set(f"{model_name}/{component_path}", param_name, new_value)
        return f"成功将 {component_path} 的 {param_name} 更新为新值。"
    except Exception as e:
        return f"参数更新失败: {str(e)}"

if __name__ == "__main__":
    # 启动 MCP 服务器，监听 Claude 的连接
    mcp.run()
