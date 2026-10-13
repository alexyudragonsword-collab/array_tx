# array_tx 路线图

只写没做的。做完的删掉，进 CHANGELOG。

## A. 被外部阻塞

### A1. 互耦 survey 典型值等全文核对 / 等实测 S 参数
`configs/*.yaml` 里 `coupling.survey` 的相邻耦合 −16 dB 只有摘要级出处（见 config 里 `ref`），本环境网络策略打不开 arXiv / PMC 全文。
拿到实测 `.sNp` 就切 `coupling.source: touchstone`，不改任何别的抽取（铁律 5）。

### A2. 负载调制下的 PA
里程碑 1 的互耦是线性泄漏（铁律 3）。PA_DPD 的 PA 模型没有负载依赖，其 ROADMAP 里也没有 load-pull 条目；
这里不自己编。等上游有了带负载依赖的 PA 再把 Γ_k = Σ_j S_kj·y_j / y_k 送进去。

## B. 已知模型缺口

### B1. polar_tx 内部随机流不独立（继承的限制）
DTC 的抖动与 LO 相噪共用一个 rng（`dtc_openloop.py`），切换抖动开关会换 LO 相噪实例。本库在阵列层用 `SeedSequence` 派生，
并且不切换 polar_tx 内部开关；polar_tx 层面的修法属于上游。

### B2. 事件引擎在 FR2 不可用
polar_tx ROADMAP B1：event 引擎 LTE-20 带宽已 29 % 相位推进不可用。FR2 400 MHz 只能用 response / dtc_openloop，
杂散与互调结论一律标"线性化引擎，不能背书"。

### B3. outphasing / rfdac 拓扑：能跑 FR2，但 DPD 方案对它们没有意义
两者已按 FR2 的载频和 LO 建链并有测试（`tests/test_element.py::test_other_topologies_run_at_fr2`）。
rfdac：`CartesianTX` 每个突发按峰值重标定满刻度、没有 `fs_scale_fixed`，DPD 会被静默抵消，所以 `dpd.scheme != none` 直接拒绝。
outphasing：a_max 已钉住，DPD 能跑，但分支恒包络、DPA 在满刻度，没有压缩可校——无 DPD −44.7 dBc，DPD 后 −44.6（2 单元冒烟）。
要让这两种拓扑的 DPD 有意义，得先给 RF-DAC 加可钉的满刻度（属 polar_tx），给 outphasing 加合路器 / 分支失配的校正（不是 ILA-GMP 这类）。

### B4. 线性泄漏下每单元 DPD 对互耦不敏感——需要负载依赖的 PA 才能分开两种 DPD
里程碑 1 实测（`cairn/LOG.md`）：互耦从 0 扫到相邻 −10 dB，三种方案在波束方向的 OTA ACLR 只动 0.02–0.04 dB；
全阵列与每单元 DPD 在波束方向差 0.07–0.12 dB，只在旁瓣方向差 0.3–0.7 dB。原因在 `cairn/architecture-invariants.md`
"被推翻的预期"。要让"每单元 DPD 比互耦为零时差"这句话有可能成立，PA 模型要先有负载依赖（A2）。

## C. 工程维护

### C1. GUI / Android 表单接入
`config.py` 的 `FORM_FIELDS` 已声明字段，三个前端照 polar_tx 的方式接；本轮不做。

## D. 明确不做

- 接收机、MIMO 预编码、信道模型：TX 损伤库，指标止于远场。
- 天线电磁仿真：互耦矩阵是输入。
- 替代认证测试：OTA 限值只做趋势比较。
- 载波聚合、多波束、FR2 以外的毫米波频段。
