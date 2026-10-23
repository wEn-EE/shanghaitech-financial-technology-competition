# 分布式金融市场状态监控平台教材

本项目按用户要求连续撰写。教材正文同时发布在聊天中并保存为本地 Markdown 文件，两处保持内容一致；此目录还保存总目录、引用登记、续写记录和经过实际运行的配套代码。

- [00_完整目录.md](./00_完整目录.md)：十篇、99章的三级主题目录。
- [01_第1章_Python编程、数据结构与算法基础.md](./01_第1章_Python编程、数据结构与算法基础.md)：第一篇导读及第1章完整正文，含公式推导、完整代码、案例、工程问题、练习、详细答案和推荐阅读。
- [02_第2章_NumPy、Pandas与科学计算.md](./02_第2章_NumPy、Pandas与科学计算.md)：第2章完整正文，含数组与表格、时间可用性、完整面板实验、12题详解及推荐阅读。
- [03_第3章_线性代数及其金融数据应用.md](./03_第3章_线性代数及其金融数据应用.md)：第3章完整正文，含投影与最小二乘、QR/SVD、正定性、因子暴露与PCA推导、完整代码、12题详解及参考阅读。
- [04_第4章_微积分、最优化与数值计算.md](./04_第4章_微积分、最优化与数值计算.md)：第4章完整正文，含微积分、凸性与KKT、梯度/Newton/投影算法、风险预算、完整代码、12题详解及参考阅读。
- [05_第5章_概率论、随机变量与概率分布.md](./05_第5章_概率论、随机变量与概率分布.md)：第5章完整正文，含Bayes与基准率、联合和混合分布、条件期望与全方差、厚尾及模拟、12题详解和参考阅读。
- [06_第6章_数理统计、参数估计与假设检验.md](./06_第6章_数理统计、参数估计与假设检验.md)：第6章完整正文，含估计、似然、信息与区间推导、功效、多重比较、HAC和分块Bootstrap、完整实验、12题详解及参考阅读。
- [07_第7章_随机过程、马尔可夫链与布朗运动.md](./07_第7章_随机过程、马尔可夫链与布朗运动.md)：第7章完整正文，含信息集、平稳与遍历、状态转移、泊松到达、布朗二次变差、伊藤公式、完整实验和12题详解。
- 参考资料登记.md：已经核对的首批权威资料及合法入口。
- 续写进度.md：后续接续位置。
- code/ch01/monitor.py：第一章行情处理器，仅用标准库，演示数据全部人工构造。
- code/ch01/test_monitor.py：6项语义验证；使用临时目录，测试结束自动清理。
- code/ch02/panel_lab.py：第2章多资产面板实验；使用现有NumPy和pandas，全部数据为人工示例。
- code/ch02/test_panel_lab.py：11项语义验证，覆盖缺失、标签与时间对齐、宏观修订、数值一致性和空输入。
- code/ch03/linear_lab.py：多资产线性代数实验；人工因子、协方差、收缩、冻结训练期PCA及逐对缺失反例。
- code/ch03/test_linear_lab.py：11项验证，包含近共线性、不可识别、半正定性和训练隔离。
- code/ch03/plot_geometry.py及images/ch03_geometry.png：投影与特征方向配图；使用既有Matplotlib生成并检查。
- code/ch04/optimization_lab.py：梯度、Newton、投影最小方差、风险预算及数值积分；仅用现有NumPy。
- code/ch04/test_optimization_lab.py：12项验证，包括边界KKT对应的投影驻点、风险预算闭式特例、导数、失败状态和尺度不变性。
- code/ch04/plot_numerics.py及images/ch04_numerics.png：优化轨迹与差分误差配图；已生成并检查。
- code/ch05/probability_lab.py：人工多资产概率模型、稳定Bayes更新、重复证据反例与尾部模拟。
- code/ch05/test_probability_lab.py：12项验证；形状、密度、矩、随机复现、零证据及模拟健全性。
- code/ch05/plot_probability.py及images/ch05_probability.png：基准率与等方差厚尾配图，已生成并检查。
- code/ch06/inference_lab.py：人工推断实验，比较区间覆盖、稀有事件比例区间和多资产检验；已有SciPy参与数值计算。
- code/ch06/test_inference_lab.py：13项验证，包括SciPy交叉核验、边界、HAC矩阵等价、平稳初始化与联合结构。
- code/ch06/plot_inference.py及images/ch06_inference.png：读取实验清单生成覆盖率配图，已检查。

