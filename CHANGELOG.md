# 变更日志

按里程碑记录做了什么、为什么。没做的在 `ROADMAP.md`。

## 未发布 / Unreleased

### 引擎行按原因与网格给免责：dtc_openloop 不再叫"线性化"，polar、os ≥ 16 不挂免责（2026-11-13）

- `report.disclaimer_for(mode, topology, oversampling)`：response 写"线性化引擎"，rfdac 写"只有失配、网格未验证"，
  dtc_openloop 在 os < 16 写"采样网格未收敛"（附 ex22 的偏差），非 polar 拓扑在 os ≥ 16 写"未验证"；polar、os ≥ 16 改写"网格已收敛"。
  引擎行带上网格（`os 4`）。所有免责共用"不能背书"，测试与页面认它。
- 守护测试：response / rfdac 在任何网格都挂免责，去掉 response 的免责测试变红（已实测）。数字不动（指纹逐位相同）。
- 示例默认网格仍是 4，现有示例照样挂免责；提到 16 的重跑（估约 30 h）留在 ROADMAP B2。

### B2 重新定性：dtc_openloop 不是线性化引擎，但 os 4 的网格没收敛；规矩不动（2026-11-13）

- 新配置键 `sim.oversampling`（0 = 标准的 4，指纹不变）；`Standard.with_oversampling` 标 assumed，对 polar_tx 原生锚点拒绝。
- ex22：os 4 / 8 / 16 / 32 上重跑 ex04 与 ex07 下结论的工况。无 DPD 的 ACLR1 / 旁瓣 / 最差亮方向收敛（≤ 0.07 dB）；
  ACLR2 在 os 4 偏高 4.74 dB；DPD 后 ACLR1 偏高 0.46–0.54 dB、旁瓣至多 1.54 dB；os 16 与 os 32 差 ≤ 0.04 dB。
  按事先容差（ACLR 0.3 dB、EVM 0.1 dB）不收敛，免责声明与 AGENTS 规矩不动。
- ROADMAP B2 按真实原因（fs/2 以上的折叠）与数字重写；新增 E 节"报回上游"（E1：polar_tx FR2 默认 os 4）；
  新主题 `cairn/dtc-openloop-grid.md`；`fr2-floor-lo.md` 追加更正（os 4 上的 ACLR2 与 DPD 后 ACLR1）。

### 换 pin 到 polar_tx@b007e60（polar_tx main），嵌套 pllsim 整棵在 5564c64；数字不动（2026-11-13）

- polar_tx 008cc90 → b007e60（18 个提交；008cc90 已是 main 的祖先，四处本库带回的修正经 polar_tx PR #9 进了 main）。
  排除清单改成 polar_tx 当前的 GUI 面：`guiutil.py`、`appbridge.py`、`guispec.py`、`webhost.py`、`webui/`（`guiqt/` 上游已删）；
  `py.typed` 不带。新非 GUI 文件逐字搬：`cal/dp_cal_fixed.py`、`export/dp_cal_vectors.py`、`export/rtl_vectors.py`、`pllsim/core/tdcspurs.py`。
- 嵌套 pllsim 整棵在 5564c64（polar_tx 的 C5）：`arch/adpll.py` extended、`arch/frac.py` extracted，两条 `pin_frozen` 去掉；
  本库嫁接的 `export/clock_profile.py` 从 00e48a2 跟到 5564c64（+158/−7：整数 ×N 倍频器 #72、文件头措辞 #73）。
- 指纹先加上 18 个内置剖面与一次带剖面的 FR2 运行（168 → 304 项），换 pin 前后逐位相同；`vendor_check --strict` 90 个文件
  （87 verbatim、1 extended、2 extracted、0 skipped）绿；ex00 仍与 polar_tx 逐位相等。
