"""水电月度抄表业务逻辑。

用量 = 本期表底 − 上一条记录表底（按时间向前寻找最近的已抄表记录，跨月顺延）；
费用默认 = 用量 × 建账时单价快照，可手工锁定；环比与异常结论在每次写入后整座公厕
按账期顺序重算，因此修改或删除历史月份会自动向后链式修正。
"""

from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import (
    ELEC_CHANGE_FLOOR_KWH,
    ELEC_UNIT,
    UTILITY_CHANGE_THRESHOLD,
    UTILITY_OVERALL_ABNORMAL,
    UTILITY_OVERALL_NORMAL,
    UTILITY_REASONS,
    UTILITY_STATUS_HIGH,
    UTILITY_STATUS_LOW,
    UTILITY_STATUS_NORMAL,
    WATER_CHANGE_FLOOR_TONS,
    WATER_UNIT,
)
from app.core.exceptions import DomainError, NotFoundError
from app.models import Restroom, UtilityRecord
from app.schemas.utility import (
    UtilityBaselineOut,
    UtilityRecordCreate,
    UtilityRecordOut,
    UtilityRecordUpdate,
)
from app.services import restroom_service

# 字段前缀 -> (用量单位, 绝对变化门槛, 单价属性)
_KINDS = {
    "water": (WATER_UNIT, WATER_CHANGE_FLOOR_TONS, "water_unit_price"),
    "elec": (ELEC_UNIT, ELEC_CHANGE_FLOOR_KWH, "elec_unit_price"),
}

SORTABLE_FIELDS = {
    "recorded_at": UtilityRecord.recorded_at,
    "reader": UtilityRecord.reader,
    "created_at": UtilityRecord.created_at,
}


def get_utility_record(db: Session, record_id: int) -> UtilityRecord:
    record = db.get(UtilityRecord, record_id)
    if record is None:
        raise NotFoundError(f"水电记录 {record_id} 不存在")
    return record


def to_out(record: UtilityRecord) -> UtilityRecordOut:
    return UtilityRecordOut.model_validate(record)


def _period_label(year: int, month: int) -> str:
    return f"{year}年{month}月"


def _exists(db: Session, restroom_id: int, year: int, month: int) -> bool:
    return bool(
        db.scalar(
            select(UtilityRecord.id).where(
                UtilityRecord.restroom_id == restroom_id,
                UtilityRecord.period_year == year,
                UtilityRecord.period_month == month,
            )
        )
    )


def list_utility_records(
    db: Session,
    *,
    restroom_id: int | None = None,
    district: str | None = None,
    period_year: int | None = None,
    period_month: int | None = None,
    abnormal: bool | None = None,
    reader: str | None = None,
    page: int = 1,
    page_size: int = 10,
    sort_by: str = "period",
    order: str = "desc",
) -> tuple[list[UtilityRecord], int]:
    stmt = select(UtilityRecord)
    if district:
        stmt = stmt.join(Restroom, Restroom.id == UtilityRecord.restroom_id).where(
            Restroom.district == district
        )
    if restroom_id:
        stmt = stmt.where(UtilityRecord.restroom_id == restroom_id)
    if period_year is not None:
        stmt = stmt.where(UtilityRecord.period_year == period_year)
    if period_month is not None:
        stmt = stmt.where(UtilityRecord.period_month == period_month)
    if abnormal is True:
        stmt = stmt.where(UtilityRecord.status == UTILITY_OVERALL_ABNORMAL)
    elif abnormal is False:
        stmt = stmt.where(UtilityRecord.status == UTILITY_OVERALL_NORMAL)
    if reader:
        stmt = stmt.where(UtilityRecord.reader.like(f"%{reader.strip()}%"))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    descending = order == "desc"
    if sort_by == "period":
        stmt = stmt.order_by(
            UtilityRecord.period_year.desc() if descending else UtilityRecord.period_year.asc(),
            UtilityRecord.period_month.desc() if descending else UtilityRecord.period_month.asc(),
            UtilityRecord.id.desc(),
        )
    else:
        column = SORTABLE_FIELDS.get(sort_by, UtilityRecord.recorded_at)
        stmt = stmt.order_by(column.desc() if descending else column.asc(), UtilityRecord.id.desc())
    rows = list(db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)))
    return rows, total


