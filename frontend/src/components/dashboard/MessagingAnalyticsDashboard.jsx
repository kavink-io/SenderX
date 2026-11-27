import React, { useEffect, useMemo, useState } from 'react';
import { useAppScope } from '../../context/ScopeContext';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import ApiClient from '../../services/api';
import { AnimatedNumber, GlassCard, GlassSkeleton } from '../glass';

const CHANNELS = ['WhatsApp', 'Email', 'SMS', 'Telegram'];
const CHANNEL_COLORS = {
  email: '#8b80f9',
  sms: '#6267e8',
  whatsapp: '#aeb8ff',
  telegram: '#45a6d9',
};

function utcDateString(value) {
  return value.toISOString().slice(0, 10);
}

function getDateRange(days) {
  const end = new Date();
  end.setUTCHours(0, 0, 0, 0);
  const start = new Date(end);
  start.setUTCDate(start.getUTCDate() - days + 1);
  return { start_date: utcDateString(start), end_date: utcDateString(end) };
}

function fillDailyTrends(rows, range) {
  if (!Array.isArray(rows) || !rows.length) return [];
  const values = new Map(rows.map((row) => [row.date, row]));
  const points = [];
  const cursor = new Date(`${range.start_date}T00:00:00Z`);
  const last = new Date(`${range.end_date}T00:00:00Z`);
  while (cursor <= last) {
    const date = utcDateString(cursor);
    const row = values.get(date);
    points.push({
      date,
      label: cursor.toLocaleDateString(undefined, { month: 'short', day: 'numeric', timeZone: 'UTC' }),
      total: Number(row?.total) || 0,
      delivered: Number(row?.delivered ?? row?.sent) || 0,
      failed: Number(row?.failed) || 0,
    });
    cursor.setUTCDate(cursor.getUTCDate() + 1);
  }
  return points;
}

function MetricCard({ label, value, note, isLoading }) {
  return (
    <div className="saas-metric">
      <div className="saas-metric-label">{label}</div>
      <div className="saas-metric-value">
        {isLoading ? <GlassSkeleton width="86px" height="27px" /> : value === null ? '—' : (
          typeof value === 'number' ? <AnimatedNumber value={value} /> : value
        )}
      </div>
      <div className="saas-metric-note">{note}</div>
    </div>
  );
}

function EmptyChart({ children }) {
  return <div className="saas-chart-empty">{children}</div>;
}

function DailyLineChart({ data, isLoading, firstKey, secondKey, label }) {
  if (isLoading) return <GlassSkeleton width="100%" height="250px" />;
  if (!data.length) return <EmptyChart>No message data is available for this date range.</EmptyChart>;

  const chartWidth = 1000;
  const chartHeight = 250;
  const left = 54;
  const right = 12;
  const top = 14;
  const bottom = 32;
  const plotWidth = chartWidth - left - right;
  const plotHeight = chartHeight - top - bottom;
  const maxValue = Math.max(1, ...data.map((point) => Math.max(point[firstKey] || 0, point[secondKey] || 0)));
  const x = (index) => left + (data.length < 2 ? plotWidth / 2 : (index / (data.length - 1)) * plotWidth);
  const y = (value) => top + plotHeight - ((Number(value) || 0) / maxValue) * plotHeight;
  const path = (key) => data.map((point, index) => `${index === 0 ? 'M' : 'L'} ${x(index)} ${y(point[key])}`).join(' ');
  const labelsEvery = Math.max(1, Math.ceil(data.length / 7));

  return (
    <div className="saas-chart saas-report-chart">
      <svg viewBox={`0 0 ${chartWidth} ${chartHeight}`} role="img" aria-label={label} preserveAspectRatio="none">
        {Array.from({ length: 5 }, (_, index) => {
          const value = Math.round((maxValue * index) / 4);
          const lineY = top + plotHeight - (index / 4) * plotHeight;
          return (
            <g key={index}>
              <line x1={left} x2={chartWidth - right} y1={lineY} y2={lineY} className="saas-chart-grid" />
              <text x={left - 10} y={lineY + 4} textAnchor="end" className="saas-chart-axis">{value.toLocaleString()}</text>
            </g>
          );
        })}
        <path d={path(firstKey)} className="saas-chart-line saas-chart-line-primary" />
        <path d={path(secondKey)} className="saas-chart-line saas-chart-line-secondary" />
        {data.map((point, index) => (
          (index % labelsEvery === 0 || index === data.length - 1) && (
            <text key={point.date} x={x(index)} y={chartHeight - 8} textAnchor="middle" className="saas-chart-axis">
              {point.label}
            </text>
          )
        ))}
      </svg>
    </div>
  );
}

