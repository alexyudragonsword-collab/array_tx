---
type: project_topic
status: active
summary: ROADMAP A2 的模型（已实现，2026-11-03）——电压模 DPA 的压缩点随有效反射系数 |1+Γ_k| 移动，Γ_k 由互耦矩阵算出，定点迭代两轮；先说清单波束下它能和不能分开什么
tags: [load-pull, coupling, dpd, proposal]
contains: [decision, prediction]
created: 2026-11-03
updated: 2026-11-03
related: [architecture-invariants.md, coupling-model.md, ROADMAP.md]
authoring_mode: ai_generated
---
# 负载调制 PA（ROADMAP A2）：模型提案

> 状态：用户 2026-11-03 批准"按提案做"，已实现（`loadpull.py`、`sim.radiate`、`element.pa.load_pull`，ex09）。预期的检验结果在文末。

## 为什么里程碑 1 的互耦分不开两种 DPD

互耦只是线性泄漏：r_k = y_k + Σ_j S_kj y_j。DPA 对输入相位旋转协变，单波束下各单元驱动只差复权重 w_k，
所以泄漏是各单元非线性输出的线性组合，每单元 DPD 把自己线性化后，波束方向的 ACLR 与互耦无关（LOG 里程碑 1，
ex02：互耦 0 → −10 dB 三方案只动 0.02–0.08 dB）。要让互耦进入非线性，耦合回来的波必须**改变 PA 自己的工作点**——这就是负载牵引。

## 模型（一阶，电压模）

- **有效反射系数**：Γ_k(t) = Σ_j S_kj(f) ⊛ y_j(t) / y_k(t)，即到达端口 k 的耦合波相对自己出射波的比值。
  它已经在 `apply_coupling` 里算出来了（leak_k / y_k），不需要新的物理输入；按频率依赖取 S_kj(f)，与铁律 3 同一条路径。
- **PA 的响应**：开关电容 / 类 D 的 DPA 是电压源：端口电压 v_k = v_fwd,k (1 + Γ_k)，而压缩由电源轨决定的最大摆幅限制。
  所以把 Rapp 的驱动量从 `drive·r` 改为 `drive·|1 + κ_a Γ_k(t)|·r`，AM-PM 同样按 `|1 + κ_p Γ_k(t)|` 缩放。
  κ_a = κ_p = 1 是"理想电压源"的读法（source: assumed，理由如上）；实测 load-pull 表（source: measured）以后可以替换整个映射。
- **定点迭代**：Γ_k 依赖 y_j，y_j 依赖 Γ_j。从无负载效应的 y^(0) 出发算 Γ^(0)，重跑 PA 得 y^(1)，再算 Γ^(1)…
  |S| ≤ −16 dB 时收缩因子约 |S|·(∂A/∂drive) ≪ 1，两轮足够；`element.pa.load_pull.iterations: 2`，并记录每轮 ‖y^(i) − y^(i−1)‖。
- **数值护栏**：包络过零附近 Γ_k = leak/y_k 无意义；|y_k| < 0.05·fs_scale 处 Γ_k 置 0，且 |Γ_k| 截到 0.5（无源矩阵下 |Γ| ≤ 泄漏增益 ≤ 1，
  实际 8 × 8 survey 的泄漏增益 0.82）。
- **不改 vendor**：arraytx 侧包一层 `LoadPulledDPA`，`__call__(code, phase)` 前先 `set_load(|1+Γ|)`；polar_tx 的 `chain.py` 照常调 `self.dpa(ck, phase)`。
  `ArraySim.radiate` 在开关开时做迭代；DPD 训练用的 PA 可调用走同一个 `radiate`，所以每单元 DPD 在 PA 前向口看到的就是负载牵引后的输出。
- **配置**：`element.pa.load_pull: {enabled: false, kappa_amam: 1.0, kappa_ampm: 1.0, iterations: 2, gamma_max: 0.5}`，默认关——
  里程碑 1 / 2a 的全部数字与指纹不动；开关开时照常是种子可复现的（没有新的随机量）。

## 先说清：单波束下它能分开什么、不能分开什么（预期，待推翻）

- 若所有单元的 PA 完全相同、驱动只差 w_k，则 Γ_k = Σ_j S_kj w_j / w_k 是**常数**（经典的"有源阻抗"：随扫描角变，不随时间变）。
  于是负载牵引只是给每个单元一个随位置、随扫描角不同的压缩点——每单元 DPD 在训练角度上仍能完全补偿。
  **预期 1**：在训练角度上，每单元 DPD 与阵列 DPD 仍只差零点几 dB。
- 真正分开的是：(a) **换扫描角不重训**——Γ_k 随 θ0 变，0° 训练的 DPD 用到 60° 会留下残余（每单元与阵列两种都受影响，量不同）；
  (b) **单元差异**——5 % PA 偏差和增益 / 相位误差让 Γ_k 有随波形变化的部分，这一部分是每单元 DPD 在自己端口看不见的；
  (c) **边缘 vs 内部单元**——8 × 8 的内部单元有 12 个邻居，Γ 的幅度可到 0.3–0.5（泄漏增益 0.82 的量级），边缘单元只有一半。
  **预期 2**：(a) 是 dB 级的效应，(b) 是零点几 dB，(c) 决定了阵列 DPD（一个模型管所有单元）在面阵上比线阵上更吃亏。
- 多波束 / MIMO（Γ_k 随波形剧烈变化）是 ROADMAP D 明确不做的；这里不编。

## 研究内容（ex09，实现后）

1. 4 单元与 8 × 8，0 / 30 / 60°：每单元的 |1+Γ_k| 的均值与标准差（时间上），边缘 vs 内部。
2. 三方案在训练角度上的波束 ACLR / EVM（预期 1 的检验）。
3. 0° 训练的两种 DPD 用到 30° / 60°（预期 2a），对比重训。
4. 单元误差开 / 关下 Γ_k 的时变部分与 DPD 残余（预期 2b）。
5. 与 ex03 / ex08 的无负载牵引数字并排，差值就是负载调制的贡献。

## 不做 / 边界

- 不碰 outphasing 的合路器负载（那是另一个模型）；rfdac 无压缩，开关对它无效并报告。
- 不引入 Γ 对 PA 效率的影响（效率不是本库的验收量）。
- 这是行为级一阶模型：真实 PA 的负载牵引是 Γ 相位相关的（Smith 圆图上压缩等高线不是圆），κ 只是标量；要更真就得实测表。
