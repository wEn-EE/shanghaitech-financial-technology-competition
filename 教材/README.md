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
- [08_第8章_时间序列分析与金融统计基础.md](./08_第8章_时间序列分析与金融统计基础.md)：第8章完整正文，含ACF/PACF、单位根、AR/MA/ARMA/ARIMA推导、预测区间、可追溯滚动实验和12题详解；第一篇完成。
- [09_第9章_金融市场结构、参与者与交易机制.md](./09_第9章_金融市场结构、参与者与交易机制.md)：第二篇开篇，含信息价差、订单簿撮合、清算交收、流动性与价格跳动推导、完整重放实验及12题详解。
- [10_第10章_股票与债券的现金流和风险.md](./10_第10章_股票与债券的现金流和风险.md)：分红、拆股与PIT复权，DDM、债券定价与自举曲线、久期凸性及信用利差推导，完整实验和12题详解。
- [11_第11章_商品、外汇及衍生品基础.md](./11_第11章_商品、外汇及衍生品基础.md)：商品期限结构、换月账本、外汇CIP、远期与保证金、二叉树及BSM推导、IV、完整实验和12题详解。
- [第12章 收益、波动、相关性与金融统计特征](./12_第12章_收益、波动、相关性与金融统计特征.md)：收益聚合、组合风险、跨期方差、厚尾机制、非同步交易、RV噪声偏差与EWMA，完整实验和12题详解。
- [第13章 市场有效性、风险溢价与资产定价](./13_第13章_市场有效性、风险溢价与资产定价.md)：有效市场和联合假设、CAPM、SDF、因子定价、HAC与PIT、完整归因实验和12题详解。
- [第14章 宏观指标、政策传导与经济周期](./14_第14章_宏观指标、政策传导与经济周期.md)：指标口径、政策传导、财政乘数、宏观意外与PIT，完整发布账本及12题详解。
- [第15章 多资产联动、风险传染与市场冲击](./15_第15章_多资产联动、风险传染与市场冲击.md)：共同因子、尾部反例、杠杆与流动性螺旋、网络传播、完整压力实验和12题详解。
- [第16章 市场状态的经济解释与历史事件](./16_第16章_市场状态的经济解释与历史事件.md)：多维标签契约、历史证据、过滤和平滑、任务区别、完整实验与12题详解。
- [第17章 多源数据、数据格式与统一模型](./17_第17章_多源数据、数据格式与统一模型.md)：多源契约、主数据与单位、规范化、模式演进、持久账本、PIT查询和12题详解。
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
8. 按用户最新确认，公式保留数学排版并兼容 VS Code 与 GitHub：行内用单美元符号且与相邻文字留空格；独立公式用不嵌套在列表中的math围栏；集合括号用lbrace/rbrace，范数用Vert，避免受限的operatorname宏。矩阵移出句子，公式行尾换行符使用显式零附加间距；具体见[数学公式阅读约定](./数学公式阅读约定.md)和[公式渲染测试页](./公式渲染测试.md)。
9. 聊天正文单独适配：用户反馈第8章句子中的公式在聊天里未正常显示。后续聊天行内改用反斜杠圆括号定界，独立公式用反斜杠方括号定界；文件继续沿用第8条。两处教学内容一致，定界符允许不同。聊天写法须依据聊天端实际反馈验证，不能以GitHub或VS Code的验证代替。
10. 用户已确认第10章普通聊天正文显示正常，第11章改为写作块后公式再次失效。后续固定使用普通聊天正文讲解教材，不用写作块承载公式，不再擅自更换呈现方式；Markdown文件沿用已验证格式。

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


## 第八章运行

在code/ch08运行：

```powershell
& 'D:\Anaconda\python.exe' -X utf8 timeseries_lab.py
& 'D:\Anaconda\python.exe' -X utf8 -m unittest -v test_timeseries_lab.py
```

[主程序](./code/ch08/timeseries_lab.py)、[12项测试](./code/ch08/test_timeseries_lab.py)、[绘图程序](./code/ch08/plot_timeseries.py)使用已有Anaconda及statsmodels0.14.4，无新增依赖。绘图程序接受manifest.json路径和输出图片路径。