def _evaluate_kind(
    *,
    kind: str,
    usage: float | None,
    last_usage: float | None,
    reading_decreased: bool,
) -> tuple[float | None, float | None, str, list[str]]:
    """返回 (环比增减量, 环比百分比, 判定状态, 可能原因)。"""
    floor = _KINDS[kind][1]
    if usage is None:
        return None, None, UTILITY_STATUS_NORMAL, []

    # 表底回退导致负用量：换表归零/抄录错误，独立于是否存在上月用量基准，优先判定
    if reading_decreased or usage < 0:
        amount = round(usage - last_usage, 2) if last_usage is not None else None
        pct = (
            round((usage - last_usage) / last_usage * 100, 1)
            if last_usage is not None and last_usage > 0
            else None
        )
        return amount, pct, UTILITY_STATUS_LOW, list(UTILITY_REASONS[f"{kind}_rollback"])

    # 首个用量为正的可比月份，没有上月用量可对比
    if last_usage is None:
        return None, None, UTILITY_STATUS_NORMAL, []

    amount = round(usage - last_usage, 2)
    pct = round((usage - last_usage) / last_usage * 100, 1) if last_usage > 0 else None

    if pct is not None and pct > UTILITY_CHANGE_THRESHOLD * 100 and abs(amount) > floor:
        return amount, pct, UTILITY_STATUS_HIGH, list(UTILITY_REASONS[f"{kind}_high"])
    if (pct is not None and pct < -UTILITY_CHANGE_THRESHOLD * 100 and abs(amount) > floor) or (
        pct is None and amount < -floor
    ):
        # 表底仍在增长，只是用量较上月明显回落
        return amount, pct, UTILITY_STATUS_LOW, list(UTILITY_REASONS[f"{kind}_low"])
    return amount, pct, UTILITY_STATUS_NORMAL, []


def recompute_restroom(db: Session, restroom_id: int) -> None:
    """按账期顺序重算该公厕全部记录的用量、费用、环比与异常结论。"""
    rows = list(
        db.scalars(
            select(UtilityRecord)
            .where(UtilityRecord.restroom_id == restroom_id)
            .order_by(
                UtilityRecord.period_year.asc(),
                UtilityRecord.period_month.asc(),
                UtilityRecord.id.asc(),
            )
        )
    )

    # 各能源独立维护“最近一次有效表底/用量”，跨月或缺抄月份顺延
    last_reading = {"water": None, "elec": None}
    last_usage = {"water": None, "elec": None}

    for record in rows:
        for kind, (_unit, _floor, price_attr) in _KINDS.items():
            reading = getattr(record, f"{kind}_reading")
            prev_reading = last_reading[kind]

            reading_decreased = (
                reading is not None and prev_reading is not None and reading < prev_reading
            )
            usage = (
                None
                if reading is None or prev_reading is None
                else round(reading - prev_reading, 2)
            )

            # 费用：手工锁定则原样保留；用量为零/表底回退时按 0 计，不计负费用
            locked = getattr(record, f"{kind}_fee_locked")
            if locked:
                pass
            elif usage is None or usage <= 0:
                setattr(record, f"{kind}_fee", None if usage is None else 0.0)
            else:
                snapshot = getattr(record, price_attr)
                price = snapshot if snapshot is not None else getattr(settings, f"{kind}_unit_price")
                setattr(record, f"{kind}_fee", round(usage * price, 2))

            amount, pct, status, reasons = _evaluate_kind(
                kind=kind,
                usage=usage,
                last_usage=last_usage[kind],
                reading_decreased=reading_decreased,
            )
            setattr(record, f"{kind}_usage", usage)
            setattr(record, f"{kind}_change_amount", amount)
            setattr(record, f"{kind}_change_pct", pct)
            setattr(record, f"{kind}_status", status)
            setattr(record, f"{kind}_reasons", reasons)

            # 表底始终顺延（换表归零后按新表底计差）；负用量不作为下月环比基准
            if reading is not None:
                last_reading[kind] = reading
            if usage is not None and usage >= 0:
                last_usage[kind] = usage

        record.status = (
            UTILITY_OVERALL_ABNORMAL
            if record.water_status != UTILITY_STATUS_NORMAL
            or record.elec_status != UTILITY_STATUS_NORMAL
            else UTILITY_OVERALL_NORMAL
        )

    db.commit()


