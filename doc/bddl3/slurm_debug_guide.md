# Python调试完全指南 - 学习BDDL数据流

## 一、VSCode调试基础

### 1.1 启动调试的三种方式

**方式1：使用调试面板**
1. 打开 `tests/test_bddl.py`
2. 点击左侧边栏的"运行和调试"图标（或按 `Ctrl+Shift+D`）
3. 在顶部下拉菜单中选择 "Python: 调试 test_bddl.py"
4. 点击绿色三角形按钮开始调试

**方式2：快捷键**
1. 打开 `tests/test_bddl.py`
2. 直接按 `F5` 启动调试
3. 如果是第一次，会提示选择配置，选择 "Python: 调试 test_bddl.py"

**方式3：右键菜单**
1. 在 `tests/test_bddl.py` 编辑器中右键
2. 选择 "调试 Python 文件"

### 1.2 设置断点

**普通断点**
- 在行号左侧点击，会出现红色圆点 🔴
- 程序运行到这一行时会暂停
- 建议的断点位置：
  - 第69行：`test_bddl_load_analyze(cfg)` - 主函数入口
  - 第93行：`test_env = og.Environment(config)` - 环境创建前

**条件断点**（右键点击断点）
```python
# 示例：只在特定条件下暂停
config['task']['type'] == 'BehaviorTask'
```

**日志点**（右键选择"添加日志点"）
```python
# 不暂停程序，只打印信息
环境配置: {config}
```

### 1.3 调试控制按钮

调试工具栏从左到右：

| 按钮 | 快捷键 | 功能 | 何时使用 |
|------|--------|------|----------|
| ▶️ 继续 | `F5` | 运行到下一个断点 | 跳过不关心的代码段 |
| ⤵️ 单步跳过 | `F10` | 执行当前行，不进入函数内部 | 快速浏览流程 |
| ⬇️ 单步调试 | `F11` | 执行当前行，进入函数内部 | **最重要！深入追踪数据流** |
| ⬆️ 单步跳出 | `Shift+F11` | 跳出当前函数 | 进错函数时快速返回 |
| ↻ 重启 | `Ctrl+Shift+F5` | 重新开始调试 | 想从头再来一遍 |
| ⬛ 停止 | `Shift+F5` | 结束调试 | 不想继续了 |

## 二、查看变量的方法

### 2.1 变量面板（左侧）
调试时左侧会显示：
- **局部变量**：当前函数内的所有变量
- **全局变量**：全局作用域的变量
- 点击变量旁的 `>` 可以展开对象查看内部属性

### 2.2 鼠标悬停
- 在代码中将鼠标悬停在任何变量上
- 会弹出该变量的当前值
- 可以展开查看对象的属性

### 2.3 监视（Watch）
1. 在左侧调试面板找到"监视"区域
2. 点击 `+` 添加表达式
3. 示例：
   ```python
   test_env.task.__class__.__name__
   len(test_env.scene.objects)
   config['task']['type']
   ```

### 2.4 调试控制台（最强大！）
在底部"调试控制台"标签中可以：
- **执行任何Python表达式**
- **调用函数**
- **修改变量值**（临时测试）

示例命令：
```python
# 查看对象类型
type(test_env)

# 查看对象的所有属性
dir(test_env.task)

# 查看文档
help(test_env.task.update_activity)

# 查看对象的字典表示
vars(test_env.task)

# 深入探索
test_env.task.object_scope.keys()
test_env.task.initial_conditions[0] if test_env.task.initial_conditions else None
```

## 三、追踪BDDL数据流的具体步骤

### 3.1 第一阶段：环境创建入口

**目标**：理解 `og.Environment(config)` 做了什么

1. 在第93行 `test_env = og.Environment(config)` 设置断点
2. 按 `F5` 启动调试，程序会停在这里
3. 在调试控制台查看配置：
   ```python
   config
   config['task']
   ```
4. 按 `F11` **进入** `Environment` 构造函数

### 3.2 第二阶段：追踪Task初始化

**目标**：找到 `BehaviorTask.__init__()` 的调用位置

1. 继续按 `F11` 深入
2. 注意观察左侧的**调用堆栈**（Call Stack）
3. 当你看到类似 `task.py` 或 `behavior_task.py` 的文件时，说明进入Task初始化了
4. 在变量面板查看 `self` 的属性变化

**关键断点位置**（如果你能找到这些文件）：
- `bddl3/bddl/condition_evaluation.py` - BDDL条件解析
- `OmniGibson/omnigibson/tasks/behavior_task.py` - 任务初始化
- 找到 `update_activity()` 方法 - 加载BDDL文件
- 找到 `initialize_activity()` 方法 - 初始化对象

### 3.3 第三阶段：查看解析结果

**目标**：观察BDDL解析后的数据结构

程序运行到第97-105行时（断点2位置）：

1. 在调试控制台执行：
   ```python
   # 查看object_scope结构
   test_env.task.object_scope
   
   # 如果是字典，查看键
   list(test_env.task.object_scope.keys())
   
   # 查看具体某个对象
   test_env.task.object_scope['apple'] if 'apple' in test_env.task.object_scope else None
   
   # 查看初始条件
   test_env.task.initial_conditions
   
   # 查看目标条件
   test_env.task.goal_conditions
   ```