- 分支规矩：在 `feat/*` 上开 PR 合 `main`（AGENTS、CONTRIBUTING）。ROADMAP 新 B10：FR2 的 LO 剖面换成整数 N 倍频链（numbers-move，另一轮）。
- fmcw_radar 所 vendor 的 `geometry.py` / `beam.py` / `coupling.py` / `touchstone.py` 本轮没有改动。

### 每单元回退（ex20）、κ × 相位（ex21）、工作台回退规则（2026-11-06）

- 新配置键 `element.pa.backoff_per_element_db`：每单元满刻度与辐射幅度（多退的单元交出功率）；空 = 旧路径，指纹逐位不变。
- ex20：每单元按 |1+Γ_k| 回退处处达标，但不比整阵列一个回退省（平均效率持平，波束功率 ±0.5 dB）。
- ex21：κ 0.5 × 相位；只在 κ 1 训练的 |1+Γ| 规则在 κ 0.5 下 14/15 达标——规则替代了互耦相位，没有替代 κ。
- `arraytx.design`（规则与判据），工作台"▶ 规则"与 POST /api/rule（Android 桥同一分发），报告带 |1+Γ| 统计。测试 194 → 201。

### 相位未知时的设计表（ex19）、c1 改标 assumed、面阵 touchstone 往返（2026-11-06）

- ex19：回退按实测 |1+Γ| 存而不按扫描角存；只在 180° 训练，在 0 / 90 / 270° 上 4 × 1 15/15、8 × 8 6/6 达标（按角度存 6/15、2/6）。
- c1 相邻互耦 source 改为 assumed（全文核对后没有够格的实测值；值 −16 dB 不变）。
- 面阵 touchstone 往返逐位测试（4 × 4 .s16p 经仿真、8 × 8 .s64p），端口 row-major。测试 191 → 194。

### 互耦相位与 E / H 面（ex18）、A1 全文核对（2026-11-06）

- ex18：8 × 8 无源上限对 E / H 面之比、对角、全局相位的依赖；|1+Γ| 随扫描角的走向对相邻互耦相位的依赖；4 × 1 / 8 × 8 设计表随相位与 E / H 面。
  相邻相位 0° 时安排倒过来（8 × 8 广播向退 3 dB、效率 36.50 %）。ex17 的图加 8 × 8 面板。
- A1：放行 arxiv.org / jees.kr 读到全文，没有够格的实测数字；`SURVEY_REF_C1` 与 YAML 的出处说明改正（值不变，指纹逐位不变）。
- 评审：ex17 8 × 8 只把无源性错误当作"不无源"；"变了的角度"不再把两边都没达标算作变化（`_common.same_setting`）。

### 设计表敏感度（ex17）与第四轮评审（2026-11-05）

- ex17：相邻互耦 −13 / −20 dB、κ 0.5、设计目标各动一个，重做设计表；互耦幅度影响最大（60° 回退 ±1 dB、效率 −6.3 / +2.1 点）。
- ex17 Part 3：8 × 8 同样的情形；−14.5 dB 时 60° 退 3 dB、效率 37.97 %；−13 dB 在 8 × 8 上不无源（泄漏增益 1.16），示例报出而不崩。
- 评审修复：`blend_banks` 拒绝 NaN 与空权重；ex16 的 8 × 8 余量改用 0.35 dB 并检查固定设置的基线；表打分工具收进 `examples/_common.py`，ex15 缓存重复评估。

### B8 关闭：8 × 8 的 DPD 表 10 张（2026-11-05）

- ex15 加"30° 以上 5°"两种网格；10 张（30° 以下 10°）与 11 张（7.5°）最坏都是 +0.35 dB。ROADMAP B8 删除。

### CI 提速与 README 结果速览（2026-11-05）

- pytest 标记 `examples`；CI 的 test 任务跳过示例冒烟，examples 任务在三个 Python 上并行跑它们（带引擎行与出图检查）。
- ex13 / ex14 的冒烟分支缩小（4 × 4、5 个角度），全尺寸不变。README 新增"结果速览"；CONTRIBUTING 写明两条测试命令。

