# Project Cairn 日志

本文件按时间倒序记录实质进展——新条目在顶。每条只写摘要与指针（数字写原值）；结论沉淀到 `cairn/<topic>.md`。

## 2026-11-03 · 里程碑 2a：矩形面阵接进全部路径；发现并修正互耦远邻相位假设（8 × 8 上不无源），加无源性检查

- 几何：`ArrayGeometry(n_x, n_y, dx, dy, f0, pattern, plane_phi_deg)`，row-major；一行 + φ=0 走原表达式逐位相同，一列在 y-z 面 = 一行在 x-z 面
  逐位相同（测试）；切面是几何的属性，beam / dpd / sim 的函数签名一个都没改。加一行不动第一行的抽取与 run seed（spawn 按索引）。
- **被推翻的假设**：里程碑 1 的 analytic / survey 把所有邻居放在 c1 的相位（180°）。一行上泄漏矩阵最大奇异值 0.33，无事；8 × 8 每个内部单元
  12 个邻居同相相加，泄漏增益 1.13 > 1，广播向波束几乎抵消（EVM −5.9 dB）——这是假设错，不是面阵物理。修正：远邻相位 = c1 相位 +
  超出一个间距的自由空间电长度（λ/2 间距 x2 +180°、对角 +74.5°），与 `path_delay_from_spacing` 的纯延时一致；`phase_from_distance` 默认开。
  修正后 8 × 8 泄漏增益 0.82、广播 EVM −25.8；`build_coupling` 对最大奇异值 > 1 抛错。
- 指纹（修正前后）：168 项中 81 项变，全部在 analytic / survey 互耦矩阵及其下游（含阵列 DPD 方案的导通输出，因为它在耦合后的远场上训练）；
  锚点、单元抽取、seed、none 方案导通输出不变。4 单元 survey 波束指标移动 ≤ 0.05 dB：30° none ACLR1 −37.313 → −37.310、
  array −43.743 → −43.702、EVM −27.975 → −27.970；60° TTD none ACLR1 −37.267 → −37.337。里程碑 1 LOG 里的 0.1 dB 级数字不受影响。
- ex08 全尺寸（survey、单元误差开、8 符号、无 DPD；EVM dB / ACLR1 dBc / 3 dB 波束宽°）：
  64 × 1：0° −26.26 / −37.4 / 1.58；30° 相移 −26.15 / −37.8 / 1.83，真延时 −26.21 / −37.4；60° 相移 −25.68 / −38.7 / 3.17，真延时 −26.22 / −37.4。
  8 × 8 φ=0：0° −26.17 / −37.2 / 12.79；30° 相移 −26.19，真延时 −26.15 / 14.83；60° 相移 −26.19，真延时 −26.18 / 28.82。
  8 × 8 φ=90：0° −26.17 / −37.2、30° −26.19（与 φ=0 一致到 0.01 dB，方阵两主面对称）。
  相移 − 真延时在 60°：64 × 1 +0.54 dB（ex06 的数字），8 × 8 两个切面 −0.01 dB——同样 64 个单元，面阵每个切面只有 8 个单元宽，斜视的 EVM 代价消失。
  8 × 8 φ=45（对角切面）：0° −26.17 / 13.04；30° 相移 −25.99，真延时 −25.95 / 15.11；60° 相移 −26.24，真延时 −26.20 / 29.59；代价 −0.04 dB。
  每次 run 11–18 s，全程 416.7 s（示例曾两次 OOM：每个 64 单元 ArrayResult 约 0.5 GB，现只留数字）。
- ex08 Part 2（8 × 8、30° 波束、阵列 DPD）：波束 ACLR1 φ=0 / 45 / 90 = −45.2 / −45.1 / −45.2 dBc；方向图 ≥ −15 dB 内最差方向 +73° / +47° / +72°，
  −41.9 / −42.5 / −41.7 dBc——DPD 只在训练方向最优，离开波束 3 dB 量级的残余往旁瓣走，三切面一致。Part 3：8 × 8 survey 矩阵 612 / 4032 非零对，
  x1 −16 dB @180°、x2 −22 @0°、y1 −16 @180°、d1 −22 @−105.4°（= 180° + 74.5° 电长度）、y2 −22 @0°。
- 配置 `configs/fr2_8x8_survey.yaml`；ROADMAP B7 记面阵互耦仍是邻域类 + assumed。测试 128 项。

