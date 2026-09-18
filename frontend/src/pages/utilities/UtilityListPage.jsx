import { useState } from 'react';
import { Link } from 'react-router-dom';

import { utilityApi } from '../../api/utility.js';
import { restroomApi } from '../../api/restrooms.js';
import { metaApi } from '../../api/meta.js';
import DataTable from '../../components/DataTable.jsx';
import Field from '../../components/Field.jsx';
import PageHeader from '../../components/PageHeader.jsx';
import Pagination from '../../components/Pagination.jsx';
import { useToast } from '../../components/Toast.jsx';
import { useAsync } from '../../hooks/useAsync.js';
import { useListQuery } from '../../hooks/useListQuery.js';
import {
  formatChangePct,
  formatMoney,
  formatNumber,
  utilityOverallTone,
  utilityStatusTone,
} from '../../utils/format.js';
import { MONTH_OPTIONS, yearOptions } from '../../utils/utility.js';
import UtilityDetailModal from './UtilityDetailModal.jsx';
import UtilityFormModal from './UtilityFormModal.jsx';

const DEFAULT_FILTERS = {
  restroom_id: '',
  district: '',
  period_year: '',
  period_month: '',
  abnormal: '',
  reader: '',
};

function ChangeCell({ value, status, reasons }) {
  const abnormal = status && status !== '正常';
  const tone =
    status === '用量偏高' ? 'change-up' : status === '用量偏低' ? 'change-down' : '';
  return (
    <span
      className={`change-cell ${abnormal ? tone : ''}`}
      title={abnormal && reasons?.length ? `${status}：${reasons.join('；')}` : undefined}
    >
      {formatChangePct(value)}
    </span>
  );
}

function UsageCell({ usage, reading, unit }) {
  return (
    <span>
      {formatNumber(usage)} <span className="muted">{unit}</span>
      {reading !== null && reading !== undefined ? (
        <span className="muted utility-reading"> / 表底 {formatNumber(reading)}</span>
      ) : null}
    </span>
  );
}

