---
type: project_topic
status: proposed
summary: ROADMAP B3 的 outphasing 合路器负载——一阶线性模型下阵列 Γ 只是一个复增益（戴维南），够不到非线性；提案只建分支源阻抗 ρ × Chireix 补偿电纳带来的单链 AM-AM，给 outphasing 的 DPD 一个可校的对象，等审阅
tags: [outphasing, combiner, load-pull, proposal]
contains: [decision, prediction]
created: 2026-11-03
updated: 2026-11-03
related: [load-pull-proposal.md, loaded-efficiency-proposal.md, ROADMAP.md]
authoring_mode: ai_generated
---
# outphasing 合路器负载（ROADMAP B3）：提案（等审阅）

> 状态：proposed。用户审阅前不实现。原选题是"给 outphasing 加合路器负载，看两种 DPD 能否分开"。动手前的电路解改变了结论，所以提案的范围比选题小。

## 现状

polar_tx 的 `OutphasingCombiner.combine` 是理想矢量和 y = g1·y1 + g2·y2；Chireix 的负载调制只进效率律，
源码注释写明"有限 PA 输出阻抗在负载调制下带来的幅度 / 相位失真刻意没建"。arraytx 的负载牵引开关对 outphasing 报告为无效。
ROADMAP B3 记着"DPD 能跑但没有东西可校"。

## 先算出来的结论：阵列负载够不到 outphasing 的非线性

把每条分支建成电压源 v_k 串源阻抗 ρ（相对 Z0），分支节点并 Chireix 补偿电纳 ±jB（polar_tx 的 b = ½ sin 2θ_c），
合路到负载 Z_L = R(1+Γ)/(1−Γ)，逐样本解线性方程。两种拓扑都解了：集总串联变压器，和 λ/4 线并联合路。θ 从 0° 扫到 85°，θ_c = 60°。

| ρ | Γ | AM-AM 起伏 | AM-PM 峰峰 |
|---|---|---|---|
| 0.05 | 0、−0.16、0.26、0.26j | 1.92 dB（四个 Γ 相同） | 0.00° |
| 0.10 | 0、−0.16、0.26、0.26j | 3.49 dB（四个 Γ 相同） | 0.00° |
| 任意 | B = 0 | 0.000 dB | 0.000° |

两种拓扑数字一样。原因是戴维南定理：线性源加线性合路器时，输出 = 开路电压 × Z_L / (Z_L + Z_th)。
开路电压只含 θ（失真的形状），Γ 只进后一个与 θ 无关的复因子。所以：

- **单波束、Γ 为常数时**，阵列负载对 outphasing 只是每单元一个复增益（幅相锥削误差），不产生互调，ACLR 不变。
  两种 DPD 在负载牵引下分不开，0° 训练用到 60° 也没有非线性损失。这与 polar DPA 的 2.8 dB 正好相反。
- 失真本身来自 ρ·B：低幅度处 cos θ + ε sin θ（ε = ρB），θ → 90° 时输出不归零。这是单条链的效应，S = 0 也有。
- 负载要够到非线性，得有非线性的源阻抗（R_on 随电流变）、未饱和的分支 PA，或随时间变的 Γ。一阶模型里都没有。

## 提案（两个选项，推荐 A）

- **A（推荐）：只建 ρ × B 的单链失真**。arraytx 侧包一层 `SourceImpedanceCombiner(OutphasingCombiner)`，`combine` 用上面的闭式
  y = (y1/(1+jρB) + y2/(1−jρB)) × 归一化。ρ = 0 时直接调父类，逐位不变。新叶子 `element.outphasing.source_impedance_rel`（默认 0，source: assumed，
  没有 R_on / Z0 的出处，只给 0.02–0.1 的扫描范围）。B3 的"DPD 没有东西可校"由此有了对象：AM-AM 起伏 2–3.5 dB。
  阵列 Γ 按戴维南因子接成每单元复增益，只为验证"线性、不影响 ACLR"这条预期，不期待新的非线性。
- **B：不建，直接关 B3**。把上面的戴维南结论写进 ROADMAP B3 和 coupling-model 主题，记为"一阶模型下 outphasing 对阵列负载免疫"。
  代价是 outphasing 的 DPD 仍无物可校。

## 预期（选 A 实现后的检验，待推翻）

1. ρ = 0 逐位等于现在（指纹不动）。
2. ρ = 0.05、S = 0 的单单元：无 DPD 的 ACLR1 明显变差；每单元 DPD 追回大部分。量级没算，ex 里给数。
3. 开负载牵引的阵列：两种 DPD 的 ACLR1 差 < 0.1 dB，0° 训练用到 60° 的 ACLR 损失 < 0.1 dB。
   如果实测不是这样，说明链里有我漏掉的非线性路径，要先查清再信数字。
4. 波束方向图：Γ 随扫描角变，每单元复增益随之变，主瓣增益和旁瓣有零点几 dB 的变化，量级 ∝ ρ|Γ|。

## 不做 / 边界

- 非线性源阻抗（R_on 随电流）不建：没有出处，且需要器件模型。
- λ/4 线的频率色散不建：合路器按瞬时网络处理，与 polar_tx 相同。
- 效率：Chireix 律不动；若第 1 项（`loaded-efficiency-proposal.md`）批准，outphasing 是否也接 loaded 效率，另行决定。
- 原始电路解在本条目的表里，没有进代码；实现时会写成测试，对拍两种拓扑的数值解。
