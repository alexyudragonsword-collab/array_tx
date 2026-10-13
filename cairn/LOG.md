# Project Cairn 日志

本文件按时间倒序记录实质进展——新条目在顶。每条只写摘要与指针（数字写原值）；结论沉淀到 `cairn/<topic>.md`。

## 2026-10-13 · 四处修正回馈 polar_tx 并换 pin 到 008cc90：指纹 168 项逐位相同，B1 了结、B3 更新

- 上游（polar_tx `claude/digital-polar-tx-dev-r0c338`，4 个提交 3bdb092…008cc90，其测试 307 项全绿）：
  NR 数字表补 120 kHz 的 50 / 400 MHz 行；`nr_dtc` 的 `fs_bb` 从 `bw·os` 改为波形真实速率（FR1 100 MHz：400 → 491.52 MS/s）并在建预设时拒绝表外组合；
  `CartesianTX` 读 `fs_scale_fixed`（钉到自身峰值时逐位同默认）；DTC 与 RF-DAC 的抖动在 σ=0 时照抽，关抖动不再换 LO 实例（抖动 > 0 的既有结果逐位不变）。
- 本库：vendor 树整体换到 008cc90（36 个 polar_tx 文件新头，嵌套的 padpd / pllsim 副本不动，`--strict` 无漂移）；FR2 波形改用 polar_tx 的
  `nr_waveform(400e6, 120e3)`，`standards.py` 不再自己拼 `GenOFDMConfig`，并校验表与出处数字一致；rfdac 满刻度钉住、DPD 不再拒绝。
- 指纹：`fingerprint.py record` 换 pin 前后 168 项 0 差异——`nr_waveform` 与手拼配置逐位同一波形，所有链路输出不变。
- ROADMAP：B1（polar_tx 内部随机流）了结——抖动/LO 这一对已修，`montecarlo.py` 的位置抽取与本库无关不动；B3 改为"rfdac DPD 能跑但无压缩可校"。
- pin 在 polar_tx 的开发分支上、尚未进其 main；CI 用全 SHA + fetch-depth 0 取，分支名变动不影响（polar_tx 对 PA_DPD 的 44cbcb3 走过同一条路）。
- 测试 88 项。

## 2026-10-13 · 共用 LO 接真实时钟剖面：28 GHz 上 64-QAM 对 LO 的要求，EVM 跟带内相噪、ACLR 跟远端底

- 数据：pll_simulator@00e48a2 用自己的 `export --clock-profile` 导出全部 18 个预设，随包提供（`bundled:<preset>`），按 (28 GHz / f0)² 换算。
- 扫 8 个剖面 + polar_tx FR2 预设 LO，30° 波束、survey 互耦、8 符号（rms 相位 = 带内 100 Hz..200 MHz，环路带宽 400 kHz 以下压平；dB / dBc）：
  dartizio23 ADPLL-BB 9.25 GHz：10.9 mrad，EVM −29.85 / DPD 后 −35.20，ACLR1 −36.9 / −41.9；
  adpll_100m_10g：23.4 mrad，−28.52 / −31.75，ACLR −35.0 / −37.6；ilcm_250m_12g：24.2 mrad，−27.94 / −30.65，ACLR −30.9 / −31.8；
  sspll_19p2m_4p8g：25.7 mrad，−28.21 / −31.08，ACLR −37.8 / −45.4；markulic16：29.7 mrad，−27.61 / −30.00；cppll_frac：32.0 mrad，−27.31 / −29.47；
  adpll_bb_100m_10g：36.2 mrad，−26.73 / −28.65，ACLR −29.2 / −29.8；spll_100m_8g：36.3 mrad，−26.71 / −28.53；polar_tx 预设：39.6 mrad，−26.41 / −28.09。
- 结论：(1) 九个 LO 全部满足 64-QAM 8 %（−21.9 dB）且余量 ≥ 4.5 dB；最干净的（dartizio23）DPD 后到 −35.2 dB。
  (2) EVM 只认带内积分：按 100 Hz..fs/2 积分时 ilcm 排最差却不是最差 EVM，改为 100 Hz..BW/2 后 9 个点拟合残差 0.25 dB。
  (3) ACLR 认 300 MHz 处的 L(f)：ilcm −118、adpll_bb −112 dBc/Hz 对应 ACLR1 −31 / −29 dBc，DPD 对它们无能为力（−31.8 / −29.8）；
  其余剖面远端 −134…−141 dBc/Hz，ACLR 回到 DPD 残余的 −45。
  (4) 斜率：无 DPD 0.31（PA 主导），DPD 后 0.64——仍不到 1，说明 DPD 残余 + 数据通路底在最干净端还占一部分。
- 缺口：9 个剖面带离散 `spurs` 条目（参考杂散），`ClockProfileLO.psd` 只用 L(f) 曲线，没注入这些杂散（ROADMAP B6）。
- 测试 88 项。耗时 ex05 全尺寸 22.6 s。

## 2026-10-13 · FR2 链的底在哪：EVM 由 LO 相噪与抖动定，ACLR 由 DPD 残余与噪声底合成

- 分解（FR2 survey 配置、单元误差关、30° 波束、8 符号，OTA 波束方向；EVM dB / ACLR1 dBc / ACLR2 dBc）：
  理想 PA + 噪声关（只剩 DTC 量化、DPA 量化、CFR）：−40.34 / −64.53 / −61.80；
  理想 PA + 噪声开（50 fs 抖动 + 28 GHz LO −100 dBc/Hz@1 MHz）：−28.35 / −50.66 / −50.72；
  Rapp PA 无 DPD 噪声关：−30.07 / −37.65 / −60.21；Rapp PA + 全阵列 DPD 噪声关：−36.91 / −46.15 / −51.01；
  Rapp PA + 全阵列 DPD 噪声开：−28.05 / −44.85 / −48.00；每单元 DPD 噪声开：−28.05 / −44.88 / −48.12。
- 结论：(1) EVM −28 dB 全部来自 LO 相噪与抖动，PA 和 DPD 对它几乎没影响（理想 PA 也是 −28.35）；离 64-QAM 的 8 %（−22 dB）有 6 dB 余量，
  但这是 polar_tx FR2 预设的 LO 假设，换时钟剖面（`element.lo.clock_profile`）会直接改这个数。
  (2) ACLR1 平台 −44.9 = DPD 残余 −46.2 与噪声底 −50.7 的功率和（−44.9，对上）。再压 ACLR 要同时动 DPD 残余（ILA 轮数 / DPA DNL）和 LO。
  (3) 噪声关时 DPD 把 EVM 从 −30.1 拉到 −36.9：DPD 本身是有效的，只是被 LO 盖住。
- 未改代码；这条是读数，供 ex03 表格解释用。

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