2. 使用Watch监视这些表达式，可以看到它们随代码执行的变化

## 四、高级调试技巧

### 4.1 条件断点 - 只在特定情况下暂停

右键点击断点 → 选择"编辑断点" → "表达式"

示例场景：
```python
# 只在处理特定对象时暂停
obj_name == "apple"

# 只在列表有内容时暂停
len(parsed_objects) > 0

# 只在发生错误时暂停
error is not None
```

### 4.2 跳过不关心的代码

如果你只关心自己的代码，不想进入库代码：
- 使用配置 "Python: 调试 test_bddl.py (仅我的代码)"
- 或者在调试控制台设置：
  ```python
  import sys
  sys.settrace(None)  # 临时关闭追踪
  ```

### 4.3 使用日志点代替print

优势：不需要修改代码，不需要重新运行

1. 右键行号 → 添加日志点
2. 输入消息模板：
   ```
   当前对象: {obj_name}, 类型: {type(obj)}
   ```
3. 程序运行时会在调试控制台输出，但不会暂停

### 4.4 回退到上一帧（限制性功能）

在调用堆栈面板：
- 右键某个栈帧 → "跳转到文件"：查看那里的代码
- 双击栈帧：切换上下文，查看那一层的变量

⚠️ 注意：Python调试器不支持真正的"时光倒流"，只能查看历史堆栈

## 五、常见问题

### 5.1 断点显示灰色空心圆 ⚪
- 原因：代码可能未被加载，或者是空行/注释行
- 解决：将断点移到有实际代码的行

### 5.2 调试时提示"找不到模块"
- 原因：PYTHONPATH或conda环境配置问题
- 解决：检查 `.vscode/launch.json` 中的 `env` 配置
- 确认使用的是 `behavior` conda环境

### 5.3 进入太多层库代码，迷路了
- 使用 `Shift+F11` (单步跳出) 返回上一层
- 或者在调用堆栈中点击你认识的函数名跳回去
- 下次使用 `F10` (单步跳过) 而不是 `F11`

### 5.4 变量显示 `<optimized out>` 或不可用
- 原因：某些优化或异步操作
- 解决：在调试控制台手动输入变量名查看

## 六、实战练习清单

按这个顺序练习，逐步深入：

- [ ] **练习1**：在第69行设置断点，启动调试，查看 `cfg` 变量
- [ ] **练习2**：使用 `F10` 单步跳过，观察打印输出
- [ ] **练习3**：在第93行用 `F11` 进入 `og.Environment()`
- [ ] **练习4**：在调试控制台执行 `dir(config)` 和 `help(og.Environment)`
- [ ] **练习5**：添加Watch表达式 `test_env.task.__class__.__name__`
- [ ] **练习6**：设置条件断点，只在特定条件下暂停
- [ ] **练习7**：使用日志点记录变量变化而不暂停程序
- [ ] **练习8**：深入BDDL解析函数，追踪 `parsed_objects` 的生成过程

## 七、使用pdb的命令行调试（备选方案）

如果VSCode调试有问题，可以在代码中插入：

```python
# 在想暂停的地方插入
import pdb; pdb.set_trace()

# Python 3.7+ 可以用内置函数
breakpoint()
```

常用pdb命令：
- `n` (next): 单步跳过，相当于F10
- `s` (step): 单步调试，相当于F11
- `c` (continue): 继续执行，相当于F5
- `p variable`: 打印变量
- `pp variable`: 漂亮打印（格式化）
- `l` (list): 显示当前代码位置
- `w` (where): 显示调用堆栈
- `q` (quit): 退出调试

## 八、推荐的学习路径

### 第1天：基础操作
- 学会设置断点、启动调试
- 熟悉 F5/F10/F11 快捷键
- 学会查看变量面板

### 第2天：深入追踪
- 使用 F11 进入 `og.Environment()`
- 观察调用堆栈
- 在调试控制台执行表达式

### 第3天：数据流追踪
- 找到 BDDL 解析的关键函数
- 在 `update_activity()` 设置断点
- 观察 `parsed_objects` 如何生成

### 第4天：高级技巧
- 使用条件断点和日志点
- 用Watch监视复杂表达式
- 尝试在调试控制台中修改变量测试不同情况

## 九、快速参考卡片

```
┌─────────────────────────────────────────────┐
│       Python调试快捷键速查表                 │
├─────────────────────────────────────────────┤
│ F5          启动调试 / 继续执行              │
│ F9          切换断点                         │
│ F10         单步跳过（不进入函数）           │
│ F11         单步调试（进入函数）⭐           │
│ Shift+F11   单步跳出                         │
│ Ctrl+Shift+D 打开调试面板                    │
│ Shift+F5    停止调试                         │
│                                              │
│ 调试黄金法则：                               │
│ • F11 进入 = 深入了解                        │
│ • F10 跳过 = 快速前进                        │
│ • 调试控制台 = 自由探索                      │
└─────────────────────────────────────────────┘
```

---

**现在就开始吧！**

1. 打开 `tests/test_bddl.py`
2. 在第69行点击设置断点
3. 按 `F5` 开始你的调试之旅！

祝学习愉快！🎉
