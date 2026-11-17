# array_tx 路线图

只写没做的。做完的删掉，进 CHANGELOG。

## A. 被外部阻塞

### A1. 互耦 survey 典型值等全文核对 / 等实测 S 参数
`configs/*.yaml` 里 `coupling.survey` 的相邻耦合 −16 dB 现标 source: assumed（见 config 里 `ref`），全文核对见下（arXiv / JEES 已放行，PMC / MDPI 仍读不到）。
拿到实测 `.sNp` 就切 `coupling.source: touchstone`，不改任何别的抽取（铁律 5）。
2026-11-05 放行 arxiv.org / www.jees.kr 后读了全文：arXiv:2407.09944 与 JKIEES 2017 都没有互耦数字；全文里只有仿真、无去耦的上界
（JEES 2026 < −20 dB @ 0.47 λ，arXiv:2010.16049 −24 dB），www.mdpi.com 站点拒绝（403）。−16 dB 自 2026-11-06 起标 assumed（值不变，偏悲观）。
要的不只是幅度：ex18 表明相邻互耦**相位**决定哪一头难（180° 时 60° 要回退，0° 时广播向要退 3 dB），E / H 面之比决定 8 × 8 的无源上限
（0 dB −14.3 dB，−3 dB −13.0 dB）。所以要的是面阵的复数 S 参数（.sNp），至少相邻行内 / 行间各一个复数。

### A2. 负载调制：只有一阶电压模，没有实测 load-pull 表
`element.pa.load_pull` 已实现（`cairn/load-pull-proposal.md`），κ = 1 是 assumed。真实 PA 的压缩等高线在 Smith 圆图上不是圆（Γ 相位相关），
要更真得换 source: measured 的 load-pull 表替换 `loadpull.amam_loaded` 的映射。
效率已含 Γ（端口净功率，`cairn/loaded-efficiency-proposal.md`），但只有 SCPA 的开关损耗；导通损耗 |i|²R_on 随 |1−Γ|² 变，没有 R_on 的出处，没建。
outphasing 的效率仍是 polar_tx 的 Chireix 律，没接 Γ。
κ 还决定 |1+Γ| 规则能不能用：ex21 中只在 κ = 1 训练的规则在 κ = 0.5 时 15 点漏 1 点（|1+Γ| < 1 的角，负载牵引"白送"的线性度减半），所以 κ 要先测，或按 κ 的范围取最坏来训练。

## B. 已知模型缺口

### B7. 面阵的互耦只有邻域类，没有单元方向图 / 极化
8 × 8 的 x1 / x2 / y1 / y2 / d1 五类邻居加上按电长度的相位，无源性只是"不违反"（泄漏增益 0.82），不是实测；E 面 / H 面耦合差异
（`c1y_rel_db`）、对角（`c_diag_rel_db`）都是 assumed。单元方向图仍是 isotropic / cos θ，没有极化。拿到面阵 .sNp 就切 touchstone（面阵往返已有逐位测试：端口按单元 row-major 序，k = ix + n_x·iy）。

### B9. 回退表按平均 |1+Γ| 存，偏保守
ex19：只在 180° 训练、按平均 |1+Γ| 取回退，没训练过的相位全部达标，但 8 × 8 比先知平均少 1.3 个效率点（外推与台阶边缘各多退 1 dB）；
8 × 8 上 |1+Γ| 0.81 / 0.87 也要退 1 dB 而 180° 的 0.74 不用——平均值盖住了边缘 / 内部单元之差。
ex20 试了每单元回退（`element.pa.backoff_per_element_db`，同一条按平均值训练的规则用到每个 |1+Γ_k|）：处处达标，但平均效率与整阵列一个回退持平
（4 × 1 50.39 对 50.48 %，8 × 8 45.31 对 45.35 %），波束功率 −0.54…+0.50 dB。没做：按每单元训练的规则（要搜每单元回退组合）、小于 1 dB 的回退台阶。

### B10. FR2 的 LO 剖面是 sub-6 剖面按 (fout/f0)² 连续放大，不是可实现的倍频链
`lo.py` 的 `ClockProfileLO` 把剖面当理想倍频 / 分频器的参考，S_φ 乘 (fout/f0)²（如 10 GHz → 28 GHz 是 ×2.8，非整数）。
pll_simulator@5564c64 的 `export/clock_profile.py`（已随本库 vendor）有整数 ×N 倍频器：`integer_multiplier` 拒绝非整数 N，
`multiply_curve` 在 f_in/2 以内给 N²·L_in 加白噪底、以外只剩底，`multiply_spurs` 加 20 log10 N 与 N±1 次谐波泄漏。
换成"整数 N 的 PLL + 倍频器"（PLL 调到 f_c/N）会动 LO 相关的数字（ex05 / ex07、EVM 底），单独一轮，标 numbers-move。

