---
type: project_topic
status: active
summary: FR2 链的数字随采样网格收不收敛——DTC / DPA 时钟固定在 4×（1966.08 MHz），网格更细只多出保持的下垂与镜像（读法 P）；os 4 的 ACLR 与可见带模板偏保守（ACLR2 约 2.1 dB）、scalar EVM 偏乐观至多 0.5 dB、per-tone EVM 已收敛；os 16 除全幅模板外全部收敛
tags: [engine, oversampling, clock, aclr, mask, spurs, dpd, validity]
contains: [decision, lesson, pitfall]
created: 2026-11-13
updated: 2026-11-16
related: [fr2-floor-lo.md, architecture-invariants.md]
authoring_mode: ai_generated
---
# dtc_openloop 的数字随网格收敛吗

## 问题怎么来的

ROADMAP B2 原来写"event 引擎在 FR2 不可用，所以 FR2 只能用线性化引擎，杂散 / 互调结论不能背书"。两半都不成立：
polar_tx B1 的根因是 TDC 量程，不是相位推进（polar_tx `cairn/adpll-event-engine.md`：127 ps 对 513 ps，LTE-20 event EVM −14.7 → −44.5 dB）；
本库 FR2 链里没有 ADPLL（nr_dtc(bw > 100 MHz) → wifi_dtc → `DTCPhaseModulator`）。event / response 都要 fs_bb ≤ fref 且整数比，
ACLR1 要 os ≥ 3、ACLR2 要 os ≥ 4，即 fref ≥ 1.47 / 1.97 GHz。

dtc_openloop 逐个更新施加量化（含一阶误差反馈）、增益误差、INL、DPA 的 AM-AM / AM-PM；它不是线性化的。

## 两种读法

- **读法 T**（2026-11-13 的第一次 ex22）：DTC / DPA 的更新时钟随网格走。os 16 是一颗时钟快 4 倍的芯片，不是同一颗芯片读得更细；
  量化噪声摊到的带宽随 os 变，所以这种比较永远"收敛"不到同一个东西（polar_tx：默认 DPA 下 os 32 − os 16 为 −1.1…−3.7 dB）。
- **读法 P**（polar_tx 0e7b7ac 起，本库 2026-11-16 跟进）：时钟是硬件的，4 × FFT 速率（FR2 1966.08 MHz，`Standard.update_oversampling`）；
  网格比时钟细时每次更新保持 os / 4 个网格点。只有网格在变，os → ∞ 是同一颗芯片的连续时间输出。

本库在 P 下的分工（`arraytx.clock`）：数字的在时钟上——波形（polar_tx `burst_on_grid`：在时钟上生成、插值到网格、更新时刻的样本逐位还原）、
CFR、DPD（GMP 在更新时刻的样本上算，观测经理想抗混叠接收机降到时钟，`to_clock`），以及 polar_tx 链内的极坐标拆分、量化、DPA 编码；
模拟的在网格上——保持后的输出与镜像、导向与真延时、单元的模拟误差、互耦、远场、指标。负载牵引的 Γ 在网格上算，DPA 取更新时刻的值。
os 4 时这一切都是恒等，指纹逐位不变。outphasing / rfdac 在 polar_tx 里没有分开时钟，它们的时钟仍随网格（os > 4 = 更快的芯片）。

## 做法（ex22，读法 P）

`sim.oversampling` 4 / 8 / 16 / 32（每次更新 1 / 2 / 4 / 8 个网格点）。事先写进示例的容差：ACLR 与模板 0.3 dB、EVM 0.1 dB；
os 4 对 os 16 判"os 4 收敛"，os 32 对 os 16 判"os 16 收敛"。比第一次多读三项（与 polar_tx ex22 相同）：per-tone EVM（保持的下垂是线性的带内响应，
per-tone 均衡能去掉、scalar 不能）；模板带外裕量分两种——可见带（时钟奈奎斯特以内，= os 4 看到的范围）与全幅（整个网格，时钟镜像在里面）。
ACLR 与模板的 FFT 长度随保持倍数放大（`metrics.NFFT × hold`），分辨率带宽在每个网格上相同。

## 数字（4 × 1，30°，8 符号，噪声关；survey 与 analytic 六个工况，570.6 s）

| 读数 | os 4 − os 16 | os 32 − os 16 | 判定 |
|---|---|---|---|
| ACLR1 | +0.32…+0.49（偏保守） | −0.04…−0.02 | os 4 ✗，os 16 ✓ |
| ACLR2 | +2.11…+2.16（偏保守） | −0.15…−0.08 | os 4 ✗，os 16 ✓ |
| EVM（scalar） | −0.48…−0.09（偏乐观，DPD 工况大） | +0.01…+0.05 | os 4 2/6，os 16 ✓ |
| EVM（per-tone） | −0.04…−0.01 | +0.00…+0.01 | os 4 ✓ |
| 模板（可见带） | −0.59…−0.44（偏保守） | −0.11…+0.08 | os 4 ✗，os 16 ✓ |
| 模板（全幅） | os 4 看不到镜像（+20…+28） | +0.56 | os 16 ✗ |
| 旁瓣 ACLR1 | +0.32…+0.60 | −0.04…+0.00 | os 4 ✗，os 16 ✓ |
| 最差亮方向 ACLR1 | +0.32…+0.47 | −0.03…−0.02 | os 4 ✗，os 16 ✓ |

