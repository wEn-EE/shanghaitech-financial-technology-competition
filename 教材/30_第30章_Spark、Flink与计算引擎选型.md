# 第30章 Spark、Flink与计算引擎选型

## 30.1 批处理、微批和有状态流处理

股票在开盘时报 100.10 元，一分钟后报 100.11 元。值班员在第 65 秒打开看板，能看到这第一分钟的收益吗？第 29 章的审计账本已经收齐两端报价。要回答看板上的问题，还要知道谁触发计算、计算读到哪个版本，以及结果何时发布。

**学习目标。** 本章沿用第 20 章的可用时间、第 28 章的报价版本和第 29 章的分区日志。学完本节，你应能给定一串报价，在纸上算出三种执行方式首次发布的时刻，解释次日更正如何改变同一个指标，并用四项资产的输出复核计算。后两节将把这项计算拆成算子，分析数据交换，再按负载、延迟和资源选择引擎。

### 30.1.1 先把要发布的数算清楚

固定一项资产，在同一天的事件秒 0 和 60 各取一笔报价。两个端点都要求使用截至计算截止时刻已经可见的最高修订号。某一端缺失，就暂缓发布该资产的收益。下表来自第 29 章合成行情的 audit 消费组。价格整数除以 10 的 scale 次方，得到该资产约定单位下的报价。不同资产的报价单位各异，同一资产两端价格相除后，收益的单位相同。

| 资产 | scale | 事件秒 0 首报整数 | 事件秒 60 首报整数 | 同一事件秒 60 的次日修订 |
|---|---:|---:|---:|---:|
| 股票 EQ_DEMO | 2 | 10010 | 10011 | 10051 |
| 债券 BOND_DEMO | 3 | 99125 | 99126 | — |
| 黄金 GOLD_DEMO | 2 | 200000 | 200001 | — |
| 外汇 FX_DEMO | 4 | 71234 | 71235 | — |

设两个端点的价格分别为 $P_0$ 和 $P_{60}$ ，且起始价格为正。用价格变化除以起始价格得到简单报价收益率。一个基点（basis point，bp）等于万分之一，用基点报告这个小幅变动更容易读数。

```math
R_{\mathrm{bp}}=10000\frac{P_{60}-P_0}{P_0}.
```

例如股票两端精度都为 2，分子和分母的价格换算因子相消。首报收益为 $10000(10011-10010)/10010$ ，约 **0.999001 bp**。若次日已有权使用更正价，起始价格仍为 100.10 元，终点变成 100.51 元，分子从 1 分变成 41 分，结果为 **40.959041 bp**。两次计算描述同一个历史分钟，差异来自输入版本。这项指标描述已观察到的报价变化。要用它识别市场状态还需给出状态规则；预测下一分钟收益需要另设预测目标；决定买卖还需仓位、成本和执行约束。

第 29 章在两个分区共写入 10 条物理记录。股票开盘首报占分区 0 的偏移量 1 和 2，两次载荷相同。audit 保存两张收据，只将这一业务版本收入 event 表一次。下文只读该表的 9 行。相同端点的正式修订有新的修订号，故仍保留。若错误地按“资产、事件秒”只保留今天看来最新的一行，就会丢失首日的 100.11 元。

### 30.1.2 给输入和输出各画一条时间线

事件秒回答行情属于哪一分钟，ready_s 表示第 28 章查询服务何时能提供该版本。为单独观察触发方式，本节设计算服务在 ready_s 当秒取得记录。四项资产的开盘首报都在第 1 秒到达，分钟末首报都在第 61 秒到达。股票的分钟末 v2 在第 86405 秒到达，事件秒仍为 60。上游样本没有逐笔的来源发布和网络接收日志。这三个到达时刻来自教学时钟。

再规定输出契约。每次触发后的计算和发布合计用 1 秒，资源充足，同秒不同资产可并行完成，不计排队。看板读取一次原子发布后的结果，在两次发布之间保留上一次值。批处理发布完整快照，微批发布本批触及且两端齐全的资产，逐条处理在该条所属资产两端齐全时发布。比较“最早看到”时，以看板可读的时刻为准。

**批处理（batch processing）。** 给作业一个有边界的输入。例如每天开盘后第 120 秒冻结一次可见快照，重算这个历史分钟。第一天截止于 120 秒，第二天截止于 86520 秒。第一次扫描能看到 8 个首报版本，按资产配对后可计算 4 个收益。第 121 秒整张表发布。次日扫描 9 个版本，股票终点选择 v2，第 86521 秒发布第二张表。这里的等待来自作业日程。若改在第 61 秒冻结快照，同样的批算法也能在第 62 秒给出首报结果。

