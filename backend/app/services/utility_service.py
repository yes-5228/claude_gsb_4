"""水电抄表记录业务逻辑。

核心规则：
- 用量 = 本期读数 - 上期读数；费用 = 用量 × 单价；环比 = 与上一自然月用量的增减百分比。
- 环比超出 ±UTILITY_ALERT_THRESHOLD_PERCENT 或用量为零时判定异常，并按表计类型与涨降方向
  生成可能原因提示。
- 上一自然月记录的新增/修改/删除会联动重算本月记录（上期读数为自动带出时一并刷新）。
"""

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.constants import METER_TYPE_UNITS, UTILITY_ALERT_THRESHOLD_PERCENT, MeterType
from app.core.exceptions import ConflictError, DomainError, NotFoundError
from app.models import Restroom, UtilityReading
from app.schemas.utility import (
    UtilityReadingCreate,
    UtilityReadingOut,
    UtilityReadingUpdate,
    UtilitySummaryOut,
)
from app.services import restroom_service

SORTABLE_FIELDS = {
    "period": UtilityReading.period,
    "usage": UtilityReading.usage,
    "fee": UtilityReading.fee,
    "change_pct": UtilityReading.change_pct,
    "created_at": UtilityReading.created_at,
}


def prev_period(period: str) -> str:
    """上一自然月，如 2026-01 -> 2025-12。"""
    year, month = int(period[:4]), int(period[5:7])
    month -= 1
    if month == 0:
        year, month = year - 1, 12
    return f"{year:04d}-{month:02d}"


def next_period(period: str) -> str:
    """下一自然月，如 2025-12 -> 2026-01。"""
    year, month = int(period[:4]), int(period[5:7])
    month += 1
    if month == 13:
        year, month = year + 1, 1
    return f"{year:04d}-{month:02d}"


def get_reading(db: Session, reading_id: int) -> UtilityReading:
    reading = db.get(UtilityReading, reading_id)
    if reading is None:
        raise NotFoundError(f"抄表记录 {reading_id} 不存在")
    return reading


def to_out(reading: UtilityReading) -> UtilityReadingOut:
    return UtilityReadingOut.model_validate(reading)


def _find_by_month(
    db: Session, restroom_id: int, meter_type: str, period: str
) -> UtilityReading | None:
    return db.scalars(
        select(UtilityReading).where(
            UtilityReading.restroom_id == restroom_id,
            UtilityReading.meter_type == meter_type,
            UtilityReading.period == period,
        )
    ).first()


def _evaluate(
    meter_type: str, usage: float | None, prev_usage: float | None, change_pct: float | None
) -> tuple[bool, list[str]]:
    """根据用量与环比生成异常判定与可能原因。"""
    if usage is None:
        return False, []
    unit = METER_TYPE_UNITS.get(meter_type, "")
    if usage == 0:
        return True, [
            f"本期{meter_type}用量为零：可能漏抄表、表计故障停走，或公厕当月停用，"
            "请核对抄表读数与表计运行状态"
        ]
    if prev_usage == 0:
        return True, [
            f"上月{meter_type}用量为零，本期突增 {usage:g}{unit}："
            "可能上月漏抄或表计故障，请核对两期抄表记录"
        ]
    if change_pct is None:
        return False, []

    threshold = UTILITY_ALERT_THRESHOLD_PERCENT
    if change_pct > threshold:
        if meter_type == MeterType.WATER:
            reason = (
                f"用水量环比增加 {change_pct:g}%：可能存在水箱、水龙头长流水或地下管网漏水，"
                "或人流量明显增大；也不排除抄表读数录入有误，建议现场排查漏水点并核对读数"
            )
        else:
            reason = (
                f"用电量环比增加 {change_pct:g}%：可能照明、排风、热水器等设备长时间运行或新增用电设备，"
                "也可能存在线路漏电或抄表错误，建议核查设备运行状态并核对读数"
            )
        return True, [reason]
    if change_pct < -threshold:
        if meter_type == MeterType.WATER:
            reason = (
                f"用水量环比减少 {abs(change_pct):g}%：可能水表故障停走、公厕限流或关停，"
                "或存在漏抄、估抄，建议核对水表运行状态"
            )
        else:
            reason = (
                f"用电量环比减少 {abs(change_pct):g}%：可能电表故障、设备停用或漏抄，"
                "建议核对电表与用电设备运行状态"
            )
        return True, [reason]
    return False, []