## 2026-11-03 · 页面上的扫描研究（任一控件 × 取值列表）与历史持久化

- `sweep_report`：ex05 / ex06 / ex07 的通用形式。每点经 `values_to_config` 只改一个叶子再建 ArraySim，所以 n=4 这一点与普通运行逐位同数
  （测试），既有单元的抽取不动（铁律 5）。宿主对每个点先建配置再排队，坏点整个研究不跑。
- 页面：顶部"扫描研究"栏（控件下拉 + 取值列表 + 图上指标），结果进同一张表 / 历史 / 可复现卡；研究图数值轴跨 ≥ 20 倍自动 log2。
  冒烟下 n = 4 / 16 / 64 三点 60° 研究从页面发起、边跑边画，刷新后 ↺ 恢复。
- 没做：按第二个控件分组的双线图（相移 vs 真延时）——用基线叠加代替；双语。测试 122 项。

## 2026-11-02 · 工作台 GUI 落地：一份单页 + 标准库宿主 + 子进程队列；方向扫描改分段 Welch 后报告 10.9 s → 0.8 s

- 决策：四张效果图（Fable / Opus × PySide6 / web）用户审阅后定"以 Fable 的 web 方案为主，加 Opus 做得好的地方"。理由同 polar_tx 10-29
  退役 Qt：一份页面三个宿主、长运行天然进程队列、不依赖 PySide6 版本。采纳 Opus 的：扫描角 × DPD 表为主视图（点行驱动图）、
  可复现卡、全宽引擎横条、模板标"stylized 非一致性条款"、手机底部导航。效果图与生成脚本在会话 scratchpad，不进仓库。
- 分层：`guispec`（描述）/ `guiutil`（计算）/ `webhost`（宿主）/ `webui/www`（画）。铁律 1 的 GUI 形态：52 个控件 = `form_fields()`
  的 52 个可见叶子（2 个隐藏：schema 版本、冒烟符号数），默认值从 `default_config()` 读，默认表单建出的配置与默认配置逐叶相同（测试）。
- 性能：报告里"ACLR 随方向"原来逐方向合成远场再 Welch，全尺寸 10.9 s / 份；改为单元信号 Welch 分段按方向相干合成（Welch 对信号线性），
  ACLR 与精确路径差 < 1e-4 dB、方向图差 ≤ 0.01 dB，0.8 s / 份；128 单元走无重叠分段控制内存（< 640 MB）。精确路径仍是 ex04 的参考。
- 实测（冒烟 2 符号、1 个工作进程）：3×3 扫描 23.8 s 流式进表；页面在 Chromium 1440×900 与 390×844 下都通过 Playwright 测试。
- 宿主安全边界：只绑 127.0.0.1，POST 要自定义头（跨站页面发不出），`/api/save` 与 `/api/config/load` 能读写本机文件——这是桌面工具的
  设计，不是服务；不要绑到 0.0.0.0。
- 测试 119 项（+5 guispec、+6 guiutil、+8 webhost、+3 webui）；CI 新任务 test-gui（playwright chromium）。
- 没做（ROADMAP C1）：Android 壳、页面上的 LO / 单元数 / 杂散扫描、双语、历史持久化。

## 2026-11-02 · B6 了结：小数 PLL 的分数杂散换算到 28 GHz 后在 −37…−43 dBc，EVM 多 0.3–0.8 dB；参考杂散看不见；ACLR 纹丝不动

- 设置：ex07，FR2 survey 互耦、4 单元、30° 波束、8 符号；18 个随包剖面里 9 个带 `spurs:`，按 f_c/f0 换算（+8.7…+21.0 dB）。
- 换算后最响的四个（都是 frac-N 预设的分数杂散，频偏 < SCS 或 ≈ 10 MHz）：sspll_frac 23.0 kHz −36.6 dBc（29.5 mrad 峰）、
  spll_frac 62.4 kHz −38.5（23.7 mrad）、markulic16 frac 48 kHz −43.3（13.7 mrad）、wu19 frac 62.4 kHz −52.6（4.7 mrad）；
  rms 杂散相位 23.4 / 16.8 / 10.3 / 3.3 mrad。其余五个剖面（参考杂散，≥ 600 kHz）都在 −83 dBc 以下、≤ 0.17 mrad。