**微批（micro-batch processing）。** 将持续到来的数据划成一个个小批次。本例每 10 秒触发，批次读入上次截止之后、本次截止及以前到达的记录。第 1 秒到达的四笔开盘价在第 10 秒一起处理，存入以资产和事件秒为键的状态表。两端尚未齐全，故没有收益输出。第 61 秒到达的四笔终点价要等到第 70 秒触发。它们与状态表中各自的开盘价配对，第 71 秒发布四项收益。如果每批都清空状态，第 70 秒的小批只有四个终点，会把本应可算的四项收益全部漏掉。

设正的到达时刻为 $a$ ，触发间隔为 $\Delta$ 秒。第一条能纳入该记录的触发线是最小的满足 $k\Delta\geq a$ 的整数倍。两边同除以正数，再向上取整，就得到发布时刻。下式假设本批已具备指标所需的全部输入。

```math
T_{\mathrm{micro}}(a)=\Delta\left\lceil\frac{a}{\Delta}\right\rceil+1.
```

按此约定，第 60 秒恰好到达就进第 60 秒的批，第 61 秒到达则进第 70 秒的批。两条记录相差 1 秒，发布却可相差 10 秒。等待触发的时间至少为零、严格小于一个周期，另加 1 秒计算与发布。实际作业若前一批尚未完成，后续批次还会多出调度等待。

**逐条有状态流处理（record-at-a-time stateful stream processing）。** 状态是处理完一条记录后仍为下一条保留的信息。对这道题，收到某资产的记录，查找该端点已见到的最高修订号，用较新版本更新，然后查询另一个端点。第 1 秒只保存开盘价。第 61 秒逐资产补入终点，各自算出收益，第 62 秒可读。次日第 86405 秒只更新股票终点，并从保留的开盘价重算，第 86406 秒发布更正。支持这次更正要求开盘数据至少保留到次日修订到达，或能从历史库取回。过早清理状态会直接失去分母。

