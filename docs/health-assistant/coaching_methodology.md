# 可解释自适应公路车教练方法 v1

## 设计目标

本系统借鉴 Garmin 官方公开的 Cycling Coach、Daily Suggested Workouts、Training Readiness、Training Status/Load Focus 的产品思路，但不复制、不反推、不声称等同于 Garmin 的专有算法。核心原则是：每条建议必须能回答“用了什么数据、为什么、缺什么数据”。

## 骑行教练闭环

1. **建立能力基线**：使用近 28 天骑行时长、距离、爬升、心率、功率和踏频；FTP、阈值心率未知时不生成伪精确训练区间。
2. **判断恢复状态**：睡眠时长/历史、距上次训练时间、近 7 天负荷相对近 4 周周均、可用的静息心率与压力数据。
3. **选择今日训练目的**：恢复、低强度耐力、节奏/阈值、VO2max、神经肌肉/冲刺，优先补训练结构中的短板，而不是每天追高强度。
4. **生成分段课表**：热身、主训练、组间恢复、冷身、终止规则；没有 FTP 时使用 RPE、说话测试和踏频。
5. **训练后调整**：后续应增加完成度、实际 RPE、疼痛/疲劳、功率衰减和心率漂移，再自动调整下一课。
6. **周期结构**：大部分时间为低强度耐力，每周通常只安排 1–2 次质量课；连续负荷后安排恢复日和减量周。

当前“训练负荷代理”是 `运动分钟 × 心率储备区间权重`，用于个人纵向比较。它不是 Garmin 基于 EPOC 的 Training Load；在最大心率和静息心率不可靠时会降低置信度。

## 体脂与减重

- 不根据单次体重或单次 BIA 体脂下结论，使用同一时间、同一测量条件下的 7 日趋势。
- 用去脂体重估算阶段目标：`目标体重 = 去脂体重 / (1 - 目标体脂率)`。
- 当前男性档案的第一阶段目标为体脂约 24%，达到后再结合功率、恢复、饥饿和训练完成度决定是否继续到 20%–24%。
- 采用小幅能量缺口和缓慢减重，优先维持去脂体重与骑行输出；若睡眠、情绪、性欲、免疫、训练表现持续下降，应停止扩大缺口并评估低能量可用性风险。

## 运动营养

- 蛋白质按体重动态计算，当前规则为 1.6–2.0 g/kg/天，并分配到 3–4 餐。
- 碳水随训练负荷周期化：轻松/休息日较低，质量课和长骑日较高，不在关键训练前后刻意低碳。
- 骑行中：60–150 分钟从 30–60 g 碳水/小时起步；更长时间在肠胃训练后逐步接近 60–90 g/小时。
- 饮水与电解质必须根据天气、出汗率、骑前后体重和口渴个体化；页面给出的每小时范围只是起始测试值。
- 饮食日志覆盖不足时，只给目标，不假装知道用户实际吃了多少。

## 主要依据

- Garmin 官方帮助：Cycling Coach、Daily Suggested Workouts、Training Readiness、Training Status、Acute Load 与 Load Focus 的公开说明。
- Thomas DT, Erdman KA, Burke LM. Nutrition and Athletic Performance. J Acad Nutr Diet. 2016. PMID: 26920240.
- Jäger R, et al. ISSN Position Stand: Protein and Exercise. 2017. PMID: 28642676.
- Mountjoy M, et al. 2023 IOC Consensus Statement on Relative Energy Deficiency in Sport. PMID: 37752011.
- Dietary Recommendations for Body Mass and Composition Manipulation in Athletes: Scoping Review. 2025. PMID: 40841871.

## 尚未完成的数据闭环

- FTP 或可靠阈值功率测试。
- 训练后主观 RPE、腿部疲劳、疼痛与课表完成度。
- 连续饮食日志和训练中补给记录。
- HRV、可靠静息心率基线及设备恢复指标。
- 比赛目标、日期、路线爬升和每周可训练日配置。
