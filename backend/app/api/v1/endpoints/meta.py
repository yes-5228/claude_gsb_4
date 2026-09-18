"""字典接口：供前端下拉选项使用。"""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import (
    ELEC_CHANGE_FLOOR_KWH,
    ELEC_UNIT,
    INSPECTION_CHECK_ITEMS,
    INSPECTION_ITEM_MAX_SCORE,
    ISSUE_TRANSITIONS,
    UTILITY_CHANGE_THRESHOLD,
    UTILITY_REASONS,
    WATER_CHANGE_FLOOR_TONS,
    WATER_UNIT,
    IssueCategory,
    IssueSeverity,
    IssueStatus,
    RestroomGrade,
    RestroomStatus,
    Shift,
)
from app.core.database import get_db
from app.services import inspection_service

router = APIRouter(prefix="/meta", tags=["字典"])


class RestroomOption(BaseModel):
    id: int
    code: str
    name: str
    district: str


class Dictionaries(BaseModel):
    restroom_status: list[str]
    restroom_grade: list[str]
    shift: list[str]
    issue_category: list[str]
    issue_severity: list[str]
    issue_status: list[str]
    inspection_check_items: list[str]
    inspection_item_max_score: int
    issue_transitions: dict[str, list[str]]
    utility_water_unit_price: float
    utility_elec_unit_price: float
    utility_change_threshold: float
    utility_water_floor: float
    utility_elec_floor: float
    utility_water_unit: str
    utility_elec_unit: str
    utility_reasons: dict[str, list[str]]


@router.get("/dictionaries", response_model=Dictionaries, summary="枚举字典")
def get_dictionaries() -> Dictionaries:
    return Dictionaries(
        restroom_status=[item.value for item in RestroomStatus],
        restroom_grade=[item.value for item in RestroomGrade],
        shift=[item.value for item in Shift],
        issue_category=[item.value for item in IssueCategory],
        issue_severity=[item.value for item in IssueSeverity],
        issue_status=[item.value for item in IssueStatus],
        inspection_check_items=list(INSPECTION_CHECK_ITEMS),
        inspection_item_max_score=INSPECTION_ITEM_MAX_SCORE,
        issue_transitions={key: list(value) for key, value in ISSUE_TRANSITIONS.items()},
        utility_water_unit_price=settings.water_unit_price,
        utility_elec_unit_price=settings.elec_unit_price,
        utility_change_threshold=UTILITY_CHANGE_THRESHOLD,
        utility_water_floor=WATER_CHANGE_FLOOR_TONS,
        utility_elec_floor=ELEC_CHANGE_FLOOR_KWH,
        utility_water_unit=WATER_UNIT,
        utility_elec_unit=ELEC_UNIT,
        utility_reasons={key: list(value) for key, value in UTILITY_REASONS.items()},
    )


@router.get("/restroom-options", response_model=list[RestroomOption], summary="公厕下拉选项")
def get_restroom_options(
    db: Annotated[Session, Depends(get_db)], keyword: str | None = None
) -> list[RestroomOption]:
    rows = inspection_service.restroom_options(db, keyword=keyword)
    return [
        RestroomOption(id=row.id, code=row.code, name=row.name, district=row.district)
        for row in rows
    ]
