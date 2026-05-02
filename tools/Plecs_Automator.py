import xmlrpc.client
import sys

PLECS_URL = "http://localhost:1080/RPC2"

def get_client():
    return xmlrpc.client.ServerProxy(PLECS_URL)

def load_model(path):
    get_client().plecs.load(path)
    return f"模型已加载: {path}"

def set_param(model, comp_path, param, value):
    get_client().plecs.set(f"{model}/{comp_path}", param, str(value))
    return f"已更新 {comp_path} 的 {param}。"

def simulate(model):
    print(f"正在运行 {model} 仿真...")
    return get_client().plecs.simulate(model)

def analyze(model, analysis):
    print(f"正在调用原生分析: {analysis}...")
    return get_client().plecs.analyze(model, analysis)

def export_scope(model, scope_path, save_path):
    get_client().plecs.scope(f"{model}/{scope_path}", "ExportCsv", save_path)
    return f"波形已导出至: {save_path}"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(1)
    
    cmd = sys.argv[1]
    try:
        if cmd == "load" and len(sys.argv) == 3: print(load_model(sys.argv[2]))
        elif cmd == "simulate" and len(sys.argv) == 3: print(simulate(sys.argv[2]))
        elif cmd == "analyze" and len(sys.argv) == 4: print(analyze(sys.argv[2], sys.argv[3]))
        elif cmd == "export" and len(sys.argv) == 5: print(export_scope(sys.argv[2], sys.argv[3], sys.argv[4]))
    except Exception as e:
        print(f"执行失败: {e}")
