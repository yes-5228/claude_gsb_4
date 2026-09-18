import { useEffect, useMemo, useState } from 'react';

import { metaApi } from '../../api/meta.js';
import { utilityApi } from '../../api/utilities.js';
import Field from '../../components/Field.jsx';
import Modal from '../../components/Modal.jsx';
import { useToast } from '../../components/Toast.jsx';
import { formatNumber, meterUnit } from '../../utils/format.js';

function currentPeriod() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
}

export default function UtilityFormModal({ reading, onClose, onSaved }) {
  const toast = useToast();
  const isEdit = Boolean(reading);
  const [options, setOptions] = useState([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [form, setForm] = useState({
    restroom_id: reading?.restroom_id ?? '',
    meter_type: reading?.meter_type ?? '水表',
    period: reading?.period ?? currentPeriod(),
    reading: reading?.reading ?? '',
    prev_reading: reading?.prev_reading ?? '',
    unit_price: reading?.unit_price ?? '',
    remark: reading?.remark ?? '',
  });

  useEffect(() => {
    metaApi
      .restroomOptions()
      .then(setOptions)
      .catch((err) => setError(err.message));
  }, []);

  // 已填上期读数时实时预览用量与费用；留空则由服务端按上一月记录自动带出
  const preview = useMemo(() => {
    const current = Number(form.reading);
    const prev = Number(form.prev_reading);
    if (form.reading === '' || form.prev_reading === '' || Number.isNaN(current) || Number.isNaN(prev)) {
      return null;
    }
    const usage = Math.round((current - prev) * 100) / 100;
    const price = Number(form.unit_price) || 0;
    return { usage, fee: Math.round(usage * price * 100) / 100 };
  }, [form.reading, form.prev_reading, form.unit_price]);

  const update = (key, value) => setForm((prev) => ({ ...prev, [key]: value }));

  const submit = async (event) => {
    event.preventDefault();
    if (!form.restroom_id) {
      setError('请选择公厕');
      return;
    }
    if (form.reading === '' || Number(form.reading) < 0) {
      setError('请填写正确的本期读数');
      return;
    }
    setSaving(true);
    setError(null);
    const payload = {
      period: form.period,
      reading: Number(form.reading),
      prev_reading: form.prev_reading === '' ? null : Number(form.prev_reading),
      unit_price: form.unit_price === '' ? 0 : Number(form.unit_price),
      remark: form.remark || null,
    };
    try {
      if (isEdit) {
        await utilityApi.update(reading.id, payload);
        toast.success('抄表记录已更新');
      } else {
        await utilityApi.create({
          ...payload,
          restroom_id: Number(form.restroom_id),
          meter_type: form.meter_type,
        });
        toast.success('抄表记录已登记');
      }
      onSaved();
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      title={isEdit ? '编辑抄表记录' : '新增抄表记录'}
      onClose={onClose}
      width={640}
      footer={
        <>
          <button type="button" className="btn" onClick={onClose}>
            取消
          </button>
          <button type="submit" form="utility-form" className="btn btn-primary" disabled={saving}>
            {saving ? '提交中…' : isEdit ? '保存修改' : '提交登记'}
          </button>
        </>
      }
    >
      {error ? <div className="alert alert-error">{error}</div> : null}
      <form id="utility-form" onSubmit={submit} className="form-grid">
        <Field label="公厕 *">
          <select
            value={form.restroom_id}
            disabled={isEdit}
            onChange={(event) => update('restroom_id', event.target.value)}
          >
            <option value="">请选择公厕</option>
            {options.map((option) => (
              <option key={option.id} value={option.id}>
                {option.code} {option.name}（{option.district}）
              </option>
            ))}
          </select>
        </Field>
        <Field label="表计类型 *">
          <select
            value={form.meter_type}
            disabled={isEdit}
            onChange={(event) => update('meter_type', event.target.value)}
          >
            <option value="水表">水表</option>
            <option value="电表">电表</option>
          </select>
        </Field>
        <Field label="抄表月份 *">
          <input
            type="month"
            value={form.period}
            onChange={(event) => update('period', event.target.value)}
          />
        </Field>
        <Field label={`本期读数（${meterUnit(form.meter_type)}）*`}>
          <input
            type="number"
            min="0"
            step="0.01"
            value={form.reading}
            placeholder="水表/电表当前示数"
            onChange={(event) => update('reading', event.target.value)}
          />
        </Field>
        <Field label="上期读数">
          <input
            type="number"
            min="0"
            step="0.01"
            value={form.prev_reading}
            placeholder="留空自动取上一月读数"
            onChange={(event) => update('prev_reading', event.target.value)}
          />
        </Field>
        <Field label={`单价（元/${meterUnit(form.meter_type)}）`}>
          <input
            type="number"
            min="0"
            step="0.01"
            value={form.unit_price}
            placeholder="用于自动计算费用"
            onChange={(event) => update('unit_price', event.target.value)}
          />
        </Field>
        <Field label="备注" full>
          <textarea
            rows="2"
            value={form.remark}
            placeholder="换表、维修等特殊情况可在此说明"
            onChange={(event) => update('remark', event.target.value)}
          />
        </Field>
      </form>

      {preview ? (
        <div className={`alert ${preview.usage < 0 ? 'alert-error' : 'alert-info'}`}>
          {preview.usage < 0
            ? `本期读数低于上期读数 ${formatNumber(preview.usage)} ${meterUnit(form.meter_type)}，请核对（如遇换表请修正上期读数）`
            : `预计用量 ${formatNumber(preview.usage)} ${meterUnit(form.meter_type)}，费用 ${formatNumber(preview.fee)} 元；提交后自动计算环比并判断是否异常`}
        </div>
      ) : (
        <div className="alert alert-info">
          上期读数留空时将自动取该公厕上一月的抄表读数；用量、费用与环比由系统自动计算
        </div>
      )}
    </Modal>
  );
}