export default function UtilityListPage() {
  const toast = useToast();
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null);
  const [detail, setDetail] = useState(null);

  const list = useListQuery((params) => utilityApi.list(params), DEFAULT_FILTERS, 10);
  const { data: districts } = useAsync(() => restroomApi.districts(), []);
  const { data: options } = useAsync(() => metaApi.restroomOptions(), []);

  const remove = async (row) => {
    if (!window.confirm(`确认删除 ${row.period_year} 年 ${row.period_month} 月该公厕的水电记录？删除后后续月份将重新环比。`)) return;
    try {
      await utilityApi.remove(row.id);
      toast.success('删除成功，后续月份已重新计算');
      list.reload();
    } catch (err) {
      toast.error(err.message);
    }
  };

  const abnormalCount = list.items.filter((row) => row.status === '异常').length;

  return (
    <>
      <PageHeader
        title="水电计量"
        description="按月抄录水表电表读数，自动核算用量费用、与上月环比，超阈值时提示可能原因"
        actions={
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => {
              setEditing(null);
              setShowForm(true);
            }}
          >
            + 登记抄表
          </button>
        }
      />
      <div className="content">
        <section className="card">
          <div className="filter-bar">
            <Field label="公厕">
              <select
                value={list.filters.restroom_id}
                onChange={(e) => list.updateFilter('restroom_id', e.target.value)}
              >
                <option value="">全部</option>
                {(options || []).map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.code} {o.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="所属区域">
              <select
                value={list.filters.district}
                onChange={(e) => list.updateFilter('district', e.target.value)}
              >
                <option value="">全部</option>
                {(districts || []).map((d) => (
                  <option key={d}>{d}</option>
                ))}
              </select>
            </Field>
            <Field label="年份">
              <select
                value={list.filters.period_year}
                onChange={(e) => list.updateFilter('period_year', e.target.value)}
              >
                <option value="">全部</option>
                {yearOptions(5).map((y) => (
                  <option key={y} value={y}>
                    {y} 年
                  </option>
                ))}
              </select>
            </Field>
            <Field label="月份">
              <select
                value={list.filters.period_month}
                onChange={(e) => list.updateFilter('period_month', e.target.value)}
              >
                <option value="">全部</option>
                {MONTH_OPTIONS.map((m) => (
                  <option key={m} value={m}>
                    {m} 月
                  </option>
                ))}
              </select>
            </Field>
            <Field label="状态">
              <select
                value={list.filters.abnormal}
                onChange={(e) => list.updateFilter('abnormal', e.target.value)}
              >
                <option value="">全部</option>
                <option value="true">仅看异常</option>
                <option value="false">仅看正常</option>
              </select>
            </Field>
            <Field label="抄表人">
              <input
                value={list.filters.reader}
                placeholder="抄表人姓名"
                onChange={(e) => list.updateFilter('reader', e.target.value)}
              />
            </Field>
            <button type="button" className="btn" onClick={list.resetFilters}>
              重置
            </button>
          </div>
        </section>

        <section className="card">
          <div className="card-title">
            <h3>月度水电台账</h3>
            <span className="hint">
              {abnormalCount > 0 ? `本页 ${abnormalCount} 条用量异常，悬停环比查看可能原因` : '环比阈值默认 ±30%（已扣除小幅波动）'}
            </span>
          </div>
          <DataTable
            loading={list.loading}
            error={list.error}
            rows={list.items}
            emptyText="暂无水电抄表记录"
            columns={[
              {
                key: 'period',
                title: '账期',
                render: (row) => `${row.period_year}-${String(row.period_month).padStart(2, '0')}`,
              },
              {
                key: 'restroom',
                title: '公厕',
                render: (row) =>
                  row.restroom ? (
                    <Link to={`/restrooms/${row.restroom.id}`}>{row.restroom.name}</Link>
                  ) : (
                    '-'
                  ),
              },
              { key: 'district', title: '区域', render: (row) => row.restroom?.district ?? '-' },
              {
                key: 'water_usage',
                title: '用水量（吨）',
                render: (row) => <UsageCell usage={row.water_usage} reading={row.water_reading} unit="吨" />,
              },
              {
                key: 'water_fee',
                title: '水费（元）',
                render: (row) => formatMoney(row.water_fee),
              },
              {
                key: 'water_change',
                title: '用水环比',
                render: (row) => (
                  <ChangeCell
                    value={row.water_change_pct}
                    status={row.water_status}
                    reasons={row.water_reasons}
                  />
                ),
              },
              {
                key: 'elec_usage',
                title: '用电量（度）',
                render: (row) => <UsageCell usage={row.elec_usage} reading={row.elec_reading} unit="度" />,
              },
              {
                key: 'elec_fee',
                title: '电费（元）',
                render: (row) => formatMoney(row.elec_fee),
              },
              {
                key: 'elec_change',
                title: '用电环比',
                render: (row) => (
                  <ChangeCell
                    value={row.elec_change_pct}
                    status={row.elec_status}
                    reasons={row.elec_reasons}
                  />
                ),
              },
              {
                key: 'total_fee',
                title: '合计费用',
                render: (row) => <strong>{formatMoney(row.total_fee)}</strong>,
              },
              {
                key: 'status',
                title: '状态',
                render: (row) => (
                  <span
                    className={`tag ${utilityOverallTone(row.status)}`}
                    title={
                      row.status === '异常'
                        ? [...(row.water_reasons || []), ...(row.elec_reasons || [])].join('；')
                        : undefined
                    }
                  >
                    {row.status}
                  </span>
                ),
              },
              {
                key: 'per_kind',
                title: '单项判定',
                render: (row) => (
                  <span className="inline">
                    {row.water_status !== '正常' ? (
                      <span className={`tag ${utilityStatusTone(row.water_status)}`}>水</span>
                    ) : null}
                    {row.elec_status !== '正常' ? (
                      <span className={`tag ${utilityStatusTone(row.elec_status)}`}>
                        {row.elec_status === '用量偏高' ? '电↑' : '电↓'}
                      </span>
                    ) : null}
                    {row.status === '正常' ? <span className="muted">—</span> : null}
                  </span>
                ),
              },
              { key: 'reader', title: '抄表人' },
              {
                key: 'actions',
                title: '操作',
                render: (row) => (
                  <div className="inline">
                    <button type="button" className="btn-link" onClick={() => setDetail(row)}>
                      详情
                    </button>
                    <button
                      type="button"
                      className="btn-link"
                      onClick={() => {
                        setEditing(row);
                        setShowForm(true);
                      }}
                    >
                      编辑
                    </button>
                    <button type="button" className="btn-link danger" onClick={() => remove(row)}>
                      删除
                    </button>
                  </div>
                ),
              },
            ]}
          />
          <Pagination meta={list.meta} onPageChange={list.setPage} />
        </section>
      </div>

      {showForm ? (
        <UtilityFormModal
          record={editing}
          onClose={() => setShowForm(false)}
          onSaved={list.reload}
        />
      ) : null}
      {detail ? <UtilityDetailModal record={detail} onClose={() => setDetail(null)} /> : null}
    </>
  );
}
