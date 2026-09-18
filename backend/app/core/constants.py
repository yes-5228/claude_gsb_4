"""业务枚举与规则常量。"""

from enum import StrEnum


class RestroomStatus(StrEnum):
    NORMAL = "正常开放"
    MAINTENANCE = "维修中"
    CLOSED = "暂停使用"


class RestroomGrade(StrEnum):
    FIRST = "一类"
    SECOND = "二类"
    THIRD = "三类"


class Shift(StrEnum):
    MORNING = "早班"
    MIDDLE = "中班"
    NIGHT = "晚班"


class InspectionResult(StrEnum):
    NORMAL = "正常"
    ABNORMAL = "发现问题"


class IssueCategory(StrEnum):
    CLEANING = "保洁不到位"
    FACILITY = "设施损坏"
    ODOR = "异味扰民"
    CONSUMABLE = "耗材缺失"
    SAFETY = "安全隐患"
    OTHER = "其他"


class IssueSeverity(StrEnum):
    NORMAL = "一般"
    SERIOUS = "严重"
    URGENT = "紧急"


class IssueStatus(StrEnum):
    PENDING = "待整改"
    PROCESSING = "整改中"
    REVIEWING = "待验收"
    DONE = "已完成"
    CLOSED = "已关闭"


# 整改流转规则：当前状态 -> 允许流转到的状态
ISSUE_TRANSITIONS: dict[str, list[str]] = {
    IssueStatus.PENDING: [IssueStatus.PROCESSING, IssueStatus.CLOSED],
    IssueStatus.PROCESSING: [IssueStatus.REVIEWING, IssueStatus.CLOSED],
    IssueStatus.REVIEWING: [IssueStatus.DONE, IssueStatus.PROCESSING],
    IssueStatus.DONE: [IssueStatus.CLOSED],
    IssueStatus.CLOSED: [],
}

# 状态流转对应的动作名称，用于生成整改流水
TRANSITION_ACTIONS: dict[tuple[str, str], str] = {
    (IssueStatus.PENDING, IssueStatus.PROCESSING): "开始整改",
    (IssueStatus.PENDING, IssueStatus.CLOSED): "作废关闭",
    (IssueStatus.PROCESSING, IssueStatus.REVIEWING): "提交验收",
    (IssueStatus.PROCESSING, IssueStatus.CLOSED): "终止关闭",
    (IssueStatus.REVIEWING, IssueStatus.DONE): "验收通过",
    (IssueStatus.REVIEWING, IssueStatus.PROCESSING): "验收驳回",
    (IssueStatus.DONE, IssueStatus.CLOSED): "归档关闭",
}

# 巡查检查项，每项 0-10 分
INSPECTION_CHECK_ITEMS: list[str] = [
    "地面与台阶清洁",
    "便池蹲位清洁",
    "洗手台与镜面",
    "通风除臭",
    "耗材补充",
    "垃圾清运",
    "工具与标识摆放",
    "墙面门窗卫生",
]

INSPECTION_ITEM_MAX_SCORE = 10

GRADE_EXCELLENT = "优秀"
GRADE_GOOD = "良好"
GRADE_PASS = "合格"
GRADE_FAIL = "不合格"

# 仍处于整改闭环中的状态，用于统计未整改问题
OPEN_ISSUE_STATUSES: list[str] = [
    IssueStatus.PENDING,
    IssueStatus.PROCESSING,
    IssueStatus.REVIEWING,
]

# 单检查项低于该分数视为不合格项
INSPECTION_ITEM_PROBLEM_THRESHOLD = 6

# ---------------------------------------------------------------------------
# 水电计量
# ---------------------------------------------------------------------------

# 单项用量判定结果
UTILITY_STATUS_NORMAL = "正常"
UTILITY_STATUS_HIGH = "用量偏高"
UTILITY_STATUS_LOW = "用量偏低"
# 整条记录的综合状态（水、电任一异常即异常）
UTILITY_OVERALL_NORMAL = "正常"
UTILITY_OVERALL_ABNORMAL = "异常"

# 环比偏离阈值：相对上月用量增减超过该比例视为异常（0.30 = 30%）
UTILITY_CHANGE_THRESHOLD = 0.30
# 绝对变化量门槛：避免小幅波动（如 1 吨→2 吨也是 +100%）造成误报
WATER_CHANGE_FLOOR_TONS = 2.0
ELEC_CHANGE_FLOOR_KWH = 30.0

# 用量单位
WATER_UNIT = "吨"
ELEC_UNIT = "度"

# 各异常情形的可能原因提示。high=用量环比明显上升；low=用量环比明显回落但
# 表底仍在增长；rollback=本期表底低于上期（换表归零/抄录错误等）。
UTILITY_REASONS: dict[str, list[str]] = {
    "water_high": [
        "用水设施疑似漏水（便器/管道长流水）",
        "清洁、绿化作业频次增加",
        "人流量明显增大",
        "水表故障或抄录有误",
    ],
    "water_low": [
        "上月用量异常偏高，本月回归正常",
        "清洁、绿化等集中作业结束，作业量回落",
        "人流量回落或抄表周期天数差异",
    ],
    "water_rollback": [
        "水表读数回退（换表归零或抄录错误）",
        "场馆关停或供水中断",
        "节水改造见效，需结合现场确认",
    ],
    "elec_high": [
        "照明、排风、空调使用时长增加",
        "用电设备故障或存在待机耗电",
        "季节性取暖、制冷用电增加",
        "电表故障或抄录有误",
    ],
    "elec_low": [
        "上月用量异常偏高，本月回归正常",
        "季节性取暖、制冷结束，用电回落",
        "设备检修、开放时间缩短或抄表周期差异",
    ],
    "elec_rollback": [
        "电表读数回退（换表归零或抄录错误）",
        "设备检修停用或场馆开放时间缩短",
        "节能改造见效，需结合现场确认",
    ],
}
