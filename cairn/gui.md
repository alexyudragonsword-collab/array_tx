---
type: project_topic
status: active
summary: GUI 的分层与决定——一份页面三个宿主（桌面应用窗口 / 浏览器 / Android WebView）、描述 / 计算 / 宿主 / 画四层、子进程与线程两种队列、页面测试的做法与踩过的坑
tags: [gui, web, android, playwright]
contains: [decision, lesson, pitfall]
created: 2026-11-03
updated: 2026-11-03
related: [architecture-invariants.md]
authoring_mode: ai_generated
---
# GUI

## 决定（2026-11-02，四张效果图审阅后）

以 web 单页为主（同 polar_tx 2026-10-29 退役 Qt 的理由：一份页面三个宿主、长运行天然进程队列、不依赖 PySide6 版本），
采纳 Opus 方案里的扫描表驱动图、可复现卡、全宽引擎横条、模板"非一致性条款"标注、手机底部导航。

## 分层（AGENTS 硬规矩：页面只画不算）

| 层 | 文件 | 规则 |
|---|---|---|
| 描述 | `guispec.py` | 控件 = `form_fields()` 的叶子（53 可见 + 2 隐藏），默认值从 `default_config()` 读；指标按域 ota / info / diagnostic；`values_to_config` 走 `config_from_dict`，GUI 改过的 survey 数字降为 assumed |
| 计算 | `guiutil.py` | `run_report / scan_report / sweep_report`；报告 = OTA 波束 + 旁瓣、per-tone EVM、`conducted_*` 诊断、三张图数据、引擎行、可复现卡（seed、cfg sha256、vendored pin、等价调用） |
| 分发 | `webhost.Api` | `get / post / call(route, req) -> (code, payload)`，HTTP 处理器与 `appbridge.call` 都只是传输 |
| 队列 | `webhost.JobQueue` | `process` 后端（桌面：spawn 子进程，取消 = 终止）/ `thread` 后端（Android：取消在行与行之间）；`execute()` 共用 |
| 画 | `webui/www/` | 无外部库，内联 SVG；`api()` 在 `window.host` 存在时走桥；≤ 760 px 底部导航；中英双语 `data-zh / data-en` + 字典 |

## 坑

- 轮询竞态：poll 在"列出任务"与"提交新任务"之间判定空闲而停下，新任务无人取——提交后置 `pollAgain` 标志。
- 全局字符串替换把字典自身条目替换成 `t(...)`（自引用，启动即 TDZ 报错）；浏览器测试抓到。替换字面量要排除定义它的那一行。
- `data-zh` 元素不能包别的元素（textContent 覆盖子节点会删掉控件）；`tests/test_android.py` 用文本规则守着。
- 共享宿主上的页面测试要等"自己那一行"而不是行数（前面测试的任务还在宿主里）。
- 1 × 1 网格把框撑满、hi == lo 时颜色 NaN——SVG 要给 width / max-width，归一化要防零跨度。
- 第一版 appbridge 用 chdir 到应用目录，测试进程里之后所有相对路径都跟着挂；改为 `State.home` 解析相对路径。
- 示例把每次运行的 `ArrayResult`（64 单元约 0.5 GB）留在内存里，全尺寸 ex08 两次 OOM；只留数字。

## 性能

报告里"ACLR 随方向"用单元信号的 Welch 分段按方向合成（`direction_scan`），每份报告的绘图数据全尺寸 10.9 s → 0.8 s，与精确路径 ACLR 差 < 1e-4 dB。

## Android

`android/` 照 polar_tx（AGP 8.1.4 / Kotlin 1.9.24 / Chaquopy 15.0.1 / Python 3.10），assets 直接指向 `src/arraytx/webui`，
`MainActivity.kt` 约 80 行 + WebChromeClient 把 prompt 按默认值确认。APK 工作流手动触发；首次构建记录见 LOG。
