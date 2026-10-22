# 第一篇　数学、统计学与编程基础
# 第2章　NumPy、Pandas与科学计算

[返回总目录](./00_完整目录.md) · [上一章](./01_第1章_Python编程、数据结构与算法基础.md) · [完整实验代码](./code/ch02/panel_lab.py) · [验证代码](./code/ch02/test_panel_lab.py)

本章把第一章逐条处理行情的思路扩展到一批资产、一段时间和多张表。目标是建立能够解释每一行、每一列、每个缺失值及其可用时间的数据面板。

**所有行情、宏观值和时间线均为人工示例，不是官方赛题数据或真实市场实验结果。**

## 学习目标

### 先修知识

完成第一章，理解函数、字典、异常、简单收益率及三个时间字段；会运行Python脚本。尚不要求掌握矩阵分解或统计推断。

### 学习结果

完成本章后，应能够：

1. 根据业务含义设计数组形状，解释数据类型、轴、步长和内存开销。
2. 区分逐元素计算、广播、归约与矩阵乘法。
3. 识别数组视图、复制和不必要的临时数组。
4. 使用Series、DataFrame、索引、分组、连接和透视。
5. 在不填造零收益的前提下构造多资产收益面板。
6. 同时检查价格有效性、标签一致性和时间可用性。
7. 重建人工宏观指标的首次发布与修订查询。
8. 验证NumPy、pandas和标量计算的数值一致性。

### 已验证环境

```text
解释器：D:\Anaconda\python.exe
Python：3.13.5
NumPy：2.1.3
pandas：2.2.3
```

使用现有Anaconda，不安装新解释器或额外依赖。工程行为按NumPy 2.1和pandas 2.2文档核对，而不是假定不同版本完全相同。

---

## 2.1　数组、广播、向量化与内存布局

### 一、把金融数据映射到数组

NumPy，即**Numerical Python，数值Python**，提供多维数组和数值计算工具。其核心对象`ndarray`是具有统一数据类型的多维数组。

设价格面板为：

\[
P\in\mathbb{R}^{T\times A}
\]

这里：

- \(T\)：时间点数量；
- \(A\)：资产数量；
- \(P_{t,a}\)：第\(t\)个时间点、第\(a\)个资产的价格；
- \(\mathbb{R}^{T\times A}\)：由实数构成的\(T\)行、\(A\)列数组。

这些符号目前只表示表格结构，矩阵理论将在下一章学习。

本章约定：**行表示时间，列表示资产。** 小节片段说明局部操作；完整依赖、输入和执行入口集中在2.3的完整程序。不同小节会分别使用NumPy数组与pandas表，须以当前对象定义为准。

```python
import numpy as np

prices = np.array([
    [100.00, 100.0],
    [101.00, 100.2],
    [ 99.99, 100.1],
    [102.00, 100.3],
], dtype=np.float64)

print(prices.shape)     # (4, 2)
print(prices.ndim)      # 2
print(prices.size)      # 8
print(prices.dtype)     # float64
```

