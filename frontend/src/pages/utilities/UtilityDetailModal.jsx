import DetailList from '../../components/DetailList.jsx';
import Modal from '../../components/Modal.jsx';
import { AbnormalTag, ChangePct } from '../../components/Tags.jsx';
import { formatDateTime, formatNumber, meterUnit } from '../../utils/format.js';

export default function UtilityDetailModal({ reading, onClose }) {
  const unit = meterUnit(reading.meter_type);
  return (
    <Modal
      title={`抄表详情 · ${reading.restroom?.name ?? ''} ${reading.period} ${reading.meter_type}`}
      onClose={onClose}
      width={620}
      footer={
        <button type="button" className="btn" onClick={onClose}>
          关闭
        </button>
      }
    >
      <DetailList
        items={[
          { label: '公厕', value: reading.restroom ? `${reading.restroom.name}（${reading.restroom.code}）` : '-' },
          { label: '所属区域', value: reading.restroom?.district ?? '-' },
          { label: '抄表月份', value: reading.period },
          { label: '表计类型', value: reading.meter_type },
          { label: '上期读数', value: reading.prev_reading === null ? '首次抄表' : `${formatNumber(reading.prev_reading)} ${unit}` },
          { label: '本期读数', value: `${formatNumber(reading.reading)} ${unit}` },
          { label: '本期用量', value: reading.usage === null ? '-' : `${formatNumber(reading.usage)} ${unit}` },
          { label: '单价', value: `${formatNumber(reading.unit_price)} 元/${unit}` },
          { label: '本期费用', value: reading.fee === null ? '-' : `${formatNumber(reading.fee)} 元` },
          { label: '环比上月', value: <ChangePct value={reading.change_pct} /> },
          { label: '状态', value: <AbnormalTag abnormal={reading.is_abnormal} /> },
          { label: '备注', value: reading.remark || '无' },
          { label: '登记时间', value: formatDateTime(reading.created_at) },
        ]}
      />
      {reading.is_abnormal && reading.abnormal_reasons?.length ? (
        <div className="alert alert-error" style={{ marginTop: 12 }}>
          <strong>异常提示与可能原因：</strong>
          <ul className="reason-list">
            {reading.abnormal_reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </Modal>
  );
}
