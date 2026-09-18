"""水电抄表记录相关数据结构。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import MeterType
from app.schemas.restroom import RestroomBrief

PERIOD_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"


class UtilityReadingCreate(BaseModel):
    restroom_id: int
    meter_type: MeterType = Field(description="表计类型：水表/电表")
    period: str = Field(pattern=PERIOD_PATTERN, description="抄表月份，格式 YYYY-MM")
    reading: float = Field(ge=0, description="本期抄表读数")
    prev_reading: float | None = Field(
        default=None, ge=0, description="上期读数，留空自动取上一月记录"
    )
    unit_price: float = Field(ge=0, default=0.0, description="单价（元/吨 或 元/度）")
    remark: str | None = Field(default=None, max_length=500)


class UtilityReadingUpdate(BaseModel):
    """局部更新；读数、单价等变更后服务端会重算用量、费用与环比。"""

    period: str | None = Field(default=None, pattern=PERIOD_PATTERN)
    reading: float | None = Field(default=None, ge=0)
    prev_reading: float | None = Field(default=None, ge=0)
    unit_price: float | None = Field(default=None, ge=0)
    remark: str | None = Field(default=None, max_length=500)


class UtilityReadingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    restroom_id: int
    restroom: RestroomBrief | None = None
    meter_type: str
    period: str
    reading: float
    prev_reading: float | None = None
    usage: float | None = None
    unit_price: float
    fee: float | None = None
    change_pct: float | None = None
    is_abnormal: bool = False
    abnormal_reasons: list[str] = Field(default_factory=list)
    remark: str | None = None
    created_at: datetime


class UtilitySummaryOut(BaseModel):
    """某一月份全部公厕的水电用量与费用汇总。"""

    period: str
    reading_count: int = Field(description="该月抄表记录条数")
    abnormal_count: int = Field(description="该月异常记录条数")
    water_usage: float = Field(description="用水量合计（吨）")
    water_fee: float = Field(description="水费合计（元）")
    water_change_pct: float | None = Field(default=None, description="用水量环比（%）")
    electricity_usage: float = Field(description="用电量合计（度）")
    electricity_fee: float = Field(description="电费合计（元）")
    electricity_change_pct: float | None = Field(default=None, description="用电量环比（%）")
