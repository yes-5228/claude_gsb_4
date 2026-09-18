"""水电抄表记录接口。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import PaginationDep, build_meta
from app.core.database import get_db
from app.schemas.common import MessageOut, Page
from app.schemas.utility import (
    PERIOD_PATTERN,
    UtilityReadingCreate,
    UtilityReadingOut,
    UtilityReadingUpdate,
    UtilitySummaryOut,
)
from app.services import utility_service

router = APIRouter(prefix="/utilities", tags=["水电计量"])

PeriodQuery = Annotated[str | None, Query(pattern=PERIOD_PATTERN, description="月份，格式 YYYY-MM")]


@router.get("", response_model=Page[UtilityReadingOut], summary="抄表记录列表")
def list_readings(
    db: Annotated[Session, Depends(get_db)],
    pagination: PaginationDep,
    restroom_id: Annotated[int | None, Query(description="按公厕过滤")] = None,
    district: Annotated[str | None, Query(description="按区域过滤")] = None,
    meter_type: Annotated[str | None, Query(description="表计类型：水表/电表")] = None,
    period_from: PeriodQuery = None,
    period_to: PeriodQuery = None,
    abnormal_only: Annotated[bool, Query(description="仅看异常记录")] = False,
    keyword: Annotated[str | None, Query(description="公厕名称/编号模糊搜索")] = None,
    sort_by: Annotated[str, Query(description="排序字段")] = "period",
    order: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
) -> Page[UtilityReadingOut]:
    rows, total = utility_service.list_readings(
        db,
        restroom_id=restroom_id,
        district=district,
        meter_type=meter_type,
        period_from=period_from,
        period_to=period_to,
        abnormal_only=abnormal_only,
        keyword=keyword,
        page=pagination.page,
        page_size=pagination.page_size,
        sort_by=sort_by,
        order=order,
    )
    return Page[UtilityReadingOut](
        items=[utility_service.to_out(row) for row in rows],
        meta=build_meta(total, pagination),
    )


@router.get("/summary", response_model=UtilitySummaryOut, summary="月度水电汇总")
def get_summary(
    db: Annotated[Session, Depends(get_db)],
    period: PeriodQuery = None,
    restroom_id: Annotated[int | None, Query(description="按公厕过滤")] = None,
) -> UtilitySummaryOut:
    return utility_service.summarize(db, period, restroom_id=restroom_id)


@router.post("", response_model=UtilityReadingOut, status_code=201, summary="新增抄表记录")
def create_reading(
    payload: UtilityReadingCreate, db: Annotated[Session, Depends(get_db)]
) -> UtilityReadingOut:
    return utility_service.to_out(utility_service.create_reading(db, payload))


@router.get("/{reading_id}", response_model=UtilityReadingOut, summary="抄表记录详情")
def get_reading(reading_id: int, db: Annotated[Session, Depends(get_db)]) -> UtilityReadingOut:
    return utility_service.to_out(utility_service.get_reading(db, reading_id))


@router.patch("/{reading_id}", response_model=UtilityReadingOut, summary="更新抄表记录")
def update_reading(
    reading_id: int, payload: UtilityReadingUpdate, db: Annotated[Session, Depends(get_db)]
) -> UtilityReadingOut:
    return utility_service.to_out(utility_service.update_reading(db, reading_id, payload))


@router.delete("/{reading_id}", response_model=MessageOut, summary="删除抄表记录")
def delete_reading(reading_id: int, db: Annotated[Session, Depends(get_db)]) -> MessageOut:
    utility_service.delete_reading(db, reading_id)
    return MessageOut(message="删除成功")