原值（survey，os 4 / 8 / 16 / 32）：无 DPD ACLR1 −37.98 / −38.23 / −38.29 / −38.31，ACLR2 −60.31 / −62.06 / −62.47 / −62.57；
每单元 DPD ACLR1 −47.04 / −47.43 / −47.53 / −47.55，ACLR2 −52.03 / −53.75 / −54.15 / −54.23，scalar EVM −37.11 / −36.81 / −36.65 / −36.61，
per-tone EVM −37.89 / −37.87 / −37.85 / −37.85；全幅模板带外裕量（无 DPD）−5.71（os 4 只看到可见带）/ −28.20 / −25.79 / −25.23 dB。

- **os 4 的 ACLR 与模板偏保守**：os 4 读出来的失真比收敛值多，所以 os 4 上"达标"的结论在收敛网格上仍达标；反过来不成立。
- **scalar EVM 偏乐观**：os 4 看不到保持的下垂（1966 MHz 时钟、±200 MHz 信道，带边约 −0.13 dB），DPD 后底更低，下垂占比更大，差到 0.48 dB。
- **全幅模板**：首个时钟镜像在 1966 ± 190 MHz（未滤波；保持的 sinc 在 f_clock 处为零，镜像带边约 −19.5 / −21 dB，±f_clock 两个镜像合计约 −22 dB），
  stylized 模板在全幅上差 25 dB 以上；os 16 → 32 动 0.56 dB
  （离散保持逼近连续保持，polar_tx 量的是 0.55 dB）。本库没有输出滤波器模型，这个读数不是一台 TX 的读数。
- **杂散（ex07 的三张最响的表）**：ΔEVM os 4 − os 16 ≤ 0.01 dB，ΔACLR1 ≤ 0.02 dB。
- **噪声底收敛了**：EVM −26.40 / −26.37 / −26.36 / −26.35，ACLR2 −50.52 / −51.41 / −51.62 / −51.66（无 DPD）。抖动按更新抽（它定时的是一个边沿），
  LO 在网格上（时钟奈奎斯特以下逐频点沿用，以上新抽）。读法 T 下这一行是 −26.40 / −26.04 / −25.75，是噪声模型随网格变，不是物理。
- 与 polar_tx 读法 P 的单链结论同向同量级：ACLR1 偏保守 0.3–1.0、NR ACLR2 1.8–2.4、可见带模板 0.5–2.9、scalar EVM 偏乐观至多 2.6、per-tone 收敛。

## 历史：读法 T 的第一次 ex22（2026-11-13）

survey，无 DPD ACLR1 −37.98 / −37.93 / −38.04，ACLR2 −60.31 / −63.47 / −65.04；每单元 DPD ACLR1 −47.04 / −46.78 / −47.50（os 32 −47.48）；
当时判"os 4 不收敛、os 16 收敛（与 os 32 差 ≤ 0.04 dB）"。os 4 的数两种读法逐位相同（os 4 时钟 = 网格）；os 8 以上 T 换的是芯片，
os 16 收敛只说明这颗更快的芯片自身稳定，不说明 os 4 的芯片读准了。引擎行原来的"os ≥ 16 不挂免责"按 T 立的，按 P 重写见 ROADMAP E1。

## 决定

- 本库跟进读法 P（用户 2026-11-16 选"全面跟进时钟 4×"）：`sim.oversampling` 必须是 4 的倍数；示例默认网格仍是 os 4。
- 引擎行（`report.disclaimer_for`）按 P 的结论收紧，单独一个 PR（ROADMAP E1）。
- 守护：`tests/test_clock.py`——每个网格上链读到的样本逐位相同；无 DPD、噪声关时 os 8 的远场经 `to_clock` 等于 os 4 的远场乘保持的带内响应
  （单元输出 1e-12；过互耦后 1e-6，见"坑"）；DPD 在时钟上；负载取更新时刻；outphasing 时钟随网格；网格必须容下整数次更新。

## 坑

- "fs ≥ 4.9 BW 才能测 ACLR2" 是能测的下限，不是测准的条件。
- 网格变细时 Welch 段长要跟着放大（`metrics.NFFT × hold`），否则分辨率带宽变宽、信道边缘抹进邻道（polar_tx：WiFi 80 MHz 仅此一项差 4 dB）。
- "亮方向"要按时钟奈奎斯特以内的功率判（`power_vs_direction_db(e, wf)`）：镜像在 f0 + k·f_clock，波束指向不同，会把信号不亮的方向点亮
  （第一次全量 ex22：最差亮方向 ACLR1 os 32 − os 16 因此 +1.32 dB，改后 −0.03）。
- 模板读带外裕量（`oob_margin_db`）：`worst_margin_db` 含带内参考，带外过了以后被钉在 0，看不出收敛。
- 时钟的奈奎斯特频点在 os 4 上是一个点，在细网格上是 ±fs4/2 两个点；分数延时、随频率变的互耦在两点上各乘各的，比较时去掉这一点。
- survey / analytic 互耦在 f0 ± fs/2 上取 257 个点再线性插值：网格越宽取点越稀，带内插值误差约 1e-7（与时钟无关）。
- 带噪声比较不同网格时，先确认噪声模型本身不随网格变（读法 P 下已不变）；判断杂散 / 互调是否收敛仍用噪声关的确定性运行。
