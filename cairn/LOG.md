# Project Cairn 日志

本文件按时间倒序记录实质进展——新条目在顶。每条只写摘要与指针（数字写原值）；结论沉淀到 `cairn/<topic>.md`。

## 2026-10-13 · 评审修正：10 条发现，5 条真缺陷，survey 块的出处规则与 AGENTS 对齐

- 真缺陷：`_f()` 的列表默认值被所有配置实例共享（改一个 `scan_deg` 会漏进之后的 `default_config()`）；`metrics.evm_equalize` 接到对
  无导频波形无效的 `track_cpe` 上（改为 polar_tx `PolarResult.evm` 同款 `evm_of_signal(equalize=)`，per_tone 现在真的不同）；
  rfdac 拓扑丢掉整个 `element.pa` 块和每单元失配种子（四个单元同一张 seed-0 阵列，违反铁律 1/5；现按 config 建 `RFDACConfig`、每单元自己的种子）；
  `np.trapezoid` 在 numpy 1.x 不存在（polar_tx CI 踩过反向的坑，改 `getattr` 回退 `trapz`）；Touchstone v1 的 2 端口块是列序 S11 S21 S12 S22，读写都按行序会把 S21/S12 读反。
- 规则修正：原校验强迫 `coupling.survey` 块里每个数都标 survey，和 AGENTS"没有出处就标 assumed，不许冒充 survey"矛盾。
  现在的规则：该块每个数必须写明来历（survey 带引文，assumed / derived 带原因），裸标量不许进。`c1_deg_at_f0` 与 `c2_rel_db` 改标 assumed。
- 其余：`beam.sidelobe` 接受数字并校验、`scan_deg` 非空且在 (−90, 90)；antenna_port 观测的每单元训练从 O(n²) 链路运行降到 O(n)；
  ex01 不再自带第二份几何与 fs；banner 不再为打印引擎名多跑一次链路（`ElementChain.engine` 直接给出 `dtc_openloop`）。
- 里程碑数字不受影响（默认 polar 拓扑、scalar EVM、4 端口 touchstone 都不走改动的分支）。
- B3 顺手了结一半：outphasing / rfdac 在 FR2 建链并有测试；rfdac 选 DPD 直接拒绝（满刻度钉不住）；outphasing 的 DPD 可跑但无用
  （−44.70 → −44.62 dBc），原因写在 ROADMAP B3。测试 82 项。

## 2026-10-13 · GMP 默认值改为无记忆 7 阶：ACLR2 的损失来自记忆抽头，不是阶数（ROADMAP B5 了结）

- 扫描：order ∈ {3,5,7,9} × memory_depth ∈ {1,3,5} × 滞后交叉项开/关，全阵列 DPD、30° 波束、survey 互耦、8 符号。
- 无 DPD：ACLR1 −37.76 / ACLR2 −50.56 / EVM −26.41。旧默认 5 阶 / 3 抽头 / 17 系数：−44.96 / −47.51 / −28.07。
- 记忆抽头只伤 ACLR2：9 阶 1 抽头 −48.29，3 抽头 −45.03，5 抽头 −44.78，ACLR1 不升反降（−45.39 → −44.87）。
  原因：单元链是 DPA + DTC，没挂实测记忆模型，几乎无记忆；多余抽头在拟合噪声和再生。交叉项在 1 抽头时 ±0.05 dB，无用。
- 阶数：无记忆 3/5/7/9 阶 ACLR1 −44.77 / −45.14 / −45.36 / −45.39，ACLR2 −49.03 / −48.01 / −48.15 / −48.29。7 阶与 9 阶已到平台。
- 决定：默认 `dpd.gmp` 改为 order 7 / memory_depth 1 / 无交叉项（7 系数，原 17）；四个 config 与数据类默认同步改。
- 新默认下里程碑数字重跑（survey −16 dB，相移导向，波束方向 OTA ACLR1 无 / 每单元 / 全阵列，dBc）：
  0° −37.8 / −45.5 / −45.5；30° −37.8 / −45.5 / −45.4；60° −37.7 / −45.4 / −45.3。全阵列追回 7.6–7.7 dB，与每单元差 +0.07…+0.12 dB。
  ACLR2 −50.6 → −48.1…−48.5（旧默认 −47.5）。旁瓣：0°(+47.1°) −35.7/−38.7/−38.4，30°(−13.4°) −38.0/−42.4/−41.8，60°(+7.7°) −38.1/−42.3/−41.4。
  analytic vs survey ≤ 0.01 dB；S=0 时两种 DPD 差 0.09 dB；互耦 0 → −10 dB 三方案只动 0.02–0.04 dB。下面里程碑 1 条目里的数字是旧默认的，结论不变。
- 旁观：DPD 后 ACLR1 平台 ≈ −45 dBc，而 FR2 链在理想 PA 下无 DPD 就是 −47 dBc 量级——DPD 已逼近 DTC 量化 / 抖动 / LO 相噪的底，
  再加阶数或抽头无益；要再往下要动 DTC 位数或 LO。

