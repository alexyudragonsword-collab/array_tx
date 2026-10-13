# array_tx 协作规则

> 本项目用 Project Cairn 组织项目知识：`AGENTS.md` 是规则与导航入口，`cairn/` 是项目知识/状态层。
> 同目录的 `CLAUDE.md` 只有一行 `@AGENTS.md`，让 Claude Code 读同一份规则；Codex 直接读本文件。

## 项目一句话

多单元阵列发射机的行为级仿真框架：每个单元是一条 vendored polar_tx 链路，阵列级互耦进链路、波束斜视按真实带宽算、
阵列级 DPD 在远场观测上训练，EVM / ACLR / 谱模板只在空间（OTA）方向上读。polar_tx 的姊妹库。

## Init 配置

- 知识库 provider：暂缓对接（首次 graduation 时再接）
- 知识库索引：尚未配置
- Graduation 目标：尚未配置

## 进入项目后的阅读顺序

1. 先读本文件。
2. 读根目录 `ROADMAP.md`（只写没做的）和 `CHANGELOG.md`（按里程碑）。
3. 读 `cairn/LOG.md` 最新几条（新条目在顶）：数字原值、被推翻的判断、下一步。
4. 读 `cairn/architecture-invariants.md`：六条铁律 ↔ 实现位置 ↔ 守护测试。
5. 代码入口：`src/arraytx/sim.py`（ArraySim）、`config.py`、`coupling.py`、`beam.py`、`dpd.py`。

## 文档职责

| 文件 | 角色 | 维护 |
|---|---|---|
| `AGENTS.md` | 规则与导航 | 很少改，≤ 65 行 |
| `CLAUDE.md` | 一行 `@AGENTS.md` | 写一次不再动 |
| `ROADMAP.md` | 只写没做的；做完就删 | 原地更新 |
| `CHANGELOG.md` | 按里程碑记做了什么、为什么 | 每个里程碑一条 |
| `cairn/LOG.md` | 时间日志，新条目在顶，每条 ≤ 20 行 | 每次实质进展加一条，数字写原值 |
| `cairn/<topic>.md` | 知识主题（当前真值） | 原地更新；陷阱写进主题正文 |
| `cairn/Reference/`、`cairn/Cited.md` | 外部原料 / 引用清单 | 有触发才建 |

## 项目铁律（每条有测试守着，见 `cairn/architecture-invariants.md`）

1. **配置是唯一真值**：阵列几何、单元拓扑、制式、互耦来源、DPD 方案、扫描角全在一个 YAML 里；代码里不许有第二套默认值。
2. **验收指标只在空间读**：EVM / ACLR / 谱模板在远场某方向上算；导通端口指标只是诊断量，函数名带 `conducted_`，示例和文档不许拿它下结论。
3. **互耦必须进链路**：单元 k 的辐射 = 自己的 PA 输出 + Σ_j S_kj × 单元 j 的 PA 输出；三个来源走同一个 `apply_coupling`；S = 0 时逐位等于单条 polar_tx 链。
4. **波束斜视按真实带宽算**：远场合成在频域逐频点乘相位，不许用"中心频率 + 修正项"。
5. **单元差异是种子可复现的随机实例**：`SeedSequence` 派生每单元、每损伤独立流；开关关闭时照抽再置零；改一处配置不换别处抽取。
6. **数值指纹**：重构用 `tools/fingerprint.py record / compare` 证明逐位不变，"测试通过"不能代替。

## 本仓库特有的硬规矩

- 外部来源的每个数字都带 `source`（survey / derived / assumed / measured）和出处；没有出处就标 `assumed`，不许冒充 survey。
  `coupling.survey` 块里每个数字都要写明来历（survey 带引文，assumed / derived 带原因），裸标量不许进。
- `src/arraytx/vendor/` 是可校验的改编副本，不是 fork：pin 到上游完整 SHA，`tools/vendor_check.py --strict` 必须绿。
- response / dtc_openloop 引擎出的杂散、互调结论一律标"线性化引擎，不能背书"；每个示例打印用的引擎。
- 互耦在里程碑 1 只是线性泄漏；负载调制等 PA_DPD 的 load-pull，不在这里编。
- 只提交到 `ccr-411c6423-uxcjms`；不开 PR、不推 main；提交信息写为什么并带实测数字。

## 冲突仲裁与知识蒸馏

- 代码和实测数字 > 任何文档；主题笔记 > LOG 历史；规则级冲突以本文件为准。
- 每次实质进展在 `cairn/LOG.md` 顶部加一条；稳定结论沉淀到主题笔记；纠正旧判断要追加说明，不悄悄覆盖。
- 完成前先过 Cairn 检查点（`references/maintenance.md`）；明确只读的请求不写 Cairn 文件。
