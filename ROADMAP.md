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

### B2. 事件引擎在 FR2 不可用
polar_tx ROADMAP B1：event 引擎 LTE-20 带宽已 29 % 相位推进不可用。FR2 400 MHz 只能用 response / dtc_openloop，
杂散与互调结论一律标"线性化引擎，不能背书"。

### B3. outphasing / rfdac 拓扑：能跑 FR2，DPD 能跑但没有东西可校
两者按 FR2 的载频和 LO 建链并有测试（`tests/test_element.py::test_other_topologies_run_at_fr2`）。
rfdac：polar_tx@008cc90 起 `CartesianTX` 读 `fs_scale_fixed`，满刻度钉住、DPD 能跑；但 polar_tx 的 RF-DAC 模型只有失配没有压缩，无可校之处。
outphasing：分支恒包络、DPA 在满刻度——无 DPD −44.7 dBc，DPD 后 −44.6（2 单元冒烟）。
要让这两种拓扑的 DPD 有意义，得给 RF-DAC 加压缩模型（属 polar_tx），给 outphasing 加合路器 / 分支失配的校正（不是 ILA-GMP 这类）。

## C. 工程维护

### C1. GUI 的剩余宿主与页面
桌面 / 浏览器的单页工作台已做（`arraytx-gui`，见 README）。没做的：
- Android 宿主：页面已按 ≤ 760 px 切好底部导航，但没有 Chaquopy + WebView 的壳（照 polar_tx `android/`，`window.host` 桥替代 fetch）。
- 页面上的扫描研究：ex05（LO 剖面）、ex06（单元数 × 斜视）、ex07（杂散）只在示例里，页面只有扫描角 × DPD。
- 中英双语标签（polar_tx 的页面有 `data-zh / data-en`，这里只有中文 + 英文单位）。
- 页面历史只在内存（刷新即丢）；polar_tx 用 localStorage 记最近 8 次。

## D. 明确不做

- 接收机、MIMO 预编码、信道模型：TX 损伤库，指标止于远场。
- 天线电磁仿真：互耦矩阵是输入。
- 替代认证测试：OTA 限值只做趋势比较。
- 载波聚合、多波束、FR2 以外的毫米波频段。