def create_utility_record(db: Session, payload: UtilityRecordCreate) -> UtilityRecord:
    restroom_service.get_restroom(db, payload.restroom_id)
    if _exists(db, payload.restroom_id, payload.period_year, payload.period_month):
        raise DomainError(
            f"该公厕{_period_label(payload.period_year, payload.period_month)}的水电记录已存在"
        )

    record = UtilityRecord(
        restroom_id=payload.restroom_id,
        period_year=payload.period_year,
        period_month=payload.period_month,
        recorded_at=payload.recorded_at or datetime.now(),
        reader=payload.reader,
        water_reading=payload.water_reading,
        elec_reading=payload.elec_reading,
        remark=payload.remark,
    )
    # 单价在建账时快照；手工费用直接锁定
    if payload.water_reading is not None:
        record.water_unit_price = settings.water_unit_price
        if not payload.water_fee_auto:
            record.water_fee = round(payload.water_fee, 2)
            record.water_fee_locked = True
    if payload.elec_reading is not None:
        record.elec_unit_price = settings.elec_unit_price
        if not payload.elec_fee_auto:
            record.elec_fee = round(payload.elec_fee, 2)
            record.elec_fee_locked = True

    db.add(record)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise DomainError(
            f"该公厕{_period_label(payload.period_year, payload.period_month)}的水电记录已存在"
        ) from None
    db.refresh(record)
    recompute_restroom(db, record.restroom_id)
    restroom_service.touch(db, record.restroom_id)
    return get_utility_record(db, record.id)


def update_utility_record(
    db: Session, record_id: int, payload: UtilityRecordUpdate
) -> UtilityRecord:
    record = get_utility_record(db, record_id)
    data = payload.model_dump(exclude_unset=True)

    if data.get("reader") is not None:
        record.reader = payload.reader
    if data.get("recorded_at") is not None and payload.recorded_at is not None:
        record.recorded_at = payload.recorded_at
    if "remark" in data:
        record.remark = payload.remark

    if payload.water_reading is not None:
        record.water_reading = payload.water_reading
    if payload.elec_reading is not None:
        record.elec_reading = payload.elec_reading

    # 此前未抄表时单价快照为空，补拍当前默认单价
    if record.water_reading is not None and record.water_unit_price is None:
        record.water_unit_price = settings.water_unit_price
    if record.elec_reading is not None and record.elec_unit_price is None:
        record.elec_unit_price = settings.elec_unit_price

    # 费用模式：False + 金额 -> 锁定；True -> 解锁并按单价重算
    if payload.water_fee_auto is False and payload.water_fee is not None:
        record.water_fee = round(payload.water_fee, 2)
        record.water_fee_locked = True
    elif payload.water_fee_auto is True:
        record.water_fee_locked = False
        record.water_fee = None
        record.water_unit_price = settings.water_unit_price
    if payload.elec_fee_auto is False and payload.elec_fee is not None:
        record.elec_fee = round(payload.elec_fee, 2)
        record.elec_fee_locked = True
    elif payload.elec_fee_auto is True:
        record.elec_fee_locked = False
        record.elec_fee = None
        record.elec_unit_price = settings.elec_unit_price

    db.commit()
    recompute_restroom(db, record.restroom_id)
    restroom_service.touch(db, record.restroom_id)
    return get_utility_record(db, record.id)


def delete_utility_record(db: Session, record_id: int) -> None:
    record = get_utility_record(db, record_id)
    restroom_id = record.restroom_id
    db.delete(record)
    db.commit()
    recompute_restroom(db, restroom_id)
    restroom_service.touch(db, restroom_id)


def get_baseline(
    db: Session, restroom_id: int, year: int, month: int
) -> UtilityBaselineOut:
    restroom_service.get_restroom(db, restroom_id)
    previous = db.scalars(
        select(UtilityRecord)
        .where(
            UtilityRecord.restroom_id == restroom_id,
            or_(
                UtilityRecord.period_year < year,
                (UtilityRecord.period_year == year) & (UtilityRecord.period_month < month),
            ),
        )
        .order_by(UtilityRecord.period_year.desc(), UtilityRecord.period_month.desc())
        .limit(1)
    ).first()
    return UtilityBaselineOut(
        exists=_exists(db, restroom_id, year, month),
        prev_year=previous.period_year if previous else None,
        prev_month=previous.period_month if previous else None,
        water_reading=previous.water_reading if previous else None,
        water_usage=previous.water_usage if previous else None,
        elec_reading=previous.elec_reading if previous else None,
        elec_usage=previous.elec_usage if previous else None,
        water_unit_price=settings.water_unit_price,
        elec_unit_price=settings.elec_unit_price,
    )
