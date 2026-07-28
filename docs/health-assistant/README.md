# health-assistant 能力迁移说明

`shkyyy18/health-assistant`（本地健康仪表盘：Strava、睡眠、体成分、餐食分析）已合并进本仓库，原仓库已归档、不再维护。本目录保存从原仓库带来的关键文档与参考实现。

## 已吸收的能力

- **训练/恢复分析与建议引擎**：`analytics.py`（纯标准库、无外部依赖的参考实现，来自原仓库 `app/analytics.py`）。输入为 Strava 活动、睡眠、体成分和每日指标的字典列表，输出最近 7 天训练统计、急慢性负荷比、恢复状态判断和当日训练建议。字段口径以原 health-assistant 的 SQLite schema 为准，接到本桥接器的导出数据时需要做字段映射。
- **教练与营养方法论**：`coaching_methodology.md`（可解释自适应公路车教练方法 v1，含体脂/减重与运动营养规则及其文献依据）。

## 未移植、留在归档仓库的部分

以下部分与 FastAPI 应用、Strava OAuth/Webhook 基础设施和原库 schema 深度耦合，完整移植工程量大，未搬入本仓库；需要时可查阅归档仓库 `shkyyy18/health-assistant`：

- 响应式中文仪表盘（FastAPI + Jinja 模板 `index.html` / `mobile.html`）。
- Strava OAuth、活动同步与 Webhook 实时订阅（含 ngrok 隧道与 Windows 启动任务脚本）。
- 餐食拍照分析（依赖外部多模态 API 凭据）。
- 睡眠与体成分的手写录入 HTTP API。

## 定位说明

本仓库的定位仍是 local-first 数据桥接器：同步、存储、导出 Mi Fitness 数据。上述分析与方法论文档作为下游仪表盘/建议功能的参考实现保留，不构成医疗建议。