### 扫描设计表（ex16）与 8 × 8 的 DPD 表步长（ex15）（2026-11-05）

- ex16：每个扫描角在 CFR × 回退上的 ACLR1-效率帕累托与设计选择（目标为 assumed 设计取值），对比全程用 60° 设置的效率代价。
- ex15：8 × 8 上的网格 × 插值规则（角度 / 阵列平均 |1+Γ| / 每单元 |1+Γ_k|），已证实 13 张表达标；ROADMAP B8 收窄为"能否 11 张"。
- `dpd.blend_banks` 接受每单元权重。新主题 `cairn/scan-design.md`。

### 代码评审一轮：Γ = ±1 的除零护栏、倒灌计数、截断比例口径、blend_banks 校验（2026-11-05）

- `loadpull.G_FLOOR`：|1+κΓ| 与 |1−Γ| 的下限，Γ = −1 / +1 不再产生 NaN；正常样本逐位不变。
- `n_backflow` 统计 |Γ| ≥ 1 的样本；`clip_fraction` 取各轮最大、分母为门限以上样本。
- `blend_banks` 校验单元数与 GMP 配置，`info` 记录两张表与权重。ex14 去掉重复的 60° 训练并减少内存。测试 185 → 187。

### 扫描角 DPD 表步长（ex14，ROADMAP B8）与全量数字复核（2026-11-04）

- ex14：网格 × 插值规则（取近邻 / 角度 / sinθ / |1+Γ|）的最坏扫描角损失；4 × 1 结论 ≤ 0.5 dB 需 9 张表，8 × 8 未定（B8）。
- `dpd.blend_banks(a, b, w)`：两张同结构 DPD 表的 GMP 系数线性插值，ex11 / ex14 共用。
- ex00–ex12 全尺寸复核，主题笔记 10 个数字按实测更新（结论不变），README 示例表按编号排序。

### |Γ| 护栏敏感度（ex13）：`gamma_max` 默认 0.5 → 1.0（2026-11-04）

- `info["load_pull"]["clip_fraction"]`：每单元 |Γ| 碰到 `gamma_max` 的样本比例。
- 默认 `element.pa.load_pull.gamma_max` 改为 1.0：0.5 在 8 × 8 广播向截掉 40 % 的样本，把阵列效率高估 1.1 个点、内部单元 2.2 个点；ACLR 与 DPD 结论变化 ≤ 0.3 dB。
- ex13 与 ex10 重跑；4 × 1 与指纹逐位不变。

### 代码评审一轮：页面效率轴回退、报告键改名、联合 bank 缓存键、训练合并为一条路径（2026-11-04）

- 报告 `info.eta_avg_pct` / `eta_matched_pct` 改名为 `eta_array_pct` / `eta_array_matched_pct`（含义上一版已变，旧名会让存下的基线错比）。
- `info["load_pull"]` 与单元 `load`：`abs_1pg_*` 为 |1+Γ|（不再乘 κ），新增 `load_gain_*`（实际作用在单元上的因子）。
- `SourceImpedanceCombiner` 不再有自己的默认值，`from_combiner` 从 preset 的合路器复制参数。效率只在 `ArraySim.run` 末尾算一次。
- `dpd.train` 单角度与多角度共用 `_train_joint`；联合 bank 的缓存键含 DPD 配置。指纹与负载牵引六组合逐位不变。测试 179 → 182。

### 效率进负载模型 + outphasing 分支源阻抗（两份提案落地，ex10 重跑、ex12）（2026-11-04）

- `loadpull.loaded_power_terms` / `LoadPulledDPA.forward_amplitude`：端口净功率 |a|²(1−|Γ|²) 与按码的 SCPA 开关损耗。
  `info["efficiency"]` 新增 `eta_loaded_*`、`eta_loaded_per_element`、`eta_array_loaded`、`eta_array_matched`、`n_backflow`；报告 `eta_avg_pct` 改为阵列 loaded，`eta_matched_pct` 为对照。
