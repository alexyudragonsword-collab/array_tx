---
type: project_topic
status: active
summary: FR2 链的底在哪——EVM 由 LO 相噪与抖动定，ACLR 由 DPD 残余与噪声底合成；时钟剖面按 (f_c/f0)² 换算，EVM 只认带内相噪，ACLR 认 300 MHz 处的 L(f)；分数杂散的量级
tags: [lo, phase-noise, spurs, evm, aclr, dpd]
contains: [decision, lesson]
created: 2026-11-03
updated: 2026-11-04
related: [architecture-invariants.md]
authoring_mode: ai_generated
---
# FR2 链的底：LO、DPD 残余、噪声底

## 分解（LOG 2026-10-13，4 单元 survey、单元误差关、30°、8 符号，EVM dB / ACLR1 dBc）

- 理想 PA、噪声关：−40.34 / −64.53（只剩 DTC 量化、DPA 量化、CFR）。
- 理想 PA、噪声开（50 fs 抖动 + LO −100 dBc/Hz@1 MHz）：−28.35 / −50.66。
- Rapp PA 无 DPD：−30.07 / −37.65（噪声关）；Rapp + 阵列 DPD：−36.91 / −46.15（噪声关），−28.05 / −44.85（噪声开）。
- 结论：EVM −28 全部来自 LO 相噪与抖动，PA 与 DPD 几乎不影响它；ACLR1 平台 −44.9 = DPD 残余 −46.2 与噪声底 −50.7 的功率和。
  DPD 后 ACLR1 ≈ −45 已逼近 DTC 量化 / 抖动 / LO 的底，再加 GMP 阶数或抽头无益（见下）。

## GMP 默认（order 7 / memory_depth 1 / 无交叉项）

记忆抽头只伤 ACLR2（9 阶 1 抽头 −48.3，3 抽头 −45.0，5 抽头 −44.8）：单元链是 DPA + DTC，没挂记忆模型，多余抽头拟合噪声再生。
阶数 3/5/7/9 的 ACLR1 −44.77 / −45.14 / −45.36 / −45.39，7 阶到平台。

## 时钟剖面（ex05）

- 18 个 pll_simulator 预设随包（`bundled:<preset>`），按 (f_c/f0)² 换算到 28 GHz（相位 × f_c/f0）。
- **EVM 只认带内相噪**：rms 相位按 100 Hz..BW/2 积分、环路带宽以下压平，9 个 LO 的 EVM 拟合残差 0.25 dB；按 fs/2 积分时 ILCM 排最差却不是最差 EVM。
- **ACLR 认 300 MHz 处的 L(f)**：ILCM −118、ADPLL-BB −112 dBc/Hz 对应 ACLR1 −31 / −29 dBc，DPD 无能为力；其余剖面远端 −134…−141，ACLR 回到 DPD 残余的 −45。
- 斜率：EVM vs 20 log10(σ_φ)，无 DPD 0.31（PA 主导），DPD 后 0.64——最干净端仍有 DPD 残余 + 数据通路底。
- 九个 LO 全部满足 64-QAM 8 %（−21.9 dB）且余量 ≥ 4.5 dB；最干净的 Dartizio'23 ADPLL-BB DPD 后 −35.1 dB（−35.09）。

## 杂散（ex07，B6）

- 剖面的 `spurs:` 走不了 PSD（polar_tx 按 PSD 抽随机幅度），改为链输出乘 exp(jφ_spur(t))；DPA 相位协变使它等价于 LO 相位加法（与加在驱动上差 < −40 dB，是 DTC 重量化）。
  峰值相位 a = 2·10^(dbc/20)·f_c/f0；起始相位来自 `lo_spurs` 流。
- frac-N 预设的分数杂散（23–62 kHz）换算到 28 GHz 后 −37…−43 dBc，EVM 多 0.25–0.54 dB（DPD 后 0.35–0.75，DPD 消不掉）；参考杂散 ≤ −83 dBc 看不见；
  ACLR1 一律不动（频偏 ≤ 13 MHz ≪ 400 MHz）。小角度估计 20 log10(rms) 功率相加，9 个剖面 rms 误差 0.11 dB；23 kHz 杂散在 67 µs 突发里只有 1.5 周期，突发内 rms 依赖起始相位。
- 64-QAM 8 % 目标下杂散无关紧要；追 −35 dB 这一档时 frac-N 的分数杂散是 0.5 dB 量级的项，DPD 和 per-tone 均衡都消不掉。

> 复核（2026-11-04，ex05 / ex07 全尺寸重跑）：拟合残差 0.25 dB、最小余量 4.8 dB（≥ 4.5）、杂散 −37…−43 dBc、EVM +0.25–0.54 dB（DPD 后 0.35–0.74）、估计误差 0.11 dB 均复现；Dartizio'23 原写 −35.2，现 −35.09。