## 2026-10-13 · 里程碑 1 完成：4 单元 FR2 线阵、三种互耦、三种 DPD、OTA 指标（ccr-411c6423-uxcjms）

> 本条数字是旧默认 GMP（5 阶 / 3 抽头 / 17 系数）下的；同日改为无记忆 7 阶后重跑的数字见上一条，结论不变。

- 验收逐条（全尺寸 8 符号，fs 1.96608 GS/s；`tests/` 74 项、`tools/vendor_check.py --strict` 86 文件无漂移）：
  (1) sub-6 / S=0 / 1 单元与 polar_tx `nr_dtc().run()` 逐位相同：True，EVM −39.91 dB 两边一致（ex00）。
  (2) 互耦→0 时每单元 vs 全阵列 DPD 的 OTA ACLR1 差 0.03 dB（< 0.5，ex02）。
  (4) 带边斜视：30° 实测 ±0.24/−0.23°、60° ±0.72/−0.70°，与 asin(sinθ0·f0/(f0+Δf)) 误差 0.00 %（ex03）。
  (5) analytic→.s4p→touchstone：矩阵与三方案远场全部逐位相同（ex01）。(6) 所有 config 数字带 source，survey 块无 ref 不加载。
- **核心数字（波束方向 OTA ACLR1，survey 互耦 −16 dB，相移导向）**：0°/30°/60° 无 DPD −37.8/−37.8/−37.7 dBc；
  每单元 −45.1/−45.0/−45.0；全阵列 −45.1/−45.0/−45.0。全阵列 DPD 追回 7.2–7.3 dB；与每单元差 +0.01…+0.03 dB。
  EVM：无 DPD −26.3…−26.4 dB，两种 DPD −28.0…−28.1 dB。旁瓣方向（30° 波束的 −13.4°）：无 DPD −38.0、每单元 −42.4、全阵列 −41.4 dBc。
- **analytic 与 survey 之差**：三方案在波束方向 ≤ 0.01 dB（ex01），远低于 2 dB 阈值——结论对耦合值不敏感，但原因是下一条，不是模型稳健。
- **被推翻的判断 1**："互耦打开后每单元 DPD 比互耦为零时差"不成立：相邻耦合从 0 扫到 −10 dB，三方案 ACLR1 只动 0.02–0.08 dB（ex02）。
  线性泄漏 + 相位协变的 DPA ⇒ 泄漏是各单元非线性的线性组合，每单元线性化后波束方向不受影响（详见 `architecture-invariants.md`）。
  要分开两种 DPD 需要负载依赖的 PA（ROADMAP A2 / B4）。全阵列 DPD 只在旁瓣方向比每单元差约 1 dB（ex03/ex04），这是互耦与 PA 偏差共同的印记。
- **被推翻的判断 2**：斜视不进波束 EVM——60° 相移 vs 真延时 EVM 差 0.0002 dB（见 invariants 笔记），斜视是指向效应。
- 发现：5 阶 GMP 把 ACLR2 从 −50.6 推到 −47.5 dBc（ROADMAP B5）；方向图零点里 ACLR 可到 −14 dBc（ex04 涂灰）。
- 耗时（本机）：ex00 2.0 s、ex01 18.6 s、ex02 31.2 s、ex03 21.6 s、ex04 51.4 s；单次 `sim.run` 无 DPD 0.6–0.8 s，带 DPD 1.6–2.3 s。
- 下一步：A1 拿实测 .sNp 切 touchstone；A2 等负载依赖的 PA；B5 扫 GMP 阶数 vs ACLR2；C1 表单接前端。

## 2026-10-13 · Project Cairn 初始化（ccr-411c6423-uxcjms）

- 新库 array_tx 建骨架：AGENTS.md（六条铁律）、ROADMAP（只写没做的）、CHANGELOG、`.cairn/config.yaml`（track / zh / provider none）。
- 上游 pin 核对：polar_tx `8a10480584e61af62c432f3fc2848745167056a3`、PA_DPD `08b9725595748b290c76d1b70355f7e6014a709e`、
  pll_simulator `00e48a2f6f7c11c0b6f106234f1490493d43e082`；三库均公开。
- 设计前读到的、推翻 prompt 假设的事实：polar_tx 三拓扑不是经 `PhaseModulator` 切换，而是三个同签名 TX 类；
  polar_tx 钉的 pllsim（931cfaf）不含 `export/clock_profile.py`，该文件须从 pll_simulator@00e48a2 单独 vendor；
  PA_DPD 和 polar_tx 的 ROADMAP 都没有 load-pull 条目（prompt 说"未动的项"，实际是没有这一项）。
- 历史迁移模式：`start_fresh`。细节见 `AGENTS.md`、`.cairn/config.yaml`、`cairn/architecture-invariants.md`。
