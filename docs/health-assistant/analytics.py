from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from math import ceil
from statistics import mean, median
from typing import Any


def _parse(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def _try_parse(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return _parse(str(value))
    except (TypeError, ValueError):
        return None


def _number(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _raw(item: dict[str, Any]) -> dict[str, Any]:
    value = item.get("raw_json")
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _sleep_hours(item: dict[str, Any]) -> float | None:
    duration = _number(item.get("duration_minutes"))
    if duration is not None:
        hours = duration / 60
        return hours if 0 < hours <= 24 else None
    if item.get("start_time") and item.get("end_time"):
        start = _try_parse(item["start_time"])
        end = _try_parse(item["end_time"])
        if start is not None and end is not None:
            hours = (end - start).total_seconds() / 3600
            return hours if 0 < hours <= 24 else None
    return None


def _activity_load(
    activity: dict[str, Any], observed_max_hr: float | None, resting_hr: float | None
) -> tuple[float, str]:
    """Transparent load proxy; deliberately not Garmin EPOC or Training Load."""
    minutes = max(0.0, _number(activity.get("moving_time")) or 0) / 60
    avg_hr = _number(activity.get("average_heartrate"))
    if avg_hr and observed_max_hr and resting_hr and observed_max_hr > resting_hr + 20:
        hrr = (avg_hr - resting_hr) / (observed_max_hr - resting_hr)
        if hrr < 0.65:
            factor, bucket = 1.0, "低有氧"
        elif hrr < 0.78:
            factor, bucket = 1.4, "中高有氧"
        else:
            factor, bucket = 1.8, "高强度"
    else:
        factor, bucket = 1.2, "强度未校准"
    return minutes * factor, bucket


def _body_analysis(
    body: list[dict[str, Any]], profile: dict[str, Any], now: datetime
) -> dict[str, Any]:
    records = [item for item in body if _try_parse(item.get("measured_at")) is not None]
    records.sort(
        key=lambda item: _parse(str(item["measured_at"])),
        reverse=True,
    )
    weights = [_number(item.get("weight_kg")) for item in records]
    weights = [value for value in weights if value is not None]
    bf_records = [item for item in records if _number(item.get("body_fat_pct")) is not None]
    latest = records[0] if records else None
    latest_bf_record = bf_records[0] if bf_records else None
    recent_weights = weights[:7]
    recent_bf = [_number(item.get("body_fat_pct")) for item in bf_records[:7]]
    recent_bf = [value for value in recent_bf if value is not None]

    reference_tz = _parse(str(latest["measured_at"])).tzinfo if latest else timezone.utc
    local_today = now.astimezone(reference_tz).date()
    this_week_start = local_today - timedelta(days=local_today.weekday())
    next_week_start = this_week_start + timedelta(days=7)
    last_week_start = this_week_start - timedelta(days=7)

    def values_between(field: str, start_date, end_date) -> list[float]:
        values: list[float] = []
        for item in records:
            measured_date = _parse(str(item["measured_at"])).astimezone(reference_tz).date()
            value = _number(item.get(field))
            if start_date <= measured_date < end_date and value is not None:
                values.append(value)
        return values

    this_week_weights = values_between("weight_kg", this_week_start, next_week_start)
    last_week_weights = values_between("weight_kg", last_week_start, this_week_start)
    this_week_bf = values_between("body_fat_pct", this_week_start, next_week_start)
    last_week_bf = values_between("body_fat_pct", last_week_start, this_week_start)

    def average(values: list[float]) -> float | None:
        return round(mean(values), 1) if values else None

    def change(current: list[float], previous: list[float]) -> float | None:
        return round(mean(current) - mean(previous), 1) if current and previous else None

    result: dict[str, Any] = {
        "status": "数据不足",
        "latest_weight_kg": round(_number(latest.get("weight_kg")) or 0, 1) if latest else None,
        "weight_average_kg": round(mean(recent_weights), 1) if recent_weights else None,
        "body_fat_pct": round(mean(recent_bf), 1) if recent_bf else None,
        "latest_body_fat_pct": None,
        "latest_body_fat_date": None,
        "this_week_label": f"{this_week_start:%m-%d}至{local_today:%m-%d}",
        "last_week_label": f"{last_week_start:%m-%d}至{(this_week_start - timedelta(days=1)):%m-%d}",
        "weight_this_week_avg_kg": average(this_week_weights),
        "weight_last_week_avg_kg": average(last_week_weights),
        "weight_week_change_kg": change(this_week_weights, last_week_weights),
        "weight_this_week_count": len(this_week_weights),
        "weight_last_week_count": len(last_week_weights),
        "body_fat_this_week_avg_pct": average(this_week_bf),
        "body_fat_last_week_avg_pct": average(last_week_bf),
        "body_fat_week_change_pct": change(this_week_bf, last_week_bf),
        "body_fat_this_week_count": len(this_week_bf),
        "body_fat_last_week_count": len(last_week_bf),
        "target_weight_range_kg": None,
        "recommended_loss_kg": None,
        "weekly_loss_kg": "0.2–0.4",
        "detail": "至少需要连续体重和体脂数据才能估算。",
        "caveat": "家用生物电阻抗体脂秤受水分、进食和运动影响，应看同一条件下的多日趋势。",
    }
    result["weight_trend_kg"] = result["weight_week_change_kg"]

    if not latest_bf_record:
        return result
    weight = _number(latest_bf_record.get("weight_kg"))
    body_fat = _number(latest_bf_record.get("body_fat_pct"))
    if (
        weight is None
        or body_fat is None
        or weight <= 0
        or not 0 <= body_fat < 80
    ):
        return result

    latest_bf_at = _parse(str(latest_bf_record["measured_at"])).astimezone(reference_tz)
    lean_mass = weight * (1 - body_fat / 100)
    sex = profile.get("sex")
    if sex == "男":
        result["status"] = "偏高" if body_fat >= 25 else ("需关注" if body_fat >= 20 else "常用健康区间")
    elif sex == "女":
        result["status"] = "偏高" if body_fat >= 32 else ("需关注" if body_fat >= 25 else "常用健康区间")
    else:
        result["status"] = "需结合性别判断"

    target_low = _number(profile.get("target_body_fat_low")) or (20 if sex == "男" else 25)
    target_high = _number(profile.get("target_body_fat_high")) or (24 if sex == "男" else 30)
    target_low = min(60.0, max(5.0, target_low))
    target_high = min(60.0, max(target_low, target_high))
    target_weight_low = lean_mass / (1 - target_low / 100)
    target_weight_high = lean_mass / (1 - target_high / 100)
    loss_low = max(0.0, weight - target_weight_high)
    loss_high = max(0.0, weight - target_weight_low)
    result.update({
        "measurement_weight_kg": round(weight, 1),
        "body_fat_pct": round(mean(recent_bf), 1) if recent_bf else round(body_fat, 1),
        "latest_body_fat_pct": round(body_fat, 1),
        "latest_body_fat_date": latest_bf_at.strftime("%Y-%m-%d"),
        "lean_mass_kg": round(lean_mass, 1),
        "target_body_fat_range": f"{target_low:.0f}%–{target_high:.0f}%",
        "target_weight_range_kg": f"{target_weight_low:.1f}–{target_weight_high:.1f}",
        "recommended_loss_kg": f"约{loss_low:.1f}公斤",
        "extended_loss_kg": f"{loss_low:.1f}–{loss_high:.1f}公斤",
        "detail": (
            f"按最近一次同时有体重和体脂的数据估算，去脂体重约{lean_mass:.1f}公斤。"
            f"先以体脂{target_high:.0f}%、体重约{target_weight_high:.1f}公斤为第一阶段；"
            f"达到后根据功率、睡眠和饥饿感，再决定是否继续到{target_low:.0f}%–{target_high:.0f}%。"
        ),
    })
    return result


def _nutrition_plan(
    body_result: dict[str, Any], nutrition: list[dict[str, Any]], workout: dict[str, Any]
) -> dict[str, Any]:
    weight = body_result.get("weight_average_kg") or body_result.get("latest_weight_kg")
    weight = float(weight) if weight else None
    protein_low = round(weight * 1.6) if weight else None
    protein_high = round(weight * 2.0) if weight else None
    easy_carb_low = round(weight * 2.5) if weight else None
    easy_carb_high = round(weight * 3.5) if weight else None
    hard_carb_low = round(weight * 4.0) if weight else None
    hard_carb_high = round(weight * 6.0) if weight else None

    logged_dates = {str(item.get("eaten_at", ""))[:10] for item in nutrition if item.get("eaten_at")}
    data_note = (
        f"近期开餐记录覆盖{len(logged_dates)}天，只能制定目标，暂不能判断你实际是否吃够。"
        if logged_dates else "尚无连续饮食记录，只能制定目标，不能评价实际摄入。"
    )
    today_easy = workout.get("intensity") in {"恢复", "低强度耐力"}
    protein_target = f"{protein_low}–{protein_high}克/天" if protein_low else "需体重数据"
    protein_plain = (
        f"这里的{protein_target}指食物中所含的‘蛋白质营养素’，不是称{protein_low}–{protein_high}克食物。"
        f"例如1个鸡蛋约含6–7克蛋白质；如果只靠鸡蛋达到{protein_low}克，约需{round(protein_low / 6.5)}个，"
        "不现实也不均衡，所以应由蛋、奶、鱼虾、瘦肉和豆制品共同完成。"
        if protein_low else "蛋白质目标指食物中所含的蛋白质营养素，不等于食物本身的重量。"
    )

    egg_count = 3
    fish_g = 160
    yogurt_g = 200
    milk_ml = 250
    fixed_protein = egg_count * 6.5 + 8 + 17 + fish_g * 0.22
    chicken_g = max(100, ceil(max(0, (protein_low or 0) - fixed_protein) / 0.30 / 10) * 10)
    main_food_protein = round(fixed_protein + chicken_g * 0.30)
    today_food_goal = (
        f"今天直接照这个吃：鸡蛋{egg_count}个 + 纯牛奶{milk_ml}毫升 + "
        f"熟鸡胸肉{chicken_g}克 + 无糖高蛋白酸奶{yogurt_g}克 + 熟鱼虾{fish_g}克。"
        f"这些主要蛋白质食物合计约{main_food_protein}克蛋白质，已达到{protein_target}的最低目标；"
        "燕麦、米饭等主食还会提供少量蛋白质。不是只吃鸡蛋，也不需要自己再换算。"
        if protein_low else "需要体重数据后才能换算今天具体吃多少。"
    )

    sample_total = "约1950–2150千卡、蛋白质约130–145克"
    if not today_easy:
        sample_total = "约2200–2450千卡、蛋白质约130–145克；额外热量主要来自训练前后主食"
    daily_menu = [
        {"meal": "早餐", "foods": f"鸡蛋{egg_count}个 + 纯牛奶{milk_ml}毫升 + 干燕麦50克 + 苹果1个", "estimate": "约570千卡；蛋白质约34克", "why": "蛋和奶补蛋白质，燕麦和水果补碳水化合物（身体训练时优先使用的能量来源）与膳食纤维。"},
        {"meal": "午餐", "foods": f"熟米饭200克（约1平碗） + 熟鸡胸肉{chicken_g}克（约1.3–1.5个手掌） + 蔬菜300克（约2拳） + 烹调油10克（约2平茶匙）", "estimate": f"约650–750千卡；蛋白质约{round(chicken_g * 0.30 + 5)}克", "why": "把肉和油称清楚，才能避免‘看着健康但油很多’；足量主食可支撑骑行，不必通过完全戒碳水减脂。"},
        {"meal": "加餐", "foods": f"无糖高蛋白酸奶{yogurt_g}克 + 香蕉1根", "estimate": "约220–300千卡；蛋白质约15–20克", "why": "用于减少晚餐前过度饥饿；训练前吃香蕉还能提供容易消化的碳水化合物。"},
        {"meal": "晚餐", "foods": (f"熟米饭150克（约3/4平碗） + 熟鱼虾{fish_g}克（约1.5–2个手掌） + 蔬菜300克 + 烹调油10克" if today_easy else f"熟米饭250克（约1.25平碗） + 熟鱼虾{fish_g}克（约1.5–2个手掌） + 蔬菜300克 + 烹调油10克；训练后可再加香蕉1根"), "estimate": ("约600–750千卡；蛋白质约35–40克" if today_easy else "约800–950千卡；蛋白质约35–40克"), "why": "鱼虾补足当天蛋白质；训练日增加主食，是为了恢复肌糖原（肌肉中储存的碳水能量），而不是奖励性暴食。"},
    ]
    return {
        "energy_strategy": "先制造每日约250–400千卡的温和热量缺口（摄入热量少于身体当天消耗的热量），目标是每周平均体重下降约0.2–0.4公斤。",
        "energy_reason": "为什么：减脂必须长期存在热量缺口，但缺口过大更容易饿、训练乏力并损失肌肉。每日少250–400千卡，一周约少1750–2800千卡，通常更容易兼顾减脂、骑行表现和坚持。体重会受水分影响，所以比较本周与上周均值，不根据某一天的涨跌突然挨饿。",
        "deficit_actions": [
            "先把全天烹调油控制在20–25克（约4–5平茶匙）；若原来每天多用20克油，仅这一项就可少约180千卡。",
            "含糖饮料改为水、无糖茶或零糖饮料；一瓶500毫升普通甜饮常可多出约180–250千卡。",
            "不取消正餐主食。休息/轻松骑日按上面的较小份量；质量课/长骑日把主食放在训练前后。",
            "连续2周看本周与上周平均体重：若每周下降不足0.2公斤，每天再减少约100–150千卡；若超过0.5公斤或训练明显乏力，每天加回约100–200千卡。",
        ],
        "protein_target": protein_target,
        "protein_explanation": protein_plain,
        "protein_distribution": "分3–4餐完成，每餐约25–40克蛋白质，比全部堆到晚餐更容易执行，也更利于全天维持肌肉蛋白合成（身体修复和建立肌肉组织的过程）。",
        "protein_portions": ["鸡蛋1个：约6–7克蛋白质；3个约19–20克。", "熟鸡胸肉100克：约30克蛋白质；熟瘦牛肉100克：约25–27克。", "熟鱼虾100克：约20–24克蛋白质。", "纯牛奶250毫升：约8克蛋白质；无糖高蛋白酸奶200克通常约15–20克，具体看包装营养成分表。", "北豆腐200克：约16–24克蛋白质，品牌和含水量不同会变化。"],
        "carb_target_easy": f"{easy_carb_low}–{easy_carb_high}克/天" if easy_carb_low else "需体重数据",
        "carb_target_hard": f"{hard_carb_low}–{hard_carb_high}克/天" if hard_carb_low else "需体重数据",
        "carb_explanation": "碳水化合物目标会随训练量变化：轻松日少一些，质量课和长骑日多一些，用来保障训练输出和训练后恢复。数字是营养素克数，不等于米饭重量。熟米饭100克通常约含25–26克碳水化合物。",
        "today": ("今天按轻松/恢复日吃：使用下方菜单的较小主食份量；若骑前明显饥饿，提前30–60分钟吃香蕉1根或吐司2片。" if today_easy else "今天按质量课/长骑日吃：训练前1–3小时吃熟米饭200克左右或面条1大碗；训练后按下方菜单完成恢复餐。"),
        "today_food_goal": today_food_goal,
        "sample_day_total": sample_total,
        "daily_menu": daily_menu,
        "during_ride": ["60分钟以内轻松骑：通常喝水即可。", "60–150分钟：每小时补30–60克碳水化合物，例如每小时香蕉1根（约25克）+运动饮料500毫升（约25–30克），或能量胶1包（常见约20–25克）+香蕉1根。", "超过150分钟或比赛模拟：先从每小时60克开始练肠胃耐受，不要第一次就直接吃到90克。", "饮水先以每小时500–750毫升为起点；炎热、大汗时补电解质（钠、钾等帮助维持体液平衡的矿物质），再按口渴和骑前后体重变化调整。"],
        "food_pattern": "川味可以保留辣椒、花椒、醋和香料；真正需要量化的是油和高脂配料。点外卖时优先选清蒸鱼、番茄牛肉、青椒肉丝少油版、麻辣烫清汤少油；回锅肉、水煮肉片、干锅和红油菜可少点，并把浮油留在碗里。",
        "data_note": data_note,
    }


def build_summary(
    activities: list[dict[str, Any]],
    sleep: list[dict[str, Any]],
    body: list[dict[str, Any]],
    daily_metrics: list[dict[str, Any]] | None = None,
    profile: dict[str, Any] | None = None,
    nutrition: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    profile = profile or {}
    metrics = daily_metrics or []
    nutrition = nutrition or []
    week_start = now - timedelta(days=7)
    month_start = now - timedelta(days=28)
    dated_activities = [
        (started_at, item)
        for item in activities
        if (started_at := _try_parse(item.get("start_date"))) is not None
        and started_at <= now
    ]
    dated_activities.sort(key=lambda pair: pair[0], reverse=True)
    recent = [item for started_at, item in dated_activities if started_at >= week_start]
    month = [item for started_at, item in dated_activities if started_at >= month_start]

    total_minutes = round(sum(max(0.0, _number(item.get("moving_time")) or 0) for item in recent) / 60)
    total_distance_km = round(
        sum(max(0.0, _number(item.get("distance")) or 0) for item in recent) / 1000,
        1,
    )
    total_elevation = round(
        sum(max(0.0, _number(item.get("total_elevation_gain")) or 0) for item in recent)
    )
    total_kj = round(
        sum(max(0.0, _number(item.get("kilojoules")) or 0) for item in recent)
    )

    sleep_values = [value for value in (_sleep_hours(item) for item in sleep[:7]) if value is not None]
    avg_sleep = mean(sleep_values) if sleep_values else None
    last_sleep = sleep_values[0] if sleep_values else None
    sleep_debt = sum(max(0.0, 7.0 - value) for value in sleep_values)

    observed_max_hr_values = [_number(item.get("max_heartrate")) for item in month]
    observed_max_hr_values = [value for value in observed_max_hr_values if value]
    observed_max_hr = max(observed_max_hr_values) if observed_max_hr_values else None
    resting_values = [_number(item.get("heart_rate_min")) for item in metrics[:14]]
    resting_values = [value for value in resting_values if value and value >= 30]
    resting_hr = median(resting_values) if resting_values else None

    acute_load = 0.0
    month_load = 0.0
    buckets = {"低有氧": 0, "中高有氧": 0, "高强度": 0, "强度未校准": 0}
    for item in month:
        load, bucket = _activity_load(item, observed_max_hr, resting_hr)
        month_load += load
        if item in recent:
            acute_load += load
            buckets[bucket] += 1
    chronic_weekly = month_load / 4 if month else 0
    load_ratio = acute_load / chronic_weekly if chronic_weekly > 0 else None

    latest_activity_at = dated_activities[0][0] if dated_activities else None
    days_since = (now - latest_activity_at).total_seconds() / 86400 if latest_activity_at else None
    low_recovery_reasons: list[str] = []
    if last_sleep is not None and last_sleep < 6:
        low_recovery_reasons.append(f"最近一晚仅睡{last_sleep:.1f}小时")
    if avg_sleep is not None and avg_sleep < 6.5:
        low_recovery_reasons.append(f"近7次睡眠平均{avg_sleep:.1f}小时")
    if load_ratio is not None and load_ratio > 1.5:
        low_recovery_reasons.append("近7天负荷明显高于近4周周均")

    if low_recovery_reasons:
        readiness = "恢复不足"
        intensity = "低强度耐力"
        workout_title = "低强度耐力 + 踏频技术"
        workout_steps = [
            "热身10分钟：RPE（主观用力程度，0–10分）2–3分，轻档逐步提高踏频。",
            "主训练30–40分钟：RPE（主观用力程度，0–10分）3–4分，能完整说句子；优先保持80–90 rpm（每分钟踩踏转数），不追速度。",
            "状态正常可做4×30秒高踏频：95–105 rpm（每分钟踩踏转数），组间轻松90秒；不是冲刺。",
            "冷身10分钟：逐步降低功率和心率。",
        ]
        rationale = "恢复指标不足时先保留有氧刺激和动作质量，不用高强度去补偿错过的训练。"
    elif days_since is not None and days_since < 2 and load_ratio is not None and load_ratio >= 1.1:
        readiness = "一般"
        intensity = "恢复"
        workout_title = "恢复骑或完全休息"
        workout_steps = [
            "任选30–45分钟非常轻松骑，RPE（主观用力程度，0–10分）2分，全程可自然交谈。",
            "保持轻档和85–95 rpm（每分钟踩踏转数），避免爬坡发力、冲刺和拉扯。",
            "若双腿沉重、静息心率异常或精神疲惫，直接休息。",
        ]
        rationale = "近期训练刺激已经足够，今天的目标是促进恢复而不是增加负荷。"
    else:
        readiness = "可训练"
        intensity = "节奏"
        workout_title = "有氧节奏能力"
        workout_steps = [
            "热身15分钟：最后加入3×30秒高踏频，组间轻松60秒。",
            "主训练3×8分钟：RPE（主观用力程度，0–10分）6分，呼吸加深但可说短句；组间轻松4分钟。",
            "随后10–20分钟轻松耐力骑，RPE（主观用力程度，0–10分）3–4分。",
            "冷身10分钟。若第二组已无法稳定输出，取消第三组。",
        ]
        rationale = "在没有可靠FTP（功能性阈值功率）和乳酸阈心率前，用RPE（主观用力程度）与说话测试控制强度，避免伪精确功率区间。"

    workout = {
        "title": workout_title,
        "intensity": intensity,
        "duration": "50–70分钟" if intensity != "恢复" else "0–45分钟",
        "readiness": readiness,
        "steps": workout_steps,
        "rationale": rationale,
        "stop_rule": "出现胸痛、异常气短、眩晕、心悸或明显不适应立即停止；持续异常应寻求医疗评估。",
    }


    if readiness == "恢复不足":
        decision_explanation = ["数据：" + "；".join(low_recovery_reasons) + "。", "判断：恢复资源不足时，高强度训练更难完成，动作质量也更容易下降。", "安排：保留低强度有氧和踏频练习，取消今天的高强度间歇。", "目的：维持训练连续性，同时避免继续累积疲劳；睡眠恢复后再做质量课，比硬撑更有效。"]
    elif readiness == "一般":
        decision_explanation = [f"数据：最近一次活动距今约{days_since:.1f}天，近7天负荷/近4周周均负荷约为{load_ratio:.2f}。", "判断：近期刺激已经不低，今天继续加量的收益较小，恢复不足的风险更高。", "安排：30–45分钟非常轻松骑，或根据腿部和精神状态完全休息。", "目的：让肌肉、神经和能量储备恢复，为下一次质量课腾出空间。"]
    else:
        known_data = []
        if avg_sleep is not None: known_data.append(f"近7次睡眠平均{avg_sleep:.1f}小时")
        if load_ratio is not None: known_data.append(f"近7天负荷/近4周周均负荷约{load_ratio:.2f}")
        if days_since is not None: known_data.append(f"距上次活动约{days_since:.1f}天")
        decision_explanation = ["数据：" + ("；".join(known_data) if known_data else "睡眠或历史负荷数据不足，未发现必须降级的信号") + "。", "判断：当前可以安排一次中等偏上的有氧节奏刺激，但不具备精确划分功率区间的条件。", "安排：做3组×8分钟可说短句的节奏训练，组间充分轻松恢复。", "目的：提高持续输出能力；用主观用力程度和说话测试限强度，避免因缺少阈值测试而练得过猛。"]

    body_result = _body_analysis(body, profile, now)
    nutrition_plan = _nutrition_plan(body_result, nutrition, workout)

    observations = [
        f"过去7天记录{len(recent)}段活动，共{total_minutes}分钟、{total_distance_km}公里、爬升{total_elevation}米。",
    ]
    if total_kj:
        observations.append(f"功率计记录的机械功约{total_kj}千焦，可用于比较骑行负荷，但不直接等同于应吃回的热量。")
    if avg_sleep is not None:
        observations.append(f"近7次睡眠平均{avg_sleep:.1f}小时，按7小时最低目标累计缺口约{sleep_debt:.1f}小时。")
    else:
        observations.append("没有可用睡眠数据，恢复判断置信度较低。")
    if body_result.get("weight_average_kg"):
        if body_result.get("body_fat_pct") is not None:
            observations.append(
                f"\u8fd1\u671f\u5e73\u5747\u4f53\u91cd{body_result['weight_average_kg']:.1f}\u516c\u65a4\uff0c\u4f53\u8102\u8d8b\u52bf\u7ea6{body_result['body_fat_pct']:.1f}%\u3002"
            )
        else:
            observations.append(
                f"\u8fd1\u671f\u5e73\u5747\u4f53\u91cd{body_result['weight_average_kg']:.1f}\u516c\u65a4\uff1b\u7f3a\u5c11\u53ef\u7528\u4f53\u8102\u6570\u636e\u3002"
            )

    suggestions = [
        f"今日课表：{workout_title}，{workout['duration']}；{rationale}",
        nutrition_plan["today"],
    ]
    if readiness == "恢复不足":
        suggestions.insert(0, "近期睡眠偏少，今天不建议安排高强度间歇训练。")

    gaps: list[str] = []
    if not profile.get("sex") or not profile.get("height_cm") or not profile.get("age"):
        gaps.append("用户档案不完整：性别、年龄、身高会影响体脂解释和能量估算。")
    if observed_max_hr is None:
        gaps.append("缺少可靠最大心率；当前不会生成心率区间。")
    else:
        gaps.append(f"最高记录心率{observed_max_hr:.0f}仅为历史观测值，不视为实验室测得最大心率。")
    gaps.append("缺少FTP（功能性阈值功率）/阈值功率测试，因此课表使用RPE（主观用力程度）和说话测试，不伪造功率区间。")
    if len({str(item.get('eaten_at', ''))[:10] for item in nutrition}) < 3:
        gaps.append("饮食日志不足3天，无法评价真实能量和营养摄入。")

    return {
        "period": "最近7天",
        "method_version": "可解释自适应骑行教练 v1",
        "training": {
            "activity_count": len(recent),
            "minutes": total_minutes,
            "distance_km": total_distance_km,
            "elevation_m": total_elevation,
            "kilojoules": total_kj,
            "acute_load": round(acute_load),
            "chronic_weekly_load": round(chronic_weekly),
            "load_ratio": round(load_ratio, 2) if load_ratio is not None else None,
            "intensity_distribution": buckets,
        },
        "readiness": {
            "status": readiness,
            "reasons": low_recovery_reasons or ["睡眠与近期训练负荷未触发降级规则"],
            "confidence": "中" if sleep_values and activities else "低",
        },
        "workout": workout,
        "decision_explanation": decision_explanation,
        "body_composition": body_result,
        "nutrition": nutrition_plan,
        "weekly_framework": [
            "每周1次质量课：节奏/阈值或短间歇，前提是睡眠和双腿状态正常。",
            "每周2次低强度耐力或恢复骑，承担大部分训练时间。",
            "每周1次逐步延长的长距离骑；总量通常每周只增加5%–10%，疲劳周不增加。",
            "至少1天完全休息；连续2–3周增加后安排1周减量。",
        ],
        "observations": observations,
        "suggestions": suggestions,
        "data_gaps": gaps,
        "method_note": "借鉴佳明公开的恢复、近期负荷、训练重点和自适应课表思路；本实现使用公开、可解释的代理指标，不复制或声称等同于佳明专有算法。",
        "glossary": [
            "RPE（主观用力程度）：用0–10分描述自己感觉有多累，0分为休息，10分为极限。",
            "FTP（功能性阈值功率）：约代表可持续接近1小时的最高平均骑行功率，需要专门测试，当前没有就不编造。",
            "EPOC（运动后过量氧耗）：运动结束后身体恢复过程中额外消耗氧气的现象。",
            "肌糖原：储存在肌肉里的碳水化合物能量，骑行时间长或强度高时会被大量使用。",
            "热量缺口：一天摄入的热量少于身体消耗的热量，是体脂下降的必要条件。",
        ],
        "disclaimer": "内容用于运动与体重管理，不替代医生、注册营养师或持证教练的个体化评估。",
    }
