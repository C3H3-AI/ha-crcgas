/**
 * crcgas-statistics-card — 华润燃气月度用气量和燃气费趋势卡片
 *
 * 配置示例:
 *   type: custom:crcgas-statistics-card
 *   title: 燃气用量统计   (可选，默认: 🔥 燃气用量统计)
 *   year: 2026          (可选，默认: 当前年)
 *   gas_statistic: crcgas:monthly_gas_usage  (可选，默认)
 *   bill_statistic: crcgas:monthly_bill_amount (可选，默认)
 *   entity: sensor.crcgas_account_balance    (可选，用于显示当前余额)
 */

import { LitElement, html, css } from 'lit';

/* ─── SVG 工具 ─── */
function barSvg(values, maxVal, unit, color, height = 100, barWidth = 20, gap = 6) {
  const total = values.length * (barWidth + gap) - gap;
  const w = Math.max(total, 180);
  const bars = values.map((v, i) => {
    const h = maxVal > 0 ? (v / maxVal) * (height - 10) : 0;
    const x = i * (barWidth + gap);
    const y = height - h;
    return `<rect x="${x}" y="${y}" width="${barWidth}" height="${h || 1}" rx="3" fill="${color}" opacity="${v > 0 ? 0.85 : 0.15}"/>`;
  }).join('');

  // Month labels along bottom
  const labels = values.map((v, i) => {
    const x = i * (barWidth + gap) + barWidth / 2;
    return `<text x="${x}" y="${height + 4}" text-anchor="middle" font-size="8" fill="var(--secondary-text-color, #888)">${i + 1}</text>`;
  }).join('');

  return `<svg width="${w}" height="${height + 14}" viewBox="0 0 ${w} ${height + 14}">${bars}${labels}</svg>`;
}