- `loadpull.SourceImpedanceCombiner` 与 `element.outphasing.source_impedance_rel`（默认 0 逐位不变）：分支源阻抗 × Chireix 电纳的闭式合路，阵列 Γ 经戴维南因子进入。
  outphasing 拓扑下负载牵引开关在 ρ > 0 时生效。页面控件仅在 outphasing 拓扑下显示。
- ex10 加 loaded 效率列与 8 × 8 每单元效率热图；ex12 检验提案的四条预期。测试 156 → 179；指纹 168 项逐位相同。

### 多扫描角 DPD（ex11）+ 页面按效率画研究 + 两份模型提案（2026-11-03）

- `dpd.train_angles_deg`：两种 DPD 都可在若干扫描角上联合拟合（GMP 基矩阵拼接成一个最小二乘），每角度保留自己的负载工作点；联合 bank 每个 ArraySim 训一次复用。
  默认空列表 = 原行为，指纹 168 项逐位相同；单角度与原路径逐位相等。
- ex11：重训 / 0° 训练 / 联合 / 30° 网格查表（取大角、系数插值）在 0–60° 的比较。结论：联合训练最差，30° 网格不够（数字见 LOG）。
- 页面：研究横轴可选"平均漏极效率"，回退与 CFR 的取值提示，CFR 可当分组控件；`?sweepx=eta` 深链接。
- `cairn/loaded-efficiency-proposal.md`、`cairn/outphasing-load-proposal.md`：status proposed，未实现。测试 150 → 156。

### 8 × 8 负载调制 DPD 对比 + 60° 回退研究（ex10）（2026-11-03）

- `element.pa.backoff_db`：钉住的满刻度抬高这么多 dB（输出功率回退），所有拓扑一样；0 逐位不变（指纹 168 项相同），负值报错。
- `info["efficiency"]` / 报告的 `eta_avg_pct`：polar_tx 的平均漏极效率，按单元平均，标明是匹配负载律（Γ 不进效率）；页面多一张 info 卡。
- ex10：8 × 8 上三方案有 / 无牵引、0° 训练用到 60°；60° 的回退 × CFR 深度扫描带效率代价。结论见 `cairn/load-pull-proposal.md` 末节与 LOG。
- 页面服务器不再为客户端中途挂断打印 traceback（只吞 `ConnectionError`）。测试 147 → 150。

### 代码评审一轮：页面轮询在 −∞ 上停摆的修复、负载牵引少跑一遍、管道竞态（2026-11-03）

- `webhost.dumps`：HTTP 与 Android 桥共用的 JSON 编码器，非有限浮点写成 `"-inf" / "inf" / "nan"`（此前 `scale_db = -inf` 的报告让 `GET /api/jobs/<id>`
  掐断连接、页面不再取行）；`do_GET` 的序列化错误也以 JSON 返回。
- `GET /api/jobs/<id>/rows/<from>`：只回还没看过的行；页面轮询改用它。进程后端在 worker 退出后收完管道里剩余的消息（`done` 不再丢）。
- `ArraySim.run`：只有 per_element + pa_output 需要预跑定工作点的 radiate，其余方案不再多跑一遍（六个组合的 `ys` 逐位不变）。
- `metrics.SEM_TX_POWER_DBM` 取代两处 23.0；`_neighbour_shape` 直接收 `_class_gains` 的 dict。测试 146 → 147；指纹 168 项逐位相同。

### 里程碑 2b：负载调制 PA（ROADMAP A2，按 `cairn/load-pull-proposal.md` 实现）（2026-11-03）

