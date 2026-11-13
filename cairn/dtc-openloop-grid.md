---
type: project_topic
status: active
summary: FR2 链的杂散 / 互调数字随采样网格收不收敛——dtc_openloop 不是线性化引擎，限制是 fs/2 以上的折叠；os 4 时无 DPD 的 ACLR1 收敛、ACLR2 偏高 4.7 dB、DPD 后 ACLR1 偏高约 0.5 dB，os 16 与 os 32 一致；免责声明因此不动
tags: [engine, oversampling, aclr, spurs, dpd, validity]
contains: [decision, lesson, pitfall]
created: 2026-11-13
updated: 2026-11-13
related: [fr2-floor-lo.md, architecture-invariants.md]
authoring_mode: ai_generated
---
# dtc_openloop 的数字随网格收敛吗

## 问题怎么来的

ROADMAP B2 原来写"event 引擎在 FR2 不可用，所以 FR2 只能用线性化引擎，杂散 / 互调结论不能背书"。两半都不成立：
polar_tx B1 的根因是 TDC 量程，不是相位推进（polar_tx `cairn/adpll-event-engine.md`：127 ps 对 513 ps，LTE-20 event EVM −14.7 → −44.5 dB）；
本库 FR2 链里没有 ADPLL（nr_dtc(bw > 100 MHz) → wifi_dtc → `DTCPhaseModulator`）。event / response 都要 fs_bb ≤ fref 且整数比，
ACLR1 要 os ≥ 3、ACLR2 要 os ≥ 4，即 fref ≥ 1.47 / 1.97 GHz。

dtc_openloop 逐样本施加量化（含一阶误差反馈）、增益误差、INL（多项式 + 正弦）、抖动、LO 相噪和更新时钟的 ZOH；
本库的 FR2 配置里 INL 为空、增益误差 0、更新时钟 = 网格。它不是线性化的；它看不到 fs/2 以上的东西，那里的非线性产物会折回。

## 做法（ex22）

`sim.oversampling` 4 / 8 / 16（/ 32），同一批符号（os 8 隔点取与 os 4 差 0.38 % 峰值，窗函数插值）。字面的 ×1 / ×2 跑不了：
ACLR1 要 fs ≥ 3 BW，os 1 / 2 只有 1.23 / 2.46 BW。DTC 与 DPA 都在网格上更新，所以 os → ∞ 是同一模型的连续时间极限。
事先定的容差（全量运行前写进示例）：与 os 16 比，ACLR 0.3 dB、EVM 0.1 dB。

## 数字（4 × 1，30°，8 符号，噪声关，survey；analytic 的 os 4 − os 16 差与之相差 ≤ 0.03 dB）

| 方案 | ACLR1 os 4 / 8 / 16 | ACLR2 os 4 / 8 / 16 | 旁瓣 ACLR1 os 4 / 16 | EVM os 4 / 16 |
|---|---|---|---|---|
| 无 DPD | −37.98 / −37.93 / −38.04 | −60.31 / −63.47 / −65.04 | −39.87 / −39.94 | −30.34 / −30.45 |
| 每单元 DPD | −47.04 / −46.78 / −47.50（os 32 −47.48） | −52.03 / −52.83 / −53.29（−53.30） | −48.95 / −50.48（−50.49） | −37.11 / −37.29 |
| 阵列 DPD | −46.91 / −46.72 / −47.45（os 32 −47.43） | −51.39 / −52.50 / −53.02（−53.06） | −45.56 / −46.03（−46.05） | −37.10 / −37.28 |

- **收敛的**：无 DPD 的 ACLR1、旁瓣 ACLR1、最差亮方向 ACLR1（os 4 − os 16 ≤ 0.07 dB）。
- **不收敛的**：ACLR2（os 4 偏高 4.74 dB；它的带 600–1000 MHz 顶到 fs/2 = 983 MHz）；DPD 后的一切（ACLR1 0.46–0.54 dB、
  旁瓣 ACLR1 至多 1.54 dB、最差亮方向 0.22–0.61 dB），而且 os 8 不单调（DPD 在折叠过的数据上训练，残余随网格变）；
  EVM 0.11–0.19 dB，压线。os 16 与 os 32 差 ≤ 0.04 dB：模型在 os 16 收敛。
- **杂散（ex07 的三张最响的表）**：ΔEVM（开 − 关）os 4 − os 16 为 −0.22…+0.19 dB，ΔACLR1 ≤ 0.03 dB。
- **噪声开的底也随网格动**：EVM −26.40 / −26.04 / −25.75、ACLR2 −50.52 / −51.96 / −52.81（os 4 / 8 / 16，无 DPD）：
  LO 相噪与抖动按网格的 fs/2 合成，网格越宽，积进来的远端相噪越多、抖动的带内密度越低。这是噪声模型的性质，不是折叠。
- **更新时钟固定在 1.966 GHz（os 16 上 ZOH）**是另一种物理：ACLR1 −38.35 / −50.33 / −50.03（无 / 每单元 / 阵列 DPD），
  EVM 读成 −17.5 dB 是 ZOH 半个更新周期的延时被标量均衡当成误差，不是失真。

## 决定

按事先的标准不收敛，`report.DISCLAIMER` 与 AGENTS 的规矩不动。准确的说法是"os 4 的网格没收敛"，不是"线性化"。
要收窄成"os ≥ 16 下 dtc_openloop 的确定性杂散 / 互调结论可背书"，得把示例默认网格提到 16（运行时间约 ×4，numbers-move），单独一轮。
报回上游：ROADMAP E1（polar_tx nr_dtc FR2 默认 os 4）。

## 坑

- "fs ≥ 4.9 BW 才能测 ACLR2" 是能测的下限，不是测准的条件；对非线性链，ACLR2 的带贴着 fs/2，折叠直接落进去。
- 过采样研究里 DTC 与 DPA 的更新时钟跟着网格走；想比"同一硬件、更细的网格"得同时钉住 `f_update` 与 `f_dpa`，而那会引入真实的 ZOH 下垂与延时。
- 带噪声比较不同网格时，底本身在动；判断杂散 / 互调是否收敛要用噪声关的确定性运行。
