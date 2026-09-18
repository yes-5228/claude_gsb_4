"""水电月度抄表记录模型。

一座公厕一个自然月一条记录，同时记录水表、电表的累计表底、用量、费用及环比结论。
用量、费用、环比、异常结论均不直接由用户录入，而是由 utility_service 在写入后
按时间顺序重算（修改历史月份会向后链式重算）。
"""

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import UTILITY_OVERALL_NORMAL, UTILITY_STATUS_NORMAL
from app.core.database import Base


class UtilityRecord(Base):
    """单座公厕单个月份的水、电抄表与费用。"""

    __tablename__ = "utility_records"
    __table_args__ = (
        UniqueConstraint(
            "restroom_id", "period_year", "period_month", name="uq_utility_restroom_period"
        ),
        Index("ix_utility_period", "period_year", "period_month"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    restroom_id: Mapped[int] = mapped_column(
        ForeignKey("restrooms.id", ondelete="CASCADE"), index=True, comment="所属公厕"
    )
    period_year: Mapped[int] = mapped_column(Integer, comment="抄表年份")
    period_month: Mapped[int] = mapped_column(Integer, comment="抄表月份，1-12")
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, index=True, comment="抄表时间"
    )
    reader: Mapped[str] = mapped_column(String(60), default="", index=True, comment="抄表人")

    # 水表
    water_reading: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="水表累计表底"
    )
    water_usage: Mapped[float | None] = mapped_column(Float, nullable=True, comment="本月用水量（吨）")
    water_unit_price: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="计费水价快照（元/吨）"
    )
    water_fee: Mapped[float | None] = mapped_column(Float, nullable=True, comment="水费（元）")
    water_fee_locked: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="水费是否为手工录入（重算时保留）"
    )
    water_change_amount: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="用水量环比增减（吨）"
    )
    water_change_pct: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="用水量环比百分比"
    )
    water_status: Mapped[str] = mapped_column(
        String(20), default=UTILITY_STATUS_NORMAL, comment="用水判定"
    )
    water_reasons: Mapped[list[str]] = mapped_column(
        JSON, default=list, comment="用水异常可能原因"
    )

    # 电表
    elec_reading: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="电表累计表底"
    )
    elec_usage: Mapped[float | None] = mapped_column(Float, nullable=True, comment="本月用电量（度）")
    elec_unit_price: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="计费电价快照（元/度）"
    )
    elec_fee: Mapped[float | None] = mapped_column(Float, nullable=True, comment="电费（元）")
    elec_fee_locked: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="电费是否为手工录入（重算时保留）"
    )
    elec_change_amount: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="用电量环比增减（度）"
    )
    elec_change_pct: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="用电量环比百分比"
    )
    elec_status: Mapped[str] = mapped_column(
        String(20), default=UTILITY_STATUS_NORMAL, comment="用电判定"
    )
    elec_reasons: Mapped[list[str]] = mapped_column(
        JSON, default=list, comment="用电异常可能原因"
    )

    # 综合状态：水、电任一异常即为异常
    status: Mapped[str] = mapped_column(
        String(20), default=UTILITY_OVERALL_NORMAL, index=True, comment="综合状态"
    )
    remark: Mapped[str | None] = mapped_column(Text, nullable=True, comment="备注")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间"
    )

    restroom: Mapped["Restroom"] = relationship(back_populates="utility_records")  # noqa: F821

    @property
    def total_fee(self) -> float:
        """本月水电费用合计。"""
        return round((self.water_fee or 0.0) + (self.elec_fee or 0.0), 2)