- EVM 关 → 开（无 DPD；dB）：sspll_frac −25.01 → −24.64（+0.37，小角度估计 +0.69）、spll_frac −26.63 → −26.09（+0.54 / +0.53）、
  markulic frac −26.78 → −26.54（+0.25 / +0.21）、wu19 −29.65 → −29.59（+0.05 / +0.04）、其余 0.00。阵列 DPD 后：+0.49（0.88）、+0.75（0.77）、
  +0.35（0.33）、+0.13（0.14）——DPD 对 LO 杂散无能为力，底越低杂散占比越大。估计 = 20·log10(rms 相位) 按功率相加，9 个剖面 rms 误差
  0.11 / 0.13 dB；唯一偏差是 sspll_frac：23 kHz 在 67 µs 突发里只有 1.5 个周期，突发内 rms 取决于起始相位，不是公式错。
- ACLR1 全部不变（≤ 0.01 dB）：杂散频偏 ≤ 13 MHz ≪ 400 MHz 信道，搬到邻道的只有带边一小条，且在 −37 dBc 以下。
- ex05 的数字不动：它扫的剖面里带杂散的三个（adpll_bb、cppll_frac、dartizio23）杂散 ≤ −83 dBc，EVM 变化 ≤ 0.01 dB。
- 实现：输出乘 exp(jφ)，与"相位加在驱动上"差 < −40 dB（DTC 重量化）；`lo_spurs` 流追加在末尾，既有流不动，指纹 168 项逐位相同；
  `spurs: false` 与去掉 `spurs:` 的剖面逐位相同（测试）。ex07 全尺寸 45.0 s。测试 97 项。
- 结论：64-QAM 8 % 的目标下杂散无关紧要；若追 −35 dB 这一档（dartizio23 + DPD），frac-N 预设的分数杂散（−37…−43 dBc）就是 0.5 dB 量级的项，
  而且 DPD 和 per-tone 均衡都消不掉它。

## 2026-11-02 · ex06：斜视在 n ≈ 64 起进波束 EVM，128 单元 60° 相移比真延时差 4.9 dB，闭式预测到 0.01 dB，per-tone 均衡全部抹平

- 设置：FR2 survey 互耦、单元误差开、8 符号、无 DPD；n ∈ {4, 8, 16, 32, 64, 128} × 0/30/60° × 相移 / 真延时；EVM 为波束方向 OTA，dB。
- 相移减真延时的 EVM 代价（实测 / 闭式）：60°：n=4 0.00、16 0.00、32 +0.03 / +0.03、64 +0.54 / +0.53、128 +4.94 / +4.95；
  30°：64 +0.07 / +0.06、128 +0.91 / +0.90。真延时的底与 n 无关（−26.3 ± 0.1，单元误差被平均，LO 主导）。
- 闭式 = 波束方向的线性频响 H(f) = (1/n) Σ_k exp(j2πf τ_k) 在激活子载波上对 scalar 均衡的残差（`beam.squint_evm_closed_form_db`）；
  单独的斜视 EVM 在 60°：n=4 −83.9、16 −59.3、32 −47.3、64 −35.2、128 −23.0、256 −10.5；30° 低 11 dB；n 翻倍 +12 dB（二阶幅度跌落 ∝ n²）。
  越过真延时底（−26.3）的 n：60° 从 128 起，30° 从 256 起。3 dB 波束宽 60°：n=4 50.3°、64 3.17°、128 1.58°；带边斜视 0.70° 与 n 无关，
  比值 0.22（64）/ 0.44（128）。
- per-tone 均衡：128 单元 60° 相移阵读 −26.86，真延时 −26.87——斜视是逐子载波的线性响应，接收端均衡能全消；per-tone 比 scalar 在每个 n 都
  还多抹掉 0.7–1.0 dB（单元增益 / 相位 / 时延误差 + 互耦造成的非平坦线性响应）。验收口径（`metrics.evm_equalize: scalar`）下斜视才算代价。
- 纠正里程碑 1 的陈述："斜视是指向效应不是 EVM 效应"只对 n=4 成立；它是 n 和扫描角的函数（`cairn/architecture-invariants.md` 已改）。
- 工程：`apply_coupling` 的 (N, n, n) 稠密矩阵在 64 单元 8 符号要 9 GB，改按非零对累加（实虚分开累加复现 einsum 位序），指纹 168 项
  逐位相同，64 单元冒烟 15.2 s → 2.3 s；128 单元全尺寸一次 run 21 s，ex06 全程 220.8 s。