“每条还是每批触发”和“是否保留状态”是两个独立的设计选择。本例的微批和逐条算法都保留两端报价。Spark Structured Streaming 4.0.1 默认用微批执行增量查询。Flink 的计算模型支持有界与无界输入，并支持有状态计算。在实际作业中，窗口触发条件、输出缓冲和写入端的提交时机都会影响看板。本节的秒数由上述协议给定。[Spark 4.0.1 编程指南](https://spark.apache.org/docs/4.0.1/streaming/index.html) · [Flink 架构说明](https://flink.apache.org/what-is-flink/flink-architecture/)

### 30.1.3 用第 29 章账本复核

在仓库根目录执行以下命令。选择的是上一章已完成的那次运行。若在新机器上复现，先依第 29.4 节生成 log.db，将路径换成该次运行的数据库。[第 29.4 节与输入生成命令](./29_第29章_消息队列、发布订阅与Kafka接入.md) · [本节独立程序](./code/ch30/opening_lab.py)

```powershell
D:/Anaconda/python.exe -X utf8 教材/code/ch30/opening_lab.py 教材/code/ch29/runs/20261119T091508_955774Z/log.db
```

程序只需 Python 标准库。load_quotes 按教学到达时刻排好输入，同秒按资产和版本排定顺序，便于重现。分区之间的这一合并顺序由回放器选定。update 仅更新同一资产、同一端点的最高版本。indicator 用分数保存精确比值，到打印时才取六位小数。一次批处理从空状态重新扫描截止前的输入；微批与逐条路径在相邻触发之间保留字典。groupby 跳过无输入的触发点，本题在空批没有定时输出。

```python
"""Replay chapter 29's validated opening quotes on a logical clock."""
import json
import sqlite3
import sys
from contextlib import closing
from fractions import Fraction
from itertools import groupby
from pathlib import Path


def load_quotes(path):
    uri = path.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as db:
        rows = db.execute(
            "SELECT body FROM event WHERE g='audit' AND s IN (0,60)"
        ).fetchall()
    if not rows:
        raise ValueError("missing chapter 29 audit events")
    return sorted((json.loads(body) for body, in rows),
                  key=lambda q: (q["ready_s"], q["asset"], q["revision"]))


def update(state, quote):
    key = (quote["asset"], quote["event_s"])
    old = state.get(key)
    if old is None or quote["revision"] > old["revision"]:
        state[key] = quote


def indicator(state, asset):
    first = state.get((asset, 0))
    last = state.get((asset, 60))
    if first is None or last is None:
        return None
    def price(q):
        return Fraction(q["price_atoms"], 10 ** q["scale"])
    return (first["revision"], last["revision"],
            10000 * (price(last) / price(first) - 1))


def replay(quotes, mode, period=10):
    def trigger(q):
        arrival = q["ready_s"]
        if mode == "record":
            return arrival
        if mode == "micro":
            return ((arrival + period - 1) // period) * period
        raise ValueError(mode)

    state = {}
    if mode == "batch":
        for cut in (120, 86520):
            state = {}
            for q in quotes:
                if q["ready_s"] <= cut:
                    update(state, q)
            for asset in sorted({asset for asset, _ in state}):
                result = indicator(state, asset)
                if result is not None:
                    yield cut + 1, asset, result
        return

    for cut, group in groupby(quotes, trigger):
        touched = set()
        for q in group:
            asset = q["asset"]
            update(state, q)
            if mode == "record":
                result = indicator(state, asset)
                if result is not None:
                    yield cut + 1, asset, result
            touched.add(asset)
        if mode == "micro":
            for asset in sorted(touched):
                result = indicator(state, asset)
                if result is not None:
                    yield cut + 1, asset, result


if __name__ == "__main__":
    quotes = load_quotes(Path(sys.argv[1]))
    for mode in ("batch", "micro", "record"):
        for visible, asset, (v0, v60, bp) in replay(quotes, mode):
            print(mode, visible, asset, v0, v60, f"{float(bp):.6f}")
```

**实跑结果。** 输出列依次是模式、看板可读秒、资产、起点修订号、终点修订号和收益基点。将三条路径首次发布的行按资产对齐，得到下表。数值相同的原因是三个首报截止都包含相同的两端版本。

| 资产 | 首报收益（bp） | 批处理可读秒 | 微批可读秒 | 逐条可读秒 |
|---|---:|---:|---:|---:|
| BOND_DEMO | 0.100883 | 121 | 71 | 62 |
| EQ_DEMO | 0.999001 | 121 | 71 | 62 |
| FX_DEMO | 0.140382 | 121 | 71 | 62 |
| GOLD_DEMO | 0.050000 | 121 | 71 | 62 |

| 股票终点变为 v2 后 | 输入可用秒 | 触发秒 | 看板可读秒 | 起点/终点版本 | 收益（bp） |
|---|---:|---:|---:|---|---:|
| 批处理 | 86405 | 86520 | 86521 | 1/2 | 40.959041 |
| 微批 | 86405 | 86410 | 86411 | 1/2 | 40.959041 |
| 逐条 | 86405 | 86405 | 86406 | 1/2 | 40.959041 |

回到第 65 秒打开看板的学生。此时逐条路径已发布 0.999001 bp，微批路径还在等第 70 秒的触发，批处理路径还在等第 120 秒的快照。后二者此时应显示“首分钟收益待发布”。显示零会把发布延迟误写成价格持平。到了第 86408 秒，逐条路径已显示更正，其余两条仍显示首报。审计某次预警要按**当时已发布的输出**选版本，只检查输入是否到达，会把尚在等待发布的更正提前用于决策。

第二次批处理又打印了债券、外汇和黄金，是因为它发布整表。微批与逐条当次只打印股票；看板沿用其余三项已有结果。若把每批打印的行直接覆盖整张看板，次日就会凭空丢掉三项资产。结果表的主键可设为“交易日、资产、指标分钟”，另存发布时间、输入版本和历次输出，便于分别查询当前值和历史值。

### 30.1.4 练习与详解

**1．基础理解。** 第 60 秒时，event_s 为 60 的股票首报已经属于该分钟。能否在第 60 秒用它计算并展示收益？

**解。** 先查可见条件。终点报价在第 61 秒才进入本节计算服务，第 60 秒仅有开盘价。即使选逐条处理，仍需等到第 61 秒凑齐输入，再用 1 秒计算和发布，最早第 62 秒显示。

**2．推导。** 若要求从最后一个必要输入到达到发布的耗时最多 5 秒，计算和发布仍占 1 秒。允许任意实数到达时刻，无积压、固定周期。微批周期如何选？

**解。** 可留给等待下一根触发线的时间是 4 秒。若周期至多 4 秒，等待严格小于或等于预算，对所有到达时刻都满足要求。若周期大于 4 秒，取一条刚过触发线的记录，其等待可任意接近整个周期，因而可超过 4 秒。所以固定周期须满足 $0\lt\Delta\leq4$ 秒。若单批作业实际花费超过周期，应重新计入积压并测量端到端耗时。

**3．编程。** 保持输入不变，调用 replay 时把 period 改为 7。求股票两次微批输出，再去掉修订，核对首日历史。把下列代码接在主程序末尾运行。

```python
def stock_rows(data):
    return [(t, r[1], round(float(r[2]), 6))
            for t, asset, r in replay(data, "micro", period=7)
            if asset == "EQ_DEMO"]

with_revision = stock_rows(quotes)
first_day = stock_rows([q for q in quotes if q["ready_s"] < 86400])
print(with_revision, first_day)
assert with_revision[:1] == first_day == [(64, 1, 0.999001)]
assert with_revision[1:] == [(86409, 2, 40.959041)]
```

**解。** 61 之后第一个 7 的倍数是 63，首次发布在 64 秒。86405 之后第一个倍数是 86408，更正发布在 86409 秒。只给首日输入时得到一个三元组；加入次日修订后，第一个三元组逐字段相同。这个测试同时核对了发布时间、终点版本和收益。

**4．金融分析。** 设一条教学提醒在首分钟报价收益超过 20 bp 时亮灯。用次日批次重建首日第 122 秒的看板，会遇到什么问题？

**解。** 第 122 秒三个看板都已发布首报，0.999001 小于 20，灯应熄灭。次日重算为 40.959041，大于 20，可以发出“历史分钟已更正”的新提醒。若只保存最终收益，再把这盏灯标到首日，就会凭次日知识制造一次历史报警。应保存旧提醒、后续修订及各自的发布时刻。该阈值只用于检验看板行为，实际报警质量还需用独立事件或业务评审来评价。

**5．工程设计。** 审计员每天需要一份可重算的完整表，值班员希望开盘后尽快看到各资产的首分钟变化。怎样让两个读者核对同一笔收益？

**解。** 一种方案是让在线作业按资产维护端点并发布增量，日批从不可变报价账本重算。两条路径共用交易日、事件端点、可用截止、版本选择、价格精度与缺失规则。对账时固定同一个输入截止，逐资产比较端点版本和精确收益，另外比较实际发布时间。晚到修订以新版本追加；查旧看板时保留当时的输出。若实测微批能满足值班时限，也可用它维护在线结果。可按四项各 2 分评价方案：给出两位读者的时限，明确相同的输入口径，说明增量怎样合成完整表，证明修订后仍能恢复旧看板。

**延伸阅读。** 完成本节后，可对照 Martin Kleppmann《Designing Data-Intensive Applications》第一版（2017）第 10、11 章，分别看有界输入的批作业和持续维护的流式结果。进一步读 Tyler Akidau 等（2015）的 *The Dataflow Model*，重点考察何时给出结果以及如何处理后到数据。阅读时可用本节的两个时刻作批注：指标属于第 60 秒，读者实际获知更正却在次日。[教材作者书站](https://dataintensive.net/) · [论文作者机构与期刊书目](https://research.google/pubs/the-dataflow-model-a-practical-approach-to-balancing-correctness-latency-and-cost-in-massive-scale-unbounded-out-of-order-data-processing/)

## 30.2 执行图、算子、并行度与数据交换

把 30.1 的计算交给两个人，每人一张纸，各自只能看自己纸上的报价。第一种分法让甲管债券和外汇，乙管股票和黄金。第二种分法让甲管开盘价，乙管一分钟后的价格。两种分法都收齐了 9 个版本，甲都收到 4 条，乙都收到 5 条。为什么第一种能算出每项资产的首分钟收益，第二种连一项也算不出？

### 30.2.1 从一道收益题画出执行图

30.1 的程序把所有报价放在同一个进程里。拆成多个任务后，要沿着一条记录回答两个问题：下一步做哪种运算？做这一步的任务能读到哪些历史记录？

把计算画成一张**有向无环图（directed acyclic graph，DAG）**。节点表示对输入施加的运算，称为**算子（operator）**。边表示上一步产生的记录如何交给下一步。本题只有一条计算路径，也是一张最简单的 DAG。若同时把输入送入审计表和收益算子，图就会出现分支。

```text
读取 audit 收据 → 选择已接受的开盘与分钟末报价 → 分发给负责该资产的任务
                                                    ↓
写入收益版本 ← 两端齐全时计算收益 ← 在该任务内更新端点的最高可见版本
```

图中“选取”只需当前记录的状态和事件秒，是无状态运算。“更新”和“计算”要读取以前的开盘价，是有状态运算。学生可以先用字典理解这层区别：选取是一次条件判断，收益计算则需要一个跨记录保留的字典。输出中的资产、两个端点版本和发布时间，要跟随收益一直保留到下游。

这张图给出**逻辑计划**。进一步规定有几个读取任务、几个状态任务、每条边怎样送数据，就得到本题的**物理执行计划**。一个算子的**并行度（parallelism）**是同时部署的并行实例数。本实验画出两个源分区和两个状态实例，每个实例只访问自己的字典。程序在本机顺序模拟它们，便于逐条检查所有状态变化。真实部署时，同一台机器也可以运行多个实例。

算子和任务的边界可以不同。例如，读者可以在一个循环里接连执行筛选和字段提取，省去把中间行再排队交给另一个线程的成本。Flink 把符合条件的相邻算子子任务组成**算子链（operator chain）**，一个任务用同一线程执行链上的工作。按资产重新分区时，上游必须先决定记录的去向，下游状态实例才能更新自己的那份数据。[Flink 架构文档，Tasks and Operator Chains](https://nightlies.apache.org/flink/flink-docs-stable/docs/concepts/flink-architecture/#tasks-and-operator-chains)

### 30.2.2 哪些记录必须在同一个地方相遇

沿用 30.1 的协议，选取交易日内事件秒 0 和 60 的报价。状态字典按“资产、事件秒”区分端点。**路由键**则要覆盖一次收益计算的全部依赖。本例可直接用资产作路由键，让同一资产的两个端点进入同一个任务，再在任务内部按事件秒分别保存。对多日独立的首分钟指标，也可按“资产、交易日”路由，更正记录须携带原来的交易日。

设 $h(q)$ 表示报价 $q$ 的目标任务。只靠本地状态完成股票收益及其修订，要求这三条记录的目标满足

```math
h(q_{0,1})=h(q_{60,1})=h(q_{60,2}).
```

下标依次为事件秒、修订号。这个条件为什么足够？从空状态开始，只要某只股票的第一条记录到达，目标任务与 30.1 的单进程程序就为它保存相同的端点。假设处理前两边的该资产状态相同，下一条仍被送到同一任务，两边用同一个版本比较规则更新，再读相同的分子和分母，得到的结果就相同。其他资产写入不同的字典键，不影响这个推理。逐条重复便覆盖整段回放。这里还要求同一资产的记录按同一回放次序处理，发布契约也相同。若允许不同到达次序，最终版本可以一致，中间发布历史仍可能不同。

第 29 章已有一种满足条件的布局。源分区 0 保存债券和股票，源分区 1 保存外汇和黄金。令源分区 0 的记录直接去状态任务 0，源分区 1 的记录直接去任务 1，称为本例的**直接转发（forward）**。每个任务都拿得到自己资产的两个端点，源端与状态端的编号也相同。

若希望任务 0 管债券和外汇，任务 1 管股票和黄金，就需要**重分区（repartition）**。两个源都要向两个目标发送记录。这样的按新分布重新组织数据通常称为 **shuffle**。本例用一张固定映射表来路由，便于手算。Flink 的键控状态把流中的键与相应状态分配到一起，并以键组（key group）为单位重新分配状态。Spark 的 RDD 模型用分区依赖描述类似的数据需求：窄依赖中，每个父分区至多供一个子分区使用；宽依赖允许一个父分区的记录供多个子分区使用。批作业中，shuffle 通常形成阶段（stage）的边界，带来序列化、数据传输及可能的磁盘读写。Flink 的流式键控交换可以持续发送新记录，处理这个持续输入无须等待整个源结束。[Flink 键控状态](https://nightlies.apache.org/flink/flink-docs-stable/docs/concepts/stateful-stream-processing/#keyed-state) · [RDD 原论文 §4、图 4](https://www.usenix.org/system/files/conference/nsdi12/nsdi12-final138.pdf) · [Spark 4.0.1 Shuffle operations](https://spark.apache.org/docs/4.0.1/rdd-programming-guide.html#shuffle-operations)

### 30.2.3 手算一张交换矩阵，再核对一笔股票收益

表中只取第 29 章 audit 组已经接受的业务版本。分区 0 的偏移量 2 是股票开盘价的重复投递，仍留在原收据表中。筛选后，按资产分发的去向如下。

| 源分区 | 资产 | 接受收据的偏移量 | 本题记录数 | 目标任务 |
|---:|---|---|---:|---:|
| 0 | 债券 | 0、3 | 2 | 0 |
| 0 | 股票 | 1、4、5 | 3 | 1 |
| 1 | 外汇 | 0、2 | 2 | 0 |
| 1 | 黄金 | 1、3 | 2 | 1 |

令矩阵 $M$ 的第 $i$ 行、第 $j$ 列记录从源分区 $i$ 发给任务 $j$ 的条数。对照表格逐格填入，得到

```math
M_{\mathrm{asset}}=
\begin{pmatrix}
2 & 3 \\[0pt]
2 & 2
\end{pmatrix}.
```

行和为 5、4，给出两个源各读了多少。列和为 4、5，给出两个状态任务各处理多少。非对角线之和为 3 加 2，即 **5 条记录换了任务编号**。若部署时把同编号的读取任务和状态任务放在同一台机器、不同编号放在不同机器，这 5 条就需要跨机传输。程序只统计逻辑去向和原始 JSON 载荷字节。实际网络流量还取决于任务放置、传输编码、压缩和协议开销。

再沿股票这条路径看任务 1 的字典。即使任务 1 同时处理黄金，两个资产也有各自的端点。

| 到达秒 | 来源坐标（分区，偏移） | 股票开盘价 | 股票分钟末价 | 任务 1 的动作 |
|---:|---|---:|---:|---|
| 1 | (0, 1) | 100.10，v1 | 缺失 | 保存开盘价，等待终点 |
| 61 | (0, 4) | 100.10，v1 | 100.11，v1 | 第 62 秒发布 0.999001 bp |
| 86405 | (0, 5) | 100.10，v1 | 100.51，v2 | 第 86406 秒发布 40.959041 bp |

现在故意改变路由，让事件秒 0 全去任务 0，事件秒 60 全去任务 1。源分区 0 的两笔开盘价仍去 0，其余三笔去 1。源分区 1 也是两笔去 0、两笔去 1。**交换矩阵逐格相同，两个字典的内容却完全不同。** 对股票而言，任务 0 只持有 100.10 元，任务 1 先后持有 100.11 元和 100.51 元。后者能正确选出终点的最高版本，却始终没有分母。其余三项资产也遇到同样的问题。只验收“9 条都处理过”“两侧负载接近”，会让这个错误实现通过。

### 30.2.4 实验：用同一个业务基准验收三张执行图

以下程序只读同一份 log.db。30.1 从 event 表读规范业务版本，本节从 receipt 表读已接受的载荷，以便同时取得源分区、偏移量和字节数。读取两张不同的表，也能检验两条路径是否保留了相同业务结果。收益计算直接复用 30.1 的 update 和 indicator。独立运行文件与 opening_lab.py 放在同一目录。[本节程序](./code/ch30/exchange_lab.py) · [30.1 的收益函数](./code/ch30/opening_lab.py)

```powershell
D:/Anaconda/python.exe -X utf8 教材/code/ch30/exchange_lab.py 教材/code/ch29/runs/20261119T091508_955774Z/log.db
```

```python
"""Trace chapter 29 audit receipts through two logical workers."""
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

from opening_lab import indicator, load_quotes, replay, update


OWNER = {"BOND_DEMO": 0, "FX_DEMO": 0, "EQ_DEMO": 1, "GOLD_DEMO": 1}


def read_input(path):
    uri = path.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as db:
        receipts = db.execute(
            "SELECT p,o,raw FROM receipt "
            "WHERE g='audit' AND t='market.quotes.ch29.v1' AND status='ACCEPTED'"
        ).fetchall()
    events = []
    for part, offset, raw in receipts:
        q = json.loads(raw)
        if q["event_s"] in (0, 60):
            events.append((q["ready_s"], part, offset, len(raw), q))
    return sorted(events, key=lambda e: e[:3])


def execute(events, route):
    states = [{}, {}]
    counts = [[0, 0], [0, 0]]
    crossing_bytes = 0
    outputs = []
    for arrival, source, offset, size, q in events:
        dest = route(source, q)
        counts[source][dest] += 1
        if dest != source:
            crossing_bytes += size
        update(states[dest], q)
        value = indicator(states[dest], q["asset"])
        if value is not None:
            outputs.append((arrival + 1, q["asset"], value))
    return counts, crossing_bytes, sorted(outputs)


if __name__ == "__main__":
    path = Path(sys.argv[1])
    events = read_input(path)
    reference = sorted(replay(load_quotes(path), "record"))
    plans = {
        "forward": lambda source, q: source,
        "asset": lambda source, q: OWNER[q["asset"]],
        "endpoint": lambda source, q: int(q["event_s"] == 60),
    }
    for name, route in plans.items():
        counts, size, outputs = execute(events, route)
        print(name, counts, size, len(outputs), outputs == reference)
        for t, asset, (start_v, end_v, bp) in outputs:
            print(t, asset, start_v, end_v, f"{float(bp):.6f}")
```

read_input 采用“ready_s、分区、偏移量”的次序回放。两个分区之间没有统一的 Kafka 偏移量，本例选这个次序使同秒输入可复现。参考程序在同秒按资产排列。这组数据中同秒记录分属不同资产，各资产的版本次序在两种读取方式下相同。比较前排序是为了比较完整输出集合，保留重复行以及每行的发布时间、资产、两个版本号和精确收益。

| 实跑计划 | 源 0 发给任务 (0, 1) | 源 1 发给任务 (0, 1) | 换编号的载荷字节 | 输出行数 | 与 30.1 逐条基准逐行相等 |
|---|---|---|---:|---:|---|
| forward，沿源布局 | (5, 0) | (0, 4) | 0 | 5 | 是 |
| asset，按资产重新布置 | (2, 3) | (2, 2) | 1074 | 5 | 是 |
| endpoint，按端点拆开 | (2, 3) | (2, 2) | 1079 | 0 | 否 |

可以复算中间的 1074。按资产路由时，股票三条原始载荷依次长 213、215、218 字节，外汇两条长 213、215 字节，五条相加正好 1074。错误路由虽然也移动五条，移动的具体记录变了，字节和随之改变。

| 可读秒 | 资产 | 起点/终点版本 | forward 和 asset 各自发布的报价收益（bp） |
|---:|---|---|---:|
| 62 | BOND_DEMO | 1/1 | 0.100883 |
| 62 | EQ_DEMO | 1/1 | 0.999001 |
| 62 | FX_DEMO | 1/1 | 0.140382 |
| 62 | GOLD_DEMO | 1/1 | 0.050000 |
| 86406 | EQ_DEMO | 1/2 | 40.959041 |

这里为两张正确的图沿用 30.1 的逻辑时钟，统一设输入可用到结果发布用 1 秒，因而可以逐行比较发布时间。本地程序实际执行了分发、状态更新、基点计算和字节计数。若要比较两张图在线上的速度，需要分别观测输入到达、交换结束、状态更新与输出提交的时刻。

### 30.2.5 并行度怎样限制吞吐

若状态只在本地，某项资产每秒到达的所有记录都会形成它所属任务的负担。设资产 $a$ 的持续到达率为 $\lambda_a$ （条/秒），任务 $j$ 的持续处理能力为 $\mu_j$ （条/秒）。在每条记录的服务成本相同、路由固定的模型里，将分给同一任务的到达率相加，得到

```math
\lambda_j^{\mathrm{in}}=\sum_{a:\,h(a)=j}\lambda_a.
```

这里把 $h$ 简写成对资产键的映射。若某个任务的到达率超过其处理能力，该任务每秒新增的积压约为二者之差。其他任务的空余容量只有在重新分配工作后才能用上。做容量规划时要让每个任务都有余量，还要检查短时开盘突发。

举一个独立于九条样本的容量算例。假设股票、债券、外汇、黄金持续每秒分别进入 800、300、150、50 条，每个状态任务每秒最多处理 1000 条。沿用源布局，任务 0 承担股票与债券，每秒到达 1100 条，10 秒约积压 1000 条。改用实验的资产布局，任务 0 处理债券和外汇，每秒 450 条，任务 1 处理股票和黄金，每秒 850 条。两边在给定模型下都能跟上。选择后一张图要付出持续交换股票和外汇的代价，在这一假设负载下就是每秒 950 条跨编号记录。开盘峰值的真实到达率、服务时间和网络余量都应另行测量。

若股票一个键就超过每秒 1000 条，继续增加处理其他键的任务仍会留下这个瓶颈。可以先将互不依赖的解析、校验并行化，再测按键更新本身的成本。历史批作业还可按端点做局部版本归并，随后把每个资产的两项有效端点送到同一处计算。在线程序若也采用局部归并，必须说明哪些中间版本会被合并，以及这是否改变读者能看到的预警历史。

### 30.2.6 练习与详解

**1．基础理解。** 同学建议把“资产、事件秒、修订号”直接用作状态任务的分发键，因为这三个字段恰好能唯一标识一个版本。这个理由充分吗？

**解。** 这个键适合判定两个业务版本是否相同。计算首分钟收益需要把开盘与分钟末配在一起，修订时还要找到旧端点。逐版本分发可能把三个必要版本送到三个任务。本题可按资产分发，在任务内部用事件秒区分端点，用修订号比较新旧。若坚持按版本分发，就必须再提供一次按资产汇集端点的步骤。

**2．推导。** 保留资产布局与原始九条记录，若两台机器间可用单向带宽均为每秒 1000 字节，只考虑原始载荷，两方向可同时传输。整段回放中，传送这些跨机载荷需要的链路忙碌时间分别是多少？

**解。** 从 0 到 1 的三条股票记录共 646 字节，占该方向 0.646 秒。从 1 到 0 的两条外汇记录共 428 字节，占反方向 0.428 秒。若五条同时备好且全双工，两方向都传完的理想下界是 0.646 秒。实际样本中的修订次日才到，这两个数描述累计传输工作量。要计算最后一次发布时刻，还要知道每条记录何时可发送以及当时已有多少排队数据。

**3．编程。** 首日沿源布局运行，次日把路由换成资产布局，却没有搬动任何历史状态。哪一行消失？把下面代码接在本节程序末尾运行。

```python
def switched(source, quote):
    if quote["ready_s"] < 86400:
        return source
    return OWNER[quote["asset"]]

_, _, changed = execute(events, switched)
missing = [row for row in reference if row not in changed]
print([(t, a, v[:2]) for t, a, v in missing])
assert len(changed) == 4
assert missing == [reference[-1]]
```

**解。** 实跑输出为 `[(86406, 'EQ_DEMO', (1, 2))]`。首日股票开盘价存在任务 0，次日修订却到了任务 1。任务 1 缺分母，所以四项首报都还在，唯独更正没有发布。若需切换布局，可在一致的输入位置冻结旧状态，按新归属转移端点，再从对应位置恢复输入。也可从足够早的账本重新构建新状态，在输出追平且逐键对账后切换读者。

**4．金融分析。** 若错误计划把空输出解释成“四项资产首分钟都没有变动”，对看板有什么后果？

**解。** 在第 62 秒，有效收益应有四项，实际算得的四个值均为正。错误计划的有效资产数是 0。覆盖率为 0/4 时，均值没有可用分母，应显示缺失并报告覆盖率。若把缺失填为零再求平均，就会显示四项资产齐全且市场平静，掩盖处理故障。审计时同时检查源端版本数、可配对资产数及已发布的资产集合，可以把故障定位到配对与输出之间。

**5．工程设计。** 希望在现有四条资产收益之上发布“四资产等权平均收益”，并允许次日更正。怎样扩展执行图？

**解。** 在按资产计算之后增加一个汇总算子，按“交易日、指标分钟”接收四项资产的贡献。每项保留最近已接受的端点版本与收益，四项齐全时发布平均数。股票修订到达时，在四项总和中减去旧股票收益，再加上新股票收益，分母仍为 4。按未舍入的精确收益计算，首报平均约 0.322567 bp，更正后约 10.312577 bp。若同一修订被重复投递，已见的同版本同内容应幂等处理。可按四项各 2 分验收：四项覆盖，引入汇总键，修订替换且分母正确，保留新旧发布的时间和输入版本。

**推荐阅读。** 入门可先读 Martin Kleppmann《Designing Data-Intensive Applications》第一版（2017）第 10 章的 *MapReduce Job Execution* 和 *Reduce-Side Joins and Grouping*，对照本节画出谁产生记录、谁按键收齐记录。理解分区后，再看 Matei Zaharia 等（2012）的 RDD 论文 §4 与图 4，区分父分区如何被子分区依赖。实现时可分别查 Spark 4.0.1 的 *Shuffle operations*、Flink 架构文档的 *Tasks and Operator Chains* 和状态文档的 *Keyed State*。[教材第 10 章](https://www.oreilly.com/library/view/designing-data-intensive-applications/9781491903063/ch10.html) · [RDD 原论文](https://www.usenix.org/system/files/conference/nsdi12/nsdi12-final138.pdf) · [Spark 编程指南](https://spark.apache.org/docs/4.0.1/rdd-programming-guide.html#shuffle-operations) · [Flink 架构](https://nightlies.apache.org/flink/flink-docs-stable/docs/concepts/flink-architecture/) · [Flink 状态](https://nightlies.apache.org/flink/flink-docs-stable/docs/concepts/stateful-stream-processing/)

**续写位置。** 30.2 完。下一节为 30.3「按数据规模、延迟和资源选择计算路线」。