## 正文发布与保存约定

1. 每次续写的教材正文既发在聊天中方便阅读，也在当次完成后写入对应的 Markdown 文件，不以摘要或提纲代替本地正文。
2. 优先按章保存，文件名采用“序号_第N章_章名.md”；章节分多次编写时顺序追加到同一文件，保留已完成内容，并在续写进度中记下精确到节的断点。
3. 本地正文包含当次发布的理论、推导、代码、案例、工程讨论、练习、答案和参考链接。代码另保留可独立运行的源文件。
4. 保存后检查正文完整性、Markdown代码围栏与本地链接，并同步更新目录和续写进度；最终回复附本次正文文件链接。
5. 后续收到“继续”时按续写进度接续，不重复已写内容。用户仅讨论保存方式时，不自行推进到下一章。
6. 用户于2026年10月22日授权：每章完成后，将教材正文、代码、配图和维护文件提交并推送到 https://github.com/wEn-EE/shanghaitech-financial-technology-competition 。沿用现有main分支；推送后核对远端提交，再报告提交链接。
7. 提交前检查内容、代码运行、公式定界、链接与Git变更范围。新产生的缓存和runs目录不加入后续提交；已在历史提交中的文件不因这条规则自动删除。
8. 按用户最新确认，公式保留数学排版并兼容 VS Code 与 GitHub：行内用单美元符号且与相邻文字留空格；独立公式用双美元符号；集合括号用 lbrace/rbrace，范数用 Vert，避免受限的 operatorname 宏。采用已核对的直立名称写法，新增算子须检查间距与上下限语义。具体见[数学公式阅读约定](./数学公式阅读约定.md)和[公式渲染测试页](./公式渲染测试.md)。

## 第一章运行

在本目录的 code/ch01 中运行：

```powershell
& 'D:\Anaconda\python.exe' monitor.py
& 'D:\Anaconda\python.exe' -m unittest -v test_monitor.py
```

实际验证环境为已安装Anaconda Python 3.13.5，没有安装Python或额外依赖。

默认运行会新建带时间戳的 runs 子目录，包含 audit.jsonl 和 summary.json。已有目录不被覆盖。输入文件可用 --input PATH，输出新目录可用 --out PATH。JSONL中每行一个JSON对象，按available_time排序。每个标的键为(source,symbol)，单个标的有效行情event_time须严格递增；不支持同一时间戳多成交排序或修订覆盖。迟到数据保留在审计记录中，待后续章节重放和修订。

这是单进程教学构件；去重状态只在本次进程内有效，写盘与内存更新没有分布式事务或崩溃一致性保证。波动统计为观测窗口描述量，不直接年化；预警阈值0.015为演示参数，没有经过真实金融数据校准。

## 第二章运行

在本目录的 code/ch02 中运行：

```powershell
& 'D:\Anaconda\python.exe' panel_lab.py
& 'D:\Anaconda\python.exe' -m unittest -v test_panel_lab.py
```

已用Anaconda Python 3.13.5、NumPy 2.1.3、pandas 2.2.3验证。没有安装新依赖。默认新建runs下的时间戳目录；输出原始结构化输入、审计表、价格与收益面板、覆盖度、滚动统计、宏观查询和manifest.json。

输入限于人工规则网格、单一展示来源、固定且事前已知的资产元数据。前级需消歧重复消息和行情键。宏观查询限一个指标和一个观测期、按序修订；生产PIT、交易日历及分布式可靠性在后续章节展开。每个网格的10秒决策延迟是教学配置，并非性能实测值。

## 第三章运行

在本目录的code/ch03中运行：

```powershell
& 'D:\Anaconda\python.exe' linear_lab.py
& 'D:\Anaconda\python.exe' -m unittest -v test_linear_lab.py
```

主实验只用既有NumPy与pandas，11项验证通过。人工数据前8行训练、后4行仅作冻结模型变换。默认新建runs时间戳目录，保存输入、系数、协方差、得分、重构、距离、模型数组与manifest.json。

