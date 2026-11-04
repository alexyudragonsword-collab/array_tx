---
type: project_topic
status: active
summary: 六条铁律各自落在哪个模块、由哪些测试守着
tags: [invariants, tests, architecture]
contains: [decision]
created: 2026-10-13
updated: 2026-11-04
related: [AGENTS.md, coupling-model.md, squint-and-evm.md, fr2-floor-lo.md, gui.md, load-pull-proposal.md]
authoring_mode: ai_generated
---

# 架构铁律与守护测试

| # | 铁律 | 实现位置 | 守护测试 |
|---|---|---|---|
| 1 | 配置是唯一真值 | `config.py`（`ArrayConfig`、`load_config`、`FORM_FIELDS`） | `tests/test_config.py` |
| 2 | 验收指标只在空间读 | `metrics.py`（`DirectionMetrics.domain`、`conducted_*` 只做诊断） | `tests/test_metrics.py`、`tests/test_sim_dpd.py::test_anchor_sim_equals_polartx_bitwise` |
| 3 | 互耦进链路，三来源同一路径 | `coupling.py`（`apply_coupling` 唯一入口；S=0 短路） | `tests/test_coupling.py`、`tests/test_touchstone.py` |
| 4 | 波束斜视按真实带宽算 | `beam.py`（`far_field` 频域逐频点） | `tests/test_beam.py` |
| 1（GUI） | 控件 = YAML 键，默认值只读不写 | `guispec.py`（`controls()` 来自 `form_fields()`，`values_to_config` 走 `config_from_dict`） | `tests/test_guispec.py` |
| 2（GUI） | 页面上的导通指标标 diagnostic | `guispec.METRICS` 的 `domain`、`guiutil.report_from_result` 的 `conducted_*` 键 | `tests/test_guiutil.py`、`tests/test_webui.py` |
| 5 | 单元差异是种子可复现的随机实例 | `seeds.py`（`SeedSequence` 派生命名流）、`element.py`（抽了再置零） | `tests/test_seeds.py`、`tests/test_element.py`、`tests/test_sim_dpd.py::test_run_matrix_and_switch_independence` |
| 6 | 数值指纹 | `tools/fingerprint.py` | `tests/test_fingerprint.py` |

## 设计决定

- **互耦观测口**：每单元 DPD 默认观测自己的 PA 前向输出（`per_element_observe: pa_output`），因为前向定向耦合器看不到从天线口返回的耦合波；
  `antenna_port` 作为可选项保留。里程碑 1 互耦是线性泄漏，负载调制等上游 PA 有负载依赖（ROADMAP A2）。
- **工作点固定**：DPD 会扩展峰值，polar_tx 链路默认按峰值重新归一化包络；本库先跑一次参考得到 `fs_scale`，之后一律 `fs_scale_fixed`。
- **共用 LO**：所有单元同一个 `lo_pn_seed`（DTC 相位调制器的独立 LO 流），抖动仍按单元独立；时钟剖面经适配器注入 PSD，不改 polar_tx。
  剖面的离散杂散走不了 PSD（polar_tx 按 PSD 抽随机幅度，杂散是已知幅度的正弦），改为链输出乘 exp(jφ_spur(t))：polar_tx 把 LO 相位加在
  DPA 的相位输入上、DPA 的 AM-AM / AM-PM 只看幅度码，二者是同一信号（`tests/test_lo_profiles.py::test_spur_rotation_of_the_output_equals_an_lo_phase_added_at_the_drive`）。
  起始相位来自 `lo_spurs` 流（共用 LO 时全阵一个抽取；新流只追加在元组末尾，既有流逐位不动）。
- **面阵 = 一行的推广，逐位相同**：`ArrayGeometry` 的单元序 row-major，`delays_s` 在 n_y = 1、φ = 0 时走原来的 `x·sinθ/c0` 表达式；
  互耦的邻域类在一行上只出现 x1 / x2；`tests/test_planar.py` 钉住一列在 y-z 面 = 一行在 x-z 面、第一行块 = 4 单元矩阵。
- **互耦矩阵必须无源**：`build_coupling` 算泄漏矩阵（零对角）的最大奇异值，> 1 抛错。里程碑 1 把所有邻居放在同一相位，一行上碰巧无源（0.33），
  8 × 8 上 1.13——远邻相位现在按电长度（`phase_from_distance`），默认开。这是物理修正，指纹 81/168 项随之变，见 CHANGELOG 2026-11-03。
- **负载调制不改 vendor**：`loadpull.LoadPulledDPA` 继承 polar_tx 的 `DPA`，`chain.py` 照常调 `dpa(code, phase)`；无负载时走原表逐位相同
  （`tests/test_loadpull.py`）。Γ_k 来自 `apply_coupling` 的泄漏（铁律 3 同一条路径），`radiate` 做定点迭代；开关关、S=0、理想 PA 时整条路径逐位不变。
- **`apply_coupling` 的累加顺序**：只对非零 S_kj 对累加，实部虚部分开累加以复现 numpy 复数 einsum 的位序；
  `tests/test_coupling.py::test_pair_sparse_leak_equals_the_dense_einsum_bit_for_bit` 钉住，换成"复数乘再加"会差 1e-15 而不再逐位相同。
- **逐位相同的边界**：S 恰为全零时 `apply_coupling` 原样返回；单元误差开关关闭时增益 ×1.0、相位 ×(1+0j)、时延 0 跳过分数延时——这三条是"1 单元 = polar_tx 逐位相同"成立的前提。

## 被推翻的预期（里程碑 1）

- **斜视不进波束方向 EVM——只在 n=4 成立**：4 单元 λ/2 在 60° 的带边斜视是 0.7°（与解析式一致），但相移与真延时导向的波束 EVM 只差 0.0002 dB。
  阵列以相位中心为原点，带边各单元的相位误差 ±0.03 rad 对称抵消，只剩二阶幅度损失
  （`tests/test_sim_dpd.py::test_squint_is_a_pointing_effect_not_a_beam_evm_effect`）。
  2026-11-02 更正（ex06）：这个二阶损失 ∝ n²，波束方向看到的是线性频响 H(f) = (1/n) Σ_k exp(j2πf τ_k)（`beam.beam_response`）；
  scalar 均衡下它在 60° 从 n=64 起可测（+0.53 dB）、n=128 达 +4.89 dB，闭式 `squint_evm_closed_form_db` 预测到 0.03 dB（2026-11-04 复核，原写 0.01）；
  per-tone 均衡全部抹平（`tests/test_scaling.py`）。
- **线性泄漏不伤每单元 DPD**：DPA 对输入相位旋转协变，单波束下各单元只差一个复权重，泄漏是各单元非线性函数的线性组合；
  每单元 DPD 把各自输出线性化后，波束方向的 ACLR 与互耦无关。数字见 `cairn/LOG.md` 里程碑 1 条目。
- **方向图零点里的 ACLR**：零点方向主载波被抵消而邻道失真没有，ACLR 可到 −20 dBc；这是真实的但不是任何人发射的方向，
  ex04 把零点涂灰并只在方向图 ≥ −15 dB 的方向上报"最差方向"。
