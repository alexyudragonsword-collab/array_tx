# array_tx

多单元阵列发射机的行为级仿真框架。每个阵列单元是一条 vendored [polar_tx](https://github.com/alexyudragonsword-collab/polar_tx) 链路；
本库加的是阵列这一层：互耦矩阵进链路、按真实带宽算的波束斜视、阵列级 DPD，以及只在远场（OTA）方向上读的 EVM / ACLR / 谱模板。
polar_tx 的姊妹库（polar_tx ROADMAP D：GUI 里不再加架构、不做接收机）。

状态：里程碑 1 完成——4 单元 λ/2 线阵、FR2 28 GHz / 400 MHz / 120 kHz、三种互耦来源、三种 DPD 方案、OTA 指标；
里程碑 2a——矩形面阵（`array.n_rows`，row-major 单元序）、任意方位切面扫描（`beam.plane_phi_deg`）、二维互耦邻域（x1 / x2 / y1 / y2 / d1）与无源性检查。
里程碑 2b——负载调制 PA（`element.pa.load_pull`，默认关）：每单元 DPA 在自己的总端口摆幅 |1+Γ_k| 上压缩，Γ_k 由互耦泄漏算出，定点迭代两轮。
数字见 `cairn/LOG.md`，没做的见 `ROADMAP.md`。

## 快速开始

```bash
pip install -e ".[test,dev]"
python examples/ex00_single_element_equals_polartx.py   # sub-6、S=0、1 单元：与 polar_tx 逐位相同
python examples/ex03_scan_angle_x_dpd.py                # 扫描角 × DPD 方案的 OTA EVM / ACLR 表
pytest -q                                               # 156 项（页面测试无 Chromium 时跳过）
ARRAYTX_SMOKE=1 python examples/ex04_aclr_vs_direction.py   # 短突发（CI 用的尺寸）
```

每个示例先打印它用的相位调制引擎；response / dtc_openloop 引擎出的杂散与互调结论一律标"线性化引擎，不能背书"。

## 工作台（GUI）

```bash
pip install -e ".[gui-test]"            # 页面测试要 playwright；只用 GUI 不需要
arraytx-gui --config configs/fr2_4el_survey.yaml   # 本地服务 + 浏览器应用窗口（关窗口即停）；--tab 开普通标签页；--no-browser 只服务
```

一份页面（`src/arraytx/webui/www`，HTML / CSS / JS，无外部库）由标准库 HTTP 宿主（`webhost.py`）提供，桌面开成应用窗口，
手机宽度（≤ 760 px）切成底部导航，和 polar_tx 2026-10 起的做法一样。页面只画：控件表由 `form_fields()` 生成（`guispec.py`，
一个控件 = 一个 YAML 键，出处标签可点开），计算全在 `guiutil.py` → `ArraySim`，每次运行是宿主起的一个子进程（队列、进度、取消）。
主视图是扫描角 × DPD 的 OTA 结果表，点一行驱动四张图（ACLR 随方向 + 方向图、波束频谱 + stylized 模板、扫描矩阵、星座）；
指标卡带 OTA 标签与对基线的差；导通口指标折叠在"诊断"条里，名字带 `conducted_`（铁律 2）；引擎行与免责声明常驻顶部；
"可复现"卡给 seed、配置 sha256、vendored pin 和等价的两行 Python。保存 YAML 时带引文的数字写成 `{value, source, ref}`，
GUI 里改过的 survey 数字自动降为 `assumed` 并注明。
"扫描研究"栏是 ex05 / ex06 / ex07 的通用形式：任选一个控件和一个取值列表（如 `array.n_elements` × `4, 8, 16, 32, 64, 128`、
`element.lo.clock_profile` × 几个 `bundled:` 剖面、`element.lo.spurs` × `false, true`），其余不变，指标随取值的曲线边跑边画；
"按"第二个控件分组（如 `beam.steering` × `phase, ttd`）就是 ex06 的两条线。最近 12 条结果存在浏览器 localStorage 里，刷新不丢（标 ↺）。
右上角 EN / 中 切换界面语言（控件说明来自配置字段的英文元数据，不翻译）。

**Android**：同一份页面的第三个宿主。`android/` 是 Chaquopy + WebView 的壳（照 polar_tx），`MainActivity.kt` 只做一件事：把页面的请求转给
`arraytx.appbridge.call(route, json)`，它和本地服务共用 `webhost.Api` 的分发，任务跑在线程后端（取消只能在行与行之间）。APK 用
`.github/workflows/android.yml` 手动触发构建（Python 3.10 / Chaquopy 15 / AGP 8.1，版本集与 polar_tx 一致）；本仓库的测试在没有 Android 的
机器上覆盖桥的全部路由（`tests/test_appbridge.py`）、壳的文本约束（`tests/test_android.py`）和页面走桥的路径（Playwright 注入 `window.host`）。
APK 在 CI 上构建过一次（2026-11-03：175 s，84.7 MB，arm64-v8a + x86_64），真机数字还没有。

## 一次仿真的数据流

```
standard（制式）→ 波形 x → CFR（公共）→ [DPD] → 导向（相移 | 真延时）
  → 单元 k 的 polar_tx 链路 → y_k（导通口，只做诊断）
  → apply_coupling：r_k = y_k + Σ_j S_kj(f)·y_j   （三种来源，同一条路径）
  → far_field(θ)：频域逐频点相位 → OTA EVM / ACLR / SEM（波束方向 + 旁瓣方向）
```

```python
from arraytx import ArraySim, load_config
sim = ArraySim(load_config("configs/fr2_4el_survey.yaml"))
r = sim.run(theta0_deg=30.0, scheme="array")      # none | per_element | array
print(r.info["engine_line"]); print(r.beam.row()); print(r.sidelobe.row())
```

## 配置（铁律 1：唯一真值）

`configs/fr2_4el_survey.yaml` 是默认配置，其它三个只改一个块：

| 文件 | 差别 |
|---|---|
| `fr2_4el_survey.yaml` | 默认：survey 互耦（相邻 −16 dB，相位随频率线性走） |
| `fr2_4el_analytic.yaml` | `coupling.source: analytic`（频率平坦） |
| `fr2_4el_touchstone.yaml` | `coupling.source: touchstone`，读由 analytic 写出的 `.s4p`（逐位相同） |
| `sub6_1el_anchor.yaml` | sub-6、1 单元、S = 0、单元误差关：与 polar_tx 逐位相同的回归锚 |

外部数字写成 `{value, source, ref}`；纯标量就是 `source: assumed`。`coupling.survey` 块里没有 ref 的数字加载时直接报错。
每个字段的单位 / 说明 / 取值在 `arraytx.config.form_fields()` 里声明（给以后的 GUI 用）。

## 示例

| 示例 | 看什么 |
|---|---|
| `ex00_single_element_equals_polartx` | 1 单元 = polar_tx `nr_dtc().run()` 逐位相同；OTA 与导通指标重合 |
| `ex01_coupling_sources` | analytic / survey / touchstone 同台；touchstone == analytic 逐位 |
| `ex02_coupling_strength_sweep` | 互耦从 0 扫到 −10 dB，三方案 OTA ACLR / EVM；S=0 时收敛 |
| `ex03_scan_angle_x_dpd` | 0 / 30 / 60° × 三方案，波束与旁瓣方向；带边斜视 vs 解析；导通诊断 |
| `ex04_aclr_vs_direction` | ACLR 随方向：非线性互调往哪辐射（方向图零点已标出） |
| `ex05_lo_profiles` | 共用 LO 换成 pll_simulator 导出的 18 个时钟剖面之一（随包提供，`bundled:<preset>`），EVM / ACLR 随 LO |
| `ex11_multi_angle_dpd` | 负载调制下一个 DPD 怎么服务多个扫描角：重训 / 0° 训练 / 多角度联合拟合 / 30° 网格查表（取近邻、系数插值），在没训练过的 15°、45° 上比 |
| `ex10_grid_load_pull_backoff` | 8 × 8 上负载调制下的三方案与扫描角失配；60° 用输出回退 / CFR 深度追回 ACLR，按 polar_tx 平均漏极效率标代价 |
| `ex09_load_pull` | 负载调制：|1+Γ_k| 随扫描角与位置，三方案在训练角度上的差，0° 训练的 DPD 用到 60° 的损失，单元偏差带来的残余 |
| `ex08_planar_array` | 8 × 8 面阵 vs 同单元数的 64 × 1 行阵：两个主平面与对角切面的波束宽、斜视代价、旁瓣，阵列 DPD 后失真往哪辐射，二维互耦矩阵 |
| `ex07_lo_spurs` | 时钟剖面的离散杂散（参考 / 小数杂散）按载频换算后注入共用 LO：9 个带杂散剖面的 EVM / ACLR 关 / 开，小角度估计 vs 实测 |
| `ex06_element_count_squint` | 单元数 4…128 × 0/30/60° × 相移 / 真延时：斜视从指向效应变成波束 EVM 的 n（闭式预测 vs 实测，per-tone 均衡抹平） |

## 模块

| 模块 | 职责 | 铁律 |
|---|---|---|
| `config.py` | YAML → 数据类树，provenance，表单字段声明 | 1 |
| `standards.py` | `fr2_nr400`（TS 38.101-2 出处，波形走 polar_tx `nr_waveform`）、`sub6_nr100`（polar_tx 原样） | — |
| `seeds.py` | `SeedSequence` 派生：每单元、每损伤独立流 | 5 |
| `element.py` / `lo.py` / `loadpull.py` | polar_tx 预设建链、固定 fs_scale、单元误差抽了再置零、共用 LO；负载牵引的 DPA 包装（不改 vendor）；`bundled:<preset>` 时钟剖面按 (f_c/f0)² 换算到载频，其 `spurs:` 表按 f_c/f0 换算成相位旋转注入（`element.lo.spurs`） | 5 |
| `geometry.py` / `beam.py` | 矩形面阵几何（一行 = 线阵，逐位相同）、扫描切面、相移 / 真延时导向、频域远场合成、斜视解析式 | 4 |
| `coupling.py` / `touchstone.py` | 三来源 → `CouplingMatrix` → 唯一的 `apply_coupling`；二维邻域类、远邻相位按电长度、无源性检查；.sNp 读写 | 3 |
| `metrics.py` | `ota_metrics`（验收）与 `conducted_metrics`（诊断） | 2 |
| `dpd.py` | none / per_element（导通口 ILA-GMP）/ array（远场 ILA-GMP） | — |
| `sim.py` / `report.py` | `ArraySim` 串联；引擎行与免责声明 | — |
| `guispec.py` / `guiutil.py` | GUI 契约（控件 = YAML 键、指标域、图）/ 报告（run / scan、绘图数据、可复现卡、YAML 往返） | 1, 2 |
| `webhost.py` / `appbridge.py` / `webui/www/` | `Api`（一份分发）+ 本地宿主（子进程队列、应用窗口）/ Android 桥（线程队列）/ 一份页面 | — |
| `tools/fingerprint.py` | 重构前后逐位比对 | 6 |
| `tools/vendor_check.py` | vendor 树对上游 pin 的漂移检查（`--strict`） | — |

## 规则

读 `AGENTS.md`（六条铁律）、`ROADMAP.md`（只写没做的）、`cairn/LOG.md`（数字原值与被推翻的判断）、`CONTRIBUTING.md`。
