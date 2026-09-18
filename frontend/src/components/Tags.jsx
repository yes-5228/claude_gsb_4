import { formatPercent, isOverdue, scoreTone, severityTone, statusTone } from '../utils/format.js';

export function StatusTag({ status }) {
  return <span className={`tag ${statusTone(status)}`}>{status}</span>;
}

export function SeverityTag({ severity }) {
  return <span className={`tag ${severityTone(severity)}`}>{severity}</span>;
}

export function ScorePill({ score }) {
  return <span className={`score-pill ${scoreTone(score)}`}>{Number(score).toFixed(1)}</span>;
}

export function OverdueTag({ deadline, status }) {
  if (!isOverdue(deadline, status)) return null;
  return <span className="tag tag-danger">已超期</span>;
}

export function GradeTag({ grade }) {
  const tone =
    grade === '优秀'
      ? 'tag-success'
      : grade === '良好'
        ? 'tag-primary'
        : grade === '合格'
          ? 'tag-warning'
          : 'tag-danger';
  return <span className={`tag ${tone}`}>{grade || '未评级'}</span>;
}

/** 环比增减幅度：上升红色、下降绿色、持平灰色，空值显示 —。 */
export function ChangePct({ value }) {
  if (value === null || value === undefined) return <span className="change-pct change-flat">—</span>;
  const num = Number(value);
  const tone = num > 0 ? 'change-up' : num < 0 ? 'change-down' : 'change-flat';
  const arrow = num > 0 ? '↑' : num < 0 ? '↓' : '→';
  return <span className={`change-pct ${tone}`}>{arrow} {formatPercent(num)}</span>;
}

/** 水电用量是否异常的标签。 */
export function AbnormalTag({ abnormal }) {
  return abnormal ? (
    <span className="tag tag-danger">异常</span>
  ) : (
    <span className="tag tag-success">正常</span>
  );
}