### B11. 联合 ILA 固定跑 `dpd.n_iterations`（默认 2）轮，第 2 轮拿频谱换 EVM（array_tx#8 提出，2026-11-17 实测）
PA_DPD a9220d6 的 `ILAPredistorter.fit` 默认 keep-best（按训练信号 NMSE、1 dB 容差保留最好一轮）；本库的 `dpd._joint_ila` 是自己的固定轮数循环，
没跟。FR2 4 × 1、30°、噪声关，每单元 DPD 1 / 2 / 3 轮：波束 ACLR1 −46.99 / −47.04 / −45.78，ACLR2 −54.05 / −52.03 / −49.06，
EVM −36.97 / −37.11 / −36.99，旁瓣 ACLR1 −51.01 / −48.95 / −46.52 dBc（阵列 DPD、开负载牵引同趋势）：第 2 轮 EVM 好 0.14 dB、ACLR2 与旁瓣差约 2 dB，
第 3 轮发散。NMSE 判据主要看带内，多半仍选第 2 轮、挡不住频谱上的 2 dB；要按频谱 / 方向选轮次得本库自己定判据。
做法候选：一个示例扫轮数 × 方案 × 波束 / 旁瓣，比 NMSE 与频谱两种判据各选哪轮，再定默认值或判据。会动 DPD 之后的数字，numbers-move，单独一轮。

### B2. FR2 的 ACLR / 模板数字在 os 4 的网格上偏保守（2026-11-16 按读法 P 重写；原题"事件引擎在 FR2 不可用"作废）
原写法两半都不成立：polar_tx B1 的根因是 TDC 量程（127 ps 对 513 ps 周期），不是相位推进，已修；本库的 FR2 链里没有 ADPLL
（nr_dtc(bw > 100 MHz) → wifi_dtc，引擎 dtc_openloop）。event / response 都要 fs_bb ≤ fref 且 fref/fs_bb 为整数，ACLR1 要 os ≥ 3、
ACLR2 要 os ≥ 4，即 fref ≥ 1.47 / 1.97 GHz，不是现实的 28 GHz 两点 ADPLL。
真正的限制是网格。DTC / DPA 时钟固定在 4 × FFT 速率（1966.08 MHz），网格更细只多出保持的下垂与镜像（读法 P，polar_tx 0e7b7ac，
本库 `arraytx.clock` 跟进）。ex22（os 4 / 8 / 16 / 32，事先定的容差 ACLR 与模板 0.3 dB、EVM 0.1 dB，与 os 16 比；六个工况）：os 4 的
ACLR1 偏保守 0.32–0.49 dB、ACLR2 2.11–2.16 dB、可见带模板 0.44–0.59 dB、旁瓣 / 最差亮方向 ACLR1 至多 0.60 dB；scalar EVM 偏乐观
0.09–0.48 dB；per-tone EVM 收敛（≤ 0.04 dB）。os 16 与 os 32 除全幅模板（镜像电平动 0.56 dB）外差 ≤ 0.15 dB。杂散 ΔEVM / ΔACLR1
os 4 − os 16 ≤ 0.02 dB；噪声底不再随网格动（`cairn/dtc-openloop-grid.md`）。读法 T 的第一次 ex22 作为历史留在主题笔记里。
引擎行按 P 给出（`report.disclaimer_for`）：polar、每次更新 ≥ 4 个网格点（os ≥ 16）时 ACLR / EVM / 可见带模板不挂免责，全幅模板照挂。
没做的：把示例默认网格提到 16 并重跑。按 LOG 里的全尺寸耗时（os 4 合计约 9 h）与 ex22 的单次耗时比（×3–4）估约 30 h，
而且 cairn 与 README 里全部 os 4 的数字都要重写；numbers-move，单独一轮。

### B3. rfdac 拓扑：能跑 FR2，DPD 能跑但没有东西可校；outphasing 的 ρ 没有出处
rfdac 按 FR2 的载频和 LO 建链并有测试（`tests/test_element.py::test_other_topologies_run_at_fr2`）；polar_tx@008cc90 起 `CartesianTX` 读 `fs_scale_fixed`，
满刻度钉住、DPD 能跑，但 polar_tx 的 RF-DAC 模型只有失配没有压缩，无可校之处。要给它加压缩模型（属 polar_tx）。
outphasing 已有分支源阻抗 ρ × Chireix 电纳的 AM-AM（`cairn/outphasing-load-proposal.md`，ex12），DPD 在 ρ = 0.1 时追回 9 dB；
但 ρ 是 assumed，没有 28 GHz 分支 R_on / Z0 的出处。非线性源阻抗（R_on 随电流）没建，那是负载能够到 outphasing 非线性的唯一一阶路径。

## C. 工程维护

### C1. Android APK 没有真机数字
APK 在 CI 上构建过一次（2026-11-03，84.7 MB，两个 ABI），桥与页面在没有 Android 的机器上测过；真机上的首次导入时间、128 单元的内存、
线程后端下一次 run 的耗时都没有数字。页面的"打开 / 保存"在手机上只按默认路径走（prompt 被 WebChromeClient 按默认值确认），没有文件选择器。

## D. 明确不做

- 接收机、MIMO 预编码、信道模型：TX 损伤库，指标止于远场。
- 天线电磁仿真：互耦矩阵是输入。
- 替代认证测试：OTA 限值只做趋势比较。
- 载波聚合、多波束、FR2 以外的毫米波频段。

## E. 报回上游（以上游 issue 跟踪）

（暂无。E1 已由 polar_tx 0e7b7ac 解决、本库跟进，见 CHANGELOG 2026-11-16。）
