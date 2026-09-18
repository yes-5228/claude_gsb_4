import { useEffect, useMemo, useState } from 'react';

import { utilityApi } from '../../api/utility.js';
import { metaApi } from '../../api/meta.js';
import Field from '../../components/Field.jsx';
import Modal from '../../components/Modal.jsx';
import { useToast } from '../../components/Toast.jsx';
import { useDictionaries } from '../../hooks/useDictionaries.js';
import { toDateTimeInput } from '../../utils/format.js';
import { formatChangePct, formatMoney, formatNumber } from '../../utils/format.js';
import { KIND_META, MONTH_OPTIONS, previewKind, yearOptions } from '../../utils/utility.js';

const toNumOrNull = (value) => {
  if (value === '' || value === null || value === undefined) return null;
  const n = Number(value);
  return Number.isNaN(n) ? null : n;
};

function UtilityBlock({
  kind,
  dictionaries,
  reading,
  setReading,
  auto,
  setAuto,
  manualFee,
  setManualFee,
  baseline,
}) {
  const meta = KIND_META[kind];
  const reasons = useMemo(() => {
    const all = dictionaries?.utility_reasons || {};
    return {
      high: all[`${kind}_high`] || [],
      low: all[`${kind}_low`] || [],
      rollback: all[`${kind}_rollback`] || [],
    };
  }, [dictionaries, kind]);

  const price =
    kind === 'water'
      ? dictionaries?.utility_water_unit_price
      : dictionaries?.utility_elec_unit_price;
  const prevReading = kind === 'water' ? baseline?.water_reading : baseline?.elec_reading;
  const prevUsage = kind === 'water' ? baseline?.water_usage : baseline?.elec_usage;

  const result = previewKind({
    reading: toNumOrNull(reading),
    prevReading,
    prevUsage,
    unitPrice: price,
    threshold: dictionaries?.utility_change_threshold ?? 0.3,
    floor:
      kind === 'water'
        ? dictionaries?.utility_water_floor ?? 2
        : dictionaries?.utility_elec_floor ?? 30,
    reasons,
  });

  const abnormal = result.status !== '正常';
  const effectiveFee = auto ? result.fee : toNumOrNull(manualFee);

  return (
    <section className={`utility-block${abnormal ? ' is-abnormal' : ''}`}>
      <div className="card-title">
        <h3>{kind === 'water' ? '💧 水表抄录' : '⚡ 电表抄录'}</h3>
        <span className={`tag ${abnormal ? 'tag-danger' : 'tag-success'}`}>{result.status}</span>
      </div>

      <div className="utility-grid">
        <Field label="上期表底">
          <input value={prevReading ?? '—'} disabled />
        </Field>
        <Field label={`本期表底（${kind === 'water' ? '累计吨数' : '累计度数'}）`}>
          <input
            type="number"
            min="0"
            step="0.01"
            value={reading}
            placeholder="未抄录请留空"
            onChange={(e) => setReading(e.target.value)}
          />
        </Field>
        <Field label={`本期用量（${meta.usageUnit}）`}>
          <input value={result.usage === null ? '—' : formatNumber(result.usage)} disabled />
        </Field>
        <Field label="环比上月">
          <input
            value={
              result.pct === null
                ? '—'
                : `${formatChangePct(result.pct)}${result.amount !== null ? `（${result.amount > 0 ? '+' : ''}${formatNumber(result.amount)} ${meta.usageUnit}）` : ''}`
            }
            disabled
            className={abnormal ? (result.status === '用量偏高' ? 'input-danger' : 'input-warning') : ''}
          />
        </Field>
        <Field label={`单价（${meta.feeUnit}）`}>
          <input value={price ?? '—'} disabled />
        </Field>
        <Field label={`费用（元）${auto ? '· 自动' : '· 手工'}`}>
          {auto ? (
            <input value={result.fee === null ? '—' : formatMoney(result.fee)} disabled />
          ) : (
            <input
              type="number"
              min="0"
              step="0.01"
              value={manualFee}
              placeholder="请填写实际费用"
              onChange={(e) => setManualFee(e.target.value)}
            />
          )}
        </Field>
      </div>

      <label className="checkbox-row" style={{ marginTop: 8 }}>
        <input type="checkbox" checked={!auto} onChange={(e) => setAuto(!e.target.checked)} />
        手工填写实际费用（默认按单价 {price} {meta.feeUnit} 自动计算）
      </label>

      {abnormal ? (
        <div className="alert alert-warning utility-reasons">
          <strong>{result.status}，可能原因：</strong>
          <ul>
            {result.reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {effectiveFee !== null ? (
        <div className="muted utility-fee-hint">
          {kind === 'water' ? '水费' : '电费'}小计：{formatMoney(effectiveFee)} 元
        </div>
      ) : null}
    </section>
  );
}

export default function UtilityFormModal({ record, onClose, onSaved }) {
  const { dictionaries } = useDictionaries();
  const toast = useToast();
  const editing = Boolean(record?.id);

  const [options, setOptions] = useState([]);
  const [baseline, setBaseline] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const now = new Date();
  const [form, setForm] = useState(() => ({
    restroom_id: record?.restroom_id ?? '',
    year: record?.period_year ?? now.getFullYear(),
    month: record?.period_month ?? now.getMonth() + 1,
    reader: record?.reader ?? '',
    recorded_at: toDateTimeInput(record?.recorded_at),
    water_reading: record?.water_reading ?? '',
    elec_reading: record?.elec_reading ?? '',
    remark: record?.remark ?? '',
  }));
  const [waterAuto, setWaterAuto] = useState(!record?.water_fee_locked);
  const [elecAuto, setElecAuto] = useState(!record?.elec_fee_locked);
  const [waterFee, setWaterFee] = useState(record?.water_fee ?? '');
  const [elecFee, setElecFee] = useState(record?.elec_fee ?? '');

  useEffect(() => {
    metaApi.restroomOptions().then(setOptions).catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (!form.restroom_id) {
      setBaseline(null);
      return;
    }
    let alive = true;
    utilityApi
      .baseline(form.restroom_id, form.year, form.month)
      .then((data) => alive && setBaseline(data))
      .catch(() => alive && setBaseline(null));
    return () => {
      alive = false;
    };
  }, [form.restroom_id, form.year, form.month]);

  const set = (key) => (e) => setForm((p) => ({ ...p, [key]: e.target.value }));

  const submit = async (event) => {
    event.preventDefault();
    setError(null);

    if (!form.restroom_id) return setError('请选择公厕');
    if (!form.reader.trim()) return setError('请填写抄表人');
    const wr = toNumOrNull(form.water_reading);
    const er = toNumOrNull(form.elec_reading);
    if (wr === null && er === null) return setError('水表、电表至少需要抄录一项读数');
    if (wr !== null && wr < 0) return setError('水表读数不能为负');
    if (er !== null && er < 0) return setError('电表读数不能为负');
    if (!waterAuto && toNumOrNull(waterFee) === null) return setError('选择手工水费时必须填写水费金额');
    if (!elecAuto && toNumOrNull(elecFee) === null) return setError('选择手工电费时必须填写电费金额');

    const recordedAt = form.recorded_at ? new Date(form.recorded_at).toISOString() : null;
    const payload = editing
      ? {
          reader: form.reader,
          recorded_at: recordedAt,
          water_reading: wr,
          elec_reading: er,
          water_fee_auto: waterAuto,
          elec_fee_auto: elecAuto,
          ...(waterAuto ? {} : { water_fee: toNumOrNull(waterFee) }),
          ...(elecAuto ? {} : { elec_fee: toNumOrNull(elecFee) }),
          remark: form.remark || null,
        }
      : {
          restroom_id: Number(form.restroom_id),
          period_year: Number(form.year),
          period_month: Number(form.month),
          reader: form.reader,
          recorded_at: recordedAt,
          water_reading: wr,
          elec_reading: er,
          water_fee_auto: waterAuto,
          elec_fee_auto: elecAuto,
          ...(waterAuto ? {} : { water_fee: toNumOrNull(waterFee) }),
          ...(elecAuto ? {} : { elec_fee: toNumOrNull(elecFee) }),
          remark: form.remark || null,
        };

    setSaving(true);
    try {
      const saved = editing
        ? await utilityApi.update(record.id, payload)
        : await utilityApi.create(payload);
      toast.success(editing ? '水电记录已更新' : '水电记录已登记');
      if (saved.status === '异常') {
        const all = [...(saved.water_reasons || []), ...(saved.elec_reasons || [])];
        toast.push(`本期用量异常：${all.slice(0, 2).join('；')}${all.length > 2 ? ' 等' : ''}`, 'error');
      }
      onSaved(saved);
      onClose();
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      title={editing ? `编辑水电记录 - ${record.period_year} 年 ${record.period_month} 月` : '登记月度水电抄表'}
      onClose={onClose}
      width={960}
      footer={
        <>
          <button type="button" className="btn" onClick={onClose}>
            取消
          </button>
          <button type="submit" form="utility-form" className="btn btn-primary" disabled={saving}>
            {saving ? '保存中…' : '保存'}
          </button>
        </>
      }
    >
      {error ? <div className="alert alert-error">{error}</div> : null}
      <form id="utility-form" onSubmit={submit} className="form-grid">
        <Field label="公厕 *" full>
          <select value={form.restroom_id} disabled={editing} onChange={set('restroom_id')}>
            <option value="">请选择公厕</option>
            {options.map((o) => (
              <option key={o.id} value={o.id}>
                {o.code} {o.name}（{o.district}）
              </option>
            ))}
          </select>
        </Field>
        <Field label="抄表年份 *">
          <select value={form.year} disabled={editing} onChange={set('year')}>
            {yearOptions(5).map((y) => (
              <option key={y} value={y}>
                {y} 年
              </option>
            ))}
          </select>
        </Field>
        <Field label="抄表月份 *">
          <select value={form.month} disabled={editing} onChange={set('month')}>
            {MONTH_OPTIONS.map((m) => (
              <option key={m} value={m}>
                {m} 月
              </option>
            ))}
          </select>
        </Field>
        <Field label="抄表人 *">
          <input value={form.reader} onChange={set('reader')} placeholder="请输入抄表人姓名" />
        </Field>
        <Field label="抄表时间">
          <input type="datetime-local" value={form.recorded_at} onChange={set('recorded_at')} />
        </Field>
        {!editing && baseline?.exists ? (
          <div className="alert alert-warning" style={{ gridColumn: '1 / -1' }}>
            该公厕 {form.year} 年 {form.month} 月已存在记录，重复提交将被拒绝
          </div>
        ) : null}
      </form>

      <UtilityBlock
        kind="water"
        dictionaries={dictionaries}
        reading={form.water_reading}
        setReading={(v) => setForm((p) => ({ ...p, water_reading: v }))}
        auto={waterAuto}
        setAuto={setWaterAuto}
        manualFee={waterFee}
        setManualFee={setWaterFee}
        baseline={baseline}
      />
      <UtilityBlock
        kind="elec"
        dictionaries={dictionaries}
        reading={form.elec_reading}
        setReading={(v) => setForm((p) => ({ ...p, elec_reading: v }))}
        auto={elecAuto}
        setAuto={setElecAuto}
        manualFee={elecFee}
        setManualFee={setElecFee}
        baseline={baseline}
      />

      <Field label="备注" full>
        <textarea
          rows="2"
          value={form.remark || ''}
          onChange={set('remark')}
          placeholder="异常情况说明、现场核查结论等（可选）"
        />
      </Field>
    </Modal>
  );
}
