# array_tx 路线图

只写没做的。做完的删掉，进 CHANGELOG。

## A. 被外部阻塞

### A1. 互耦 survey 典型值等全文核对 / 等实测 S 参数
`configs/*.yaml` 里 `coupling.survey` 的相邻耦合 −16 dB 只有摘要级出处（见 config 里 `ref`），本环境网络策略打不开 arXiv / PMC 全文。
拿到实测 `.sNp` 就切 `coupling.source: touchstone`，不改任何别的抽取（铁律 5）。

### A2. 负载调制：只有一阶电压模，没有实测 load-pull 表
`element.pa.load_pull` 已实现（`cairn/load-pull-proposal.md`），κ = 1 是 assumed。真实 PA 的压缩等高线在 Smith 圆图上不是圆（Γ 相位相关），
要更真得换 source: measured 的 load-pull 表替换 `loadpull.amam_loaded` 的映射。outphasing 的合路器负载是另一个模型，没做。

## B. 已知模型缺口

### B7. 面阵的互耦只有邻域类，没有单元方向图 / 极化
8 × 8 的 x1 / x2 / y1 / y2 / d1 五类邻居加上按电长度的相位，无源性只是"不违反"（泄漏增益 0.82），不是实测；E 面 / H 面耦合差异
（`c1y_rel_db`）、对角（`c_diag_rel_db`）都是 assumed。单元方向图仍是 isotropic / cos θ，没有极化。拿到面阵 .sNp 就切 touchstone。

### B2. 事件引擎在 FR2 不可用
polar_tx ROADMAP B1：event 引擎 LTE-20 带宽已 29 % 相位推进不可用。FR2 400 MHz 只能用 response / dtc_openloop，
杂散与互调结论一律标"线性化引擎，不能背书"。

### B3. outphasing / rfdac 拓扑：能跑 FR2，DPD 能跑但没有东西可校
两者按 FR2 的载频和 LO 建链并有测试（`tests/test_element.py::test_other_topologies_run_at_fr2`）。
rfdac：polar_tx@008cc90 起 `CartesianTX` 读 `fs_scale_fixed`，满刻度钉住、DPD 能跑；但 polar_tx 的 RF-DAC 模型只有失配没有压缩，无可校之处。
outphasing：分支恒包络、DPA 在满刻度——无 DPD −44.7 dBc，DPD 后 −44.6（2 单元冒烟）。
要让这两种拓扑的 DPD 有意义，得给 RF-DAC 加压缩模型（属 polar_tx），给 outphasing 加合路器 / 分支失配的校正（不是 ILA-GMP 这类）。

## C. 工程维护

### C1. Android APK 没有真机数字
APK 在 CI 上构建过一次（2026-11-03，84.7 MB，两个 ABI），桥与页面在没有 Android 的机器上测过；真机上的首次导入时间、128 单元的内存、
线程后端下一次 run 的耗时都没有数字。页面的"打开 / 保存"在手机上只按默认路径走（prompt 被 WebChromeClient 按默认值确认），没有文件选择器。

## D. 明确不做

- 接收机、MIMO 预编码、信道模型：TX 损伤库，指标止于远场。
- 天线电磁仿真：互耦矩阵是输入。
- 替代认证测试：OTA 限值只做趋势比较。
- 载波聚合、多波束、FR2 以外的毫米波频段。
