import Modal from '../../components/Modal.jsx';
import DetailList from '../../components/DetailList.jsx';
import {
  formatDateTime,
  formatMoney,
  formatNumber,
  formatChangePct,
  utilityStatusTone,
} from '../../utils/format.js';

function KindDetail({ title, data, unit }) {
  const rows = [
    { label: '本期表底', value: data.reading === null ? '未抄录' : formatNumber(data.reading) },
    { label: `本期用量（${unit}）`, value: formatNumber(data.usage) },
    {
      label: '计费单价',
      value: data.unit_price === null ? '—' : `${formatMoney(data.unit_price)} 元/${unit}`,
    },
    {
      label: `费用（元）`,
      value: (
        <span className="inline">
          {formatMoney(data.fee)}
          <span className={`tag ${data.locked ? 'tag-warning' : 'tag-primary'}`}>
            {data.locked ? '手工' : '自动'}
          </span>
        </span>
      ),
    },
    {
      label: '环比增减量',
      value: data.change_amount === null ? '—' : `${data.change_amount > 0 ? '+' : ''}${formatNumber(data.change_amount)} ${unit}`,
    },
    { label: '环比幅度', value: formatChangePct(data.change_pct) },
    {
      label: '判定',
      value: <span className={`tag ${utilityStatusTone(data.status)}`}>{data.status}</span>,
    },
  ];

  return (
    <section className="card">
      <div className="card-title">
        <h3>{title}</h3>
      </div>
      <DetailList items={rows} />
      {data.reasons?.length ? (
        <div className="utility-reason-tags">
          {data.reasons.map((r) => (
            <span key={r} className="tag tag-warning">
              {r}
            </span>
          ))}
        </div>
      ) : null}
    </section>
  );
}

export default function UtilityDetailModal({ record, onClose }) {
  if (!record) return null;
  return (
    <Modal
      title={`水电抄表详情 - ${record.period_year} 年 ${record.period_month} 月`}
      onClose={onClose}
      width={860}
      footer={
        <button type="button" className="btn" onClick={onClose}>
          关闭
        </button>
      }
    >
      <section className="card">
        <div className="card-title">
          <h3>基本信息</h3>
          <span className={`tag ${record.status === '异常' ? 'tag-danger' : 'tag-success'}`}>
            {record.status}
          </span>
        </div>
        <DetailList
          items={[
            { label: '公厕', value: record.restroom ? `${record.restroom.name}（${record.restroom.code}）` : '—' },
            { label: '所属区域', value: record.restroom?.district ?? '—' },
            { label: '账期', value: `${record.period_year} 年 ${record.period_month} 月` },
            { label: '抄表人', value: record.reader || '—' },
            { label: '抄表时间', value: formatDateTime(record.recorded_at) },
            { label: '水电费用合计', value: `${formatMoney(record.total_fee)} 元` },
            { label: '备注', value: record.remark || '无' },
          ]}
        />
      </section>

      <KindDetail
        title="💧 用水明细"
        unit="吨"
        data={{
          reading: record.water_reading,
          usage: record.water_usage,
          unit_price: record.water_unit_price,
          fee: record.water_fee,
          locked: record.water_fee_locked,
          change_amount: record.water_change_amount,
          change_pct: record.water_change_pct,
          status: record.water_status,
          reasons: record.water_reasons,
        }}
      />
      <KindDetail
        title="⚡ 用电明细"
        unit="度"
        data={{
          reading: record.elec_reading,
          usage: record.elec_usage,
          unit_price: record.elec_unit_price,
          fee: record.elec_fee,
          locked: record.elec_fee_locked,
          change_amount: record.elec_change_amount,
          change_pct: record.elec_change_pct,
          status: record.elec_status,
          reasons: record.elec_reasons,
        }}
      />
    </Modal>
  );
}
