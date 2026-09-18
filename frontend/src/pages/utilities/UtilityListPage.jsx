import { useState } from 'react';
import { Link } from 'react-router-dom';

import { restroomApi } from '../../api/restrooms.js';
import { utilityApi } from '../../api/utilities.js';
import DataTable from '../../components/DataTable.jsx';
import Field from '../../components/Field.jsx';
import PageHeader from '../../components/PageHeader.jsx';
import Pagination from '../../components/Pagination.jsx';
import StatCard from '../../components/StatCard.jsx';
import { AbnormalTag, ChangePct } from '../../components/Tags.jsx';
import { useToast } from '../../components/Toast.jsx';
import { useAsync } from '../../hooks/useAsync.js';
import { useListQuery } from '../../hooks/useListQuery.js';
import { formatNumber, meterUnit } from '../../utils/format.js';
import UtilityDetailModal from './UtilityDetailModal.jsx';
import UtilityFormModal from './UtilityFormModal.jsx';

const DEFAULT_FILTERS = {
  keyword: '',
  district: '',
  meter_type: '',
  period_from: '',
  period_to: '',
  abnormal_only: '',
};

export default function UtilityListPage() {
  const toast = useToast();
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null);
  const [active, setActive] = useState(null);

  const list = useListQuery(
    (params) => utilityApi.list({ ...params, abnormal_only: params.abnormal_only || undefined }),
    DEFAULT_FILTERS,
    10,
  );
  const { data: districts } = useAsync(() => restroomApi.districts(), []);
  const { data: summary, reload: reloadSummary } = useAsync(() => utilityApi.summary(), []);

  const reloadAll = () => {
    list.reload();
    reloadSummary();
  };

  const remove = async (row) => {
    const name = row.restroom?.name || '该公厕';
    if (!window.confirm(`确认删除 ${name} ${row.period} 的${row.meter_type}抄表记录？`)) return;
    try {
      await utilityApi.remove(row.id);
      toast.success('删除成功');
      reloadAll();
    } catch (err) {
      toast.error(err.message);
    }
  };

  return (
    <>
      <PageHeader
        title="水电计量"
        description="按月抄录水表电表读数，自动计算用量、费用与环比，超出正常区间（±30%）自动预警"
        actions={
          <button type="button" className="btn btn-primary" onClick={() => setShowForm(true)}>
            + 新增抄表记录
          </button>
        }
      />
      <div className="content">
        <div className="stat-grid">
          <StatCard
            label={`本月用水量（${summary?.period || '-'}）`}
            value={summary ? formatNumber(summary.water_usage) : '-'}
            unit="吨"
            foot={summary ? <ChangePct value={summary.water_change_pct} /> : null}
          />
          <StatCard
            label="本月水费"
            value={summary ? formatNumber(summary.water_fee) : '-'}
            unit="元"
            tone="info"
          />
          <StatCard
            label="本月用电量"
            value={summary ? formatNumber(summary.electricity_usage) : '-'}
            unit="度"
            foot={summary ? <ChangePct value={summary.electricity_change_pct} /> : null}
          />
          <StatCard
            label="本月电费"
            value={summary ? formatNumber(summary.electricity_fee) : '-'}
            unit="元"
            tone="info"
          />
          <StatCard
            label="本月异常记录"
            value={summary ? summary.abnormal_count : '-'}
            unit="条"
            tone={summary?.abnormal_count ? 'danger' : 'primary'}
            foot={summary ? `共抄表 ${summary.reading_count} 条` : null}
          />
        </div>

        <section className="card">
          <div className="filter-bar">
            <Field label="关键字" full>
              <input
                value={list.filters.keyword}
                placeholder="公厕名称 / 编号"
                onChange={(event) => list.updateFilter('keyword', event.target.value)}
              />
            </Field>
            <Field label="所属区域">
              <select
                value={list.filters.district}
                onChange={(event) => list.updateFilter('district', event.target.value)}
              >
                <option value="">全部</option>
                {(districts || []).map((item) => (
                  <option key={item}>{item}</option>
                ))}
              </select>
            </Field>
            <Field label="表计类型">
              <select
                value={list.filters.meter_type}
                onChange={(event) => list.updateFilter('meter_type', event.target.value)}
              >
                <option value="">全部</option>
                <option value="水表">水表</option>
                <option value="电表">电表</option>
              </select>
            </Field>
            <Field label="起始月份">
              <input
                type="month"
                value={list.filters.period_from}
                onChange={(event) => list.updateFilter('period_from', event.target.value)}
              />
            </Field>
            <Field label="结束月份">
              <input
                type="month"
                value={list.filters.period_to}
                onChange={(event) => list.updateFilter('period_to', event.target.value)}
              />
            </Field>
            <Field label="仅看异常">
              <select
                value={list.filters.abnormal_only}
                onChange={(event) => list.updateFilter('abnormal_only', event.target.value)}
              >
                <option value="">全部</option>
                <option value="true">仅异常</option>
              </select>
            </Field>
            <button type="button" className="btn" onClick={list.resetFilters}>
              重置
            </button>
          </div>
        </section>

        <section className="card">
          <DataTable
            loading={list.loading}
            error={list.error}
            rows={list.items}
            emptyText="暂无抄表记录"
            columns={[
              { key: 'period', title: '月份' },
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
              { key: 'meter_type', title: '表计' },
              {
                key: 'prev_reading',
                title: '上期读数',
                render: (row) => formatNumber(row.prev_reading),
              },
              { key: 'reading', title: '本期读数', render: (row) => formatNumber(row.reading) },
              {
                key: 'usage',
                title: '用量',
                render: (row) =>
                  row.usage === null ? '-' : `${formatNumber(row.usage)} ${meterUnit(row.meter_type)}`,
              },
              {
                key: 'fee',
                title: '费用',
                render: (row) => (row.fee === null ? '-' : `${formatNumber(row.fee)} 元`),
              },
              { key: 'change_pct', title: '环比', render: (row) => <ChangePct value={row.change_pct} /> },
              {
                key: 'is_abnormal',
                title: '状态',
                render: (row) => <AbnormalTag abnormal={row.is_abnormal} />,
              },
              {
                key: 'actions',
                title: '操作',
                render: (row) => (
                  <div className="inline">
                    <button type="button" className="btn-link" onClick={() => setActive(row)}>
                      详情
                    </button>
                    <button type="button" className="btn-link" onClick={() => setEditing(row)}>
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
        <UtilityFormModal onClose={() => setShowForm(false)} onSaved={reloadAll} />
      ) : null}

      {editing ? (
        <UtilityFormModal
          reading={editing}
          onClose={() => setEditing(null)}
          onSaved={reloadAll}
        />
      ) : null}

      {active ? <UtilityDetailModal reading={active} onClose={() => setActive(null)} /> : null}
    </>
  );
}