1200期人工四资产收益按600/200/400划分训练、验证和测试；滚动窗口只在验证期选择，测试期遵循固定规则更新。共4800条测试预测保存训练和发布时序、参数、模型版本及区间。训练期诊断、测试覆盖与已知人工断点分开报告；不能当作真实市场状态识别或交易回测。171处公式本地语法检查通过，正文程序与独立源文件一致，全部教学栏目与12题详解完成。第一篇完成，后续接第二篇第9章。


## 第九章运行

在code/ch09运行：

```powershell
& 'D:\Anaconda\python.exe' -X utf8 market_lab.py
& 'D:\Anaconda\python.exe' -X utf8 -m unittest -v test_market_lab.py
```

[主程序](./code/ch09/market_lab.py)仅用标准库；[12项测试](./code/ch09/test_market_lab.py)覆盖撮合、撤单、重复、缺口、非法消息和确定性重放。[绘图程序](./code/ch09/plot_market.py)使用已有Matplotlib，依次接收运行manifest.json与输出图片路径。没有新增依赖。

15条人工命令、16次到达，14条应用、1条拒绝、1条重复；股票三笔成交120股，均价100.0316666667元。序号缺口时不发布可用盘口；单边盘口的价差为缺失。该程序是教学撮合与接收实验，没有真实交易接入、清算交收、崩溃恢复或端到端精确一次保证。总目录已补齐第8章链接与8.4，并加入第9章链接与9.4；下次接第10章。


## 第十章运行

在code/ch10运行：

```powershell
& 'D:\Anaconda\python.exe' -X utf8 cashflow_lab.py
& 'D:\Anaconda\python.exe' -X utf8 -m unittest -v test_cashflow_lab.py
```

[主程序](./code/ch10/cashflow_lab.py)与[14项测试](./code/ch10/test_cashflow_lab.py)仅用标准库；[绘图程序](./code/ch10/plot_cashflows.py)使用已有Matplotlib，接受manifest路径和输出图片路径。每次新建runs目录，保存输入、结果、环境与哈希。没有新增依赖。

人工分红、拆股分别造成裸价格−1%、−50%，当时版本总收益均为零；迟到纠错只用于事后重述。五年半年付息债券面值100、票息4%、名义YTM3%，价格104.6110923、修正久期4.5246008、凸性23.8065816。14项程序检查、9项格式测试与99式本地数学语法检查通过。不是实际交易、收益预测或真实日历债券引擎。总目录已链接第10章并加入10.4；下一章为第11章。


## 第十一章运行

在仓库根目录运行：

```powershell
& 'D:\Anaconda\python.exe' -X utf8 教材/code/ch11/derivatives_lab.py
& 'D:\Anaconda\python.exe' -X utf8 -m unittest discover -s 教材/code/ch11 -v
```

[主程序](./code/ch11/derivatives_lab.py)和[14项检查](./code/ch11/test_derivatives_lab.py)只使用标准库；[绘图程序](./code/ch11/plot_derivatives.py)使用已有Matplotlib，接受运行目录路径。人工换月账本最终权益1026，错误拼接盈利80；FX锁汇收益等于本币利息，BSM看涨10.4505835722、反解IV约20%。不含真实交易、生产清算、动态强平或真实系统延迟。总目录已链接第11章并加入11.4；下一章为第12章。

## 第十二章运行

在仓库根目录运行：

```powershell
& 'D:\Anaconda\python.exe' -X utf8 教材/code/ch12/risk_lab.py
& 'D:\Anaconda\python.exe' -X utf8 -m unittest discover -s 教材/code/ch12 -v
```

[主程序](./code/ch12/risk_lab.py)及[12项检查](./code/ch12/test_risk_lab.py)使用已有NumPy2.1.3；[绘图程序](./code/ch12/plot_risk.py)使用已有Matplotlib，接受运行目录。600期训练、600期样本外，三种风险估计共用数据与固定参数；人工断点仅用于事后分组，不进入预测器。同步相关约0.80，滞后一格约0；独立报价噪声使最密采样RV约为真值20.6倍。结果不是实时预警或真实交易表现。总目录已链接第12章并加入12.4，下一章为第13章。

## 第十三章运行

在仓库根目录运行：