def _recalculate(db: Session, reading: UtilityReading) -> None:
    """根据当前字段与上一自然月记录，重算用量、费用、环比与异常标记（不提交）。"""
    prev = _find_by_month(db, reading.restroom_id, reading.meter_type, prev_period(reading.period))
    if reading.prev_reading_auto:
        reading.prev_reading = prev.reading if prev is not None else None

    if reading.prev_reading is None:
        # 首次抄表，无基期
        reading.usage = None
        reading.fee = None
        reading.change_pct = None
        reading.is_abnormal = False
        reading.abnormal_reasons = []
        return

    usage = round(reading.reading - reading.prev_reading, 2)
    if usage < 0:
        raise DomainError(
            f"本期读数 {reading.reading:g} 低于上期读数 {reading.prev_reading:g}，"
            "请核对抄表读数（如遇换表请修正上期读数）"
        )
    reading.usage = usage
    reading.fee = round(usage * reading.unit_price, 2)

    prev_usage = prev.usage if prev is not None else None
    if prev_usage:
        reading.change_pct = round((usage - prev_usage) / prev_usage * 100, 1)
    else:
        # 无上一月记录，或上月用量为零（除零无意义，由异常原因提示）
        reading.change_pct = None
    reading.is_abnormal, reading.abnormal_reasons = _evaluate(
        reading.meter_type, usage, prev_usage, reading.change_pct
    )


def _recalculate_successor(db: Session, reading: UtilityReading) -> None:
    """联动重算下一自然月记录（存在时）。"""
    successor = _find_by_month(
        db, reading.restroom_id, reading.meter_type, next_period(reading.period)
    )
    if successor is not None:
        _recalculate(db, successor)


def _ensure_unique(
    db: Session, restroom_id: int, meter_type: str, period: str, exclude_id: int | None = None
) -> None:
    existing = _find_by_month(db, restroom_id, meter_type, period)
    if existing is not None and existing.id != exclude_id:
        raise ConflictError(f"该公厕 {period} 的{meter_type}已存在抄表记录，请勿重复登记")


def list_readings(
    db: Session,
    *,
    restroom_id: int | None = None,
    district: str | None = None,
    meter_type: str | None = None,
    period_from: str | None = None,
    period_to: str | None = None,
    abnormal_only: bool = False,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 10,
    sort_by: str = "period",
    order: str = "desc",
) -> tuple[list[UtilityReading], int]:
    stmt = select(UtilityReading)
    if district or keyword:
        stmt = stmt.join(Restroom, Restroom.id == UtilityReading.restroom_id)
    if district:
        stmt = stmt.where(Restroom.district == district)
    if keyword:
        like = f"%{keyword.strip()}%"
        stmt = stmt.where(or_(Restroom.name.like(like), Restroom.code.like(like)))
    if restroom_id:
        stmt = stmt.where(UtilityReading.restroom_id == restroom_id)
    if meter_type:
        stmt = stmt.where(UtilityReading.meter_type == meter_type)
    if period_from:
        stmt = stmt.where(UtilityReading.period >= period_from)
    if period_to:
        stmt = stmt.where(UtilityReading.period <= period_to)
    if abnormal_only:
        stmt = stmt.where(UtilityReading.is_abnormal.is_(True))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    column = SORTABLE_FIELDS.get(sort_by, UtilityReading.period)
    stmt = stmt.order_by(
        column.desc() if order == "desc" else column.asc(),
        UtilityReading.meter_type,
        UtilityReading.id.desc(),
    )
    rows = list(db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)))
    return rows, total


def create_reading(db: Session, payload: UtilityReadingCreate) -> UtilityReading:
    restroom_service.get_restroom(db, payload.restroom_id)
    meter_type = payload.meter_type.value if hasattr(payload.meter_type, "value") else payload.meter_type
    _ensure_unique(db, payload.restroom_id, meter_type, payload.period)
    reading = UtilityReading(
        restroom_id=payload.restroom_id,
        meter_type=meter_type,
        period=payload.period,
        reading=payload.reading,
        prev_reading=payload.prev_reading,
        prev_reading_auto=payload.prev_reading is None,
        unit_price=payload.unit_price,
        remark=payload.remark,
    )
    _recalculate(db, reading)
    db.add(reading)
    _recalculate_successor(db, reading)
    db.commit()
    db.refresh(reading)
    restroom_service.touch(db, payload.restroom_id)
    return reading


