---
type: project_topic
status: active
summary: 互耦模型的当前真值——三来源一条路径、邻域类与电长度相位、无源性检查、线性泄漏分不开两种 DPD 的原因、apply_coupling 的位序
tags: [coupling, touchstone, dpd, passivity]
contains: [decision, lesson, pitfall]
created: 2026-11-03
updated: 2026-11-04
related: [architecture-invariants.md, load-pull-proposal.md]
authoring_mode: ai_generated
---
# 互耦模型

## 当前真值

- **一条路径**：analytic / survey / touchstone 都产出 `CouplingMatrix(freqs, S[F,n,n])`，只经 `apply_coupling` 进链路：
  R_k(f) = Y_k(f) + Σ_j S_kj(f) Y_j(f)，对角永远不用（单元自身的反射不在这里建）。S 恰为全零时原样返回输入对象（1 单元 = polar_tx 逐位相同的前提）。
- **邻域类**（analytic / survey）：x1 相邻、x2 隔一个、y1 隔一行、y2 隔两行、d1 对角；一行上只出现 x1 / x2，即里程碑 1 的形状。
  幅度：c1（survey −16 dB，摘要级出处见 config）、c2_rel −6 dB、c1y_rel 0 dB、c_diag_rel −6 dB（后三者 assumed，理由在 `config.py` 的 ref）。
- **相位**：x1 在 f0 为 c1_deg（180°，符号约定）；远邻 = c1_deg + 超出一个间距的自由空间电长度（`phase_from_distance`，默认开）：
  λ/2 间距 x2 +180°（即 0°），对角 +74.5°（即 −105.4°）。survey 的频率依赖是纯延时 φ(f) = φ0 − 2π(f−f0) d/c（`path_delay_from_spacing`）。
- **无源性**：`build_coupling` 算泄漏矩阵的最大奇异值，> 1 抛错。4 单元 survey 0.33；8 × 8 survey 0.82。
- **touchstone**：v1、Hz / RI、2 端口块是列序 S11 S21 S12 S22（读写都按行序会把 S21/S12 读反）；端口序 = 单元 row-major 序；
  analytic → .sNp → touchstone 回读逐位相同（等值端点 `np.interp` 精确）。

## 为什么线性泄漏分不开每单元 DPD 与阵列 DPD（里程碑 1 被推翻的预期）

DPA 的 AM-AM / AM-PM 只看幅度码，对输入相位旋转协变；单波束下各单元驱动只差复权重 w_k，所以 y_j = w_j·NL(x)，泄漏 Σ S_kj y_j 是各单元非线性的
线性组合。每单元 DPD 把 y_k 线性化成 G w_k x 后，辐射信号是线性信号的线性组合，波束方向的 ACLR 与互耦无关（ex02：0 → −10 dB 只动 0.03–0.06 dB）。
阵列 DPD 只在旁瓣方向比每单元差约 1 dB（a_k(θ) 变了，PA 偏差的残余往旁瓣走）。要让互耦进非线性必须让耦合波改 PA 的工作点：`load-pull-proposal.md`。

## 坑

- **远邻同相位在面阵上不无源**：所有邻居放在 c1 相位，一行上泄漏增益 0.33（碰巧没事），8 × 8 上 1.13 > 1，广播向波束几乎抵消（EVM −5.9 dB）。
  现象像"面阵物理"，其实是假设错；修正后指纹 81/168 项变，4 单元波束指标移动 ≤ 0.05 dB（CHANGELOG 2026-11-03）。
- **`apply_coupling` 的位序**：只对非零对累加，实部虚部分开累加才能复现 numpy 复数 einsum；"复数乘再加"差 1e-15，指纹就不逐位了。
  稠密 (N, n, n) 矩阵在 64 单元 8 符号要 9 GB，这也是为什么按对累加。
- **方向扫描的 ACLR**：页面用单元信号的 Welch 分段按方向合成（`guiutil.direction_scan`），与逐方向合成远场的精确路径（ex04）ACLR 差 < 1e-4 dB、
  方向图差 ≤ 0.01 dB；分段应用的延时是 ~0.01 样本的边缘效应。
- **零点里的 ACLR**：方向图零点主载波被抵消、邻道失真没有，ACLR 可到 −14…−20 dBc；真实但没人往那儿发，ex04 / 页面只在 ≥ −15 dB 的方向上报。

> 复核（2026-11-04，ex01 / ex02 / ex04 全尺寸重跑）：ex02 的变化量原写 0.02–0.08 dB（里程碑 1，远邻相位按电长度之前），现为 0.03–0.06 dB；泄漏增益 1.129 / 0.822、页面方向扫描与精确路径 ACLR 差 2.6e-6 dB、方向图差 0.006 dB 均复现。