function DeliveryOutcomeChart({ data, isLoading }) {
  if (isLoading) return <GlassSkeleton width="100%" height="250px" />;
  const outcomes = data.map((point) => point.delivered + point.failed);
  if (!outcomes.some(Boolean)) return <EmptyChart>No completed delivery outcomes are available for this range.</EmptyChart>;

  const chartWidth = 1000;
  const chartHeight = 250;
  const left = 54;
  const right = 12;
  const top = 14;
  const bottom = 32;
  const plotWidth = chartWidth - left - right;
  const plotHeight = chartHeight - top - bottom;
  const maxValue = Math.max(1, ...outcomes);
  const step = plotWidth / data.length;
  const barWidth = Math.max(2, step * 0.58);
  const labelsEvery = Math.max(1, Math.ceil(data.length / 7));

  return (
    <div className="saas-chart saas-report-chart">
      <svg viewBox={`0 0 ${chartWidth} ${chartHeight}`} role="img" aria-label="Daily delivered and failed messages" preserveAspectRatio="none">
        {data.map((point, index) => {
          const x = left + index * step + (step - barWidth) / 2;
          const deliveredHeight = (point.delivered / maxValue) * plotHeight;
          const failedHeight = (point.failed / maxValue) * plotHeight;
          const baseline = top + plotHeight;
          return (
            <g key={point.date}>
              <rect x={x} y={baseline - deliveredHeight} width={barWidth} height={deliveredHeight} fill="var(--chart-secondary)" rx="2" />
              <rect x={x} y={baseline - deliveredHeight - failedHeight} width={barWidth} height={failedHeight} fill="var(--status-error)" rx="2" />
              {(index % labelsEvery === 0 || index === data.length - 1) && (
                <text x={x + barWidth / 2} y={chartHeight - 8} textAnchor="middle" className="saas-chart-axis">{point.label}</text>
              )}
            </g>
          );
        })}
        <line x1={left} x2={chartWidth - right} y1={top + plotHeight} y2={top + plotHeight} className="saas-chart-grid" />
      </svg>
    </div>
  );
}

