/**
 * crcgas-statistics-card — 华润燃气统计仪表盘卡片
 *
 * 借鉴 xiaoshi930/state_grid_info 卡片设计风格:
 * - 顶部余额+状态
 * - 阶梯用量进度条
 * - 月度柱状图（用气量+费用双轴）
 * - 底部汇总
 *
 * 配置示例:
 *   type: custom:crcgas-statistics-card
 *   title: 我家燃气统计
 *   entity: sensor.chu_fang_hua_run_ran_qi_ran_qi_zhang_hu_yu_e
 */

const MONTHS_ZH = ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'];

class CrcgasStatisticsCard extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      config: { type: Object },
      _year: { type: Number, state: true },
      _gasData: { type: Array, state: true },
      _billData: { type: Array, state: true },
      _totals: { type: Object, state: true },
      _balance: { type: Number, state: true },
      _step1Remain: { type: Number, state: true },
      _step2Remain: { type: Number, state: true },
      _status: { type: String, state: true },
      _loading: { type: Boolean, state: true },
      _error: { type: String, state: true },
      _showCost: { type: Boolean, state: true },
    };
  }

  setConfig(config) {
    if (!config) throw new Error('Invalid configuration');
    this.config = {
      title: config.title || '🔥 燃气统计',
      gasStatistic: config.gas_statistic || 'crcgas:monthly_gas_usage',
      billStatistic: config.bill_statistic || 'crcgas:monthly_bill_amount',
      balanceEntity: config.entity || '',
      year: config.year || new Date().getFullYear(),
    };
    this._year = this.config.year;
    this._showCost = true;
  }

  connectedCallback() {
    super.connectedCallback();
    this._loadData();
  }

  updated(changedProps) {
    super.updated(changedProps);
    if (changedProps.has('_year')) this._loadData();
  }

  async _loadData() {
    if (!this.hass) return;
    this._loading = true;
    this._error = '';
    try {
      const start = new Date(this._year, 0, 1).toISOString();
      const end = new Date(this._year + 1, 0, 1).toISOString();
      const [gasResult, billResult] = await Promise.all([
        this.hass.callWS({
          type: 'recorder/statistics_during_period',
          start_time: start,
          end_time: end,
          statistic_ids: [this.config.gasStatistic],
          period: 'month',
        }),
        this.hass.callWS({
          type: 'recorder/statistics_during_period',
          start_time: start,
          end_time: end,
          statistic_ids: [this.config.billStatistic],
          period: 'month',
        }),
      ]);

      const gasStats = gasResult?.[this.config.gasStatistic] || [];
      const billStats = billResult?.[this.config.billStatistic] || [];

      // Build month-indexed lookup
      const gasByMonth = {};
      for (const s of gasStats) {
        const d = new Date(s.start);
        const m = d.getMonth();
        gasByMonth[m] = s;
      }
      const billByMonth = {};
      for (const s of billStats) {
        const d = new Date(s.start);
        const m = d.getMonth();
        billByMonth[m] = s;
      }

      const gasData = [];
      const billData = [];
      let totalGas = 0, totalBill = 0, monthsWithData = 0;

      for (let m = 0; m < 12; m++) {
        const g = gasByMonth[m];
        const b = billByMonth[m];
        const gasVal = g ? (g.sum || g.state || 0) : 0;
        const billVal = b ? (b.sum || b.state || 0) : 0;
        gasData.push(Number(gasVal.toFixed(1)));
        billData.push(Number(billVal.toFixed(2)));
        if (g && g.sum > 0) { totalGas += (g.sum || g.state || 0); monthsWithData++; }
        if (b && b.sum > 0) totalBill += (b.sum || b.state || 0);
      }

      this._gasData = gasData;
      this._billData = billData;
      this._totals = {
        totalGas: Number(totalGas.toFixed(1)),
        totalBill: Number(totalBill.toFixed(2)),
        monthsWithData,
      };

      // Read current entity values for balance, tier, status
      if (this.config.balanceEntity && this.hass.states[this.config.balanceEntity]) {
        this._balance = parseFloat(this.hass.states[this.config.balanceEntity].state) || 0;
      }
      // Try to find step sensors
      const prefix = 'sensor.chu_fang_hua_run_ran_qi';
      const s1 = this.hass.states[`${prefix}_yi_dang_sheng_yu_qi_liang`];
      const s2 = this.hass.states[`${prefix}_er_dang_sheng_yu_qi_liang`];
      this._step1Remain = s1 ? parseFloat(s1.state) || 0 : null;
      this._step2Remain = s2 ? parseFloat(s2.state) || 0 : null;
      const st = this.hass.states[`${prefix}_ji_cheng_zhuang_tai`];
      this._status = st ? st.state : null;

    } catch (e) {
      console.error('crcgas-card: load failed', e);
      this._error = e.message || '数据加载失败';
    }
    this._loading = false;
  }

  /* ─── 渲染柱状图 ─── */
  _renderBars(values, unit, color, maxVal) {
    if (!values || values.length === 0) return html`<div class="empty">暂无数据</div>`;
    const max = maxVal || Math.max(...values, 1);
    const barWidth = 22;
    const gap = 4;
    return html`
      <div class="chart-container">
        <div class="y-label">${max}${unit}</div>
        <div class="bars">
          ${values.map((v, i) => {
            const h = max > 0 ? (v / max) * 120 : 0;
            const hasData = v > 0;
            return html`
              <div class="bar-col" @click=${() => this._showCost = !this._showCost}>
                <div class="bar-value" style="opacity:${hasData ? 1 : 0.3}">${hasData ? v.toFixed(v % 1 === 0 ? 0 : 1) : '-'}</div>
                <div class="bar-track">
                  <div class="bar-fill" style="height:${Math.max(h, 2)}px;background:${color};opacity:${hasData ? 0.85 : 0.1}"></div>
                </div>
                <div class="bar-label">${i + 1}</div>
              </div>`;
          })}
        </div>
      </div>`;
  }

  render() {
    if (!this.hass) return html`<ha-card><div class="loading">等待连接...</div></ha-card>`;

    // Stepped pricing progress
    const totalTier = (this._step1Remain !== null && this._step2Remain !== null)
      ? this._step1Remain + this._step2Remain : null;

    return html`
      <ha-card>
        <div class="card-body">
          <!-- Header -->
          <div class="header">
            <div class="header-title">${this.config.title}</div>
            <div class="year-nav">
              <button class="nav-btn" @click=${() => this._year--}>&lsaquo;</button>
              <span class="year-text">${this._year}</span>
              <button class="nav-btn" @click=${() => this._year++}>&rsaquo;</button>
            </div>
          </div>

          ${this._loading ? html`<div class="loading"><ha-circular-progress indeterminate></ha-circular-progress></div>` : ''}
          ${this._error ? html`<div class="error">⚠ ${this._error}</div>` : ''}

          ${!this._loading && !this._error ? html`
            <!-- Status Bar -->
            <div class="status-bar">
              ${this._balance !== null ? html`
                <div class="stat-item">
                  <div class="stat-value ${this._balance < 10 ? 'warn' : ''}">¥${this._balance.toFixed(2)}</div>
                  <div class="stat-label">账户余额</div>
                </div>` : ''}
              <div class="stat-item">
                <div class="stat-value">${this._totals?.totalGas ?? '-'}</div>
                <div class="stat-label">年用量 (m³)</div>
              </div>
              <div class="stat-item">
                <div class="stat-value">¥${(this._totals?.totalBill ?? 0).toFixed(0)}</div>
                <div class="stat-label">年费用</div>
              </div>
              ${this._status ? html`
                <div class="stat-item">
                  <div class="stat-value status-dot ${this._status === 'normal' || this._status === '正常' ? 'ok' : 'err'}"></div>
                  <div class="stat-label">${this._status}</div>
                </div>` : ''}
            </div>

            <!-- Tier Progress -->
            ${totalTier !== null ? html`
            <div class="tier-section">
              <div class="section-title">阶梯用量</div>
              <div class="tier-bar">
                <div class="tier-track">
                  <div class="tier-fill tier-1" style="flex:${this._step1Remain}"></div>
                  <div class="tier-fill tier-2" style="flex:${this._step2Remain}"></div>
                </div>
                <div class="tier-labels">
                  <span>一档余 ${this._step1Remain}m³</span>
                  <span>二档余 ${this._step2Remain}m³</span>
                </div>
              </div>
            </div>` : ''}

            <!-- Gas Usage Chart -->
            <div class="chart-section">
              <div class="section-title">月度用气量 (m³)</div>
              ${this._renderBars(this._gasData, 'm³', 'var(--gas-color, #ff7043)', Math.max(...this._gasData, 10))}
            </div>

            <!-- Cost Chart -->
            <div class="chart-section">
              <div class="section-title">月度燃气费 (CNY)</div>
              ${this._renderBars(this._billData, '¥', 'var(--cost-color, #7c4dff)', Math.max(...this._billData, 10))}
            </div>

            <!-- Footer Summary -->
            <div class="footer">
              <div class="footer-row">
                <span>${this._year}年用气量</span>
                <span class="footer-val">${this._totals?.totalGas ?? '-'} m³</span>
              </div>
              <div class="footer-row">
                <span>${this._year}年费用</span>
                <span class="footer-val">¥${(this._totals?.totalBill ?? 0).toFixed(2)}</span>
              </div>
              <div class="footer-row">
                <span>有数据月数</span>
                <span class="footer-val">${this._totals?.monthsWithData ?? 0} 个月</span>
              </div>
            </div>
          ` : ''}
        </div>
      </ha-card>`;
  }

  static get styles() {
    return css`
      :host { --gas-color: #ff7043; --cost-color: #7c4dff; }
      ha-card { border-radius: 12px; overflow: hidden; }
      .card-body { padding: 16px; }

      /* Header */
      .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
      .header-title { font-size: 16px; font-weight: 600; color: var(--primary-text-color); }
      .year-nav { display: flex; align-items: center; gap: 8px; }
      .nav-btn { background: var(--secondary-background-color); border: 1px solid var(--divider-color); border-radius: 6px; padding: 4px 10px; cursor: pointer; font-size: 16px; color: var(--primary-text-color); line-height: 1; }
      .nav-btn:hover { background: var(--primary-color); color: #fff; }
      .year-text { font-size: 14px; font-weight: 500; min-width: 44px; text-align: center; color: var(--primary-text-color); }

      /* Status bar */
      .status-bar { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 14px; background: var(--secondary-background-color); border-radius: 10px; padding: 12px; }
      .stat-item { flex: 1; min-width: 70px; text-align: center; }
      .stat-value { font-size: 18px; font-weight: 700; color: var(--primary-text-color); }
      .stat-value.warn { color: #f44336; }
      .stat-label { font-size: 11px; color: var(--secondary-text-color); margin-top: 2px; }
      .status-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; margin: 4px 0; }
      .status-dot.ok { background: #4caf50; }
      .status-dot.err { background: #f44336; }

      /* Tier progress */
      .tier-section { margin-bottom: 14px; }
      .section-title { font-size: 12px; font-weight: 600; color: var(--secondary-text-color); margin-bottom: 6px; }
      .tier-bar { }
      .tier-track { display: flex; height: 16px; border-radius: 8px; overflow: hidden; background: var(--divider-color); }
      .tier-fill { transition: flex 0.3s; }
      .tier-1 { background: linear-gradient(90deg, #66bb6a, #43a047); }
      .tier-2 { background: linear-gradient(90deg, #ffa726, #f57c00); }
      .tier-labels { display: flex; justify-content: space-between; font-size: 10px; color: var(--secondary-text-color); margin-top: 4px; }

      /* Chart */
      .chart-section { margin-bottom: 14px; }
      .chart-container { display: flex; align-items: flex-end; gap: 6px; position: relative; min-height: 140px; }
      .y-label { position: absolute; top: 0; right: 0; font-size: 10px; color: var(--secondary-text-color); }
      .bars { display: flex; align-items: flex-end; gap: 4px; flex: 1; height: 130px; padding-top: 16px; }
      .bar-col { display: flex; flex-direction: column; align-items: center; flex: 1; cursor: pointer; }
      .bar-value { font-size: 9px; color: var(--secondary-text-color); margin-bottom: 2px; white-space: nowrap; }
      .bar-track { width: 100%; max-width: 24px; height: 120px; background: var(--divider-color); border-radius: 4px; position: relative; display: flex; align-items: flex-end; }
      .bar-fill { width: 100%; border-radius: 4px; transition: height 0.3s; min-height: 2px; }
      .bar-label { font-size: 9px; color: var(--secondary-text-color); margin-top: 3px; }

      /* Footer */
      .footer { border-top: 1px solid var(--divider-color); padding-top: 10px; margin-top: 4px; }
      .footer-row { display: flex; justify-content: space-between; padding: 3px 0; font-size: 12px; color: var(--primary-text-color); }
      .footer-val { font-weight: 600; }

      /* States */
      .loading { padding: 40px; text-align: center; color: var(--secondary-text-color); }
      .error { padding: 20px; text-align: center; color: #f44336; font-size: 13px; }
      .empty { padding: 20px; text-align: center; color: var(--secondary-text-color); font-size: 12px; }
    `;
  }

  getCardSize() { return 6; }
}

customElements.define('crcgas-statistics-card', CrcgasStatisticsCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: 'crcgas-statistics-card',
  name: '华润燃气统计',
  description: '华润燃气月度用气量和费用趋势',
  preview: true,
});