**形状，Shape**，记录每个维度的长度；**轴，Axis**，指定沿哪个维度执行操作。`shape=(4,2)`不会自动附带“时间×资产”的业务解释，必须由程序和文档共同约定。[NumPy数组入门](https://numpy.org/doc/2.1/user/quickstart.html)

模型中还可能出现：

\[
X\in\mathbb{R}^{B\times L\times A\times F}
\]

其中\(B\)为样本批次数，\(L\)为回看长度，\(F\)为特征数量。交换轴的顺序可能仍产生合法数组，却改变模型看到的含义。

### 二、数据类型不仅影响内存，也影响答案

**数据类型，Data Type，dtype**，决定每个元素的表示方式。

| 类型 | 常见用途 | 需要注意 |
|---|---|---|
| `float64` | 价格、收益、统计计算 | 仍是有限精度 |
| `float32` | 大型模型输入 | 精度较低，需要误差验证 |
| `int64` | 数量、离散序号 | 固定位宽，存在溢出边界 |
| `bool` | 有效性掩码 | 不能直接代表价格 |
| `object` | 通用Python对象 | 不宜作为密集数值计算的默认表示 |

例如：

```python
import numpy as np

a = np.float32(100_000_000)
b = np.float32(100_000_001)

print(a == b)  # True
```

在这个量级，`float32`已经不能区分相差1的这两个数。若先丢失价格精度，再计算收益，换成`float64`也不能恢复丢失的信息。

因此，降低精度应遵循：

> 先定义业务容许误差，再比较关键统计和模型输出，最后决定存储或计算精度。

不能只检查程序是否报错，也不能把本例推广为“所有金融数据都必须用同一种类型”。

### 三、内存布局与步长

对没有额外对象引用的密集数值数组，数据缓冲区大小为：

\[
\text{bytes}
=
\left(\prod_{k=0}^{d-1}n_k\right)b
\]

其中：

- \(d\)：维度数量；
- \(n_k\)：第\(k\)个维度长度；
- \(b\)：每个元素字节数。

上述\(4\times2\)的`float64`价格数组占用：

\[
4\times2\times8=64\text{字节}
\]

这只是元素缓冲区，不包括Python对象、索引、其他数组和进程开销。

```python
print(prices.itemsize)  # 8
print(prices.nbytes)    # 64
print(prices.strides)   # 通常为 (16, 8)
```

**步长，Stride**，表示沿某个轴移动一个位置时，内存地址变化多少字节。

对本例按行连续存储的数组：

\[
s_0=2\times8=16,\qquad s_1=8
\]

元素\((i,j)\)相对首元素的字节偏移为：

\[
\operatorname{offset}(i,j)=is_0+js_1
\]

所以\((2,1)\)的偏移为：

\[
2\times16+1\times8=40
\]

转置、切片可以改变步长；并非每个数组都按行连续。某些下游运算还可能为满足连续布局要求而创建复制。[ndarray内存布局](https://numpy.org/doc/2.1/reference/arrays.ndarray.html#internal-memory-layout-of-an-ndarray)

### 四、索引、切片、视图与复制

```python
print(prices[0, 0])     # 第一时点、第一资产
print(prices[:, 0])     # 第一资产的全部时间
print(prices[1:3, :])   # 第1、2行，右边界不包含
```

**视图，View**，与原数组共享数据；**复制，Copy**，拥有独立的数据缓冲区。

```python
import numpy as np

original = np.array([100.0, 101.0, 102.0])
view = original[1:]
view[0] = 999.0

print(original)                       # [100. 999. 102.]
print(np.shares_memory(original, view))  # True

independent = original[1:].copy()
independent[0] = 888.0

print(original[1])                    # 999.0
```

基本数组切片通常返回视图；整数数组和布尔数组进行高级索引时通常返回复制。但直接对原数组执行高级索引赋值，会修改原数组：

```python
x = np.array([10.0, 20.0, 30.0])
selected = x[[0, 2]]
selected[0] = -1.0
print(x[0])             # 10.0

x[[0, 2]] = 0.0
print(x)                # [ 0. 20.  0.]
```

判断共享关系可用`np.shares_memory`。不能因为有了“新变量名”就假定数据独立；也不能笼统断言所有`reshape`都会复制或都不复制。[视图与复制](https://numpy.org/doc/2.1/user/basics.copies.html)

### 五、向量化不是消灭计算步骤

**向量化，Vectorization**，是以数组操作表达一批元素的计算，减少逐元素进入Python解释器的开销。

对正价格面板：

\[
R_{t,a}=\frac{P_{t,a}}{P_{t-1,a}}-1
\]

没有缺失和非法价格时，可写为：

```python
returns = prices[1:, :] / prices[:-1, :] - 1.0
print(returns.shape)  # (3, 2)
```

其中：

- `prices[1:, :]`：当前端点；
- `prices[:-1, :]`：前一端点；
- 相同位置执行除法。

标量双循环与数组表达式仍然都要处理约\(TA\)个元素，时间复杂度通常都是\(O(TA)\)。差别主要来自执行开销、底层实现和内存访问，而不是复杂度自动降低。

NumPy的**通用函数，Universal Function，ufunc**，支持数组级逐元素计算。`np.vectorize`则主要提供调用便利，其实现本质上仍接近循环，不能据名称认定它必然加速。[numpy.vectorize说明](https://numpy.org/doc/2.1/reference/generated/numpy.vectorize.html)

向量化也不意味着运算自动在GPU上执行。

### 六、广播：不显式复制的形状匹配

**广播，Broadcasting**，允许某些形状不同的数组进行逐元素运算。

比较形状时从最右边的维度开始。不足的维度在左侧视为1。每个对应维度必须：

1. 长度相等；或
2. 其中一个长度为1。

输出采用非1的长度；两者都为1时输出为1。长度不兼容时应报错。[广播规则](https://numpy.org/doc/2.1/user/basics.broadcasting.html)

设：

\[
R\in\mathbb{R}^{T\times A},\qquad
\mu\in\mathbb{R}^{A}
\]

把\(\mu\)解释为每个资产的均值，则：

\[
Z_{t,a}=R_{t,a}-\mu_a
\]

对应：

```python
asset_mean = returns.mean(axis=0)  # shape: (2,)
centered = returns - asset_mean
```

形状对齐为：

```text
returns:     (3, 2)
asset_mean:     (2)
补齐后:      (1, 2)
结果:        (3, 2)
```

如果需要减去每个时间点的横截面均值：

```python
time_mean = returns.mean(axis=1, keepdims=True)  # (3, 1)
cross_centered = returns - time_mean
```

两者的金融含义不同：

- 前者比较某资产相对自身样本中心的位置；
- 后者比较同一时点各资产相对横截面中心的位置。

**当时间数量恰好等于资产数量时，错误方向也可能合法广播。形状检查是必要条件，不是语义正确的充分条件。**

### 七、归约和矩阵乘法

**归约，Reduction**，把某个轴上的多个元素汇总为较少元素。

对`shape=(T,A)`的收益矩阵：

| 操作 | 输出形状 | 含义 |
|---|---|---|
| `R.mean(axis=0)` | `(A,)` | 每个资产的时间平均 |
| `R.mean(axis=1)` | `(T,)` | 每个时点的横截面平均 |
| `R.mean()` | 标量 | 所有元素混在一起的平均 |
| `R.mean(axis=0, keepdims=True)` | `(1,A)` | 保留资产轴对应形状 |

`R * w`是逐元素加权；`R @ w`是矩阵与向量的乘积：

\[
s_t=\sum_{a=1}^{A}R_{t,a}w_a
\]

对于以统一基础货币计价、口径一致且权重为期初权重的简单总收益，类似表达式可以计算组合收益。本章跨资产原始价格尚未完成这些处理，因此只把它用作**监控加权分数**。

### 八、掩码与安全除法

**掩码，Mask**，是与数据相对应的布尔数组，用于指明哪些位置符合规则。

```python
valid = np.isfinite(prices) & (prices > 0)
```

数组条件使用`&`、`|`和`~`，并对比较表达式加括号。Python的`and`、`or`不是对应的逐元素操作。

下面的写法仍可能先计算除零：

```python
# 不作为安全除法方案：
# result = np.where(previous > 0, current / previous - 1, np.nan)
```

函数接收到参数之前，`current / previous`已经执行，`np.where`不会把它变成逐元素的惰性分支。

正确做法是在除法本身施加条件：

```python
import numpy as np

current = np.array([101.0, 102.0, np.nan])
previous = np.array([100.0, 0.0, 100.0])

valid = (
    np.isfinite(current)
    & np.isfinite(previous)
    & (current > 0)
    & (previous > 0)
)

result = np.full(current.shape, np.nan)
np.divide(current, previous, out=result, where=valid)
result -= 1.0

print(result)  # [0.01  nan  nan]
```

必须先初始化`out`；否则未执行除法的位置可能保留未初始化内容。[numpy.divide](https://numpy.org/doc/2.1/reference/generated/numpy.divide.html)

完整实验还检查：有效端点上的除法是否发生溢出，避免把计算失败静默当成普通缺失。

### 九、有缺失值时的统计定义

设\(I_a\)为资产\(a\)的有效收益位置集合，\(n_a=|I_a|\)为有效样本数。

当\(n_a>0\)：

\[
\bar r_a=\frac{\sum_{t\in I_a}R_{t,a}}{n_a}
\]

当\(n_a>1\)：

\[
s_a^2
=
\frac{\sum_{t\in I_a}(R_{t,a}-\bar r_a)^2}{n_a-1}
\]

当条件不满足时，对应统计量应为空。

NumPy普通`mean/std`通常会传播`NaN`；`nanmean/nanstd`忽略`NaN`，但不自动把无穷当成缺失；pandas的`mean/std`默认跳过缺失。因此先统一有效值口径，再比较结果。[NumPy nanmean](https://numpy.org/doc/2.1/reference/generated/numpy.nanmean.html)、[nanstd](https://numpy.org/doc/2.1/reference/generated/numpy.nanstd.html)

这意味着统计结果至少应附带有效样本数量。两列标准差数值接近，但一列只有2个样本、另一列有2000个样本，证据强度不同。

NumPy的`std`默认`ddof=0`，分母为\(n\)；pandas的`DataFrame.std`默认`ddof=1`，分母为\(n-1\)。公平比较必须显式统一定义。[NumPy std](https://numpy.org/doc/2.1/reference/generated/numpy.std.html)、[pandas std](https://pandas.pydata.org/pandas-docs/version/2.2/reference/api/pandas.DataFrame.std.html)

`ddof`表示**自由度调整，Delta Degrees of Freedom**。选择`ddof=1`不自动证明相关、非平稳金融样本具有某种无偏估计性质。

### 十、数值一致性应使用明确容差

`np.isclose(a,b)`使用类似：

\[
|a-b|\leq \operatorname{atol}+\operatorname{rtol}|b|
\]

的准则，其中\(b\)是参考值，因此通常不是对称定义；它与第一章`math.isclose`的公式也不同。[numpy.isclose](https://numpy.org/doc/2.1/reference/generated/numpy.isclose.html)

验证收益计算：

```python
np.testing.assert_allclose(
    actual,
    expected,
    rtol=1e-12,
    atol=1e-15,
    equal_nan=True,
)
```

这里`actual`和`expected`分别代表待检查结果与独立参考结果。容差应与任务精度要求相符。不能通过放宽容差掩盖轴方向、单位或时间对齐错误。

---

## 2.2　表格、索引、分组、连接与缺失值

### 一、Series：标签与数值共同构成数据

pandas的**序列，Series**，是一维带标签的数据结构；**数据框，DataFrame**，是带行列标签的二维表格，可以包含不同类型的列。[数据结构说明](https://pandas.pydata.org/pandas-docs/version/2.2/user_guide/dsintro.html)

```python
import pandas as pd

r = pd.Series(
    [0.01, 0.03],
    index=["EQ_DEMO", "BOND_DEMO"],
)

w = pd.Series(
    [0.8, 0.2],
    index=["BOND_DEMO", "EQ_DEMO"],
)

print((r * w).sum())               # 0.026
print(r.to_numpy() @ w.to_numpy()) # 0.014
```

第一式按资产标签对齐：

\[
0.01\times0.2+0.03\times0.8=0.026
\]

第二式丢掉标签，按当前位置相乘：

\[
0.01\times0.8+0.03\times0.2=0.014
\]

两个程序都没有报错，但第二个不符合此处权重定义。

从DataFrame转换为NumPy之前，应固定：

- 行索引；
- 资产顺序；
- 特征顺序；
- 数据类型；
- 缺失处理策略。

这些顺序也应随模型制品保存。

### 二、选择、过滤与赋值

```python
frame = pd.DataFrame({
    "symbol": ["EQ_DEMO", "BOND_DEMO"],
    "price": [101.0, 100.2],
})

print(frame.loc[0, "price"])  # 按标签
print(frame.iloc[0, 1])       # 按位置

selected = frame.loc[
    frame["price"].gt(100),
    ["symbol", "price"],
].copy()

frame.loc[frame["symbol"].eq("EQ_DEMO"), "price"] = 102.0
```

`loc`的标签切片通常包含结束标签；`iloc`的位置切片不包含结束位置。使用前应区分标签和整数位置。

避免链式赋值：

```python
# 不采用：
# frame[frame["symbol"] == "EQ_DEMO"]["price"] = 102.0
```

选出的中间对象是否与原表共享数据，不应成为程序正确性依赖。对本章pandas 2.2环境，采用显式`loc`赋值和在需要时`copy()`的方式。[索引与赋值](https://pandas.pydata.org/pandas-docs/version/2.2/user_guide/indexing.html)

### 三、缺失值具有不同来源

pandas中常见：

- `NaN`：浮点缺失或非法数值结果；
- `NaT`：日期时间缺失；
- `pd.NA`：部分可空类型采用的缺失标记。

使用`isna()`、`notna()`检查，不能靠`x == np.nan`。[缺失数据说明](https://pandas.pydata.org/pandas-docs/version/2.2/user_guide/missing_data.html)

对金融系统，应继续区分缺失原因：

| 原因 | 可能的处理 |
|---|---|
| 尚未发布或尚未获取 | 保持未知，等待新数据 |
| 市场休市 | 结合交易日历解释 |
| 接入故障 | 触发数据质量预警 |
| 字符串无法解析 | 隔离并保留原文 |
| 样本数量不足 | 输出统计为空及数量 |
| 字段不适用 | 不强行生成数值 |

本章数值数组用`NaN`表达“该位置不提供有效数值”，具体原因另存审计表，不能让一个`NaN`代替全部质量解释。

### 四、类型转换必须保留证据

```python
raw_price = pd.Series(["100.0", "oops", "101.5"])
numeric = pd.to_numeric(raw_price, errors="coerce")

quality = pd.DataFrame({
    "raw_price": raw_price,
    "numeric_price": numeric,
    "parse_failed": raw_price.notna() & numeric.isna(),
})

print(quality)
```

结果中`"oops"`转为空，但仍可在`raw_price`找到原文。

`errors="coerce"`只是转换行为，不是清洗策略。后续还需决定隔离、停止、修复或重新获取，并记录原因。

日期处理也一样：`pd.to_datetime(..., utc=True)`可以把没有时区的时间解释为UTC，因此**使用`utc=True`不等于验证原数据本来携带时区**。本章先检查显式时区，再转换。[to_datetime文档](https://pandas.pydata.org/pandas-docs/version/2.2/reference/api/pandas.to_datetime.html)

### 五、分组计算：避免跨资产取前值

长表中一行对应一条观测：

```text
event_time  source     symbol      price
09:30       SYNTHETIC  EQ_DEMO     100
09:31       SYNTHETIC  BOND_DEMO   200
09:32       SYNTHETIC  EQ_DEMO     110
```

直接对整列价格`shift(1)`会把不同资产相邻行连接起来。

应先排序并按业务键分组：

```python
ordered = quotes.sort_values(
    ["source", "symbol", "event_time"]
).copy()

previous = ordered.groupby(
    ["source", "symbol"],
    sort=False,
)["price_numeric"].shift(1)
```

这里`quotes`表示已经解析的行情表。

不过，按资产分组只保证“同一资产”，并不保证固定时间跨度。例中股票类代理的100到110跨越2分钟，不能自动标成一分钟收益。

### 六、长表与宽表

**长表，Long Format**，便于存储来源、资产、时间和质量字段。

**宽表，Wide Format**，把资产展开为列，适合密集计算。

```python
wide = quotes.pivot(
    index="event_time",
    columns="symbol",
    values="price_numeric",
)
```

同一来源内，若“事件时间—资产”不唯一，`pivot`应当失败，迫使开发者解释重复含义。

不能为了让代码运行，直接换成默认取平均的`pivot_table`，把冲突报价悄悄平均掉。

实际项目先完成消息去重、来源选择和版本消歧；本章检测到未解决的重复业务键时明确停止。

### 七、连接的行数为什么可能膨胀

行情表连接资产元数据：

```python
joined = quotes.merge(
    assets,
    on=["source", "symbol"],
    how="left",
    validate="many_to_one",
    indicator=True,
)
```

`validate="many_to_one"`要求右表业务键唯一。`indicator=True`增加`_merge`列，帮助发现没有匹配到元数据的行情。

如果左表某个键有\(n_L(k)\)行，右表同键有\(n_R(k)\)行，普通匹配可能产生：

\[
n_L(k)n_R(k)
\]

行。

若左边有3行报价，右边误存2行同键元数据，就可能得到6行；这些重复行还会改变统计权重。[连接与重复键](https://pandas.pydata.org/pandas-docs/version/2.2/user_guide/merging.html)

pandas可能将两侧空连接键相互匹配，这与某些SQL空值行为不同。因此业务键应先验证，不能把空资产代码当成合法资产。

### 八、重建时间网格与禁止隐式填充

设某资产价格为：

\[
100,\quad\mathrm{NaN},\quad110,\quad121
\]

按固定相邻网格计算：

\[
\mathrm{NaN},\quad\mathrm{NaN},\quad\mathrm{NaN},\quad0.1
\]

如果先向前填充：

\[
100,\quad100,\quad110,\quad121
\]

则收益变成：

\[
\mathrm{NaN},\quad0,\quad0.1,\quad0.1
\]

这里凭空出现了零收益，还把跨两个网格的变化移到了一个网格。

本章明确使用：

```python
returns = wide.pct_change(fill_method=None)
```

`pct_change`输出的是小数变化比例，0.01代表1%，不是已经乘100的百分数。[pct_change文档](https://pandas.pydata.org/pandas-docs/version/2.2/reference/api/pandas.DataFrame.pct_change.html)

即便如此，还必须检查时间可用性：该函数不会自动知道某个价格当时是否已经收到。

### 九、重采样不是自动解决时间有效性

**重采样，Resampling**，把原有时间索引映射到目标频率并聚合。

例如：

```python
minute_last = tick_prices.resample(
    "1min",
    label="right",
    closed="right",
).last()
```

这里`tick_prices`应为按事件时间建立索引的价格序列，区间按右端闭合，例如\((09{:}30,09{:}31]\)，标签放在09:31。

但是，09:31对应的最后成交可能直到09:31:05才收到。把聚合结果标记为09:31，并不意味着平台能在09:31:00立即使用。

交易时段、停牌、跨市场日历与迟到聚合将在后续章节展开。本章只使用预先声明的人工分钟网格。

### 十、文件格式与模式恢复

CSV方便人工检查，但通常不会完整保存：

- 时区类型；
- 可空整数类型；
- 列的业务单位；
- 索引层次；
- 数据质量规则。

读取时应显式恢复模式，例如：

```python
table = pd.read_csv(
    "quotes.csv",
    dtype={"symbol": "string"},
)
```

随后按契约解析时间和数值。

直接读取资产代码可能丢失前导零。不能因为文件能打开，就认为数据模式没有变化。

本章使用JSONL保存原始结构化示例，用CSV输出检查表，再用清单文件记录环境和数据口径。生产场景下，原始文件字节、来源授权和模式版本也应保留。

---

## 2.3　多资产收益面板与数值一致性

### 一、同时定义价格、时间与可用性

沿用第一章资产代码，扩展为四个时间点：

| UTC事件时间 | EQ_DEMO | BOND_DEMO | GOLD_DEMO | FX_DEMO |
|---|---:|---:|---:|---:|
| 01:30 | 100.00 | 100.0 | 2000 | 7.000 |
| 01:31 | 101.00 | 100.2 | 2020 | 7.007 |
| 01:32 | 99.99 | 100.1 | 暂不可用 | 7.000 |
| 01:33 | 102.00 | 100.3 | 2030 | 6.993 |

其他记录在事件后1—4秒获得。黄金类代理01:32的价格2025直到01:34:10才收到。

本章人为设置：

\[
d_t=t+10\text{秒}
\]

其中\(d_t\)是计划决策时点。这个10秒是**教学配置**，不是实测延迟或系统性能承诺。

再设：

- \(C\)：本次重放的截止时间；
- \(K_{t,a}\)：价格\(P_{t,a}\)的获取时间；
- \(d_t\leq C\)：只输出截止时间之前已经到达的决策。

一个单期收益在\(d_t\)可计算，至少要求：

\[
P_{t,a},P_{t-1,a}\text{均为有限正数}
\]

并且：

\[
K_{t,a}\leq d_t,\qquad K_{t-1,a}\leq d_t
\]

满足条件时：

\[
R_{t,a}
=
\frac{P_{t,a}}{P_{t-1,a}}-1
\]

否则输出为空，并通过输入审计与覆盖度解释。

这两个获取时间都必须与**当前决策时点**比较。前一期价格即使晚于前一期决策到达，只要早于当前决策，仍可能用于当前收益计算。

因此，不能先把“前一期决策时未知的价格”永久删除，再简单对显示表`shift(1)`。计算所需的历史端点和当时显示的行情表不是同一个对象。

真实系统还要求计算已经完成。本章暂时假定计算在预留时间内完成；生产实现必须记录和验证特征就绪时间。

### 二、预期收益面板

在上述规则下：

| UTC事件时间 | EQ_DEMO | BOND_DEMO | GOLD_DEMO | FX_DEMO |
|---|---:|---:|---:|---:|
| 01:30 | 空 | 空 | 空 | 空 |
| 01:31 | 0.010000 | 0.002000 | 0.010000 | 0.001000 |
| 01:32 | -0.010000 | -0.000998 | 空 | -0.000999 |
| 01:33 | 0.020102 | 0.001998 | 空 | -0.001000 |

表中为小数收益，并作了显示舍入。

01:33黄金价格已知，但前一分钟端点当时未知，故该分钟收益仍为空。不能把01:31到01:33的两分钟变化当成01:33的一分钟收益。

### 三、覆盖度与监控加权分数

人为设置监控权重：

\[
w=(0.4,\ 0.3,\ 0.2,\ 0.1)
\]

这些正权重之和为1，仅用于教学。

设：

\[
M_{t,a}=
\begin{cases}
1,&R_{t,a}\text{有效}\\
0,&\text{否则}
\end{cases}
\]

定义加权覆盖度：

\[
c_t=\sum_a w_aM_{t,a}
\]

本例覆盖度为：

\[
0,\quad1,\quad0.8,\quad0.8
\]

覆盖度衡量按这组权重计算时的数据完整程度，不能解释为市场健康概率或流动性指标。

当四个收益全部有效时，计算：

\[
s_t=\sum_a w_aR_{t,a}
\]

否则令\(s_t\)为空。

01:31的分数为：

\[
s
=
0.4(0.01)+0.3(0.002)+0.2(0.01)+0.1(0.001)
=0.0067
\]

对应实现：

```python
score = returns.mul(weights, axis=1).sum(
    axis=1,
    min_count=len(weights),
)
```

`min_count`控制至少需要多少个非缺失值。[DataFrame.sum](https://pandas.pydata.org/pandas-docs/version/2.2/reference/api/pandas.DataFrame.sum.html)

普通求和常跳过缺失。若缺失资产被悄悄排除，或剩余权重被悄悄归一化，监控分数的定义就变了。允许降级计算时，应另设清楚的指标名称和覆盖条件。

### 四、滚动统计怎样避免使用后续观测

长度3的右对齐窗口为：

\[
W_t=\{R_{t-2,a},R_{t-1,a},R_{t,a}\}
\]

当三个位置都有效，均值为：

\[
\bar r_{t,a}
=
\frac{R_{t-2,a}+R_{t-1,a}+R_{t,a}}{3}
\]

标准差为：

\[
s_{t,a}
=
\sqrt{
\frac{
\sum_{i=t-2}^{t}(R_{i,a}-\bar r_{t,a})^2
}{2}
}
\]

代码：

```python
rolling_std = returns.rolling(
    window=3,
    min_periods=3,
).std(ddof=1)
```

这里`min_periods=3`要求该窗口内有3个有效观测；它不是要求“从其他时间凑足3条数据”。默认右对齐有助于按过去与当前计算，不能为方便绘图随意改成居中窗口。[rolling文档](https://pandas.pydata.org/pandas-docs/version/2.2/reference/api/pandas.DataFrame.rolling.html)

用当前收益识别当前状态时，可以明确使用当前已知信息；若声称在本期开始前预测本期结果，则不能把期末价格计算出的特征放到期初。

### 五、宏观首次发布与修订的查询

人工指标`CPI_DEMO`针对同一个观测期`2024-12`：

| 修订序号 | 值 | 发布时间 | 获取时间 |
|---|---:|---|---|
| 0 | 1.9 | 01:31:00 | 01:31:02 |
| 1 | 2.1 | 01:33:00 | 01:33:20 |

若查询时间为\(d\)，本例选择：

\[
j^*(d)
=
\arg\max_{j:\ K_j\leq d}K_j
\]

即在已经获取的版本中选择最后获取的版本。这里额外假设：只有一个指标、一个观测期，修订按序到达，代码也检查这些条件。

对应工具是按时间向后匹配的`merge_asof`：

```python
result = pd.merge_asof(
    queries.sort_values("decision_time"),
    versions.sort_values("available_time"),
    left_on="decision_time",
    right_on="available_time",
    direction="backward",
)
```

两侧匹配时间须有序。使用`nearest`可能匹配到查询时点之后的记录，不能作为本例的在线查询规则。[merge_asof文档](https://pandas.pydata.org/pandas-docs/version/2.2/reference/api/pandas.merge_asof.html)

不要把多个观测期的全部修订直接混在一起“取最后一条”：较旧观测期的晚到修订可能覆盖新观测期。本章函数对此明确拒绝，完整版本模型留到第20章。

### 六、完整可运行实验

完整程序包括：

1. 人工行情、资产元数据与宏观版本生成；
2. 原始表快照；
3. 类型、时间、价格及资产映射检查；
4. 行级审计与截止时间过滤；
5. 价格、获取时间和收益面板；
6. 加权覆盖度、监控分数及滚动标准差；
7. 宏观时点查询；
8. 版本和运行清单。

本章输入应已由前级解决消息重投与业务冲突。若检测到重复消息键或重复行情网格键，程序明确停止，不擅自平均或覆盖。

```python
"""第2章：NumPy/pandas多资产面板实验；全部输入为人工数据。"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


def utc_time(value) -> pd.Timestamp:
    result = pd.Timestamp(value)
    if pd.isna(result) or result.tzinfo is None:
        raise ValueError("as_of must contain a timezone")
    return result.tz_convert("UTC")


def demo_data():
    clock = pd.date_range("2025-01-06T01:30:00Z", periods=4, freq="min")
    prices = {
        "EQ_DEMO": [100.0, 101.0, 99.99, 102.0],
        "BOND_DEMO": [100.0, 100.2, 100.1, 100.3],
        "GOLD_DEMO": [2000.0, 2020.0, None, 2030.0],
        "FX_DEMO": [7.0, 7.007, 7.0, 6.993],
    }
    rows = []
    for j, (symbol, values) in enumerate(prices.items()):
        for i, value in enumerate(values):
            if value is not None:
                rows.append({
                    "source": "SYNTHETIC", "event_id": f"{symbol}-{i}",
                    "symbol": symbol, "price": value,
                    "event_time": clock[i].isoformat(),
                    "published_time": clock[i].isoformat(),
                    "available_time": (clock[i] + pd.Timedelta(seconds=j + 1)).isoformat(),
                })
    rows.append({
        "source": "SYNTHETIC", "event_id": "GOLD_DEMO-2-late",
        "symbol": "GOLD_DEMO", "price": 2025.0,
        "event_time": clock[2].isoformat(), "published_time": clock[2].isoformat(),
        "available_time": "2025-01-06T01:34:10+00:00",
    })
    assets = pd.DataFrame({
        "source": ["SYNTHETIC"] * 4, "symbol": list(prices),
        "asset_class": ["equity", "bond", "commodity", "fx"],
        "monitor_weight": [0.4, 0.3, 0.2, 0.1],
    })
    macro = pd.DataFrame({
        "indicator": ["CPI_DEMO", "CPI_DEMO"],
        "observation_period": ["2024-12", "2024-12"],
        "revision": [0, 1], "value": [1.9, 2.1],
        "published_time": ["2025-01-06T01:31:00Z", "2025-01-06T01:33:00Z"],
        "available_time": ["2025-01-06T01:31:02Z", "2025-01-06T01:33:20Z"],
    })
    return pd.DataFrame(rows), assets, macro, clock


def prepare_quotes(raw, assets, as_of):
    required = {"source", "event_id", "symbol", "price",
                "event_time", "published_time", "available_time"}
    if not required.issubset(raw.columns):
        raise ValueError(f"missing columns: {sorted(required - set(raw.columns))}")
    keys = ["source", "symbol"]
    if assets[keys].isna().any().any() or assets.duplicated(keys).any():
        raise ValueError("asset keys must be non-null and unique")
    cutoff = utc_time(as_of)
    q = raw.copy(deep=True).reset_index(drop=True)
    q["input_row"] = np.arange(len(q))
    bad_id = pd.Series(False, index=q.index)
    for name in ("source", "symbol", "event_id"):
        bad_id |= ~q[name].map(lambda x: isinstance(x, str) and bool(x.strip()))
    bad_time = pd.Series(False, index=q.index)
    for name in ("event_time", "published_time", "available_time"):
        explicit = q[name].astype("string").str.contains(r"(?:Z|[+-]\d{2}:\d{2})$", na=False)
        q[name] = pd.to_datetime(q[name], utc=True, errors="coerce", format="ISO8601")
        bad_time |= ~explicit | q[name].isna()
    q["price_numeric"] = pd.to_numeric(q["price"], errors="coerce").astype("float64")
    bad_price = (~np.isfinite(q["price_numeric"]) | q["price_numeric"].le(0)
                 | q["price"].map(lambda x: isinstance(x, (bool, np.bool_))))
    bad_order = ~(q["event_time"].le(q["published_time"])
                  & q["published_time"].le(q["available_time"]))
    q = q.merge(assets, on=keys, how="left", validate="many_to_one", indicator=True)
    # merge保持左表行序；显式验证后使用与原输入对应的质量掩码。
    if q["input_row"].tolist() != list(range(len(raw))):
        raise RuntimeError("unexpected input row order")
    q["bad_id"], q["bad_time"], q["bad_price"] = bad_id, bad_time, bad_price
    q["bad_time_order"] = bad_order
    q["status"] = np.select(
        [bad_id, bad_time, bad_price, bad_order, q["_merge"].eq("left_only"),
         q["available_time"].gt(cutoff)],
        ["invalid_id", "invalid_time", "invalid_price", "invalid_time_order",
         "unknown_asset", "not_available"], default="accepted")
    accepted = q.loc[q["status"].eq("accepted")].copy()
    for unique_key in (["source", "event_id"], ["source", "symbol", "event_time"]):
        if accepted.duplicated(unique_key).any():
            raise ValueError(f"resolve duplicate/conflicting keys upstream: {unique_key}")
    return accepted, q


def safe_returns(current, previous):
    current = np.asarray(current, dtype="float64")
    previous = np.asarray(previous, dtype="float64")
    if current.shape != previous.shape:
        raise ValueError("price arrays must have identical shapes")
    valid = (np.isfinite(current) & np.isfinite(previous)
             & (current > 0) & (previous > 0))
    result = np.full(current.shape, np.nan, dtype="float64")
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        np.divide(current, previous, out=result, where=valid)
        result -= 1.0
    if np.any(valid & ~np.isfinite(result)):
        raise FloatingPointError("return overflow on valid endpoints")
    return result


def build_panel(quotes, assets, clock, as_of, source="SYNTHETIC"):
    cutoff = utc_time(as_of)
    clock = pd.DatetimeIndex(clock)
    if clock.tz is None or not clock.is_unique or not clock.is_monotonic_increasing:
        raise ValueError("clock must be ordered, unique and timezone-aware")
    clock = clock.tz_convert("UTC")
    # 固定10秒为教学用决策延迟；不代表实测计算延迟。
    grid = clock[clock + pd.Timedelta(seconds=10) <= cutoff]
    decisions = pd.Series(grid + pd.Timedelta(seconds=10), index=grid)
    meta = assets.loc[assets["source"].eq(source)].set_index("symbol")
    if meta.empty or not meta.index.is_unique:
        raise ValueError("source requires unique asset metadata")
    q = quotes.loc[quotes["source"].eq(source)]
    if not q["event_time"].isin(clock).all():
        raise ValueError("off-grid observations require an explicit resampling rule")
    q = q.loc[q["available_time"].le(cutoff)]
    if q.empty:
        price = pd.DataFrame(np.nan, index=grid, columns=meta.index, dtype="float64")
        ready = pd.DataFrame(pd.NaT, index=grid, columns=meta.index, dtype="datetime64[ns, UTC]")
    else:
        price = q.pivot(index="event_time", columns="symbol", values="price_numeric")
        ready = q.pivot(index="event_time", columns="symbol", values="available_time")
    price = price.reindex(index=grid, columns=meta.index)
    ready = ready.reindex(index=grid, columns=meta.index).astype("datetime64[ns, UTC]")
    current_known = ready.le(decisions, axis=0)
    previous_known = ready.shift(1).le(decisions, axis=0)
    result = safe_returns(price.to_numpy(), price.shift(1).to_numpy())
    returns = pd.DataFrame(result, index=grid, columns=meta.index)
    returns = returns.where(current_known & previous_known)
    known_price = price.where(current_known)
    weights = meta["monitor_weight"].reindex(returns.columns).astype("float64")
    if (not np.isfinite(weights).all() or not weights.gt(0).all()
            or not np.isclose(weights.sum(), 1.0, rtol=0, atol=1e-12)):
        raise ValueError("demo weights must be positive and sum to one")
    monitoring = pd.DataFrame({
        "decision_time": decisions,
        "coverage": returns.notna().mul(weights, axis=1).sum(axis=1),
        "weighted_monitor_score": returns.mul(weights, axis=1).sum(
            axis=1, min_count=len(weights)),
    })
    summary = pd.DataFrame({"count": returns.count(), "mean": returns.mean(),
                            "sample_std": returns.std(ddof=1)})
    return {"prices": known_price, "returns": returns, "monitoring": monitoring,
            "summary": summary, "rolling_std": returns.rolling(3, min_periods=3).std(ddof=1)}


def macro_asof(decision_times, macro, as_of):
    cutoff = utc_time(as_of)
    decisions = pd.DatetimeIndex([utc_time(value) for value in decision_times], tz="UTC")
    if decisions.isna().any() or (decisions > cutoff).any():
        raise ValueError("queries must be valid and no later than as_of")
    m = macro.copy(deep=True)
    if (m[["indicator", "observation_period"]].isna().any().any()
            or m["indicator"].nunique() != 1 or m["observation_period"].nunique() != 1):
        raise ValueError("this demo requires one indicator and one observation period")
    for name in ("published_time", "available_time"):
        explicit = m[name].astype("string").str.contains(r"(?:Z|[+-]\d{2}:\d{2})$", na=False)
        m[name] = pd.to_datetime(m[name], utc=True, errors="coerce", format="ISO8601")
        if not explicit.all() or m[name].isna().any():
            raise ValueError("macro timestamps require explicit timezones")
    if (m["published_time"] > m["available_time"]).any():
        raise ValueError("macro acquisition predates publication")
    m["value"] = pd.to_numeric(m["value"], errors="raise")
    if not np.isfinite(m["value"]).all() or m["available_time"].duplicated().any():
        raise ValueError("macro values must be finite; acquisition ties need disambiguation")
    m = m.loc[m["available_time"].le(cutoff)].sort_values("available_time")
    revision = pd.to_numeric(m["revision"], errors="raise")
    if (not np.isfinite(revision).all() or revision.duplicated().any()
            or not revision.is_monotonic_increasing or not revision.mod(1).eq(0).all()):
        raise ValueError("resolve out-of-order or invalid revisions before this demo join")
    queries = pd.DataFrame({"decision_time": decisions, "query_id": np.arange(len(decisions))})
    result = pd.merge_asof(queries.sort_values("decision_time"), m,
                           left_on="decision_time", right_on="available_time",
                           direction="backward", allow_exact_matches=True)
    result["age"] = result["decision_time"] - result["available_time"]
    return result.sort_values("query_id").reset_index(drop=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    output = args.out or Path(__file__).parent / "runs" / datetime.now(
        timezone.utc).strftime("run_%Y%m%dT%H%M%S_%fZ")
    output.mkdir(parents=True, exist_ok=False)
    raw, assets, macro, clock = demo_data()
    for name, frame in {"raw_quotes": raw, "raw_macro": macro, "assets": assets}.items():
        frame.to_json(output / f"{name}.jsonl", orient="records", lines=True, force_ascii=False)
    cutoff = utc_time("2025-01-06T01:34:00Z")
    accepted, audit = prepare_quotes(raw, assets, cutoff)
    frames = build_panel(accepted, assets, clock, cutoff)
    frames["audit"] = audit
    frames["macro_queries"] = macro_asof([
        "2025-01-06T01:31:01Z", "2025-01-06T01:31:03Z",
        "2025-01-06T01:33:10Z", "2025-01-06T01:33:25Z"], macro, cutoff)
    for name, frame in frames.items():
        frame.to_csv(output / f"{name}.csv", encoding="utf-8-sig", index=True)
    report = {"data_kind": "synthetic", "as_of": cutoff.isoformat(),
              "python_note": "existing Anaconda interpreter",
              "numpy": np.__version__, "pandas": pd.__version__,
              "input_rows": len(raw), "status_counts": audit["status"].value_counts().to_dict(),
              "panel_shape": list(frames["returns"].shape),
              "valid_returns": frames["returns"].count().to_dict()}
    (output / "manifest.json").write_text(json.dumps(report, ensure_ascii=False,
                                                     indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    print(f"Artifacts: {output.resolve()}")


if __name__ == "__main__":
    main()
```

### 七、运行方法与真实执行结果

在PowerShell中：

```powershell
Set-Location 'E:\AAAstudy\国元证券金融科技竞赛\教材\code\ch02'

& 'D:\Anaconda\python.exe' panel_lab.py
& 'D:\Anaconda\python.exe' -m unittest -v test_panel_lab.py
```

代码已经实际运行。截止时间为`2025-01-06T01:34:00Z`时：

```json
{
  "input_rows": 16,
  "status_counts": {
    "accepted": 15,
    "not_available": 1
  },
  "panel_shape": [4, 4],
  "valid_returns": {
    "EQ_DEMO": 3,
    "BOND_DEMO": 3,
    "GOLD_DEMO": 1,
    "FX_DEMO": 3
  }
}
```

输入16条，15条当时可用、1条尚未获取；没有把这1条从原始快照和审计表中删除。

程序保存原始JSONL、审计CSV、价格与收益CSV、滚动统计、宏观查询以及`manifest.json`。默认输出新目录，不覆盖已有运行。

描述性统计结果约为：

| 资产 | 有效收益数 | 均值 | 样本标准差 |
|---|---:|---:|---:|
| EQ_DEMO | 3 | 0.006701 | 0.015320 |
| BOND_DEMO | 3 | 0.001000 | 0.001730 |
| GOLD_DEMO | 1 | 0.010000 | 空 |
| FX_DEMO | 3 | -0.000333 | 0.001154 |

这些是人工小样本的计算结果，不是模型效果或金融结论。

### 八、验证覆盖的行为

11项验证全部通过，检查了：

- 输入去向数量及原始表不被修改；
- NumPy、pandas和标量参考计算一致；
- 缺失价格不变成零收益，也不跨空档补算一分钟收益；
- 不因缺失而隐式调整监控权重；
- 后来获取黄金缺失价格，不改写先前决策输出；
- 前一期报价在前一期决策后到达、但在本期决策前到达时，仍能用于本期收益；
- 宏观值按获取时间和修订查询，保持原查询顺序；
- 零分母、形状错误和溢出得到明确处理；
- 非法价格和无时区时间留下质量标记；
- 重复元数据和未消歧消息明确失败；
- 空截止区间、无时区查询和乱序修订得到处理。

验证针对本章声明的输入条件，不是完整PIT系统或分布式可靠性的证明。

---

## 工程实现与常见问题

### 一、不要把所有表一次展开成巨大数组

\(100000\)个时点、\(500\)个资产的`float64`面板，单个缓冲区为：

\[
100000\times500\times8
=400000000\text{字节}
\]

约400MB，尚不含索引和其他对象。

同时保留当前价格、前值、收益、临时结果和掩码时，峰值内存可能显著增加。广播可以避免显式复制输入，但输出和临时数组仍可能很大。

可采用：

- 分块读取；
- 仅保留所需列；
- 限定资产池；
- 复用合适的输出缓冲区；
- 使用增量算法；
- 测量实际峰值内存后再决定是否需要分布式计算。

分块计算收益时，必须把上一块的最后一个有效网格端点及其时间元数据带到下一块，不能每块重新制造一条“首次观测”。

### 二、排序、连接和透视也有成本

对\(N\)条长表排序，通常需要约\(O(N\log N)\)比较规模；连接成本受键类型、唯一性和数据大小影响；宽表计算及输出通常至少处理\(TA\)个位置。

如果数值运算很快，而大部分时间花在文本解析和重复排序上，仅改写一个算术表达式不会解决瓶颈。

先分别测量读取、解析、连接、计算和写出，再优化实际慢的阶段。

### 三、全样本统计不能直接成为历史在线特征

`summary`汇总本次输出区间，方便检查结果。

它不能直接回填为每个历史时点的“当时均值和波动率”，也不能当作训练期以外已经拟合好的标准化参数。

历史在线特征应逐时点使用可用窗口；模型预处理参数还应按训练集边界拟合。第三篇会系统处理。

### 四、静态元数据也是一个简化假设

本例资产池、类别和监控权重固定，并假定事前已知。

真实资产池存在上市、退市、合约到期、指数成分变化、来源映射更新和权重调整。使用今天的资产池回看历史，可能产生样本选择偏差。

要实现完整历史重建，元数据和配置也应版本化。

### 五、空输入必须保留明确模式

截止时间早于首次决策时，本章返回0行、4列的空收益表，不把“尚无数据”当作崩溃理由。

空日期列仍需明确时区类型；全缺失资产列也要有明确类型。不能依赖非空数据自动推断模式。

### 六、保留时间约束不等于完成市场微观结构建模

本章计算的是人工规则网格上的价格变化。

没有处理：

- 真实交易日历；
- 买卖报价差；
- 陈旧报价；
- 跨市场休市；
- 分红和合约换月；
- 基础货币转换；
- 报价来源的历史修订。

这些问题会改变可比较性和经济解释，应在后续接入和建模时显式解决。

### 七、宏观“最后可用”仍需有效期政策

代码返回获取时间和`age`，没有统一设置“超过多少秒就失效”。

月度宏观指标与高频报价的新鲜度要求不同。不能把所有数据都设成同样的过期时长，也不能无限期沿用旧值而不显示年龄。

### 八、性能报告必须先证明结果一致

比较循环与向量化实现时，应统一：

- 输入数据及其生成方式；
- dtype、形状和缺失比例；
- 输出定义；
- 是否包含读取和转换；
- 重复次数与计时范围；
- 正确性容差；
- 机器与库版本。

本章没有报告未经测量的加速倍数。程序通过并不自动意味着速度更快或资源成本更低。

---

## 本章总结

1. 数组形状、标签和时间语义需要共同定义。
2. 向量化减少解释器开销，仍受算法与内存成本约束。
3. 广播方向合法，不代表金融含义正确。
4. 视图共享、精度转换和标签丢失都可能造成静默错误。
5. 缺失价格不能自动填成零收益。
6. 固定区间收益需要两个端点及其获取时间。
7. 宏观修订应按当时可用版本查询。
8. 覆盖度、样本数量和质量记录应与数值共同输出。
9. 本章面板构件将为线性代数、风险统计、特征工程和模型训练提供统一数据接口。

---

## 分层练习题

### A组：基础理解

**习题1　形状与广播**

设`R.shape == (5, 4)`。判断下列计算能否广播、结果形状是什么，以及需要怎样解释操作数：

1. `R * w`，其中`w.shape == (4,)`；
2. `R - m`，其中`m.shape == (5,)`；
3. `R - m[:, None]`，其中`m.shape == (5,)`；
4. 若`R.shape == (4,4)`，`R-m`没有报错，是否足以证明减的是每行均值？

**习题2　内存与视图**

一个C顺序连续的`float64`数组形状为`(3,4)`。

1. 元素缓冲区有多少字节？
2. 通常步长是什么？
3. 元素`[2,3]`相对起点的字节偏移是多少？
4. 基本切片和显式`copy()`分别对原始数据有什么影响？

### B组：数学推导

**习题3　缺失端点**

同一规则网格上的价格为：

\[
100,\quad \mathrm{NaN},\quad110,\quad121
\]

分别计算不填充与先向前填充后的收益。指出哪些输出不是原始观察所支持的同频收益。说明为什么最后一条有效价格不能替代“上一个规则网格端点”。

**习题4　统计口径**

收益只有：

\[
0.01,\quad-0.01
\]

计算均值、`ddof=0`标准差和`ddof=1`标准差。若另一个资产只有一个有效收益，应输出什么？

**习题5　广播方向的静默错误**

设：

\[
X=\begin{pmatrix}2&10\\4&14\end{pmatrix}
\]

以列为资产，计算列均值。分别写出`X-mu`和`X-mu[:,None]`的结果，解释哪一个完成了按资产去中心化。

### C组：编程与数据工程

**习题6　标签不能随意丢弃**

资产收益为`EQ_DEMO=0.01`、`BOND_DEMO=0.03`。

权重Series按`BOND_DEMO、EQ_DEMO`顺序存放`0.8、0.2`。

写出正确的pandas计算、正确的NumPy计算，以及错误位置相乘的结果。补充一种缺失权重检查。

**习题7　安全除法**

输入：

```python
current = [101.0, 102.0, float("nan"), 99.0]
previous = [100.0, 0.0, 100.0, 100.0]
```

实现有效端点上的收益计算。要求没有除零警告，不能用0替代未知收益，并说明为何`np.where`包住除法仍不足够。

**习题8　带样本数量的统计函数**

实现`masked_moments(x)`，输入二维收益数组，按列输出有效数量、均值和样本标准差。

要求：

- 忽略非有限数，但不修改原数组；
- 全缺失列返回数量0、均值和标准差为空；
- 只有一个样本时标准差为空；
- 不依赖“先把所有缺失填0，再直接平均”的错误方法。

### D组：金融与时间分析

**习题9　两个端点的获取时间**

价格100对应01:30，直到01:30:20获取；价格101对应01:31，01:31:02获取。

决策时点分别为01:30:10与01:31:10。

回答：

1. 01:30:10的行情显示表能否显示100？
2. 01:31:10能否计算这两个网格之间的收益？
3. 先屏蔽每行决策时未知价格，再对显示表取前值，会造成什么问题？

**习题10　宏观修订与观测期**

沿用本章宏观时间线，给出01:31:01、01:31:03、01:33:10、01:33:25可用的值。

随后假设新观测期已发布，旧观测期又发生一次修订。解释为什么全表按获取时间取最后一条，不能直接代表“当前最新观测期的宏观水平”。

### E组：开放式工程设计

**习题11　分块处理**

需要处理100000个时间点、500个资产。

设计分块方案，说明：

- 单个`float64`与`float32`缓冲区大小；
- 块边界需要传递哪些状态；
- 如何证明分块与一次性计算结果一致；
- 为什么只比较运行时间不够。

**习题12　向在线平台交付面板**

为状态识别服务设计一个特征批次契约。至少包含标签顺序、单位、时间、缺失原因、计算版本及降级规则，并给出验收标准。

---

## 详细参考答案

### 习题1参考答案

1. 可以。把`w`视为`(1,4)`，输出`(5,4)`。本例应解释为每个资产一个权重。
2. 不可以。最右维度4与5不相等，也都不为1。
3. 可以。`m[:,None]`形状为`(5,1)`，输出`(5,4)`。若`m`保存每个时点的横截面均值，这样才能逐行减去它。
4. 不足。`(4,)`默认对齐最后一个维度，即列方向。需要确认`m`实际如何生成和如何解释。

形状相等只能证明操作能执行，不能证明资产与时间轴的业务定义一致。

### 习题2参考答案

缓冲区：

\[
3\times4\times8=96\text{字节}
\]

在题设连续布局下：

\[
s_0=4\times8=32,\qquad s_1=8
\]

偏移：

\[
2\times32+3\times8=88\text{字节}
\]

切片示例：

```python
import numpy as np

x = np.arange(12, dtype=np.float64).reshape(3, 4)
shared = x[1:, :]
independent = x[1:, :].copy()

shared[0, 0] = -1.0
independent[0, 1] = -2.0

assert x[1, 0] == -1.0
assert x[1, 1] == 5.0
```

`shared`共享数据，其修改影响原数组。`independent`不共享这部分数据缓冲区。

### 习题3参考答案

不填充：

\[
[\mathrm{NaN},\mathrm{NaN},\mathrm{NaN},0.1]
\]

第一项没有前值；第二项当前缺失；第三项前一个规则端点缺失；第四项有完整端点：

\[
121/110-1=0.1
\]

向前填充后：

\[
[100,100,110,121]
\]

收益：

\[
[\mathrm{NaN},0,0.1,0.1]
\]

第二项0来自人为沿用旧价格，不是新观察。第三项0.1实际上覆盖两个原始网格的价格变化，却被压到一个网格。

最后有效观测100可以用于计算100到110的跨期变化，但需要同时输出正确的时间跨度，不能称作相同频率的一期收益。

### 习题4参考答案

均值：

\[
\bar r=(0.01-0.01)/2=0
\]

离差平方和：

\[
M_2=(0.01)^2+(-0.01)^2=0.0002
\]

`ddof=0`：

\[
s_0=\sqrt{0.0002/2}=0.01
\]

`ddof=1`：

\[
s_1=\sqrt{0.0002/(2-1)}
\approx0.0141421356
\]

若只有一个收益，均值就是该收益；按`ddof=1`定义的样本标准差为空，样本数量应为1。

这不是说资产没有波动，而是当前数据不足以按该公式描述样本离散程度。

### 习题5参考答案

列均值：

\[
\mu=(3,12)
\]

正确计算：

\[
X-\mu
=
\begin{pmatrix}
2-3&10-12\\
4-3&14-12
\end{pmatrix}
=
\begin{pmatrix}
-1&-2\\
1&2
\end{pmatrix}
\]

`mu[:,None]`将其改为列向量：

\[
\begin{pmatrix}3\\12\end{pmatrix}
\]

广播后：

\[
X-\mu[:,None]
=
\begin{pmatrix}
2-3&10-3\\
4-12&14-12
\end{pmatrix}
=
\begin{pmatrix}
-1&7\\
-8&2
\end{pmatrix}
\]

错误结果每列不再以0为均值。它把“第一个资产的均值”用于第一行，把“第二个资产的均值”用于第二行，混淆了资产和时间。

### 习题6参考答案

```python
import pandas as pd

r = pd.Series(
    [0.01, 0.03],
    index=["EQ_DEMO", "BOND_DEMO"],
)
w = pd.Series(
    [0.8, 0.2],
    index=["BOND_DEMO", "EQ_DEMO"],
)

if not r.index.is_unique or not w.index.is_unique:
    raise ValueError("资产标签必须唯一")
if set(r.index) != set(w.index):
    raise ValueError("收益与权重资产集合不同")

aligned_w = w.reindex(r.index)

if aligned_w.isna().any():
    raise ValueError("存在缺失权重")

pandas_score = r.mul(aligned_w).sum(min_count=len(r))
numpy_score = r.to_numpy() @ aligned_w.to_numpy()

print(pandas_score)  # 0.026
print(numpy_score)   # 0.026
```

错误位置相乘：

\[
0.01(0.8)+0.03(0.2)=0.014
\]

多出或缺失资产、重复标签和权重为空，都应在转换之前检查。只检查数组长度相同不够。

### 习题7参考答案

```python
import numpy as np

current = np.array([101.0, 102.0, np.nan, 99.0])
previous = np.array([100.0, 0.0, 100.0, 100.0])

valid = (
    np.isfinite(current)
    & np.isfinite(previous)
    & (current > 0)
    & (previous > 0)
)

result = np.full(current.shape, np.nan)
np.divide(current, previous, out=result, where=valid)
result -= 1

np.testing.assert_allclose(
    result,
    [0.01, np.nan, np.nan, -0.01],
    equal_nan=True,
)
```

`np.where(condition, current / previous, ...)`的除法表达式先执行，因此可能已经除零。把`where`传给除法运算本身，才控制哪些位置执行除法。

对极端量级，还应像完整实验那样检查有限有效端点是否产生非有限结果。

### 习题8参考答案

```python
import numpy as np


def masked_moments(x):
    x = np.asarray(x, dtype=np.float64)
    if x.ndim != 2:
        raise ValueError("需要二维数组")

    valid = np.isfinite(x)
    count = valid.sum(axis=0)

    total = np.where(valid, x, 0.0).sum(
        axis=0, dtype=np.float64
    )

    mean = np.full(count.shape, np.nan, dtype=np.float64)
    np.divide(total, count, out=mean, where=count > 0)

    centered = np.zeros_like(x)
    np.subtract(x, mean, out=centered, where=valid)
    m2 = np.square(centered).sum(axis=0, dtype=np.float64)

    variance = np.full(count.shape, np.nan, dtype=np.float64)
    np.divide(m2, count - 1, out=variance, where=count > 1)

    return count, mean, np.sqrt(variance)


x = np.array([
    [0.01, np.nan, 0.03],
    [-0.01, np.nan, np.nan],
])

count, mean, std = masked_moments(x)

np.testing.assert_array_equal(count, [2, 0, 1])
np.testing.assert_allclose(mean, [0, np.nan, 0.03], equal_nan=True)
np.testing.assert_allclose(
    std,
    [np.sqrt(0.0002), np.nan, np.nan],
    equal_nan=True,
)
```

这里把缺失位置临时写成0只用于求**有效值之和**，分母仍是有效数量，不是总行数；与把缺失当成真实零观测不同。

第二遍只在有效位置计算中心离差。全缺失列不会执行无效位置的减法或除法。

非有限数据的原因仍应由外部审计保存。对于极端大数，还需要另行检查累加和平方溢出。

### 习题9参考答案

1. 不能。01:30:10时还没有收到100。
2. 可以。在01:31:10时，两个端点均已获取，收益为：

\[
101/100-1=0.01
\]

3. 若先把01:30显示表中的100屏蔽为空，再对显示表取前值，会误以为本期没有前端点，从而少算一条实际上已经可以计算的收益。

正确条件是：

\[
K_{t-1,a}\leq d_t
\]

而不是要求：

\[
K_{t-1,a}\leq d_{t-1}
\]

本章在原始端点面板上计算前值，并将两个端点的获取时间与当前决策时点比较。

这也说明，“历史显示结果不可改写”和“当前计算可以使用后来已获得的历史事实”可以同时成立。

### 习题10参考答案

本章查询结果：

| 查询UTC时间 | 可用值 |
|---|---:|
| 01:31:01 | 空 |
| 01:31:03 | 1.9 |
| 01:33:10 | 1.9 |
| 01:33:25 | 2.1 |

01:31:01虽然已经发布，但系统尚未获取。01:33:10虽然修订已发布，但还没收到修订值。

多个观测期时，至少需要区分：

- 指标；
- 观测期；
- 发布批次或修订版本；
- 该版本获取时间。

先在每个观测期内选择当时可用的正确版本，再根据查询语义选“最新观测期”或完整历史序列。

例如新观测期为1月，后来收到12月修订：它应更新12月历史版本，不能把“最新宏观水平”从1月退回12月。

### 习题11参考答案

单个`float64`缓冲区：

\[
100000\times500\times8
=400000000\text{字节}
\]

单个`float32`缓冲区：

\[
100000\times500\times4
=200000000\text{字节}
\]

两者分别约400MB和200MB，仅指元素缓冲区。

参考方案：

1. 按连续时间块读取，固定资产列顺序和dtype。
2. 保留上一块末尾网格的价格及获取时间，供下一块首条收益使用。
3. 若计算长度\(w\)的滚动统计，还需保留足够的前序收益或等价的完整统计状态。
4. 保留缺失、交易间隔和决策时间信息，不能跨块改变时间语义。
5. 每块输出写入新的分区，并记录输入范围、参数和质量数量。

验证至少比较：

- 收益值及空值位置；
- 首尾边界；
- 资产顺序；
- 每行覆盖度；
- 滚动窗口预热状态；
- 宏观查询版本；
- 未来追加数据对既有决策的影响。

可把一次性计算作为小规模参考，使用明确容差比较分块输出。正式速度测试再扩大规模，并分别测量读取、转换、计算、写出和峰值内存。

若更快的方案制造了零收益或跨块前视，它不满足相同任务定义，不能算公平的性能改进。

### 习题12参考答案

一个批次契约可包含：

```text
batch_id
dataset_version
feature_schema_version
asset_mapping_version
configuration_version
source
asset_order
feature_order
event_time
decision_time
input_available_time
feature_ready_time
values
validity_mask
quality_reason
coverage
lookback_definition
units
```

字段的主要责任：

- `asset_order`与`feature_order`固定数值轴含义；
- `units`防止小数收益、百分数及价格单位混用；
- `validity_mask`与`quality_reason`区分可用数值和缺失原因；
- 时间字段区分事件、获取、决策和真正就绪；
- 版本字段使历史重算能够恢复当时配置；
- `lookback_definition`明确计数窗口、时间窗口及边界；
- `coverage`帮助服务判断本批次是否满足输入要求。

可采用“完整输入正常推理、部分输入进入预先验证的降级模型、严重缺失输出状态未知”的规则。阈值和降级模型必须经过验证，不能把“缺数据”直接映射成“低风险”。

参考验收标准：

| 项目 | 权重 |
|---|---:|
| 标签、单位和模式可验证 | 20% |
| 时间与版本可重建 | 25% |
| 缺失、覆盖与降级行为明确 | 20% |
| 数值一致性和边界测试 | 20% |
| 性能、资源与运行记录 | 15% |

仅有数组形状和接口地址不足以支撑可复现的金融状态识别服务。

---

## 推荐教材与延伸阅读

### 1．Wes McKinney，2022

**Python for Data Analysis，第三版，O’Reilly。**

- 知识点：NumPy数组、pandas表格、清洗、连接和时间序列。
- 阅读位置：第4章数组；第5章pandas；第7章清洗；第8章连接与重塑；第10章分组；第11章时间序列。
- 推荐理由：帮助把分散API组织成可解释的数据处理流程。
- 适合阶段：第一章之后至本科进阶。
- 合法入口：[作者公开HTML版本](https://wesmckinney.com/book/)、[第4章](https://wesmckinney.com/book/numpy-basics)、[第5章](https://wesmckinney.com/book/pandas-basics)、[第8章](https://wesmckinney.com/book/data-wrangling)。

作者允许在线阅读，正文转载条件与示例代码许可不同。本章采用独立表述与自行编写的金融示例。

### 2．NumPy开发团队，NumPy 2.1官方手册

- 年份说明：版本文档，无单一出版年；本次查阅日期为2026年10月21日。
- 知识点：形状、dtype、步长、视图和复制。
- 阅读位置：`The N-dimensional array`的`Internal memory layout`；`Copies and views`。
- 推荐理由：准确核对数组共享和内存行为。
- 适合阶段：入门至工程进阶。
- 官方入口：[ndarray](https://numpy.org/doc/2.1/reference/arrays.ndarray.html)、[Copies and views](https://numpy.org/doc/2.1/user/basics.copies.html)。

### 3．NumPy开发团队，广播与数值API文档

- 年份说明：NumPy 2.1版本文档，2026年查阅。
- 知识点：广播、安全除法、标准差与近似比较。
- 阅读位置：`Broadcasting`，以及`divide`、`std`、`isclose`条目。
- 推荐理由：理解参数的精确定义及容易忽略的边界。
- 适合阶段：完成2.1之后。
- 官方入口：[广播](https://numpy.org/doc/2.1/user/basics.broadcasting.html)、[divide](https://numpy.org/doc/2.1/reference/generated/numpy.divide.html)、[std](https://numpy.org/doc/2.1/reference/generated/numpy.std.html)、[isclose](https://numpy.org/doc/2.1/reference/generated/numpy.isclose.html)。

### 4．pandas开发团队，pandas 2.2.3用户指南

- 年份说明：版本文档，2026年查阅。
- 知识点：标签、索引、缺失数据、连接和表格变形。
- 阅读位置：`Intro to data structures`、`Indexing and selecting data`、`Working with missing data`、`Merge, join, concatenate and compare`。
- 推荐理由：核对自动对齐、赋值和连接基数行为。
- 适合阶段：2.2及工程实践。
- 官方入口：[数据结构](https://pandas.pydata.org/pandas-docs/version/2.2/user_guide/dsintro.html)、[索引](https://pandas.pydata.org/pandas-docs/version/2.2/user_guide/indexing.html)、[缺失数据](https://pandas.pydata.org/pandas-docs/version/2.2/user_guide/missing_data.html)、[连接](https://pandas.pydata.org/pandas-docs/version/2.2/user_guide/merging.html)。

### 5．pandas开发团队，时间计算API文档

- 年份说明：pandas 2.2.3版本文档，2026年查阅。
- 知识点：变化比例、滚动窗口、有效样本和截至时点连接。
- 阅读位置：`DataFrame.pct_change`、`DataFrame.rolling`、`DataFrame.sum`及`merge_asof`。
- 推荐理由：核对`fill_method`、`min_periods`、`min_count`和匹配方向。
- 适合阶段：完成本章实验后逐项查阅。
- 官方入口：[pct_change](https://pandas.pydata.org/pandas-docs/version/2.2/reference/api/pandas.DataFrame.pct_change.html)、[rolling](https://pandas.pydata.org/pandas-docs/version/2.2/reference/api/pandas.DataFrame.rolling.html)、[sum](https://pandas.pydata.org/pandas-docs/version/2.2/reference/api/pandas.DataFrame.sum.html)、[merge_asof](https://pandas.pydata.org/pandas-docs/version/2.2/reference/api/pandas.merge_asof.html)。

---

**本章完成。下一章：第3章《线性代数及其金融数据应用》，从学习目标与3.1“向量空间、线性方程组与最小二乘”开始。**