def update_reading(
    db: Session, reading_id: int, payload: UtilityReadingUpdate
) -> UtilityReading:
    reading = get_reading(db, reading_id)
    data = payload.model_dump(exclude_unset=True)
    old_period = reading.period

    if data.get("period") and payload.period != reading.period:
        _ensure_unique(db, reading.restroom_id, reading.meter_type, payload.period, exclude_id=reading.id)
        reading.period = payload.period
    if data.get("reading") is not None:
        reading.reading = payload.reading
    if "prev_reading" in data:
        # 显式传 null 表示恢复自动带出
        reading.prev_reading = payload.prev_reading
        reading.prev_reading_auto = payload.prev_reading is None
    if data.get("unit_price") is not None:
        reading.unit_price = payload.unit_price
    if "remark" in data:
        reading.remark = payload.remark

    _recalculate(db, reading)
    _recalculate_successor(db, reading)
    if old_period != reading.period:
        # 月份被修改，原月份的后继记录也需按新基期重算
        successor = _find_by_month(
            db, reading.restroom_id, reading.meter_type, next_period(old_period)
        )
        if successor is not None and successor.id != reading.id:
            _recalculate(db, successor)
    db.commit()
    db.refresh(reading)
    restroom_service.touch(db, reading.restroom_id)
    return reading


def delete_reading(db: Session, reading_id: int) -> None:
    reading = get_reading(db, reading_id)
    restroom_id = reading.restroom_id
    successor = _find_by_month(
        db, reading.restroom_id, reading.meter_type, next_period(reading.period)
    )
    db.delete(reading)
    db.flush()
    if successor is not None:
        _recalculate(db, successor)
    db.commit()
    restroom_service.touch(db, restroom_id)


def _period_totals(db: Session, period: str, meter_type: str, restroom_id: int | None) -> tuple[float, float]:
    stmt = select(
        func.coalesce(func.sum(UtilityReading.usage), 0.0),
        func.coalesce(func.sum(UtilityReading.fee), 0.0),
    ).where(
        UtilityReading.period == period,
        UtilityReading.meter_type == meter_type,
    )
    if restroom_id:
        stmt = stmt.where(UtilityReading.restroom_id == restroom_id)
    usage, fee = db.execute(stmt).one()
    return round(float(usage), 2), round(float(fee), 2)


def summarize(db: Session, period: str | None = None, restroom_id: int | None = None) -> UtilitySummaryOut:
    """汇总某一月份（缺省取有记录的最新月份）的水电用量、费用与环比。"""
    if not period:
        stmt = select(func.max(UtilityReading.period))
        if restroom_id:
            stmt = stmt.where(UtilityReading.restroom_id == restroom_id)
        period = db.scalar(stmt)
    if not period:
        return UtilitySummaryOut(
            period="",
            water_usage=0.0,
            water_fee=0.0,
            electricity_usage=0.0,
            electricity_fee=0.0,
        )

    water_usage, water_fee = _period_totals(db, period, MeterType.WATER.value, restroom_id)
    elec_usage, elec_fee = _period_totals(db, period, MeterType.ELECTRICITY.value, restroom_id)
    prev_water, _ = _period_totals(db, prev_period(period), MeterType.WATER.value, restroom_id)
    prev_elec, _ = _period_totals(db, prev_period(period), MeterType.ELECTRICITY.value, restroom_id)

    count_stmt = select(func.count()).select_from(UtilityReading).where(
        UtilityReading.period == period
    )
    abnormal_stmt = (
        select(func.count())
        .select_from(UtilityReading)
        .where(UtilityReading.period == period, UtilityReading.is_abnormal.is_(True))
    )
    if restroom_id:
        count_stmt = count_stmt.where(UtilityReading.restroom_id == restroom_id)
        abnormal_stmt = abnormal_stmt.where(UtilityReading.restroom_id == restroom_id)
    reading_count = db.scalar(count_stmt) or 0
    abnormal_count = db.scalar(abnormal_stmt) or 0

    return UtilitySummaryOut(
        period=period,
        reading_count=reading_count,
        abnormal_count=abnormal_count,
        water_usage=water_usage,
        water_fee=water_fee,
        water_change_pct=round((water_usage - prev_water) / prev_water * 100, 1)
        if prev_water
        else None,
        electricity_usage=elec_usage,
        electricity_fee=elec_fee,
        electricity_change_pct=round((elec_usage - prev_elec) / prev_elec * 100, 1)
        if prev_elec
        else None,
    )