示例证明线性代数关系，不构成真实金融状态识别绩效。train_end记录训练样本事件边界，不等于模型完成或发布时间。距离没有未经校准的金融报警阈值；逐对缺失反例不会混入正常协方差估计。可选配图脚本使用现有Matplotlib，不需新增依赖。

## 第四章运行

在本目录的code/ch04中运行：

```powershell
& 'D:\Anaconda\python.exe' optimization_lab.py
& 'D:\Anaconda\python.exe' -m unittest -v test_optimization_lab.py
```

12项验证通过，既有Python 3.13.5、NumPy 2.1.3；配图使用已有Matplotlib 3.10.0。没有安装依赖。默认输出到新建runs时间戳目录，保存人工协方差、解数组、各算法迭代历史及manifest.json。

协方差为事先指定的人工矩阵，不是官方数据拟合结果。优化成功仅代表给定目标的数值检查满足阈值；不代表真实状态准确率、收益预测或交易绩效。主实验拒绝未收敛解，风险预算函数失败时抛出异常。

## 第五章运行

在本目录的code/ch05中运行：

```powershell
& 'D:\Anaconda\python.exe' probability_lab.py
& 'D:\Anaconda\python.exe' -m unittest -v test_probability_lab.py
```

已有Python 3.13.5、NumPy 2.1.3；配图使用现有Matplotlib，没有安装新库。默认20万次独立混合抽样，保存模型参数、32行人工预览和manifest.json，不保存全部模拟样本。12项验证通过。

模型的状态、概率、条件分布与收益均为人工设定；独立抽样不是历史行情或Markov序列。模拟误差不包含真实市场中的参数、模型和非平稳误差。状态识别、收益预测、报警决策和交易策略分别解释。

## 第六章运行

在本目录的code/ch06中运行：

```powershell
& 'D:\Anaconda\python.exe' inference_lab.py
& 'D:\Anaconda\python.exe' -m unittest -v test_inference_lab.py
```

已有Python 3.13.5、NumPy 2.1.3、SciPy 1.15.3；配图使用Matplotlib 3.10.0，没有安装依赖。13项验证通过，习题9、10另行执行。默认每个相关性情景1000条独立人工序列，每条240个观测、399次循环块重抽样。输出到新建runs目录，保存samples.npz与manifest.json；清单记录配置、环境、程序和样本文件哈希。

配图可用现有解释器执行plot_inference.py，并传入本次输出的manifest.json路径。图展示实际覆盖率；HAC与分块Bootstrap在本例仍有欠覆盖，不能将算法名称当作金融可靠性保证。全部为固定窗口人工实验，没有真实PIT接入、在线预警或交易绩效声明。

## 第七章运行

在本目录的code/ch07中运行：

```powershell
& 'D:\Anaconda\python.exe' process_lab.py
& 'D:\Anaconda\python.exe' -m unittest -v test_process_lab.py
```

[主程序](./code/ch07/process_lab.py)、[8项测试](./code/ch07/test_process_lab.py)及[绘图程序](./code/ch07/plot_process.py)使用现有Anaconda、NumPy和Matplotlib；没有安装新库。默认新建runs目录，保存1600行人工多资产对数收益、oracle状态、新闻计数及包含参数、环境与哈希的manifest.json。绘图程序依次接收清单路径和输出图片路径。

训练只使用前1000个状态形成的999次转移，测试评估其后600次转移。标签是模拟真值，不是从市场行情在线识别的结果；全部NLL比较仅在同一人工样本与可见状态假设下成立。独立的4000路径布朗实验验证二次变差误差和左右端积分和；配图已生成并视觉检查。正文260处公式通过本机KaTeX语法验证，GitHub沿用用户此前确认的代表性写法，未声称逐式在线验收。

## 当前数学排版约定

2026-10-23按用户补充的GitHub截图修正：普通行内公式使用单美元符号与安全名称命令，独立公式统一使用math围栏，矩阵移出句子。见[数学公式阅读约定](./数学公式阅读约定.md)及[公式渲染测试](./公式渲染测试.md)。本地数学语法检查与GitHub的Markdown解析检查分别进行。

前七章2148处公式已通过实际GitHub文件页的识别和内容传递核对，详见[公式兼容性核对记录](./公式兼容性核对记录.md)；该记录与逐式视觉验收相区分。
