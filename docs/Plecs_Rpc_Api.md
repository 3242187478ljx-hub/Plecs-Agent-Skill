# Agent 命令行调用指南

当用户提出需求时，请在后台终端执行以下 Python 命令：

1. **加载模型**: `python tools/plecs_automator.py load "my_private_models/你的模型.plecs"`
2. **运行仿真**: `python tools/plecs_automator.py simulate "ModelName"`
3. **稳态分析**: `python tools/plecs_automator.py analyze "ModelName" "Steady-State Analysis"`
4. **导出波形**: `python tools/plecs_automator.py export "ModelName" "Circuit/Scope" "data.csv"`

修改参数或 C-Script 时，需编写临时 Python 脚本 import 本工具的 `set_param` 方法。