- 测试 93 项（+3 ex06、+1 稀疏路径逐位守护、+1 示例冒烟）。

## 2026-11-02 · 体检：两库全绿，ROADMAP 丢了 B6（补回），上游走了 14 个提交但 vendored 物理零变化，pin 不动

- array_tx `ccr-411c6423-uxcjms` @ 917f25d：ruff 过、88 项测试 60 s 全过（本地 Python 3.13 / numpy 2.5.3，CI 矩阵 3.10–3.12）、
  ex00–ex05 冒烟各 2–8 s 退出 0、`vendor_check --strict` 49 文件无漂移、指纹对 10-13 换 pin 后的记录 168 项 0 差异。
- 记录缺陷：换 pin 提交 e8a622a 删 B1 时把 B6（时钟剖面杂散未注入）一并删了，LOG / CHANGELOG 仍引用它，工作没做——已补回并注明。
- 上游核对：polar_tx main 5d84ed0 → 9a7ab05（7 提交，GUI P0–P4b，Streamlit / Qt 前端退役，换单页 web GUI；vendored 范围内只有
  `outphasing.py` 在 `env_skew_s ≠ 0` 时加一条 UserWarning，本库不设该字段）；PA_DPD 08b9725 → 6241112（7 提交全是 GUI，`src/` 零改动）；
  pll_simulator 仍在 00e48a2。三个 pin 都不动：数字不会变，换 pin 只换头部。上次为 polar_tx 钉的 PySide6 < 6.12 随 Qt 退役失效，不再相关。
- polar_tx 本地：PR #9 已合并（5d84ed0），开发分支 `claude/digital-polar-tx-dev-r0c338` 落后 main 7 个提交；再回馈上游前先重置到 main。
- 宽规则 ruff（E,W,F,B,UP）284 条：264 条行长、6 条 `zip` 无 `strict`，无功能问题，不动。
- 下一步（已选）：ex06 单元数扩展（斜视何时进 EVM）、B6 杂散注入。

## 2026-10-13 · 四处修正回馈 polar_tx 并换 pin 到 008cc90：指纹 168 项逐位相同，B1 了结、B3 更新

- 上游（polar_tx `claude/digital-polar-tx-dev-r0c338`，4 个提交 3bdb092…008cc90，其测试 307 项全绿）：
  NR 数字表补 120 kHz 的 50 / 400 MHz 行；`nr_dtc` 的 `fs_bb` 从 `bw·os` 改为波形真实速率（FR1 100 MHz：400 → 491.52 MS/s）并在建预设时拒绝表外组合；
  `CartesianTX` 读 `fs_scale_fixed`（钉到自身峰值时逐位同默认）；DTC 与 RF-DAC 的抖动在 σ=0 时照抽，关抖动不再换 LO 实例（抖动 > 0 的既有结果逐位不变）。
- 本库：vendor 树整体换到 008cc90（36 个 polar_tx 文件新头，嵌套的 padpd / pllsim 副本不动，`--strict` 无漂移）；FR2 波形改用 polar_tx 的
  `nr_waveform(400e6, 120e3)`，`standards.py` 不再自己拼 `GenOFDMConfig`，并校验表与出处数字一致；rfdac 满刻度钉住、DPD 不再拒绝。
- 指纹：`fingerprint.py record` 换 pin 前后 168 项 0 差异——`nr_waveform` 与手拼配置逐位同一波形，所有链路输出不变。
- ROADMAP：B1（polar_tx 内部随机流）了结——抖动/LO 这一对已修，`montecarlo.py` 的位置抽取与本库无关不动；B3 改为"rfdac DPD 能跑但无压缩可校"。
- pin 在 polar_tx 的开发分支上、尚未进其 main；CI 用全 SHA + fetch-depth 0 取，分支名变动不影响（polar_tx 对 PA_DPD 的 44cbcb3 走过同一条路）。
- 上游 CI 补记：008cc90 推上去后 polar_tx 只有 `test-gui` 红，两次都是 Streamlit AppTest 里的 Bus error；逐项比对安装清单，唯一差异是
  PySide6 6.11.2 → 6.12.0，本地用 6.12.0 在未动的 main 上同样崩、6.11.2 两边都过。polar_tx 又加一提交 0ff8ea8（`guiqt` 钉 `<6.12`，
  不碰本库 vendor 的任何文件），其 CI 第 110 次 12 个任务全绿。本库 pin 保持 008cc90，不需要动。
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