```powershell
& 'D:\Anaconda\python.exe' -X utf8 教材/code/ch13/pricing_lab.py
& 'D:\Anaconda\python.exe' -X utf8 -m unittest discover -s 教材/code/ch13 -v
```

[主程序](./code/ch13/pricing_lab.py)使用已有NumPy2.1.3；[12项测试](./code/ch13/test_pricing_lab.py)以已有statsmodels0.14.4交叉核对HAC；[绘图](./code/ch13/plot_pricing.py)使用已有Matplotlib3.10.0，接受运行目录。600期训练、600期样本外，窗口240与HAC5预先固定；EQ单因子截距t比率5.3364，双因子1.3446，真实人工截距为零。同期因子解释与事前均值预测分开，不将归因误差当预测误差；两状态SDF例价格.95/92/98。不含真实行情、生产服务或交易业绩。目录已链接第13章并加入13.4，下次接第14章。


## 第十四章运行

在仓库根目录运行：

```powershell
& 'D:\Anaconda\python.exe' -X utf8 教材/code/ch14/macro_lab.py
& 'D:\Anaconda\python.exe' -X utf8 -m unittest discover -s 教材/code/ch14 -v
```

[主程序](./code/ch14/macro_lab.py)及[12项测试](./code/ch14/test_macro_lab.py)仅用标准库；[绘图](./code/ch14/plot_macro.py)用已有Matplotlib，接受运行目录。144条人工发布、36次快照，未来修订使19次象限改变；59次可标准化首次意外、1次缺合格预期、1次重复。数值为确定性SYNTHETIC实验，不代表真实市场发生率。目录已链接第14章并加入14.4，下次接第15章。


## 第十五章运行

在仓库根目录运行：

```powershell
& 'D:\Anaconda\python.exe' -X utf8 教材/code/ch15/contagion_lab.py
& 'D:\Anaconda\python.exe' -X utf8 -m unittest discover -s 教材/code/ch15 -v
```

[主程序](./code/ch15/contagion_lab.py)和[14项测试](./code/ch15/test_contagion_lab.py)使用已有NumPy2.1.3；[绘图](./code/ch15/plot_contagion.py)使用已有Matplotlib，接受运行目录。8万组人工机制样本；三机构四资产压力测试仅改变冲击参数，总损失4.8/5.703135/9.032046，未直接持有股票的C出现间接损失。数值为SYNTHETIC情景，不是预测、违约概率或真实市场绩效。目录已链接第15章并加入15.4，下次接第16章。


## 第十六章运行

在仓库根目录运行：

```powershell
& 'D:\Anaconda\python.exe' -X utf8 教材/code/ch16/regime_lab.py
& 'D:\Anaconda\python.exe' -X utf8 -m unittest discover -s 教材/code/ch16 -v
```

[主程序](./code/ch16/regime_lab.py)和[14项测试](./code/ch16/test_regime_lab.py)使用已有NumPy；[绘图](./code/ch16/plot_regimes.py)使用已有Matplotlib并接受运行目录。720期人工收益、240期规则校准、479期可观测评分；HMM使用事先已知生成参数，只验证推断机制。过滤Brier约.005039不代表真实学习绩效；平滑与过滤5期类别不同，20期规则波动未知，17期上行且高波动。目录已链接第16章并加入16.4，第二篇完成，下次接第三篇第17章。


## 第十七章运行

在仓库根目录运行：

```powershell
& 'D:\Anaconda\python.exe' -X utf8 教材/code/ch17/model_lab.py
& 'D:\Anaconda\python.exe' -X utf8 -m unittest discover -s 教材/code/ch17 -v
```

[主程序](./code/ch17/model_lab.py)、[Schema](./code/ch17/schema.sql)与[17项测试](./code/ch17/test_model_lab.py)仅用现有Python标准库。实测Python3.13.5、SQLite3.45.3；代码要求Python>=3.12、SQLite>=3.37。12次人工投递形成8个事件版本、1次重复、3条隔离；原始消息全部保留。两次宏观快照为2.30%和2.10%；同键异值不覆盖，较旧版本迟到不回滚。接收时间等同逻辑可用时间是实验零处理延迟假设，不是实测服务延迟。支持本地事务故障留证，尚无自动PENDING恢复或分布式精确一次。目录已链接第17章并加入17.4，下次接第18章。
