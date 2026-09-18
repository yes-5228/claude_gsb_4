"""水电抄表记录模型。"""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import MeterType
from app.core.database import Base


class UtilityReading(Base):
    """一座公厕一块表（水表/电表）一个自然月的抄表记录。

    用量、费用、环比与异常标记均由服务端在写入时计算并落库，
    上一自然月记录变化时会联动重算本月记录。
    """

    __tablename__ = "utility_readings"
    __table_args__ = (
        UniqueConstraint("restroom_id", "meter_type", "period", name="uq_utility_reading_month"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    restroom_id: Mapped[int] = mapped_column(
        ForeignKey("restrooms.id", ondelete="CASCADE"), index=True, comment="所属公厕"
    )
    meter_type: Mapped[str] = mapped_column(
        String(10), default=MeterType.WATER.value, index=True, comment="表计类型：水表/电表"
    )
    period: Mapped[str] = mapped_column(String(7), index=True, comment="抄表月份，格式 YYYY-MM")
    reading: Mapped[float] = mapped_column(Float, comment="本期抄表读数")
    prev_reading: Mapped[float | None] = mapped_column(Float, nullable=True, comment="上期读数")
    prev_reading_auto: Mapped[bool] = mapped_column(
        Boolean, default=True, comment="上期读数是否为自动带出（自动带出时随上一月记录联动更新）"
    )
    usage: Mapped[float | None] = mapped_column(Float, nullable=True, comment="本期用量")
    unit_price: Mapped[float] = mapped_column(Float, default=0.0, comment="单价（元/吨 或 元/度）")
    fee: Mapped[float | None] = mapped_column(Float, nullable=True, comment="本期费用（元）")
    change_pct: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="与上月用量的增减幅度（%），无基期为空"
    )
    is_abnormal: Mapped[bool] = mapped_column(
        Boolean, default=False, index=True, comment="用量是否超出正常区间"
    )
    abnormal_reasons: Mapped[list[str]] = mapped_column(
        JSON, default=list, comment="异常提示与可能原因"
    )
    remark: Mapped[str | None] = mapped_column(Text, nullable=True, comment="备注")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="登记时间")

    restroom: Mapped["Restroom"] = relationship(back_populates="utility_readings")  # noqa: F821