- `loadpull.py`：`LoadPulledDPA` 是 polar_tx `DPA` 的子类，无负载时逐位同原表；有负载时 Rapp 读在 `drive·|1+κ_a Γ|·r`、结果除以 |1+κ_a Γ|
  （耦合波由 `apply_coupling` 之后加上），AM-PM 读在 `r·|1+κ_p Γ|`；`active_reflection` 算 Γ_k = (r_k − y_k)/y_k，包络过零处置 0、|Γ| 截到 gamma_max。
- `ArraySim.radiate`：开关开且有互耦时做定点迭代（默认两轮），单元保留最后一轮的负载作为工作点；`dpd.train` 走同一个 `radiate`，
  所以阵列 DPD 与天线口观测看到的是迭代后的 PA，每单元 DPD 在 PA 前向口看到的是带负载的 PA。`run` 在 per_element + pa_output 时先用无 DPD 的导向驱动跑一次定工作点（其余方案在训练里自己 radiate）。
- 配置 `element.pa.load_pull{enabled false, kappa_amam 1, kappa_ampm 1, iterations 2, gamma_max 0.5, floor 0.05}`，κ 带 assumed 出处；
  开关关、S=0、理想 PA、rfdac / outphasing 拓扑下逐位不变（指纹 168 项相同，测试）。页面的 6 个新控件随开关显隐。
- 示例 ex09、测试 138 → 146 项。数字与被推翻 / 证实的预期见 `cairn/LOG.md`。

### Android 壳：appbridge + 线程后端队列 + android/（2026-11-03）

- `webhost.Api`：把 HTTP 处理器里的分发抽出来，`get / post / call(route, req) -> (code, payload)`，HTTP 与 Android 桥共用一份。
  `JobQueue(backend="thread")`：Chaquopy 没有 multiprocessing，任务跑在线程上，取消在行与行之间协作完成；`execute()` 是两种后端共用的执行体。
- `appbridge.call(route, json) -> json`：永不抛错，坏路由 / 坏 JSON / 库内异常都在带内返回；相对路径落在 `ARRAYTX_HOME`（应用私有目录）。
- `app.js`：`window.host` 存在时所有请求走桥（`onHostReply` 回包），否则 fetch；Playwright 注入假桥测这条路。
- `android/`（Gradle 8.1 / Kotlin 1.9 / Chaquopy 15.0.1 / Python 3.10，assets 直接指向 `src/arraytx/webui`），`MainActivity.kt` 约 80 行，
  WebChromeClient 把页面的 prompt 按默认值确认；`.github/workflows/android.yml` 手动构建 APK（未在此运行）。
- 测试 130 → 138 项（appbridge 4、android 3、webui 1）。ROADMAP C1 关闭。

### 页面：研究按第二个控件分组（双线），中英双语（2026-11-03）

- `sweep_report` / `POST /api/sweep` 加 `group_path` / `group_values`：同一组取值对第二个控件的每个值各跑一遍，行带 `group_value`；
  宿主先把每个组合建成合法配置。页面"按"下拉 + 分组取值，研究图一组一条线（ex06 的相移 vs 真延时），布尔 / 枚举取值用一组一行的格子。
- 双语：静态文本 `data-zh / data-en`，动态文本走 `T` 字典，右上角切换并记在 localStorage；指标名用 spec 里的 zh / en；控件说明保持英文元数据。
- 测试 128 → 130 项。

### 里程碑 2a：矩形面阵、扫描切面、二维互耦邻域；互耦远邻相位改按电长度并加无源性检查（2026-11-03）

- `geometry.ArrayGeometry(n_x, n_y, dx, dy, f0, pattern, plane_phi_deg)`：row-major 单元序（第一行就是原线阵），`delays_s(θ)` 在配置的
  切面里算，一行 + φ=0 走原表达式逐位相同；`LinearArray(n, …)` 保留为一行的构造。`with_plane(φ)` 换切面。所有 beam / dpd / sim 函数签名不变。
