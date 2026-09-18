"""水电月度抄表相关数据结构。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.restroom import RestroomBrief


class UtilityRecordCreate(BaseModel):
    restroom_id: int = Field(description="所属公厕")
    period_year: int = Field(ge=2000, le=2100, description="抄表年份")
    period_month: int = Field(ge=1, le=12, description="抄表月份，1-12")
    recorded_at: datetime | None = Field(default=None, description="抄表时间，留空取当前时间")
    reader: str = Field(min_length=1, max_length=60, description="抄表人")

    water_reading: float | None = Field(default=None, ge=0, description="水表本期累计表底")
    elec_reading: float | None = Field(default=None, ge=0, description="电表本期累计表底")

    # 费用默认按单价自动计算；置为 False 时必须提供对应手工费用
    water_fee_auto: bool = Field(default=True, description="水费是否按单价自动计算")
    elec_fee_auto: bool = Field(default=True, description="电费是否按单价自动计算")
    water_fee: float | None = Field(default=None, ge=0, description="手工水费（元）")
    elec_fee: float | None = Field(default=None, ge=0, description="手工电费（元）")

    remark: str | None = Field(default=None, max_length=500, description="备注")

    @model_validator(mode="after")
    def _validate(self) -> "UtilityRecordCreate":
        if self.water_reading is None and self.elec_reading is None:
            raise ValueError("水表、电表至少需要抄录一项读数")
        if not self.water_fee_auto and self.water_fee is None:
            raise ValueError("选择手工水费时必须填写水费金额")
        if not self.elec_fee_auto and self.elec_fee is None:
            raise ValueError("选择手工电费时必须填写电费金额")
        if self.water_reading is None and self.water_fee is not None:
            raise ValueError("未抄录水表读数时不能登记水费")
        if self.elec_reading is None and self.elec_fee is not None:
            raise ValueError("未抄录电表读数时不能登记电费")
        return self


class UtilityRecordUpdate(BaseModel):
    """局部更新；所属公厕与账期不可修改（需删除后重建）。"""

    recorded_at: datetime | None = None
    reader: str | None = Field(default=None, min_length=1, max_length=60)

    water_reading: float | None = Field(default=None, ge=0)
    elec_reading: float | None = Field(default=None, ge=0)

    # 不传 *_fee_auto 表示保持现状；显式 False 时需带费用，True 表示切回自动计费
    water_fee_auto: bool | None = None
    elec_fee_auto: bool | None = None
    water_fee: float | None = Field(default=None, ge=0)
    elec_fee: float | None = Field(default=None, ge=0)

    remark: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _validate(self) -> "UtilityRecordUpdate":
        if self.water_fee_auto is False and self.water_fee is None:
            raise ValueError("选择手工水费时必须填写水费金额")
        if self.elec_fee_auto is False and self.elec_fee is None:
            raise ValueError("选择手工电费时必须填写电费金额")
        return self


class UtilityRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    restroom_id: int
    restroom: RestroomBrief | None = None
    period_year: int
    period_month: int
    recorded_at: datetime
    reader: str

    water_reading: float | None = None
    water_usage: float | None = None
    water_unit_price: float | None = None
    water_fee: float | None = None
    water_fee_locked: bool = False
    water_change_amount: float | None = None
    water_change_pct: float | None = None
    water_status: str
    water_reasons: list[str] = Field(default_factory=list)

    elec_reading: float | None = None
    elec_usage: float | None = None
    elec_unit_price: float | None = None
    elec_fee: float | None = None
    elec_fee_locked: bool = False
    elec_change_amount: float | None = None
    elec_change_pct: float | None = None
    elec_status: str
    elec_reasons: list[str] = Field(default_factory=list)

    status: str
    total_fee: float = 0.0
    remark: str | None = None
    created_at: datetime
    updated_at: datetime


class UtilityBaselineOut(BaseModel):
    """表单抄录前的参考信息：上一期表底/用量与当前默认单价。"""

    exists: bool = Field(description="该公厕该账期是否已存在记录")
    prev_year: int | None = None
    prev_month: int | None = None
    water_reading: float | None = Field(default=None, description="上期水表表底")
    water_usage: float | None = Field(default=None, description="上期用水量")
    elec_reading: float | None = Field(default=None, description="上期电表表底")
    elec_usage: float | None = Field(default=None, description="上期用电量")
    water_unit_price: float
    elec_unit_price: float
