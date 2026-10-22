<!-- 与聊天中的第一篇导读和第1章正文同步归档；包含完整代码、练习及详解。 -->

[返回总目录](./00_完整目录.md) · [配套代码](./code/ch01/monitor.py) · [验证代码](./code/ch01/test_monitor.py)

# 第一篇　数学、统计学与编程基础

本篇回答一个基础问题：

**怎样把金融问题写成具有明确输入、计算规则、时间边界和可验证输出的程序？**

如果收益率计算错误、未来数据混入历史特征、重复消息反复更新模型，后续采用再复杂的分布式架构或神经网络，也无法修复这些基础错误。

本篇的知识依据包括以下已经核对的官方课程和作者资源。后续各章还会补充对应的具体阅读位置。

| 方向 | 首批参考资料 | 本教材中的用途 |
|---|---|---|
| Python与计算思维 | MIT 6.0001，2016年课程 | 程序分解、容器、测试与效率。[课程资料](https://ocw.mit.edu/courses/6-0001-introduction-to-computer-science-and-programming-in-python-fall-2016/pages/lecture-slides-code/) |
| 数据结构 | 邓俊辉《数据结构（C++语言版）》及配套课程 | 理解结构选择与复杂度；本教材另写Python实现。[作者官网](https://dsa.cs.tsinghua.edu.cn/~deng/ds/dsacpp/) |
| 线性代数 | Gilbert Strang，MIT 18.06，2010年 | 向量空间、投影、分解与正定性。[课程入口](https://ocw.mit.edu/courses/18-06-linear-algebra-spring-2010/) |
| 微积分 | David Jerison等，MIT 18.01SC，2010年 | 导数、积分、近似与数值方法。[课程入口](https://ocw.mit.edu/courses/18-01sc-single-variable-calculus-fall-2010/) |
| 最优化 | Boyd、Vandenberghe，《Convex Optimization》，2004年 | 凸性、约束优化及数值算法。[作者授权阅读入口](https://web.stanford.edu/~boyd/cvxbook/) |
| 概率 | Harvard Stat110及Blitzstein、Hwang配套教材 | 条件概率、随机变量与马尔可夫链。[官方入口](https://stat110.hsites.harvard.edu/) |
| 统计 | Orloff、French Kamrin，MIT 18.05，2022年 | 估计、检验、区间与回归。[课程入口](https://ocw.mit.edu/courses/18-05-introduction-to-probability-and-statistics-spring-2022/) |
| 随机过程 | Pishro-Nik，2014年教材 | 随机过程、Poisson过程、马尔可夫链与布朗运动。[作者在线教材](https://www.probabilitycourse.com/) |
| 时间序列 | Hyndman、Athanasopoulos，2021年第三版教材 | 探索、时间结构、诊断与验证。[官方在线教材](https://otexts.com/fpp3/) |

这些资料的开放阅读条件各不相同。教材采用独立表述与原创示例，不把“能够在线阅读”等同于“允许任意转载”。

---

# 第1章　Python编程、数据结构与算法基础

> 本章公式采用普通 Markdown 文本记法，无需数学插件；上下标、分式与矩阵的读法见[数学公式阅读约定](./数学公式阅读约定.md)。

## 学习目标

### 学习本章之前

读者应能够：

- 在计算机上打开和保存文本文件；
- 理解加减乘除、百分数、求和与平方；
- 大致理解程序按指令执行的含义。

不要求事先学习金融工程、数据库或分布式系统。

### 完成本章之后

读者应能够：

1. 用Python表示一条包含时间信息的行情。
2. 使用列表、字典、集合与双端队列。
3. 把行情处理拆分为解析、验证、计算和审计。
4. 正确计算简单收益率、窗口均值与样本标准差。
5. 解释为什么重复、迟到和冲突消息需要不同处理。
6. 分析一个算法的时间复杂度与空间复杂度。
7. 运行一个具有输入检查和审计输出的小型行情处理器。
8. 说明该处理器与完整市场状态识别平台之间的关系。

### 本章交付物

本章完成的是平台的一个基础构件：

```text
人工行情消息
    ↓
格式解析与有效性检查
    ↓
重复、冲突和迟到识别
    ↓
收益率与窗口统计
    ↓
教学用跳变预警
    ↓
审计记录与结果文件
```

这里的跳变预警只是简单规则，尚未构成具有经济含义的市场状态标签。

---

## 1.1　Python程序、类型与函数

### 一、先把金融任务写清楚

假设屏幕上出现一条消息：

> 某资产最新价格为101。

直接把101放进列表，程序当然能够执行，但信息远远不够。

至少还应知道：

- 这是什么资产？
- 价格由哪个来源提供？
- 价格对应什么时间？
- 来源何时发布？
- 本系统何时拿到？
- 消息是否已经处理过？
- 101与上一条价格是否具有可比性？

因此，一个可验证的任务应写成：

> 接收包含资产、来源、消息标识、事件时间、发布时间、获取时间和价格的记录；检查记录是否满足数据契约；在满足条件时更新本资产统计，并保存每一条记录的处理决定。

这里的**数据契约，Data Contract**，指发送方和接收方共同遵守的字段、类型、单位、时间语义及质量约束。

这也是软件工程的起点：先定义行为，再编写代码。

### 二、程序的四个组成部分

一个数据处理程序通常包括：

| 部分 | 本章例子 |
|---|---|
| 输入 | 一条行情消息 |
| 状态 | 已处理消息、上次价格、最近若干收益 |
| 转换规则 | 校验、去重、计算收益 |
| 输出 | 特征、预警标志、审计记录 |

**状态，State**，是程序为后续计算保留的信息。

注意，本章中的“程序状态”与“金融市场状态”含义不同。前者是计算机保存的内部信息；后者描述市场的趋势、波动、流动性或经济驱动特征。

### 三、变量、对象与基本类型

Python中的变量可以理解为指向对象的名称。

```python
symbol = "EQ_DEMO"
price = 100.0
message_count = 3
is_valid = True
previous_price = None
```

对应类型为：

| 表达式 | 类型 | 作用 |
|---|---|---|
| `"EQ_DEMO"` | `str`，字符串 | 表示代码、来源和文字 |
| `100.0` | `float`，浮点数 | 表示近似实数 |
| `3` | `int`，整数 | 表示数量、序号 |
| `True` | `bool`，布尔值 | 表示逻辑判断 |
| `None` | 空值对象 | 表示尚不存在或不适用 |

`None`与0不同。

第一条价格没有上一条可比价格，因此收益率应为`None`。如果把它填成0，就把“无法计算”改写成了“已经观察到零收益”。

这种替换会改变样本数量、均值和波动统计。

### 四、浮点数为什么不能随意比较

执行：

```python
print(0.1 + 0.2)
print(0.1 + 0.2 == 0.3)
```

通常得到：

```text
0.30000000000000004
False
```

原因是许多十进制小数无法用有限位二进制精确表示。Python浮点数保存的是接近目标数值的二进制近似值。[Python浮点运算说明](https://docs.python.org/3.13/tutorial/floatingpoint.html)

对于数值结果，可以使用容差比较：

```python
import math

print(math.isclose(
    0.1 + 0.2,
    0.3,
    rel_tol=1e-12,
    abs_tol=1e-12,
))
```

其基本判定思想是：

```text
|a-b| ≤ max( ε_rel max(|a|,|b|), ε_abs )
```

其中：

- `a,b`：待比较数；
- `ε_rel`：相对容差；
- `ε_abs`：绝对容差。

容差应与计算尺度相适应，不能把任意较大的容差当作修复错误的方法。

对于需要按最小报价单位精确保存的价格，可以考虑整数报价单位；对于十进制金额计算，可以考虑`Decimal`。但`Decimal`也有精度和舍入设置，不等于所有计算自动无限精确。[Python decimal文档](https://docs.python.org/3.13/library/decimal.html)

本章用浮点数演示统计特征，暂不实现交易记账。

### 五、条件与循环

条件语句用于表达数据规则：

```python
import math

price = 100.0

if not math.isfinite(price):
    print("价格不是有限数")
elif price <= 0:
    print("不满足本演示的数据契约")
else:
    print("可以继续处理")
```

`math.isfinite`用于排除：

- 非数值结果，Not a Number，`NaN`；
- 正无穷；
- 负无穷。

仅判断`price > 0`不足以排除所有非法数值。例如正无穷仍大于0。

循环用于逐条处理输入：

```python
prices = [100.0, 101.0, 99.99]

for index, price in enumerate(prices):
    print(index, price)
```

`enumerate`同时提供序号与元素。Python序列通常从0开始编号。

条件、循环和函数的具体语法可与官方教程第4节对照学习。[Python控制流教程](https://docs.python.org/3.13/tutorial/controlflow.html)

### 六、函数：把规则变成可独立检查的单元

**函数，Function**，是接收参数并执行一段明确计算的程序单元。

```python
import math


def simple_return(previous: float, current: float) -> float:
    """计算本演示中正价格资产的相邻观测收益。"""
    if not math.isfinite(previous) or not math.isfinite(current):
        raise ValueError("价格必须是有限数")
    if previous <= 0 or current <= 0:
        raise ValueError("本演示要求价格为正")

    result = (current - previous) / previous

    if not math.isfinite(result):
        raise ValueError("收益计算溢出")

    return result


print(simple_return(100.0, 101.0))
```

输出：

```text
0.01
```

这个函数具有清楚的边界：

- 输入：前后两次价格；
- 输出：一个小数形式的收益率；
- 假设：价格为有限正数，两个价格可以比较；
- 错误行为：违反假设时抛出异常。

函数签名中的`float`是**类型标注，Type Annotation**。它帮助阅读和工具检查，但通常不会自动验证运行时输入。

因此：

```python
def f(x: float):
    return x
```

并不保证调用者一定传入浮点数。

### 七、异常不是错误的替代解释

**异常，Exception**，是程序在无法按正常路径继续时发出的控制信号。

```python
try:
    result = simple_return(0.0, 101.0)
except ValueError as exc:
    print("该记录不能进入收益计算：", exc)
```

需要区分两类问题：

1. 一条输入消息无效，例如缺少价格；
2. 程序自身存在缺陷，例如访问了不存在的内部属性。

第一类可以记录后继续处理。第二类应暴露出来并修复。

因此不应习惯性使用：

```python
try:
    ...
except Exception:
    pass
```

这会使数据丢失、程序缺陷和环境故障一起消失在日志之外。

---

## 1.2　容器、对象、迭代器与异常

### 一、列表：保存有序序列

**列表，List**，是可以修改的有序容器。

```python
prices = [100.0, 101.0, 99.99]
prices.append(102.0)

print(prices[0])
print(prices[-1])
print(prices[1:3])
```

输出：

```text
100.0
102.0
[101.0, 99.99]
```

切片`[1:3]`包含位置1，不包含位置3。

列表适合：

- 保存一批历史数据；
- 按顺序遍历；
- 按位置访问元素。

但列表并不是所有队列任务的最佳结构。

如果不断执行：

```python
prices.pop(0)
```

列表需要移动后续元素，规模越大，开销越明显。Python官方教程也建议队列使用`collections.deque`。[列表与队列](https://docs.python.org/3.13/tutorial/datastructures.html#using-lists-as-queues)

### 二、字典：按业务键寻找状态

**字典，Dictionary**，保存键与值的映射。

```python
latest_price = {
    ("SOURCE_A", "EQ_DEMO"): 100.0,
    ("SOURCE_A", "BOND_DEMO"): 100.2,
}

key = ("SOURCE_A", "EQ_DEMO")
print(latest_price[key])
```

为什么键不只使用资产代码？

因为两个数据源可能：

- 使用相同代码表示不同品种；
- 对同一资产提供不同口径；
- 在不同时间到达；
- 发生数据源故障或切换。

本章用：

```text
资产键 = (source,symbol)
```

保持来源之间的计算状态独立。

后续会建立资产主数据和来源映射，统一真正可比较的记录。

### 三、集合：检查是否出现过

**集合，Set**，用于保存不重复的元素并进行成员检查。

```python
seen = set()

message_key = ("SOURCE_A", "event-001")

if message_key not in seen:
    seen.add(message_key)
    print("第一次出现")
```

但是，只有集合还不够判断消息冲突。

例如同一个消息标识先后出现：

```text
event-001，价格100
event-001，价格105
```

这可能是来源修订，也可能是数据错误。

如果只有`seen`集合，程序只能知道标识出现过，却不能比较业务内容。

因此，本章最终用字典保存：

```text
消息键 → 已见业务内容
```

由此区分：

- 同键、同内容：重复；
- 同键、不同内容：冲突。

### 四、栈与队列

**栈，Stack**，采用后进先出，Last In, First Out，LIFO。

**队列，Queue**，采用先进先出，First In, First Out，FIFO。

行情消息按获取顺序处理时，通常更接近队列。

**双端队列，Double-ended Queue，deque**，允许在两端高效添加和移除元素。

```python
from collections import deque

recent_returns = deque(maxlen=3)

for value in [0.01, -0.01, 0.02, 0.005]:
    recent_returns.append(value)

print(list(recent_returns))
```

输出：

```text
[-0.01, 0.02, 0.005]
```

设置`maxlen=3`后，加入第四个元素会移除最早的一个。

必须注意：

> 如果维护了额外的窗口总和，需要在旧元素被移除之前取得它，不能依赖自动移除后再寻找。

双端队列的端点操作及其使用方式见官方文档。[collections.deque](https://docs.python.org/3.13/library/collections.html#collections.deque)

### 五、赋值与复制

下面的代码经常导致隐蔽错误：

```python
raw_prices = [100.0, 101.0]
clean_prices = raw_prices

clean_prices.append(102.0)

print(raw_prices)
```

输出：

```text
[100.0, 101.0, 102.0]
```

因为两个名称引用同一个列表。

若要建立独立的浅复制：

```python
clean_prices = raw_prices.copy()
```

但浅复制不会递归复制内部对象：

```python
raw = [{"price": 100.0}]
copied = raw.copy()

copied[0]["price"] = 999.0

print(raw[0]["price"])
```

仍会输出：

```text
999.0
```

在金融数据处理中，这可能造成“清洗层修改了原始层”。

本教材采用的原则是：

- 保留原始输入；
- 清洗生成新记录；
- 记录变换原因；
- 避免通过共享可变对象修改历史证据。

### 六、用数据类表示一条行情

**类，Class**，用于定义具有共同数据和行为的对象。

**数据类，Data Class**，是Python标准库提供的一种简化数据对象定义的方式：

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class SimpleQuote:
    source: str
    event_id: str
    symbol: str
    price: float
```

使用：

```python
quote = SimpleQuote(
    source="SYNTHETIC",
    event_id="e1",
    symbol="EQ_DEMO",
    price=100.0,
)

print(quote.symbol)
```

`frozen=True`限制实例字段的重新赋值，有助于避免行情对象被无意修改。但它不等于递归冻结对象内部所有内容。[dataclasses官方文档](https://docs.python.org/3.13/library/dataclasses.html)

### 七、迭代器与生成器

**迭代器，Iterator**，能够逐个提供元素。

**生成器，Generator**，是一种便于编写迭代器的机制，常使用`yield`产生元素。

```python
def valid_positive_prices(values):
    for value in values:
        if value > 0:
            yield value


for price in valid_positive_prices([100.0, -1.0, 101.0]):
    print(price)
```

对于大文件，逐行读取：

```python
with open("quotes.jsonl", encoding="utf-8") as stream:
    for line in stream:
        ...
```

避免一次把全部文件载入内存。

但应区分：

- 输入是否逐条读取；
- 内部状态是否持续增长。

一个程序即使逐行读取，如果把所有消息标识永久保存在内存里，内存仍会不断增长。

### 八、时间字段必须有语义

本章行情对象包含三个时间：

| 字段 | 含义 |
|---|---|
| `event_time` | 该报价对应的市场事件时间 |
| `published_time` | 来源对外发布该报价的时间 |
| `available_time` | 本系统获得该记录的时间 |

还存在第四个重要时间：

> 特征计算完成、真正可以被下游使用的时间。

本章暂不模拟计算耗时，因此输出保留`input_available_time`，明确它只是输入的获取时间。

在真实平台中，需要额外记录计算完成时间，不能把收到数据的时间当成特征已经计算完成的时间。

本章统一使用**协调世界时，Coordinated Universal Time，UTC**保存时间，并要求输入显式携带时区偏移。

例如：

```text
2025-01-06T09:30:00+08:00
2025-01-06T01:30:00+00:00
```

两者表示同一时刻。

没有时区的：

```text
2025-01-06T09:30:00
```

含义不充分。本章将其拒绝，而不是自行猜测。

Python区分具有时区信息和没有时区信息的日期时间对象。[datetime官方文档](https://docs.python.org/3.13/library/datetime.html)

---

## 1.3　收益统计、算法复杂度与正确性

### 一、从价格变化推导简单收益率

设：

- `P_(t-1)`：前一次可比价格；
- `P_t`：当前价格；
- `r_t`：这两个观测之间的简单收益率。

本节先假设：

1. 价格为正；
2. 两次价格属于同一资产和同一价格口径；
3. 期间没有需要单独计入的分红、利息或其他现金流；
4. 暂不考虑手续费。

持有一单位资产，价格变化产生的损益为：

```text
Δ P_t = P_t-P_(t-1)
```

用初始投入归一化：

```text
r_t = ((Δ P_t) / (P_(t-1)))
```

代入：

```text
r_t = ((P_t-P_(t-1)) / (P_(t-1)))
```

拆开分子：

```text
r_t = ((P_t) / (P_(t-1)))-1
```

因此：

```text
P_t = P_(t-1)(1+r_t)
```

例如：

```text
P_(t-1) = 100, P_t = 101
```

则：

```text
r_t = ((101-100) / (100)) = 0.01 = 1%
```

**程序内部通常保存0.01，显示时再格式化为1%。**

若把1当作1%输入模型，量纲会放大100倍。

### 二、多期收益为什么不能直接相加

由：

```text
P_1 = P_0(1+r_1)
```

以及：

```text
P_2 = P_1(1+r_2)
```

代入得到：

```text
P_2 = P_0(1+r_1)(1+r_2)
```

因此两期累计收益为：

```text
R_(0,2) = ((P_2) / (P_0))-1 = (1+r_1)(1+r_2)-1
```

展开：

```text
R_(0,2) = r_1+r_2+r_1 r_2
```

只有忽略乘积项时，才近似等于收益之和。

以：

```text
r_1 = 1%, r_2 = -1%
```

为例：

```text
R_(0,2) = 1.01 × 0.99-1 = -0.0001
```

即：

```text
R_(0,2) = -0.01%
```

价格路径为：

```text
100→101→99.99
```

所以“一涨一跌抵消”并不成立。

推广到`T`期：

```text
1+R_(0,T) = ∏_(t = 1)^T(1+r_t)
```

其中`∏`表示连乘。

### 三、对数收益的可加性

定义**对数收益，Log Return**：

```text
ℓ_t = ln((P_t) / (P_(t-1)))
```

利用：

```text
ln(ab) = ln a+ln b
```

可得：

```text
∑_(t = 1)^T ℓ_t = ln( ((P_1) / (P_0)) ((P_2) / (P_1)) ⋯ ((P_T) / (P_(T-1))) )
```

中间价格约去：

```text
∑_(t = 1)^T ℓ_t = ln((P_T) / (P_0))
```

因此对数收益可以跨时间相加。

但它要求价格比值为正，也不能在没有说明的情况下替代包含现金流的总收益。对于可能出现零价格或负价格的合约，应重新选择损益和归一化方式。

### 四、均值及其最小平方解释

给定`n`个收益：

```text
r_1,r_2,…,r_n
```

样本均值为：

```text
r̄ = ((1) / (n))∑_(i = 1)^n r_i
```

这里：

- `n`：观测数量；
- `∑`：求和；
- `r̄`：用一个数概括收益中心的位置。

为什么选择算术均值？

考虑用常数`a`代表全部收益，并用平方误差衡量代表效果：

```text
L(a) = ∑_(i = 1)^n(r_i-a)^2
```

将：

```text
r_i-a = (r_i-r̄)+(r̄-a)
```

代入：

```text
L(a) = ∑_(i = 1)^n [(r_i-r̄)+(r̄-a)]^2
```

展开：

```text
L(a) = ∑_(i = 1)^n(r_i-r̄)^2 + 2(r̄-a)∑_(i = 1)^n(r_i-r̄) + n(r̄-a)^2
```

根据均值定义：

```text
∑_(i = 1)^n(r_i-r̄) = ∑_(i = 1)^n r_i-nr̄ = 0
```

所以：

```text
L(a) = ∑_(i = 1)^n(r_i-r̄)^2 + n(r̄-a)^2
```

第一项与`a`无关，第二项非负，且在：

```text
a = r̄
```

时等于0。

因此，样本均值是使平方误差最小的常数代表。

这不是说金融收益必然围绕一个长期不变的均值波动。它只是给定这批样本时的数学性质。

### 五、样本方差与标准差

定义离差平方和：

```text
M_2 = ∑_(i = 1)^n(r_i-r̄)^2
```

当`n ≥ 2`时，常用样本方差为：

```text
s^2 = ((M_2) / (n-1))
```

样本标准差为：

```text
s = sqrt(s^2)
```

平方使正负离差不会相互抵消；开方使标准差恢复到收益率的量纲。

为什么分母出现`n-1`？

因为：

```text
∑_(i = 1)^n(r_i-r̄) = 0
```

当均值已经用这批数据估计后，最后一个离差由前面`n-1`个离差决定。更严格的无偏性证明需要抽样假设，将在第6章完成。

本章只把它作为窗口内的描述统计量。对于存在序列相关和分布变化的金融数据，不能不加条件地宣称它是某个固定总体波动率的无偏估计。

当`n = 1`时：

- 可以计算均值；
- 不能按上述公式计算样本标准差。

所以本章输出`None`，不会输出0。

### 六、为什么采用两遍计算

可以把离差平方和改写成：

```text
M_2 = ∑ r_i^2-nr̄^2
```

但当数据量级较大而离散程度很小时，右侧是两个相近大数相减，容易产生数值误差。

本章采用两遍计算：

第一遍：

```text
r̄ = ((∑ r_i) / (n))
```

第二遍：

```text
M_2 = ∑(r_i-r̄)^2
```

实现时使用`math.fsum`改善求和精度，但这仍是有限精度计算，不能理解为精确实数运算。

### 七、窗口统计与增量更新

**窗口，Window**，指参与当前计算的一组观测。

本章使用最近`w`个有效相邻观测收益组成的**计数窗口，Count Window**。

设完整窗口总和为：

```text
S_t = r_(t-w+1)+⋯+r_t
```

新收益`r_(t+1)`到达后，最早收益`r_(t-w+1)`离开：

```text
S_(t+1) = r_(t-w+2)+⋯+r_t+r_(t+1)
```

与原式比较：

```text
S_(t+1) = S_t-r_(t-w+1)+r_(t+1)
```

因此：

```text
r̄_(t+1) = ((S_(t+1)) / (w))
```

维护总和可以使均值更新只需要常数次算术操作。

不过，长期反复加减也会积累数值误差。实际实现可以定期根据窗口重新求和，并检查误差。

本章完整程序直接从短窗口重算均值和标准差，使实现容易检查。它的每条有效消息统计开销为`O(w)`，没有把它描述成常数时间。

### 八、时间复杂度

**时间复杂度，Time Complexity**，描述输入规模增长时，计算步骤如何增长。

若处理`N`条消息：

- 每条固定执行若干检查：通常记为`O(N)`；
- 每条重算长度为`w`的窗口：通常为`O(Nw)`；
- 对全部消息排序：比较排序通常为`O(Nlog N)`。

大`O`符号表示渐近上界，并不是运行秒数。

例如：

```text
T(N) = 5N+100
```

随着`N`增大，线性项主导，因此写为：

```text
T(N) = O(N)
```

算法分析的建模方法可参考MIT 6.006。[算法课程](https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020/)

### 九、为什么列表去重容易变慢

假设每来一条消息，都在已有消息列表中顺序查找。

若消息都不同，第`i`条消息大约需要比较`i-1`次，总比较次数为：

```text
0+1+⋯+(N-1)
```

利用等差数列求和：

```text
∑_(i = 1)^N(i-1) = ((N(N-1)) / (2))
```

所以：

```text
T(N) = O(N^2)
```

字典或集合在适当散列条件下，成员检查通常具有平均`O(1)`成本，使整体接近平均`O(N)`。

但不能把这个平均结论说成无条件的最坏情况保证。

### 十、空间复杂度

**空间复杂度，Space Complexity**，描述额外存储随规模的增长。

设：

- `A`：资产键数量；
- `w`：每个资产保留的收益数量；
- `U`：已见唯一消息键数量。

本章程序主要保存：

1. 每个资产的最新价格：`O(A)`；
2. 每个资产的收益窗口：`O(Aw)`；
3. 已见消息及业务内容：`O(U)`。

因此内存状态总体为：

```text
O(Aw+U)
```

虽然输入逐行读取，但去重状态会随着`U`增长。这是后续需要通过状态保留策略、持久化和消息日志解决的工程问题。

### 十一、正确性与不变量

**不变量，Invariant**，是在一系列操作之后仍然应成立的性质。

本章维护：

1. 同一资产键的已接受事件时间严格递增；
2. 重复和冲突消息不更新资产价格；
3. 迟到消息不覆盖当前最新价格；
4. 第一条价格不产生收益；
5. 窗口中最多有`w`个收益；
6. 每条输入都有处理记录。

另一个重要性质是：

> 给已经处理的输入追加未来消息，不应改变当时已经产生的输出。

若第`k`条输出为`y_k`，它应当只依赖：

```text
x_1,…,x_k
```

及当时已经确定的配置，而不是：

```text
x_(k+1),x_(k+2),…
```

这可以称为前缀一致性要求。它是检查前视偏差的一种程序测试，但不等于已经证明整套系统满足所有PIT条件，更不等于经济学上的因果识别。

---

## 1.4　可审计行情处理器的完整实现

### 一、数据契约

本章采用**JSON，JavaScript Object Notation，JavaScript对象表示法**保存单条消息。

文件采用JSONL形式：每行一个JSON对象。

一条示例消息为：

```json
{
  "source": "SYNTHETIC",
  "event_id": "e1",
  "symbol": "EQ_DEMO",
  "event_time": "2025-01-06T01:30:00+00:00",
  "published_time": "2025-01-06T01:30:00+00:00",
  "available_time": "2025-01-06T01:30:01+00:00",
  "price": 100.0
}
```

JSON解析机制见Python官方文档。[json文档](https://docs.python.org/3.13/library/json.html)

本章要求：

- 来源、标识和资产代码是非空字符串；
- 价格是有限正数；
- 时间包含时区；
- 对本演示报价，满足：

```text
t_event ≤ t_published ≤ t_available
```

- 输入按`available_time`非递减到达；
- 同一来源与资产的已接受`event_time`严格递增。

最后一条是本章的简化条件。真实逐笔数据可能在同一时间戳下存在多笔成交，需要加入交易所序号或其他顺序字段。

### 二、五种处理决定

| 决定 | 含义 | 更新资产统计 |
|---|---|---|
| `accepted` | 满足契约且推进事件时间 | 是 |
| `duplicate` | 同消息键、相同业务内容 | 否 |
| `conflict` | 同消息键、不同业务内容 | 否 |
| `late` | 新消息键，但事件时间没有推进 | 否 |
| `invalid` | 格式、数值或输入顺序违反契约 | 否 |

“没有更新统计”不等于“删除数据”。原始记录和处理理由都会保留。

### 三、为什么不把所有迟到消息立即插回窗口

假设已经收到：

```text
09:30  100
09:32  102
```

之后才收到：

```text
09:31  101
```

如果把迟到价格插入历史序列，原先的：

```text
100→102
```

应改为：

```text
100→101→102
```

不仅新增一条收益，原有相邻关系也发生变化。

这会影响：

- 窗口成员；
- 历史统计；
- 已生成的预警；
- 下游模型输出。

因此“支持乱序”需要定义结果修订机制。本章先把迟到记录隔离并保留，后续用事件时间、水位线和重放机制处理。

### 四、预警规则

本章只实现：

```text
jump_alert_t = 𝟏{|r_t| ≥ θ}
```

其中：

- `𝟏{ · }`：条件成立时为1，否则为0；
- `θ = 0.015`：教学用阈值，即1.5%。

该参数没有通过真实数据校准。

它表示“相邻有效观测价格变化较大”，不能直接解释为：

- 市场进入危机；
- 牛市或熊市已经形成；
- 未来价格将下跌；
- 应该买入或卖出。

### 五、完整代码

代码已经保存在：

[monitor.py](./code/ch01/monitor.py)

以下为完整实现：

```python
"""第1章：标准库行情监控器。全部演示行情均为人工构造。"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable


def parse_time(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be a string")

    result = datetime.fromisoformat(
        value.replace("Z", "+00:00")
    )

    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError(
            "timestamp must contain a UTC offset"
        )

    return result.astimezone(timezone.utc)


@dataclass(frozen=True)
class Quote:
    source: str
    event_id: str
    symbol: str
    event_time: datetime
    published_time: datetime
    available_time: datetime
    price: float

    def identity(self) -> tuple:
        # 重投时本次到达时间可以不同，业务内容不能改变。
        return (
            self.symbol,
            self.event_time,
            self.published_time,
            self.price,
        )


def parse_quote(raw: str) -> Quote:
    row = json.loads(raw)

    if not isinstance(row, dict):
        raise ValueError("JSON must be an object")

    for name in ("source", "event_id", "symbol"):
        if (
            not isinstance(row.get(name), str)
            or not row[name].strip()
        ):
            raise ValueError(
                f"{name} must be a nonempty string"
            )

    value = row["price"]

    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
    ):
        raise ValueError(
            "price must be a JSON number"
        )

    price = float(value)

    if not math.isfinite(price) or price <= 0:
        raise ValueError(
            "this demo requires finite positive prices"
        )

    event, published, available = (
        parse_time(row[name])
        for name in (
            "event_time",
            "published_time",
            "available_time",
        )
    )

    if not event <= published <= available:
        raise ValueError(
            "quote timestamps violate "
            "event <= published <= available"
        )

    return Quote(
        row["source"],
        row["event_id"],
        row["symbol"],
        event,
        published,
        available,
        price,
    )


class Monitor:
    def __init__(
        self,
        window: int = 3,
        threshold: float = 0.015,
    ):
        if (
            isinstance(window, bool)
            or not isinstance(window, int)
            or window < 2
        ):
            raise ValueError(
                "window must be an integer >= 2"
            )

        if (
            not math.isfinite(threshold)
            or threshold <= 0
        ):
            raise ValueError(
                "threshold must be finite and positive"
            )

        self.window = window
        self.threshold = threshold

        self.seen: dict[
            tuple[str, str], tuple
        ] = {}

        self.latest: dict[
            tuple[str, str], Quote
        ] = {}

        self.returns: dict[
            tuple[str, str], deque[float]
        ] = {}

        self.last_available: datetime | None = None

    def process(
        self,
        q: Quote,
    ) -> tuple[str, str, dict | None]:
        if (
            self.last_available is not None
            and q.available_time < self.last_available
        ):
            return (
                "invalid",
                "input is not ordered by available_time",
                None,
            )

        self.last_available = q.available_time

        message_key = (q.source, q.event_id)
        old_identity = self.seen.get(message_key)

        if old_identity is not None:
            status = (
                "duplicate"
                if old_identity == q.identity()
                else "conflict"
            )
            return status, "existing message key", None

        asset_key = (q.source, q.symbol)
        previous = self.latest.get(asset_key)

        if (
            previous is not None
            and q.event_time <= previous.event_time
        ):
            self.seen[message_key] = q.identity()
            return (
                "late",
                "event time does not advance; "
                "retained for replay",
                None,
            )

        r = (
            None
            if previous is None
            else (
                (q.price - previous.price)
                / previous.price
            )
        )

        if r is not None and not math.isfinite(r):
            return "invalid", "return overflow", None

        values = list(
            self.returns.get(asset_key, ())
        )

        if r is not None:
            values.append(r)

        values = values[-self.window:]
        n = len(values)

        mean = math.fsum(values) / n if n else None

        variance = (
            math.fsum(
                (x - mean) ** 2
                for x in values
            ) / (n - 1)
            if n >= 2
            else None
        )

        # 全部数值计算成功后再改变本资产状态。
        self.seen[message_key] = q.identity()
        self.latest[asset_key] = q
        self.returns[asset_key] = deque(
            values,
            maxlen=self.window,
        )

        feature = {
            "source": q.source,
            "symbol": q.symbol,
            "event_id": q.event_id,
            "event_time": q.event_time.isoformat(),
            "input_available_time": (
                q.available_time.isoformat()
            ),
            "price": q.price,
            "return": r,
            "count": n,
            "mean": mean,
            "sample_std": (
                math.sqrt(variance)
                if variance is not None
                else None
            ),
            "warmup": n < self.window,
            "jump_alert": (
                r is not None
                and abs(r) >= self.threshold
            ),
            "rule_version": "jump-v1-demo",
        }

        return (
            "accepted",
            "validated and applied",
            feature,
        )


def demo_lines() -> list[str]:
    base = datetime(
        2025, 1, 6, 1, 30,
        tzinfo=timezone.utc,
    )

    def row(
        event_id: str,
        symbol: str,
        second: int,
        arrival: int,
        price: float,
    ) -> str:
        return json.dumps(
            {
                "source": "SYNTHETIC",
                "event_id": event_id,
                "symbol": symbol,
                "event_time": (
                    base
                    + timedelta(seconds=second)
                ).isoformat(),
                "published_time": (
                    base
                    + timedelta(seconds=second)
                ).isoformat(),
                "available_time": (
                    base
                    + timedelta(seconds=arrival)
                ).isoformat(),
                "price": price,
            },
            allow_nan=False,
        )

    return [
        row("e1", "EQ_DEMO", 0, 1, 100.0),
        row("b1", "BOND_DEMO", 0, 2, 100.0),
        row("g1", "GOLD_DEMO", 0, 3, 2000.0),
        row("f1", "FX_DEMO", 0, 4, 7.0),
        row("e2", "EQ_DEMO", 60, 61, 101.0),
        row("b2", "BOND_DEMO", 60, 62, 100.2),
        row("g2", "GOLD_DEMO", 60, 63, 2020.0),
        row("f2", "FX_DEMO", 60, 64, 7.007),
        row("e3", "EQ_DEMO", 120, 121, 99.99),
        row("e4", "EQ_DEMO", 180, 181, 102.0),
        row("e2", "EQ_DEMO", 60, 182, 101.0),
        row("e_late", "EQ_DEMO", 30, 183, 98.0),
        row("e_bad", "EQ_DEMO", 240, 241, 0.0),
        row("e2", "EQ_DEMO", 60, 242, 101.5),
        "{broken json",
    ]


def run(
    lines: Iterable[str],
    output: Path,
) -> dict:
    output.mkdir(
        parents=True,
        exist_ok=False,
    )

    monitor = Monitor()
    counts: Counter = Counter()

    latest_feature: dict[
        tuple[str, str], dict
    ] = {}

    # 一个输入行对应一条审计记录；
    # 原文保留在 raw 字段中。
    with (
        output / "audit.jsonl"
    ).open("w", encoding="utf-8") as audit:

        for line_no, line in enumerate(
            lines,
            start=1,
        ):
            raw = line.rstrip("\r\n")
            feature = None

            try:
                q = parse_quote(raw)
                status, reason, feature = (
                    monitor.process(q)
                )
            except (
                ValueError,
                KeyError,
                TypeError,
                OverflowError,
            ) as exc:
                status = "invalid"
                reason = (
                    f"{type(exc).__name__}: {exc}"
                )

            record = {
                "line": line_no,
                "raw": raw,
                "status": status,
                "reason": reason,
                "feature": feature,
            }

            audit.write(
                json.dumps(
                    record,
                    ensure_ascii=False,
                    allow_nan=False,
                )
                + "\n"
            )

            counts[status] += 1

            if feature is not None:
                latest_feature[
                    (q.source, q.symbol)
                ] = feature

    summary = {
        "data_kind": "synthetic_or_user_supplied",
        "counts": dict(counts),
        "latest": [
            latest_feature[k]
            for k in sorted(latest_feature)
        ],
    }

    (
        output / "summary.json"
    ).write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )

    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    output = (
        args.out
        or Path(__file__).parent
        / "runs"
        / datetime.now(timezone.utc).strftime(
            "run_%Y%m%dT%H%M%S_%fZ"
        )
    )

    if args.input is None:
        summary = run(demo_lines(), output)
    else:
        with args.input.open(
            encoding="utf-8-sig"
        ) as stream:
            summary = run(stream, output)

    print(
        json.dumps(
            summary["counts"],
            ensure_ascii=False,
            sort_keys=True,
        )
    )

    print(
        f"Artifacts: {output.resolve()}"
    )


if __name__ == "__main__":
    main()
```

### 六、核心代码解释

**1．为什么先解析，再更新状态？**

如果输入缺字段、价格非法或时间无法解析，程序应在更新资产状态之前失败。

否则可能发生：

> 新价格已经覆盖旧价格，但统计量更新失败。

下一条消息将基于错误的内部状态计算。

**2．为什么排除布尔价格？**

在Python中：

```python
isinstance(True, int)
```

结果为`True`。

如果只判断`isinstance(value, (int, float))`，`True`可能被当成价格1。因此代码先排除`bool`。

**3．为什么消息标识与资产键不同？**

消息键：

```python
(source, event_id)
```

用于识别来源中的同一业务消息。

资产键：

```python
(source, symbol)
```

用于保存该资产的最新价格和收益窗口。

它们分别回答：

- 这条消息处理过吗？
- 这条消息属于哪一组计算状态？

**4．为什么重复判断不比较本次获取时间？**

同一业务消息可能被重新投递。

两次投递的`available_time`可以不同，但资产、事件时间、发布时间和价格相同，仍应识别为重复。

这里的获取时间表示本次到达；若要记录“系统首次见到该业务事实的时间”，需要另外保存首次获取记录。

**5．为什么迟到消息不更新最新价格？**

因为本章选择了“保持当前状态、保留迟到证据”的策略。

这是明确的简化策略，不是一般意义上的乱序处理完成方案。

**6．`warmup`表示什么？**

当窗口目标长度为3，而当前只有1个或2个收益时：

```python
warmup = True
```

下游可以据此决定是否使用该统计量。

代码仍输出当前已有样本的统计，同时明确样本数量不足。不能仅显示一个标准差数值而隐藏样本量。

**7．程序是否具有幂等性？**

**幂等性，Idempotency**，通常指同一操作重复执行不会产生额外的业务状态变化。

本章同一进程中，重复消息不会再次更新价格和收益窗口。

但每次投递仍会增加一条审计记录，而且进程重启后去重内存会丢失。因此这里只实现了有限范围内的资产状态去重，不能据此声称端到端Exactly-once。

### 七、运行环境与方法

本章已经在你的现有环境中验证：

```text
解释器：D:\Anaconda\python.exe
Python：3.13.5
额外依赖：无
```

在PowerShell中运行：

```powershell
Set-Location 'E:\AAAstudy\国元证券金融科技竞赛\教材\code\ch01'

& 'D:\Anaconda\python.exe' monitor.py
```

默认创建新的运行目录，保存：

```text
audit.jsonl
summary.json
```

已有输出目录不会被覆盖。

读取自己的JSONL文件：

```powershell
& 'D:\Anaconda\python.exe' monitor.py --input '.\quotes.jsonl'
```

这里的文件必须满足本章契约；正式比赛数据还需要适配器。

### 八、实际验证结果

演示输入共15条，程序实际得到：

```json
{
  "accepted": 10,
  "conflict": 1,
  "duplicate": 1,
  "invalid": 2,
  "late": 1
}
```

数量满足：

```text
10+1+1+2+1 = 15
```

这是一项简单但有价值的守恒检查：

> 每条输入都应当能在处理结果中找到去向。

配套验证代码：

[test_monitor.py](./code/ch01/test_monitor.py)

运行：

```powershell
& 'D:\Anaconda\python.exe' -m unittest -v test_monitor.py
```

已经通过6项验证：

1. 演示输入的分类数量与收益计算正确；
2. 非法价格和时间得到拒绝；
3. 重复、冲突、迟到不会覆盖最新价格；
4. 窗口统计与独立计算结果一致；
5. 追加未来消息不改变过去输出；
6. 不符合获取时间顺序的输入被明确标记。

这些验证用于检查本章的语义边界，不代表完整平台已经通过压力、故障恢复或安全测试。

---

## 金融场景案例：四类资产的统一处理与解释边界

演示包含四个资产：

| 资产代码 | 教学含义 | 价格口径 |
|---|---|---|
| `EQ_DEMO` | 股票类代理 | 人工价格序列 |
| `BOND_DEMO` | 债券类代理 | 人工价格序列 |
| `GOLD_DEMO` | 黄金类代理 | 人工价格序列 |
| `FX_DEMO` | 外汇类代理 | 人工汇率序列 |

这些名称只是示例标签，不对应实际交易品种。

### 一、股票类代理

有效价格为：

```text
100, 101, 99.99, 102
```

三个收益分别为：

```text
r_1 = ((101-100) / (100)) = 0.01
```

```text
r_2 = ((99.99-101) / (101)) = -0.01
```

```text
r_3 = ((102-99.99) / (99.99)) ≈ 0.0201020102
```

因此：

```text
r̄ = ((0.01-0.01+0.0201020102) / (3)) ≈ 0.0067006701
```

即每个观测区间的算术平均收益约为：

```text
0.670067%
```

实际程序的窗口样本标准差约为：

```text
s ≈ 0.0153198217
```

即：

```text
1.531982%
```

最后一期：

```text
|r_3|>1.5%
```

所以演示规则产生跳变标志。

整个价格区间的累计收益则为：

```text
R = ((102) / (100))-1 = 2%
```

**窗口收益均值、单期收益和累计收益是三个不同的量。**

### 二、债券类代理

价格：

```text
100→100.2
```

简单价格收益为：

```text
r = ((100.2-100) / (100)) = 0.002 = 0.2%
```

但真实债券监控还要区分：

- 净价与全价；
- 应计利息；
- 票息现金流；
- 久期与信用利差。

本章计算的是人工价格变化，不能自动解释为债券总收益。

### 三、黄金类代理

价格：

```text
2000→2020
```

收益：

```text
r = ((2020-2000) / (2000)) = 1%
```

虽然价格绝对变化为20，与股票例子不同，但收益率归一化后可以比较变化比例。

然而不同资产的常态波动和流动性不同，统一使用1.5%的阈值未必具有相同风险含义。

### 四、外汇类代理

汇率：

```text
7.000→7.007
```

变化比例为：

```text
r = ((7.007-7.000) / (7.000)) = 0.001 = 0.1%
```

“汇率上升”意味着哪种货币升值，取决于标价方式。

因此，资产主数据必须记录：

- 基准货币；
- 报价货币；
- 标价方向；
- 单位和倍率。

计算公式正确，不代表金融解释已经正确。

### 五、本章为何还不能识别市场状态

要识别**市场状态，Market Regime**，至少还需要回答：

- 状态描述的是哪个市场和时间尺度？
- 依据趋势、波动、流动性还是宏观驱动？
- 状态是互斥类别还是多个并行维度？
- 如何评价状态稳定性？
- 怎样处理判断不确定和状态过渡？

单个收益超阈值，只能构成一个局部观测证据。

市场状态识别、未来收益预测与交易决策将在后续章节分别建模。

---

## 工程实现与常见问题

### 一、价格有效性必须按品种定义

本章要求正价格，是为了明确简单收益和对数收益的适用范围。

这个规则不能直接推广到所有金融合约。

正确的工程实现应当由资产类型和字段语义决定：

- 是否允许0；
- 是否允许负数；
- 最小报价单位；
- 价格上下界；
- 合约倍率；
- 适用的收益或损益定义。

违反某条规则的记录应被隔离并保留原因，不能没有说明地从数据中消失。

### 二、计数窗口不等于时间窗口

最近3条收益，可能来自：

- 3秒；
- 3分钟；
- 几小时；
- 数据中断后的几个不等长区间。

因此本章的标准差是“最近3个有效观测区间的离散程度”。

不能未经频率检查就乘：

```text
sqrt(252)
```

或其他系数进行年化。

年化涉及采样频率、交易日历及收益依赖结构，后续会单独讨论。

### 三、缺失消息会改变收益跨度

如果中间一条行情未能进入计算：

```text
09:30 → 09:31 → 09:32
```

可能变成：

```text
09:30 → 09:32
```

此时收益跨度更长。

本章没有自动插补。正式系统需要保留：

- 两端事件时间；
- 区间长度；
- 数据新鲜度；
- 中断与恢复标记。

不能把所有相邻观测收益都假定为同样长度的一分钟收益。

### 四、消息冲突不应随意覆盖

同一个消息标识出现不同价格时，本章保留为冲突。

正式系统还需要区分：

- 合法修订；
- 来源撤销；
- 消息标识复用；
- 接入程序错误；
- 字段口径变化。

如果来源明确提供修订序号，应使用修订模型，而不是永久拒绝所有变更。

### 五、获取时间应由可信接入环节记录

示例把`available_time`写在输入中，方便重放。

实际在线接入时，本系统获取时间应由接入程序记录，不能未经检查直接相信外部消息声称的“系统获取时间”。

PIT，即**截至时点一致性，Point-in-Time**，要求按照当时真实可用的信息重建输入。

仅有一个时间戳字段远远不够。

### 六、内存去重不能无限增长

本章`seen`保存本次运行中出现过的唯一消息。

正式系统可能采用：

- 持久化去重表；
- 有边界的状态保留；
- 来源序号与偏移量；
- 历史重放范围约束；
- 数据库唯一约束。

状态保留时间不能随意设置。若允许重放30天数据，却只保留1小时去重信息，就需要另行保证重放的业务幂等性。

### 七、写文件不等于崩溃一致性

本章先更新内存，再写审计文件。

如果进程恰好在两步之间崩溃，两者可能不一致。

此外，普通文件写入也没有自动提供分布式事务。

因此本章不能保证：

- 重启后继续原状态；
- 业务输出恰好一次；
- 内存、文件和外部通知一致提交。

后续会通过日志、检查点、幂等输出和事务边界讨论这些问题。

### 八、审计日志也需要边界

保存原始消息有助于复现，但正式平台还要考虑：

- 数据授权范围；
- 访问权限；
- 保存周期；
- 磁盘容量；
- 日志完整性；
- 敏感字段处理。

审计日志用于追溯，不应成为无限增长且无人管理的第二套数据库。

---

## 本章总结

本章建立了平台开发的第一组基础：

1. 金融计算必须先明确资产、单位、口径和时间。
2. 第一条行情没有可比前值时，收益应为空。
3. 简单收益跨期需要复利连接，不能直接相加。
4. 列表、字典、集合和双端队列解决不同问题。
5. 重复、冲突、迟到和非法数据具有不同语义。
6. 数据清洗应留下原始记录和处理理由。
7. 程序正确性应通过不变量和独立计算检查。
8. 窗口统计和跳变标志还不能构成完整市场状态识别。
9. 本章单进程实现为后续数据工程、流计算和模型服务提供可检查的计算基础。

---

## 分层练习题

### A组：基础理解

**习题1**

解释以下四个值在行情处理中可能分别表示什么：

```python
None
0.0
float("nan")
False
```

为什么不能统一替换为0？

**习题2**

判断下列程序输出，并解释原因：

```python
a = [{"price": 100.0}]
b = a.copy()
b[0]["price"] = 101.0

print(a[0]["price"])
```

提出一种适合本章行情对象的避免误改方案。

### B组：数学推导

**习题3**

价格依次为：

```text
200, 220, 198
```

计算：

1. 两个单期简单收益；
2. 单期收益的算术平均；
3. 累计收益；
4. 对数收益之和。

说明第2项和第3项为何不同。

**习题4**

设窗口已有：

```text
r_1 = 0.01, r_2 = -0.02, r_3 = 0.03
```

新收益为：

```text
r_4 = 0.00
```

窗口长度为3。

计算更新前后的均值和样本方差，并验证滚动总和公式。

### C组：编程与算法

**习题5**

用列表保存已见消息，每次线性查找。

1. 推导处理`N`条互不重复消息时的比较次数。
2. 当`N = 10000`时计算比较次数。
3. 说明字典方法的平均复杂度和额外存储成本。

**习题6**

编写函数：

```python
first_ge(values, target)
```

输入升序列表，返回第一个不小于`target`的元素位置。

若不存在，返回列表长度。

要求：

- 空列表能够运行；
- 正确处理重复值；
- 时间复杂度为`O(log n)`；
- 解释循环不变量。

**习题7**

不保存全部历史观测，只保存：

- 数量`n`；
- 均值`m`；
- 离差平方和`M_2`。

推导新观测`x`到达时的更新公式，并编写代码。

说明该算法能否直接代替固定长度滚动窗口。

### D组：金融分析

**习题8**

两个资产都触发“单期变化超过1.5%”：

- 资产A平时每期波动很小；
- 资产B平时每期波动较大。

说明为什么同一阈值不一定代表同等异常程度。提出两种改进方向，并说明局限。

**习题9**

以下全部为人工宏观数据：

- 10:00:00首次发布指标值1.9；
- 10:00:05本系统获取；
- 次日10:00:00发布修订值2.1；
- 次日10:00:04本系统获取修订。

回答：以下时点的在线系统可以使用什么值？

1. 首日09:59:59；
2. 首日10:00:03；
3. 首日10:00:06；
4. 次日10:00:02；
5. 次日10:00:05。

假设计算耗时暂时忽略。

### E组：开放式工程设计

**习题10**

把本章处理器改造成“进程崩溃后可以恢复，并且重复消息不会重复产生业务预警”的系统。

给出：

- 持久化内容；
- 消息键与预警键；
- 恢复步骤；
- 需要测试的崩溃位置；
- 尚不能保证的语义。

不得只回答“使用Kafka即可”。

---

## 详细参考答案

### 习题1参考答案

四个值不能混为一谈。

`None`可以表示尚无前一条价格，因此收益无法定义。

`0.0`表示已经完成计算，结果确实为零。

`NaN`可能来自非法计算、缺失传播或外部输入，需要识别来源。它具有特殊比较行为，例如：

```python
x = float("nan")
print(x == x)
```

输出为`False`。

`False`表示逻辑否定。如果被当成数值0，可能掩盖类型错误。

全部替换成0会：

1. 人为增加有效样本；
2. 改变均值和标准差；
3. 把数据故障误写成市场平稳；
4. 使下游无法区分缺失和真实零变化。

合理做法是保留空值或质量状态，并在模型使用前明确定义处理规则。

### 习题2参考答案

输出：

```text
101.0
```

`a.copy()`只复制外层列表。内部字典仍由`a`和`b`共同引用。

一种方案是重新构造记录：

```python
a = [{"price": 100.0}]
b = [{**row} for row in a]
b[0]["price"] = 101.0

print(a[0]["price"])
```

输出：

```text
100.0
```

但如果字典内部还含嵌套可变对象，这仍不等于深复制。

对本章结构，更适合使用字段明确、不可随意改写的数据类，清洗时创建新对象，并保留原始对象与变更原因。

### 习题3参考答案

第一期：

```text
r_1 = ((220-200) / (200)) = 0.10
```

第二期：

```text
r_2 = ((198-220) / (220)) = -0.10
```

算术平均：

```text
r̄ = ((0.10-0.10) / (2)) = 0
```

累计收益：

```text
R = (1.10)(0.90)-1 = -0.01 = -1%
```

也可以直接计算：

```text
R = ((198) / (200))-1 = -1%
```

对数收益之和：

```text
ℓ_1+ℓ_2 = ln((220) / (200)) + ln((198) / (220))
```

利用对数乘法法则：

```text
ℓ_1+ℓ_2 = ln((198) / (200)) = ln(0.99) ≈ -0.0100503359
```

算术平均为0，只说明两个单期收益数值的平均为0。累计收益还包含复利乘积项：

```text
r_1 r_2 = -0.01
```

因此两者不同。

### 习题4参考答案

更新前：

```text
S = 0.01-0.02+0.03 = 0.02
```

均值：

```text
r̄ = ((0.02) / (3)) = ((1) / (150)) ≈ 0.0066666667
```

三个离差为：

```text
((1) / (300)), -((2) / (75)), ((7) / (300))
```

离差平方和为：

```text
M_2 = (((1) / (300)))^2 + (-((2) / (75)))^2 + (((7) / (300)))^2
```

统一分母：

```text
M_2 = ((1+64+49) / (90000)) = ((114) / (90000)) = ((19) / (15000))
```

样本方差：

```text
s^2 = ((M_2) / (2)) = ((19) / (30000)) ≈ 0.0006333333
```

更新后窗口为：

```text
[-0.02, 0.03, 0]
```

滚动总和：

```text
S_new = 0.02-0.01+0 = 0.01
```

均值：

```text
r̄_new = ((0.01) / (3)) = ((1) / (300))
```

离差为：

```text
-((7) / (300)), ((8) / (300)), -((1) / (300))
```

离差平方和：

```text
M_(2,new) = ((49+64+1) / (90000)) = ((19) / (15000))
```

因此：

```text
s^2_new = ((19) / (30000))
```

这个例子中均值变化，但样本方差恰好不变。不能据此推断滚动更新通常保持方差不变。

### 习题5参考答案

第`i`条消息需要比较前面`i-1`个标识，因此：

```text
C(N) = ∑_(i = 1)^N(i-1) = ((N(N-1)) / (2))
```

代入：

```text
N = 10000
```

得到：

```text
C(10000) = ((10000 × 9999) / (2)) = 49 995 000
```

这是比较次数的理论计算，不是实际运行时间测试结果。

字典成员查询在适当散列条件下平均为`O(1)`，处理全部消息平均接近`O(N)`。

但字典需要保存键和对应内容，占用`O(U)`额外状态，而且实际内存开销通常大于简单存放若干整数所需的字节数。

### 习题6参考答案

完整实现：

```python
def first_ge(values, target):
    left = 0
    right = len(values)

    while left < right:
        middle = (left + right) // 2

        if values[middle] < target:
            left = middle + 1
        else:
            right = middle

    return left


assert first_ge([], 3) == 0
assert first_ge([1, 2, 2, 5], 2) == 1
assert first_ge([1, 2, 2, 5], 3) == 3
assert first_ge([1, 2, 2, 5], 6) == 4
```

循环不变量为：

- `left`之前的元素都小于目标；
- `right`及其之后的元素都不小于目标；
- 待确定边界位于`[left, right]`。

若中点元素小于目标，答案不可能在中点及其左侧，因此移动左边界。

否则中点可能是答案，不能跳过它，故令右边界等于中点。

每次区间大致减半，经过`k`次后长度约为：

```text
((n) / (2^k))
```

当其不超过1：

```text
2^k ≥ n
```

因此：

```text
k ≥ log _2 n
```

时间复杂度为：

```text
O(log n)
```

额外空间为：

```text
O(1)
```

### 习题7参考答案

设旧样本量为`n-1`，旧均值为`m`，新观测为`x`。

定义：

```text
δ = x-m
```

新均值：

```text
m' = (((n-1)m+x) / (n))
```

整理：

```text
m' = m+((x-m) / (n)) = m+((δ) / (n))
```

对旧观测`x_i`：

```text
x_i-m' = (x_i-m)-((δ) / (n))
```

把所有旧观测的平方展开并求和：

```text
∑_(i = 1)^(n-1)(x_i-m')^2 = M_2 + (n-1)((δ^2) / (n^2))
```

其中交叉项为0，因为：

```text
∑_(i = 1)^(n-1)(x_i-m) = 0
```

新观测相对新均值的离差为：

```text
x-m' = δ-((δ) / (n)) = δ((n-1) / (n))
```

加入它的平方：

```text
M_2' = M_2 + (n-1)((δ^2) / (n^2)) + δ^2 (((n-1)^2) / (n^2))
```

合并：

```text
M_2' = M_2+δ^2 ((n-1) / (n))
```

也可写为：

```text
M_2' = M_2+δ(x-m')
```

实现：

```python
import math


class OnlineMoments:
    def __init__(self):
        self.n = 0
        self.mean = 0.0
        self.m2 = 0.0

    def update(self, x):
        if not math.isfinite(x):
            raise ValueError("观测必须是有限数")

        self.n += 1

        delta = x - self.mean
        self.mean += delta / self.n
        delta_after = x - self.mean

        self.m2 += delta * delta_after

    def sample_variance(self):
        if self.n < 2:
            return None
        return self.m2 / (self.n - 1)


stats = OnlineMoments()

for value in [0.01, -0.02, 0.03]:
    stats.update(value)

print(stats.mean)
print(stats.sample_variance())
```

它维护从开始到当前的全部观测统计，每次更新只需固定数量运算，额外空间为`O(1)`。

**它不能直接代替固定长度滚动窗口。**

滚动窗口还需要移除离开的旧观测，并处理移除产生的数值误差与边界情况。

### 习题8参考答案

同一个绝对收益阈值忽略了资产自身尺度。

一种改进是标准化：

```text
z_t = ((r_t-μ̂_(t-1)) / (σ̂_(t-1)))
```

这里均值和标准差只用当前观测之前的信息估计，避免当前异常同时改变基准。

局限包括：

- 波动估计存在误差；
- 标准差接近0时不稳定；
- 厚尾分布下不能把`z`值直接解释为正态尾部概率；
- 波动突然改变时历史尺度可能失效。

另一种改进是历史经验分位数阈值：

> 与过去同一资产、相近频率和交易时段的变化分布比较。

局限包括：

- 需要足够样本；
- 极端分位数估计不稳定；
- 市场制度变化后历史分位数可能不适用；
- 反复监测会增加总误报数量。

无论采用哪种方法，都应在时间顺序验证中评价误报、漏报和检测延迟。

### 习题9参考答案

按本系统实际获取时间：

| 时点 | 可使用值 | 原因 |
|---|---:|---|
| 首日09:59:59 | 无 | 尚未发布和获取 |
| 首日10:00:03 | 无 | 已公开发布，但系统尚未获取 |
| 首日10:00:06 | 1.9 | 首次发布值已经获取 |
| 次日10:00:02 | 1.9 | 修订已发布，但系统尚未获取 |
| 次日10:00:05 | 2.1 | 修订已经获取 |

如果研究问题是“公开市场在何时可能知道”，发布时间可能是相应边界。

如果研究问题是“本平台当时能够做出什么输出”，必须使用本平台获取时间，并进一步考虑计算完成时间。

历史回放首日数据时，不能把后来修订的2.1填回首日特征。

### 习题10参考答案

一种参考方案如下。

**持久化内容**

至少包括：

- 原始输入日志及来源位置；
- 消息业务键；
- 已接受行情状态；
- 收益窗口；
- 规则版本；
- 预警业务键；
- 已处理位置或恢复点。

**键设计**

消息键可为：

```text
(source, event_id, revision)
```

其中`revision`是否存在由来源契约决定。

预警键可以包含：

```text
(rule_version, source, symbol, event_id, alert_type)
```

保证同一事件、同一规则版本的同类预警可以被唯一约束。

不能只使用“当前时间”作为预警键，否则重放会生成新键。

**恢复流程**

1. 读取最近一次完整提交的状态与处理位置。
2. 从该位置后重放原始消息。
3. 使用消息键检查重复。
4. 按相同规则版本恢复统计。
5. 通过预警唯一键避免重复业务记录。
6. 将外部发送状态与内部预警记录关联。

**需要注入故障的位置**

至少包括：

- 输入已读取，状态尚未更新；
- 状态更新后，处理位置尚未提交；
- 预警记录写入后，外部发送之前；
- 外部发送成功后，发送结果尚未记录；
- 恢复时再次遇到同一消息。

**尚不能保证的部分**

数据库中预警记录唯一，不等于外部接收者只收到一次。

例如发送成功后进程崩溃，系统不知道发送是否成功，重试可能重复。

需要结合接收端幂等键、事务性待发送记录、重试协议及明确的业务容忍方式设计。

本题参考评分：

| 方面 | 比例 |
|---|---:|
| 数据与状态持久化完整性 | 25% |
| 消息键、时间与版本语义 | 25% |
| 崩溃恢复和重放逻辑 | 20% |
| 预警输出的一致性边界 | 15% |
| 可执行测试与容量考虑 | 15% |

仅列出Kafka、Redis、数据库等技术名称，没有解释提交边界和恢复步骤，不足以构成完整答案。

---

## 推荐教材与延伸阅读

### 1．John V. Guttag，2016

**Introduction to Computation and Programming Using Python: With Application to Understanding Data，第二版，MIT Press。**

- 对应内容：程序分解、函数、数据结构、测试与计算思维。
- 阅读位置：与MIT 6.0001第4—12讲对应学习；具体页码按所持版本定位。
- 适合阶段：初学至本科。
- 推荐理由：强调如何把问题转化为可以计算和检验的程序。
- 合法入口：[MIT课程大纲中的书目信息](https://ocw.mit.edu/courses/6-0001-introduction-to-computer-science-and-programming-in-python-fall-2016/pages/syllabus/)。

图书不假定免费，公开课程材料可作为配套。

### 2．Ana Bell、Eric Grimson、John Guttag，2016

**MIT 6.0001: Introduction to Computer Science and Programming in Python。**

- 阅读位置：第4讲函数，第5讲容器与可变性，第7讲测试，第8—9讲类，第10—12讲效率与搜索。
- 适合阶段：初学。
- 推荐理由：有讲义、代码和练习，便于与本章程序逐项对照。
- 官方入口：[Lecture Slides and Code](https://ocw.mit.edu/courses/6-0001-introduction-to-computer-science-and-programming-in-python-fall-2016/pages/lecture-slides-code/)。

### 3．邓俊辉，2013

**《数据结构（C++语言版）》，第三版。**

- 对应内容：算法分析、线性结构、栈与队列、结构选择。
- 阅读位置：作者官网教材及“数据结构[基础]”课程入口；按版本目录定位对应主题。
- 适合阶段：本科进阶。
- 推荐理由：有助于理解数据结构的实现机制和性能差异。
- 合法入口：[作者教材页面](https://dsa.cs.tsinghua.edu.cn/~deng/ds/dsacpp/)、[配套MOOC说明](https://dsa.cs.tsinghua.edu.cn/~deng/ds/mooc/)。

本教材采用Python，不要求先掌握全套C++语法。

### 4．Erik Demaine、Jason Ku、Justin Solomon，2020

**MIT 6.006: Introduction to Algorithms。**

- 对应内容：计算问题建模、复杂度、数据结构与算法正确性。
- 阅读位置：课程Lecture Notes与搜索、序列结构相关材料。
- 适合阶段：掌握基础Python之后。
- 推荐理由：帮助从“代码能运行”进一步走向“解释为什么正确、为什么高效”。
- 官方入口：[MIT 6.006](https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020/)。

### 5．Python Software Foundation，持续更新

**Python 3.13官方文档。**

- 本次查阅日期：2026年10月21日。
- 阅读位置：教程第4、5、9、15节，以及`collections`、`datetime`、`dataclasses`、`json`、`unittest`条目。
- 适合阶段：所有阶段，按问题查阅。
- 推荐理由：核实语言和标准库实际行为。
- 官方入口：[Python 3.13文档](https://docs.python.org/3.13/)。

这是持续更新的版本文档，不具有单一固定出版年份；网页显示的补丁版本可能高于本地安装版本。本章以现有Anaconda中的Python 3.13.5实际运行结果为准。

---

**本次进度：已完成十篇99章三级目录，以及第一篇第1章全部教学内容。第一章配套程序已运行，6项验证通过；未下载教材PDF或安装额外依赖。**

**下次续写位置：第一篇第2章《NumPy、Pandas与科学计算》，从学习目标及2.1“数组、广播、向量化与内存布局”开始。**

