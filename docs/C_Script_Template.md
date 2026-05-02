# PLECS C-Script 编写规范与标准模板

## ⚠️ 核心禁令 (Agent 必须遵守)
1. **绝不能包含 `main()` 函数**：PLECS C-Script 是由仿真器底层的求解器在特定生命周期调用的代码块。
2. **禁止使用标准 I/O 函数**：如 `printf()` 等。调试信息如需输出，需通过额外配置，常规控制代码中严禁出现。
3. **严格遵守宏定义映射**：禁止直接操作底层指针，必须通过官方提供的宏（如 `InputSignal` 或自定义的 `Input()`）读写端口数据。

---

## 🛠️ 1. 代码声明区 (Code Declarations)
这是整个 C-Script 的头部，用于引入数学库、定义宏、映射端口、以及声明所有全局变量和静态变量。

```c
#include "math.h"

// 1. 物理常数与仿真步长定义
#define PI 3.14159265358979f
#define SQRT3_3 0.57735026918f
#define Ts (1/(float)20e3)  // 离散控制周期，如 20kHz

// 2. 端口宏映射 (使代码具备高可读性)
// 注意：索引 j 从 0 开始。例如 InputSignal(0, 0) 是第1个输入端口的第1个元素。
#define VAB InputSignal(0, 0)
#define VBC InputSignal(0, 1)
#define ILA InputSignal(1, 0)
#define ILB InputSignal(1, 1)

#define MA OutputSignal(0, 0)
#define MB OutputSignal(0, 1)
#define MC OutputSignal(0, 2)

// 3. 全局控制变量声明 (锁相环、PI控制器历史状态、中间计算变量)
float Pll_vq, Pll_d, Pll_w, Pll_ph;
float Pll_Kp, Pll_Ki;

float VdcRef, VdcKp, VdcKi;
float VdcErr_old, VdcPiOut;
```

---

## 🚀 2. 初始化区 (StartFcn)
此函数仅在仿真时间 `t = 0` 时执行一次。只能用于给声明区定义的变量赋初始值。

```c
// 锁相环 (PLL) 参数初始化
Pll_Kp = 0.1f;
Pll_Ki = 6.0f;
Pll_w = 2.0f * PI * 50.0f; // 初始角速度 50Hz
Pll_ph = 0.0f;

// 电压外环 PI 参数初始化
VdcRef = 700.0f;
VdcKp = 1.0f;
VdcKi = 10.0f;
VdcErr_old = 0.0f;
VdcPiOut = 0.0f;

// 确保初始输出为零，避免第一步报错
MA = 0.0f;
MB = 0.0f;
MC = 0.0f;
```

---

## ⚙️ 3. 核心运行区 (OutputFcn)
这是 C-Script 的心脏。在仿真的每一个步长（或指定的采样点）都会执行。必须在这里完成**读取输入 -> 执行控制算法 -> 写入输出**的全流程。

```c
// ==================== 1. 读取与坐标变换 ====================
// 线电压转相电压计算
float Va = (2.0f*VAB + VBC)/3.0f;
float Vb = (-VAB + VBC)/3.0f;

// Clark 变换 (3/2 变换)
float Val = Va;
float Vbe = SQRT3_3 * (Va + 2.0f*Vb);

// ==================== 2. 锁相环 (SRF-PLL) 计算 ====================
// Park 变换得到 Vq
Pll_vq = -sinf(Pll_ph)*Val + cosf(Pll_ph)*Vbe;

// PI 调节器更新角速度
Pll_w += Pll_vq * Pll_Ki * Ts;
// 积分更新相位
Pll_ph += (Pll_w + Pll_vq * Pll_Kp) * Ts;

// 相位限幅归一化至 0~2PI
if (Pll_ph > 2.0f*PI) {
    Pll_ph -= 2.0f*PI;
} else if (Pll_ph < 0.0f) {
    Pll_ph += 2.0f*PI;
}

// ==================== 3. 谐波提取或电流内环计算 ====================
// (此处插入复杂的控制逻辑，如多谐振计算、电流预测控制等)
float Ma0 = 0.0f; // 假设计算得到的A相调制波初始值
float Mb0 = 0.0f;
float Mc0 = 0.0f;
float Mn = 0.0f;  // 共模注入项

// ==================== 4. SVPWM 或最终输出赋值 ====================
// 必须在函数结束前，通过宏将结果赋值给输出端口
MA = Ma0 + Mn;
MB = Mb0 + Mn;
MC = -(MA + MB); // 三相三线制系统，C相为负的A+B
```

---

## 🔄 4. 离散状态更新区 (UpdateFcn - 可选)
如果控制算法需要利用 PLECS 的内置离散状态机（如 `DiscState(i)`），则在此处更新状态变量。一般的纯代码变量历史值更新也可以放在这里，或直接合并在 `OutputFcn` 的末尾。

```c
// 示例：更新离散状态
// DiscState(0) = DiscState(0) + InputSignal(0, 0) * Ts;
```