- 配置：`array.n_rows`、`array.spacing_y_lambda`、`beam.plane_phi_deg`；analytic / survey 块加 `c1y_rel_db`、`c_diag_rel_db`（assumed，带理由）
  和 `phase_from_distance`。新配置 `configs/fr2_8x8_survey.yaml`。
- 互耦：邻域类 x1 / x2 / y1 / y2 / d1；**物理修正**：远邻的 f0 相位 = c1 相位 + 超出一个间距的自由空间电长度（λ/2 间距的 x2 +180°，
  对角 +74.5°），与 `path_delay_from_spacing` 的"纯延时"一致。此前所有邻居都放在 c1 相位：一行上无源（泄漏增益 0.33），
  8 × 8 上泄漏增益 1.13 > 1，广播向的波束几乎抵消（EVM −5.9 dB）——不是物理，是假设错。`build_coupling` 现在算泄漏矩阵的最大奇异值，
  > 1 拒绝加载。指纹：168 项中 81 项变（analytic / survey 的互耦矩阵及其下游；锚点、单元抽取、导通输出不变），
  4 单元 survey 的波束指标移动 ≤ 0.05 dB（30° ACLR1 −37.313 → −37.310，阵列 DPD −43.743 → −43.702）。
- 示例 ex08，测试 122 → 128 项（`tests/test_planar.py` 5 项 + ex08 冒烟）。

### 页面上的扫描研究 + 历史持久化（2026-11-03）

- `guiutil.sweep_report` / `POST /api/sweep`：一个控件 × 取值列表，每点一个 ArraySim（经 `values_to_config`，其余叶子不动），逐行回传；
  宿主先把每个点建成合法配置再排队。页面"扫描研究"栏 + 指标随取值的图（数值取值跨 ≥ 20 倍用 log2 轴，布尔 / 枚举用格子），边跑边画。
- 最近 12 条报告存 localStorage（按端口），刷新恢复并标 ↺。测试 119 → 122 项。

### 工作台 GUI：一份单页（桌面应用窗口 / 浏览器 / 手机宽度），标准库宿主，子进程队列（2026-11-02）

- `guispec.py`：控件 = `form_fields()` 的每个叶子（分组、单位、取值、显隐规则、出处），指标按域（ota / info / diagnostic）声明，
  图按种类声明；`values_to_config` 走 `config_from_dict`，GUI 改过的 survey 数字降为 assumed 并注明；`to_yaml` 写回 `{value, source, ref}`，载回同值同出处。
- `guiutil.py`：`run_report` / `scan_report`（一个 ArraySim 跑 scan_deg × 方案，逐行回传）：OTA 波束 + 旁瓣、per-tone EVM、导通诊断、
  三张图的数据、引擎行、可复现卡（seed、配置 sha256、vendored pin、等价调用）。`direction_scan` 用单元信号的 Welch 分段按方向合成，
  与逐方向合成远场的精确路径 ACLR 差 < 1e-4 dB、方向图差 < 0.01 dB，每份报告的绘图数据 10.9 s → 0.8 s（全尺寸）。
- `webhost.py`：`GET /api/spec|config|jobs`，`POST /api/validate|save|run|scan|jobs/<id>/cancel`；每个任务一个 spawn 子进程，取消即终止；
  POST 要 `X-ArrayTX` 头；绑 127.0.0.1；`arraytx-gui` 开 Chromium 系应用窗口，关窗口即停（照 polar_tx `webhost`）。
- `webui/www/`：无外部库的 HTML / CSS / JS + 内联 SVG 图；≤ 760 px 底部导航。设计取自本会话的两组效果图（Fable web 为主，
  Opus 的扫描表驱动图、可复现卡、全宽引擎横条、模板"非一致性条款"标注）。
- CI 加 `test-gui`（Playwright + Chromium，`ARRAYTX_REQUIRE_BROWSER=1`）。测试 97 → 119 项。ROADMAP C1 改写为剩余宿主。

