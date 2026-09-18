"""水电月度抄表接口。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import PaginationDep, build_meta
from app.core.database import get_db
from app.schemas.common import MessageOut, Page
from app.schemas.utility import (
    UtilityBaselineOut,
    UtilityRecordCreate,
    UtilityRecordOut,
    UtilityRecordUpdate,
)
from app.services import utility_service

router = APIRouter(prefix="/utility-records", tags=["水电计量"])


@router.get("", response_model=Page[UtilityRecordOut], summary="水电抄表月度台账")
def list_utility_records(
    db: Annotated[Session, Depends(get_db)],
    pagination: PaginationDep,
    restroom_id: Annotated[int | None, Query(description="按公厕过滤")] = None,
    district: Annotated[str | None, Query(description="按区域过滤")] = None,
    period_year: Annotated[int | None, Query(description="按年份过滤")] = None,
    period_month: Annotated[int | None, Query(ge=1, le=12, description="按月份过滤")] = None,
    abnormal: Annotated[bool | None, Query(description="是否异常：true 仅异常 / false 仅正常")] = None,
    reader: Annotated[str | None, Query(description="抄表人模糊搜索")] = None,
    sort_by: Annotated[str, Query(pattern="^(period|recorded_at|reader|created_at)$")] = "period",
    order: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
) -> Page[UtilityRecordOut]:
    rows, total = utility_service.list_utility_records(
        db,
        restroom_id=restroom_id,
        district=district,
        period_year=period_year,
        period_month=period_month,
        abnormal=abnormal,
        reader=reader,
        page=pagination.page,
        page_size=pagination.page_size,
        sort_by=sort_by,
        order=order,
    )
    return Page[UtilityRecordOut](
        items=[utility_service.to_out(row) for row in rows],
        meta=build_meta(total, pagination),
    )


@router.post("", response_model=UtilityRecordOut, status_code=201, summary="登记月度水电抄表")
def create_utility_record(
    payload: UtilityRecordCreate, db: Annotated[Session, Depends(get_db)]
) -> UtilityRecordOut:
    return utility_service.to_out(utility_service.create_utility_record(db, payload))


@router.get("/baseline", response_model=UtilityBaselineOut, summary="新增抄表时的上期参考")
def get_baseline(
    db: Annotated[Session, Depends(get_db)],
    restroom_id: Annotated[int, Query(description="公厕 ID")],
    period_year: Annotated[int, Query(ge=2000, le=2100, description="抄表年份")],
    period_month: Annotated[int, Query(ge=1, le=12, description="抄表月份")],
) -> UtilityBaselineOut:
    return utility_service.get_baseline(db, restroom_id, period_year, period_month)


@router.get("/{utility_record_id}", response_model=UtilityRecordOut, summary="水电抄表详情")
def get_utility_record(
    utility_record_id: int, db: Annotated[Session, Depends(get_db)]
) -> UtilityRecordOut:
    return utility_service.to_out(utility_service.get_utility_record(db, utility_record_id))


@router.patch("/{utility_record_id}", response_model=UtilityRecordOut, summary="更新水电抄表")
def update_utility_record(
    utility_record_id: int,
    payload: UtilityRecordUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> UtilityRecordOut:
    return utility_service.to_out(
        utility_service.update_utility_record(db, utility_record_id, payload)
    )


@router.delete("/{utility_record_id}", response_model=MessageOut, summary="删除水电抄表")
def delete_utility_record(
    utility_record_id: int, db: Annotated[Session, Depends(get_db)]
) -> MessageOut:
    utility_service.delete_utility_record(db, utility_record_id)
    return MessageOut(message="删除成功")