function BreakdownList({ rows, isLoading, emptyText, getLabel, getValue, maxValue, color }) {
  if (isLoading) return <GlassSkeleton width="100%" height="150px" />;
  if (!rows.length) return <div className="saas-empty-state">{emptyText}</div>;
  const max = Math.max(1, Number(maxValue) || 0, ...rows.map(getValue));
  return (
    <div className="saas-channel-list">
      {rows.map((row, index) => {
        const value = Number(getValue(row)) || 0;
        const width = Math.max(0, Math.min(100, (value / max) * 100));
        const rowColor = typeof color === 'function' ? color(row, index) : color;
        return (
          <div className="saas-channel-row" key={`${getLabel(row)}-${index}`}>
            <div className="saas-channel-heading">
              <span><i style={{ backgroundColor: rowColor || 'var(--accent-blue)' }} />{getLabel(row)}</span>
              <strong>{value.toLocaleString()}</strong>
            </div>
            <div className="saas-channel-track">
              <span style={{ width: `${width}%`, backgroundColor: rowColor || 'var(--accent-blue)' }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function formatDuration(milliseconds) {
  if (milliseconds < 1000) return `${Math.round(milliseconds)} ms`;
  if (milliseconds < 60000) return `${(milliseconds / 1000).toFixed(2)} s`;
  return `${(milliseconds / 60000).toFixed(2)} min`;
}

function buildAnalyticsRows(report) {
  return [
    ['Section', 'Metric', 'Date or channel', 'Value'],
    ['Summary', 'Total messages', '', report.overview?.total_messages ?? ''],
    ['Summary', 'Delivery rate (%)', '', report.overview?.delivery_rate_percent ?? ''],
    ['Summary', 'Failure rate (%)', '', report.overview?.failure_rate_percent ?? ''],
    ['Summary', 'Average delivery time (ms)', '', report.overview?.average_delivery_time_ms ?? 'Unavailable'],
    ...((report.daily_trends || []).map((item) => ['Daily trend', 'Messages', item.date, item.total])),
    ...((report.daily_trends || []).map((item) => ['Daily trend', 'Delivered', item.date, item.delivered ?? item.sent])),
    ...((report.daily_trends || []).map((item) => ['Daily trend', 'Failed', item.date, item.failed])),
    ...((report.channels || []).map((item) => ['Channel', 'Messages', item.channel, item.count])),
    ...((report.channels || []).map((item) => ['Channel', 'Delivered', item.channel, item.delivered ?? item.sent])),
    ...((report.channels || []).map((item) => ['Channel', 'Failed', item.channel, item.failed])),
    ...((report.failure_reasons || []).map((item) => ['Failure reason', item.reason, '', item.count])),
    ...((report.hourly_trends || []).map((item) => ['Hourly trend', 'Messages', `${String(item.hour).padStart(2, '0')}:00 UTC`, item.total])),
    ...((report.delivery_latency_trends || []).map((item) => ['Delivery latency', 'Average milliseconds', item.date, item.average_ms])),
  ];
}

function downloadCsv(report, range) {
  const rows = buildAnalyticsRows(report);
  const csv = rows.map((row) => row.map((value) => `"${String(value ?? '').replace(/"/g, '""')}"`).join(',')).join('\r\n');
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `senderx-analytics-${range.start_date}-to-${range.end_date}.csv`;
  anchor.click();
  URL.revokeObjectURL(url);
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (character) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  }[character]));
}

function buildPrintableReport(report, range) {
  const rows = buildAnalyticsRows(report);
  const headers = rows[0].map((value) => `<th scope="col">${escapeHtml(value)}</th>`).join('');
  const body = rows.slice(1).map((row) => (
    `<tr>${row.map((value) => `<td>${escapeHtml(value)}</td>`).join('')}</tr>`
  )).join('');
  const exportDate = new Date();
  const exportTimestamp = exportDate.toLocaleString();
  const fileTitle = `senderx-analytics-${range.start_date}-to-${range.end_date}`;

  return `<!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>${escapeHtml(fileTitle)}</title>
        <style>
          @page { size: landscape; margin: 14mm; }
          * { box-sizing: border-box; }
          body { color: #172033; font: 10pt/1.45 Arial, sans-serif; margin: 0; }
          header { border-bottom: 2px solid #635bdb; margin-bottom: 18px; padding-bottom: 12px; }
          header strong { color: #5146c8; font-size: 13pt; letter-spacing: .04em; }
          h1 { font-size: 19pt; margin: 10px 0 4px; }
          header p { color: #596579; margin: 3px 0; }
          table { border-collapse: collapse; table-layout: fixed; width: 100%; }
          thead { display: table-header-group; }
          tr { break-inside: avoid; page-break-inside: avoid; }
          th, td { border: 1px solid #d8deea; overflow-wrap: anywhere; padding: 6px 8px; text-align: left; }
          th { background: #f0f2fb; color: #25304a; font-weight: 700; }
          tbody tr:nth-child(even) { background: #f8f9fc; }
          @media print { a { color: inherit; text-decoration: none; } }
        </style>
      </head>
      <body>
        <header>
          <strong>SenderX</strong>
          <h1>Messaging Analytics</h1>
          <p>Report period: ${escapeHtml(range.start_date)} through ${escapeHtml(range.end_date)} (UTC)</p>
          <p>Exported: ${escapeHtml(exportTimestamp)}</p>
        </header>
        <table>
          <thead><tr>${headers}</tr></thead>
          <tbody>${body}</tbody>
        </table>
      </body>
    </html>`;
}

export default function MessagingAnalyticsDashboard({ paneId = 'tab-org-analytics' }) {
  const { activeAppId } = useAppScope();
  const { hasPermission } = useAuth();
  const { showToast } = useToast();
  const [activePreset, setActivePreset] = useState('7d');
  const [appliedRange, setAppliedRange] = useState(() => getDateRange(7));
  const [customStart, setCustomStart] = useState(() => getDateRange(7).start_date);
  const [customEnd, setCustomEnd] = useState(() => getDateRange(7).end_date);
  const [rangeError, setRangeError] = useState('');
  const [report, setReport] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isExportingPdf, setIsExportingPdf] = useState(false);
  const [loadError, setLoadError] = useState('');
  const canReadAnalytics = hasPermission('organization:analytics:read');

  useEffect(() => {
    let active = true;
    async function loadReport() {
      setIsLoading(true);
      setLoadError('');
      if (!canReadAnalytics) {
        setReport(null);
        setLoadError('Analytics data is not available to your role.');
        setIsLoading(false);
        return;
      }
      try {
        const result = await ApiClient.getOrganizationAnalytics({
          ...appliedRange,
          include_details: true,
        });
        if (!result?.success) throw new Error(result?.message || 'The analytics request failed.');
        if (active) setReport(result);
      } catch (error) {
        console.error('Failed to load organization analytics:', error);
        if (active) {
          setReport(null);
          setLoadError('Analytics data could not be loaded from SenderX.');
          showToast('Could not load analytics data', 'error');
        }
      } finally {
        if (active) setIsLoading(false);
      }
    }
    loadReport();
    return () => { active = false; };
  }, [activeAppId, appliedRange, canReadAnalytics, showToast]);

  const dailyTrends = useMemo(
    () => fillDailyTrends(report?.daily_trends, appliedRange),
    [report, appliedRange]
  );
  const channels = Array.isArray(report?.channels) ? report.channels : [];
  const hourlyTrends = Array.isArray(report?.hourly_trends) ? report.hourly_trends : [];
  const latencyTrends = Array.isArray(report?.delivery_latency_trends) ? report.delivery_latency_trends : [];
  const failureReasons = Array.isArray(report?.failure_reasons) ? report.failure_reasons : [];
  const overview = report?.overview || {};

  const selectPreset = (preset, days) => {
    setActivePreset(preset);
    setRangeError('');
    setAppliedRange(getDateRange(days));
  };

  const applyCustomRange = () => {
    if (!customStart || !customEnd) {
      setRangeError('Choose both a start and end date.');
      return;
    }
    if (customStart > customEnd) {
      setRangeError('The start date must be on or before the end date.');
      return;
    }
    setRangeError('');
    setActivePreset('custom');
    setAppliedRange({ start_date: customStart, end_date: customEnd });
  };

  const exportPdf = () => {
    if (!report || isLoading || isExportingPdf) return;
    const printWindow = window.open('', '_blank');
    if (!printWindow) {
      showToast('Allow pop-ups to print or save this report as a PDF.', 'error');
      return;
    }

    setIsExportingPdf(true);
    printWindow.opener = null;
    let exportFinished = false;
    let exportTimeout;
    const releaseExport = () => {
      if (exportFinished) return;
      exportFinished = true;
      window.clearTimeout(exportTimeout);
      setIsExportingPdf(false);
    };
    const finishExport = () => {
      releaseExport();
      if (!printWindow.closed) printWindow.close();
    };

    try {
      printWindow.document.open();
      printWindow.document.write(buildPrintableReport(report, appliedRange));
      printWindow.document.close();
      printWindow.addEventListener('afterprint', finishExport, { once: true });
      printWindow.addEventListener('pagehide', releaseExport, { once: true });
      window.setTimeout(() => {
        if (printWindow.closed) {
          releaseExport();
          return;
        }
        try {
          printWindow.focus();
          printWindow.print();
        } catch (error) {
          finishExport();
          showToast(error?.message || 'Could not open the print dialog.', 'error');
        }
      }, 250);
      exportTimeout = window.setTimeout(releaseExport, 60000);
    } catch (error) {
      finishExport();
      showToast(error?.message || 'Could not prepare the analytics report.', 'error');
    }
  };

  const channelRows = CHANNELS.map((name) => {
    const channel = channels.find((item) => String(item.channel || '').toLowerCase() === name.toLowerCase());
    const count = Number(channel?.count) || 0;
    const delivered = Number(channel?.delivered ?? channel?.sent) || 0;
    const failed = Number(channel?.failed) || 0;
    return {
      name,
      count: channel ? count.toLocaleString() : '—',
      delivered: channel ? delivered.toLocaleString() : '—',
      failed: channel ? failed.toLocaleString() : '—',
      rate: channel && count ? `${((delivered / count) * 100).toFixed(2)}%` : '—',
    };
  });

  return (
    <div className="tab-pane active saas-dashboard saas-analytics-report" id={paneId}>
      <div className="saas-report-heading">
        <div>
          <h1>Messaging Analytics</h1>
          <p>Historical delivery performance for {appliedRange.start_date} through {appliedRange.end_date} (UTC).</p>
        </div>
      </div>

      <div className="saas-report-toolbar">
        <div className="saas-report-filter-group" aria-label="Analytics date range">
          {[
            ['today', 'Today', 1],
            ['7d', 'Last 7 Days', 7],
            ['30d', 'Last 30 Days', 30],
            ['90d', 'Last 90 Days', 90],
          ].map(([preset, label, days]) => (
            <button type="button" key={preset} className={`saas-report-filter ${activePreset === preset ? 'active' : ''}`} onClick={() => selectPreset(preset, days)}>
              {label}
            </button>
          ))}
          <button type="button" className={`saas-report-filter ${activePreset === 'custom' ? 'active' : ''}`} onClick={() => { setActivePreset('custom'); setRangeError(''); }}>
            Custom Date Range
          </button>
        </div>
        <div className="saas-report-export">
          <button type="button" className="btn btn-secondary" disabled={!report || isLoading} onClick={() => downloadCsv(report, appliedRange)}>
            Export CSV
          </button>
          <button type="button" className="btn btn-secondary" disabled={!report || isLoading || isExportingPdf} onClick={exportPdf}>
            {isExportingPdf ? 'Preparing PDF…' : 'Export PDF'}
          </button>
        </div>
      </div>

      {activePreset === 'custom' && (
        <div className="saas-report-custom-range">
          <label>
            Start date
            <input type="date" className="form-control" value={customStart} max={customEnd || undefined} onChange={(event) => setCustomStart(event.target.value)} />
          </label>
          <label>
            End date
            <input type="date" className="form-control" value={customEnd} min={customStart || undefined} onChange={(event) => setCustomEnd(event.target.value)} />
          </label>
          <button type="button" className="btn btn-primary" onClick={applyCustomRange}>Apply dates</button>
        </div>
      )}
      {rangeError && <p className="saas-report-error" role="alert">{rangeError}</p>}
      {loadError && <p className="saas-report-error" role="alert">{loadError}</p>}

      <div className="saas-metrics-card">
        <MetricCard label="Total Messages" value={report ? Number(overview.total_messages) || 0 : null} note="In the selected date range" isLoading={isLoading} />
        <MetricCard label="Delivery Rate" value={report ? `${Number(overview.delivery_rate_percent || 0).toFixed(2)}%` : null} note="Successfully delivered or handed off" isLoading={isLoading} />
        <MetricCard label="Failure Rate" value={report ? `${Number(overview.failure_rate_percent || 0).toFixed(2)}%` : null} note="Failed or dead-lettered messages" isLoading={isLoading} />
        <MetricCard
          label="Average Delivery Time"
          value={overview.average_delivery_time_ms == null ? (report ? '—' : null) : formatDuration(Number(overview.average_delivery_time_ms))}
          note={overview.delivery_time_sample_size ? `Based on ${overview.delivery_time_sample_size.toLocaleString()} recorded status histories` : 'No delivery timing records for this range'}
          isLoading={isLoading}
        />
      </div>

      <div className="saas-report-grid">
        <GlassCard className="saas-analysis-card saas-report-card">
          <div className="saas-analysis-header">
            <div>
              <h2>Message Volume Over Time</h2>
              <p>Daily messages and successful delivery outcomes.</p>
            </div>
          </div>
          <div className="saas-chart-legend">
            <span><i className="legend-total" />Messages</span>
            <span><i className="legend-delivered" />Delivered</span>
          </div>
          <DailyLineChart data={dailyTrends} isLoading={isLoading} firstKey="total" secondKey="delivered" label="Daily message volume and deliveries" />
        </GlassCard>

        <GlassCard className="saas-analysis-card saas-report-card">
          <div className="saas-analysis-header">
            <div>
              <h2>Delivery Success vs Failure</h2>
              <p>Daily outcomes from persisted message status records.</p>
            </div>
          </div>
          <div className="saas-chart-legend">
            <span><i className="legend-delivered" />Delivered</span>
            <span><i className="saas-report-failed-legend" />Failed</span>
          </div>
          <DeliveryOutcomeChart data={dailyTrends} isLoading={isLoading} />
        </GlassCard>

        <GlassCard className="saas-analysis-card saas-report-card">
          <div className="saas-analysis-header">
            <div>
              <h2>Channel-wise Message Distribution</h2>
              <p>Message counts by channel for the selected period.</p>
            </div>
          </div>
          <BreakdownList
            rows={channels}
            isLoading={isLoading}
            emptyText="No channel data is available for this date range."
            getLabel={(row) => row.channel || 'Other'}
            getValue={(row) => row.count}
            color={(row) => CHANNEL_COLORS[String(row.channel || '').toLowerCase()]}
          />
        </GlassCard>

        <GlassCard className="saas-analysis-card saas-report-card">
          <div className="saas-analysis-header">
            <div>
              <h2>Channel Performance</h2>
              <p>Recorded delivery and failure totals by channel.</p>
            </div>
          </div>
          {isLoading ? <GlassSkeleton width="100%" height="180px" /> : (
            <div className="saas-operations-table-wrap">
              <table className="saas-operations-table saas-channel-performance-table">
                <thead>
                  <tr><th>Channel</th><th>Messages</th><th>Delivered</th><th>Failed</th><th>Rate</th></tr>
                </thead>
                <tbody>
                  {channelRows.map((row) => (
                    <tr key={row.name}>
                      <td>{row.name}</td><td>{row.count}</td><td>{row.delivered}</td><td>{row.failed}</td><td>{row.rate}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </GlassCard>

        <GlassCard className="saas-analysis-card saas-report-card">
          <div className="saas-analysis-header">
            <div>
              <h2>Hourly Message Trends</h2>
              <p>UTC hour-of-day totals across the selected range.</p>
            </div>
          </div>
          <BreakdownList
            rows={hourlyTrends}
            isLoading={isLoading}
            emptyText="Hourly message data is not available for this range."
            getLabel={(row) => `${String(row.hour).padStart(2, '0')}:00 UTC`}
            getValue={(row) => row.total}
            maxValue={Math.max(1, ...hourlyTrends.map((row) => Number(row.total) || 0))}
            color="var(--chart-primary)"
          />
        </GlassCard>

        <GlassCard className="saas-analysis-card saas-report-card">
          <div className="saas-analysis-header">
            <div>
              <h2>Delivery Latency Trends</h2>
              <p>Message creation to first successful provider handoff.</p>
            </div>
          </div>
          {latencyTrends.length ? (
            <BreakdownList
              rows={latencyTrends}
              isLoading={isLoading}
              emptyText="No delivery timing records are available for this range."
              getLabel={(row) => row.date}
              getValue={(row) => row.average_ms}
              color="var(--chart-secondary)"
            />
          ) : isLoading ? <GlassSkeleton width="100%" height="150px" /> : (
            <div className="saas-empty-state">No delivery timing records are available for this range.</div>
          )}
        </GlassCard>

        <GlassCard className="saas-analysis-card saas-report-card">
          <div className="saas-analysis-header">
            <div>
              <h2>Failure Reason Breakdown</h2>
              <p>Recorded provider error codes; message text is not exposed here.</p>
            </div>
          </div>
          <BreakdownList
            rows={failureReasons}
            isLoading={isLoading}
            emptyText="No failed messages or recorded failure codes are available for this range."
            getLabel={(row) => row.reason}
            getValue={(row) => row.count}
            color="var(--status-error)"
          />
        </GlassCard>

        <GlassCard className="saas-analysis-card saas-report-card">
          <div className="saas-analysis-header">
            <div>
              <h2>Organization-wise Performance</h2>
              <p>Cross-organization comparisons are restricted to platform administration.</p>
            </div>
          </div>
          <div className="saas-empty-state">This report contains data for the current organization only.</div>
        </GlassCard>
      </div>

      {report && (
        <div className="saas-report-footnote">
          CSV exports use the current organization, application scope, and date range. PDF export is not supported.
        </div>
      )}
    </div>
  );
}