### B6 了结：时钟剖面的离散杂散注入共用 LO（2026-11-02）

- `lo.py`：`ClockProfileLO.spurs_at_carrier()`（dbc 是单边带杂散电平 → 峰值相位 2·10^(dbc/20)，乘 f_c/f0；频偏不变）、`spur_rms_rad`、
  `spur_phase_rad`。`element.py`：链输出乘 exp(jφ_spur(t))——polar_tx 把 LO 相位加在 DPA 的相位输入上、DPA 的 AM-AM / AM-PM 只看幅度码，
  所以 LO 上加相位与输出旋转是同一信号（测试对比"把相位加在驱动上"：差在 DTC 重量化，< −40 dB）。
- `seeds.py`：`lo_spurs` 流追加在两个元组末尾（spawn 按索引，既有流逐位不动；指纹 168 项相同）；`element.lo.spurs` 开关默认开，关时照抽再置零。
- 示例 ex07（9 个带杂散剖面，关 / 开，无 DPD 与阵列 DPD）与 3 项测试。数字见 `cairn/LOG.md`。测试 93 → 97 项。

### ex06 单元数扩展：斜视何时进波束 EVM；`apply_coupling` 改按非零对累加（2026-11-02）

- `beam.py`：`beam_response`（相移导向下波束方向看到的线性频响 H(f)，Dirichlet 核）、`squint_evm_closed_form_db`（scalar 均衡残差）、
  `beamwidth_3db_deg`、`tone_frequencies_hz`。ex06 扫 n = 4…128 × 0/30/60° × phase/ttd，scalar 与 per-tone 两种均衡口径。
- `coupling.py`：`apply_coupling` 不再构造 (N, n, n) 稠密矩阵（64 单元 8 符号要 9 GB），改为只对非零 S_kj 对累加，实部虚部分开累加
  以复现 numpy 复数 einsum 的位序——指纹 168 项逐位相同，另有测试钉住；64 单元冒烟一次 run 15.2 s → 2.3 s。
- 结论与数字见 `cairn/LOG.md`；`cairn/architecture-invariants.md` 的"斜视不进 EVM"改为随 n 的陈述。测试 88 → 93 项。

### 换 pin 到 polar_tx@008cc90：四处修正回馈上游后，FR2 波形改用 polar_tx 自己的数字表（2026-10-13）

- polar_tx 侧（其开发分支）：NR 400 MHz 数字表、`nr_dtc.fs_bb`、`CartesianTX` 可钉满刻度、抖动"抽了再置零"。
- 本库：vendor 整体到 008cc90；`standards.py` 的 FR2 波形改用 `nr_waveform`；rfdac 拓扑允许 DPD；ROADMAP B1 删、B3 改。
- 指纹换 pin 前后 168 项逐位相同。

### 共用 LO 接真实时钟剖面：pll_simulator 的 18 个预设随包提供，EVM / ACLR 随 LO 扫描（2026-10-13）

- `src/arraytx/data/clock_profiles/`：pll_simulator@00e48a2 用自己的 `export --clock-profile` 导出的全部 18 个预设（文件内 `source:` 行带提交号），未经编辑。
  config 里 `element.lo.clock_profile: "bundled:<preset>"`，或相对 config 文件的路径。
- `lo.py`：`resolve_profile`、`list_bundled`、`rms_phase_rad`（可按 DTC 的锁定近似在环路带宽以下压平）。剖面按 (f_c / f0)² 换算到载频。
- 示例 ex05 与 5 项测试。数字见 `cairn/LOG.md`。
- 为什么：FR2 链的 EVM 完全由 LO 决定（上一条 LOG），而共用 LO 这条路此前只用合成夹具测过。

### 里程碑 1：4 单元 FR2 线阵、三种互耦来源、三种 DPD 方案、OTA 指标（2026-10-13）

**做了什么**