/* ─── 卡片定义 ─── */
class CrcgasStatisticsCard extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      config: { type: Object },
      _year: { type: Number, state: true },
      _gasData: { type: Array, state: true },
      _billData: { type: Array, state: true },
      _totals: { type: Object, state: true },
      _loading: { type: Boolean, state: true },
      _error: { type: String, state: true },
    };
  }

  setConfig(config) {
    this.config = {
      title: config.title || '🔥 燃气用量统计',
      gas_statistic: config.gas_statistic || 'crcgas:monthly_gas_usage',
      bill_statistic: config.bill_statistic || 'crcgas:monthly_bill_amount',
      entity: config.entity || '',
      ...config,
    };
    if (!this._year) this._year = new Date().getFullYear();
  }

  getCardSize() { return 7; }

  connectedCallback() {
    super.connectedCallback();
    if (this.hass && !this._year) {
      this._year = new Date().getFullYear();
      this._loadData();
    }
  }

  updated(changedProps) {
    super.updated(changedProps);
    if (changedProps.has('hass') && this.hass && !this._gasData) {
      if (!this._year) this._year = new Date().getFullYear();
      this._loadData();
    }
  }

  async _loadData() {
    if (!this.hass) return;
    this._loading = true;
    this._error = '';
    const year = this._year;

    try {
      const start = `${year}-01-01T00:00:00+08:00`;
      const end = `${year + 1}-01-01T00:00:00+08:00`;

      const [gasResult, billResult] = await Promise.all([
        this.hass.callWS({
          type: 'recorder/statistics_during_period',
          statistic_ids: [this.config.gas_statistic],
          start_time: start,
          end_time: end,
          period: 'month',
        }),
        this.hass.callWS({
          type: 'recorder/statistics_during_period',
          statistic_ids: [this.config.bill_statistic],
          start_time: start,
          end_time: end,
          period: 'month',
        }),
      ]);

      // Parse gas data — extract per-month state values
      const gasRaw = gasResult?.[this.config.gas_statistic] || [];
      const billRaw = billResult?.[this.config.bill_statistic] || [];

      // group by month (1-12)
      const gasByMonth = new Array(12).fill(0);
      const billByMonth = new Array(12).fill(0);

      for (const entry of gasRaw) {
        const d = new Date(entry.start);
        const m = d.getUTCMonth(); // 0-based
        if (m >= 0 && m < 12) gasByMonth[m] += (entry.sum || 0);
      }

      for (const entry of billRaw) {
        const d = new Date(entry.start);
        const m = d.getUTCMonth();
        if (m >= 0 && m < 12) billByMonth[m] += (entry.sum || 0);
      }

      // Calculate deltas between months for "total_increasing" type
      const gasMonthly = new Array(12).fill(0);
      const billMonthly = new Array(12).fill(0);
      let prevGas = 0, prevBill = 0;
      for (let i = 0; i < 12; i++) {
        gasMonthly[i] = Math.round((gasByMonth[i] - prevGas) * 100) / 100;
        billMonthly[i] = Math.round((billByMonth[i] - prevBill) * 100) / 100;
        prevGas = gasByMonth[i];
        prevBill = billByMonth[i];
      }

      // Totals
      const totalGas = gasMonthly.reduce((a, b) => a + b, 0);
      const totalBill = billMonthly.reduce((a, b) => a + b, 0);
      const monthsWithData = gasMonthly.filter(v => v > 0).length;

      this._gasData = gasMonthly;
      this._billData = billMonthly;
      this._totals = { totalGas, totalBill, monthsWithData };
      this._loading = false;
    } catch (e) {
      this._error = e.message || '数据加载失败';
      this._loading = false;
    }
  }

  _changeYear(delta) {
    this._year += delta;
    this._gasData = null;
    this._billData = null;
    this._totals = null;
    this._loadData();
  }

  _format(v) {
    return typeof v === 'number' ? v.toFixed(1) : '0';
  }

  render() {
    const title = this.config.title;
    const currentYear = new Date().getFullYear();

    return html`
      <ha-card>
        <div class="header">
          <span class="title">${title}</span>
          <div class="year-nav">
            <button class="nav-btn" @click=${() => this._changeYear(-1)}
              ?disabled=${this._loading}>‹</button>
            <span class="year-label">${this._year}</span>
            <button class="nav-btn" @click=${() => this._changeYear(1)}
              ?disabled=${this._loading || this._year >= currentYear}>›</button>
          </div>
        </div>

        ${this._loading ? html`
          <div class="loading">
            <ha-circular-progress size="small" active></ha-circular-progress>
            <span>加载中...</span>
          </div>
        ` : this._error ? html`
          <div class="error">⚠ ${this._error}</div>
        ` : this._gasData ? html`
          <div class="charts">
            <div class="chart-section">
              <div class="chart-title">
                <ha-icon icon="mdi:fire" style="width:16px;height:16px;color:var(--warning-color,#ff9800)"></ha-icon>
                <span>月度用气量 (m³)</span>
              </div>
              <div class="chart-body chart-gas">
                ${this._renderSvgChart('gas')}
              </div>
            </div>

            <div class="chart-section">
              <div class="chart-title">
                <ha-icon icon="mdi:currency-cny" style="width:16px;height:16px;color:var(--success-color,#43a047)"></ha-icon>
                <span>月度燃气费 (¥)</span>
              </div>
              <div class="chart-body chart-bill">
                ${this._renderSvgChart('bill')}
              </div>
            </div>
          </div>

          <div class="summary">
            <div class="sum-item">
              <span class="sum-label">${this._year} 年用量</span>
              <span class="sum-val">${this._format(this._totals.totalGas)} m³</span>
            </div>
            <div class="sum-item">
              <span class="sum-label">${this._year} 年费用</span>
              <span class="sum-val">¥${this._format(this._totals.totalBill)}</span>
            </div>
            <div class="sum-item">
              <span class="sum-label">有数据月数</span>
              <span class="sum-val">${this._totals.monthsWithData} 个月</span>
            </div>
            ${this.config.entity && this.hass?.states?.[this.config.entity] ? html`
              <div class="sum-item">
                <span class="sum-label">当前余额</span>
                <span class="sum-val">¥${this._format(this.hass.states[this.config.entity].state)}</span>
              </div>
            ` : ''}
          </div>
        ` : html`
          <div class="empty">暂无数据</div>
        `}
      </ha-card>
    `;
  }

  _renderSvgChart(type) {
    const data = type === 'gas' ? this._gasData : this._billData;
    if (!data) return '';
    const max = Math.max(...data, 1);
    const color = type === 'gas'
      ? 'var(--warning-color, #ff9800)'
      : 'var(--success-color, #43a047)';
    return html`<div class="svg-wrap">${barSvg(data, max, type === 'gas' ? 'm³' : '¥', color)}</div>`;
  }

  static get styles() {
    return css`
      :host { display: block; }
      ha-card {
        padding: 14px 16px 12px;
        font-family: var(--paper-font-body1_-_font-family, inherit);
      }
      .header {
        display: flex; align-items: center; justify-content: space-between;
        margin-bottom: 12px;
      }
      .title {
        font-size: 16px; font-weight: 600;
        color: var(--primary-text-color);
      }
      .year-nav {
        display: flex; align-items: center; gap: 6px;
      }
      .nav-btn {
        width: 28px; height: 28px; border-radius: 50%;
        border: 1px solid var(--divider-color, #ddd);
        background: var(--card-background-color, #fff);
        color: var(--primary-text-color);
        font-size: 16px; cursor: pointer;
        display: flex; align-items: center; justify-content: center;
        line-height: 1; padding: 0;
      }
      .nav-btn:disabled { opacity: 0.3; cursor: default; }
      .nav-btn:hover:not(:disabled) {
        background: var(--secondary-background-color, #f5f5f5);
      }
      .year-label {
        font-size: 14px; font-weight: 500; min-width: 42px; text-align: center;
      }

      .loading {
        display: flex; align-items: center; justify-content: center; gap: 8px;
        padding: 30px 0; color: var(--secondary-text-color); font-size: 13px;
      }
      .error { padding: 20px; text-align: center; font-size: 13px; color: var(--error-color, #db4437); }
      .empty { padding: 30px; text-align: center; font-size: 13px; color: var(--secondary-text-color); }

      .charts { display: flex; flex-direction: column; gap: 14px; }
      .chart-section { }
      .chart-title {
        display: flex; align-items: center; gap: 4px;
        font-size: 11px; font-weight: 500;
        color: var(--secondary-text-color); margin-bottom: 4px;
      }
      .svg-wrap {
        overflow-x: auto; overflow-y: hidden;
        -webkit-overflow-scrolling: touch;
        padding: 2px 0;
      }
      .svg-wrap::-webkit-scrollbar { height: 3px; }
      .svg-wrap::-webkit-scrollbar-thumb { background: var(--scrollbar-thumb-color, #ccc); border-radius: 3px; }

      .summary {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
        gap: 8px; margin-top: 12px; padding-top: 10px;
        border-top: 1px solid var(--divider-color, #eee);
      }
      .sum-item {
        text-align: center;
      }
      .sum-label {
        display: block; font-size: 10px;
        color: var(--secondary-text-color); margin-bottom: 2px;
      }
      .sum-val {
        display: block; font-size: 15px; font-weight: 600;
        color: var(--primary-text-color);
      }
    `;
  }
}

customElements.define('crcgas-statistics-card', CrcgasStatisticsCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'crcgas-statistics-card',
  name: '华润燃气统计',
  description: '显示华润燃气的月度用气量和费用趋势图',
  preview: true,
});
