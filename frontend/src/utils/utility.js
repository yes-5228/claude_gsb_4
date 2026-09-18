/**
 * 水电抄表前端预览：与后端 utility_service 的用量/费用/环比/异常判定保持一致，
 * 仅用于录入时实时提示，最终结果以后端重算为准。
 */

export const KIND_META = {
  water: { label: '用水', usageUnit: '吨', feeUnit: '元/吨' },
  elec: { label: '用电', usageUnit: '度', feeUnit: '元/度' },
};

const round2 = (v) => Math.round(v * 100) / 100;

/**
 * 计算单个能源的预览。
 * @returns {{usage:number|null, fee:number|null, amount:number|null,
 *   pct:number|null, status:string, reasons:string[], decreased:boolean}}
 */
export function previewKind(
  { reading, prevReading, prevUsage, unitPrice, threshold, floor, reasons },
) {
  const empty = {
    usage: null,
    fee: null,
    amount: null,
    pct: null,
    status: '正常',
    reasons: [],
    decreased: false,
  };
  if (reading === null || reading === undefined || Number.isNaN(Number(reading))) return empty;
  const cur = Number(reading);
  if (prevReading === null || prevReading === undefined) {
    return { ...empty, usage: null, fee: null };
  }

  const prev = Number(prevReading);
  const decreased = cur < prev;
  const usage = round2(cur - prev);

  if (decreased || usage < 0) {
    return {
      usage,
      fee: 0,
      amount: prevUsage === null || prevUsage === undefined ? null : round2(usage - Number(prevUsage)),
      pct:
        prevUsage !== null && prevUsage !== undefined && Number(prevUsage) > 0
          ? round2(((usage - Number(prevUsage)) / Number(prevUsage)) * 1000) / 10
          : null,
      status: '用量偏低',
      reasons: reasons.rollback || [],
      decreased: true,
    };
  }

  if (prevUsage === null || prevUsage === undefined) {
    return { ...empty, usage, fee: round2(usage * Number(unitPrice)) };
  }

  const last = Number(prevUsage);
  const amount = round2(usage - last);
  const pct = last > 0 ? Math.round(((usage - last) / last) * 1000) / 10 : null;

  if (pct !== null && pct > threshold * 100 && Math.abs(amount) > floor) {
    return {
      usage,
      fee: round2(usage * Number(unitPrice)),
      amount,
      pct,
      status: '用量偏高',
      reasons: reasons.high || [],
      decreased: false,
    };
  }
  if (
    (pct !== null && pct < -threshold * 100 && Math.abs(amount) > floor) ||
    (pct === null && amount < -floor)
  ) {
    return {
      usage,
      fee: round2(usage * Number(unitPrice)),
      amount,
      pct,
      status: '用量偏低',
      reasons: reasons.low || [],
      decreased: false,
    };
  }
  return {
    usage,
    fee: round2(usage * Number(unitPrice)),
    amount,
    pct,
    status: '正常',
    reasons: [],
    decreased: false,
  };
}

/** 生成账期下拉的年份列表：当前年向前若干年。 */
export function yearOptions(span = 5) {
  const current = new Date().getFullYear();
  return Array.from({ length: span + 1 }, (_, i) => current - span + i);
}

export const MONTH_OPTIONS = Array.from({ length: 12 }, (_, i) => i + 1);

/** 将 yyyy-mm-dd 等输入转成月份选择需要的 1-12。 */
export function periodLabel(year, month) {
  return `${year} 年 ${month} 月`;
}