- 新库骨架：Project Cairn（AGENTS.md 六条铁律、ROADMAP 只写没做的、`cairn/LOG.md`）、CI（lint / test 3.10–3.12 / 示例冒烟 / vendor 漂移 `--strict`）。
- `src/arraytx/vendor/polartx`：polar_tx@8a10480 的 `src/polartx` 去掉 GUI 面后原样 vendor（86 个文件，83 verbatim，3 个沿用 polar_tx 的 extended/extracted）；
  pll_simulator@00e48a2 的 `export/clock_profile.py` 单独 vendor（polar_tx 的 pllsim pin 不含它）。`tools/vendor_check.py` 从 polar_tx 改编，只剥两行归属头。
- `config.py`：单一 YAML 真值 + 每个数字的 provenance（survey 块无 ref 不加载）+ 表单字段声明（给以后 GUI）。
- `standards.py`：`fr2_nr400`（28 GHz / 400 MHz / 120 kHz / 264 RB，TS 38.101-2 出处）与 `sub6_nr100`（polar_tx `nr_dtc()` 原样，回归锚）。
- `seeds.py` / `element.py` / `lo.py`：`SeedSequence` 派生每单元每损伤独立流；单元链经 polar_tx 预设工厂建、CFR 外移、包络满刻度固定（DPD 不改工作点）；
  `lo_pn_seed` 共用 LO；时钟剖面经鸭子类型适配器注入。
- `geometry.py` / `beam.py`：频域逐频点远场合成（斜视真算）、相移 / 真延时导向、斜视解析式、最高旁瓣方向。
- `coupling.py` / `touchstone.py`：analytic / survey / touchstone 三来源同一 `CouplingMatrix`、同一 `apply_coupling`；S=0 原样返回；.sNp 读写回读逐位。
- `metrics.py` / `dpd.py` / `sim.py`：OTA 与导通两域指标；none / per_element（导通口 ILA-GMP）/ array（远场 ILA-GMP）；`ArraySim.run_matrix`。
- 示例 ex00–ex04、`tools/fingerprint.py`（record / compare）、74 项测试。

**为什么这样做**

- 单元链不重写：polar_tx 的链是基带等效、增益归一的，直接当 PA 输出进互耦和远场；1 单元 S=0 与 polar_tx 逐位相同是全库的锚。
- CFR 外移与 fs_scale 固定：polar_tx 每次 run 按峰值重新归一化包络，DPD 扩展峰值后工作点会漂移，所以先跑一次参考再钉死。
- 互耦只做线性泄漏：PA_DPD 的 PA 无负载依赖，其 ROADMAP 也没有 load-pull 条目，不在这里编负载调制。

**里程碑数字**（survey 互耦 −16 dB，波束方向 OTA ACLR1，dBc；8 符号全尺寸）

| 扫描角 | 无 DPD | 每单元 ILA-GMP | 全阵列 ILA-GMP（OTA） | 旁瓣方向 无 / 每单元 / 全阵列 |
|---|---|---|---|---|
| 0° | −37.8 | −45.5 | −45.5 | −35.7 / −38.7 / −38.4（+47.1°） |
| 30° | −37.8 | −45.5 | −45.4 | −38.0 / −42.4 / −41.8（−13.4°） |
| 60° | −37.7 | −45.4 | −45.3 | −38.1 / −42.3 / −41.4（+7.7°） |

全阵列 DPD 追回 7.6–7.7 dB；analytic 与 survey 之差 ≤ 0.01 dB；互耦→0 时两种 DPD 差 0.09 dB；带边斜视与解析式误差 0.00 %。
默认 GMP 是无记忆 7 阶（7 系数）：扫描表明这条链几乎无记忆，记忆抽头只伤 ACLR2（`cairn/LOG.md`）。
被推翻的判断与原因见 `cairn/LOG.md`、`cairn/architecture-invariants.md`。
