/**
 * crcgas-statistics-card — 华润燃气统计仪表盘卡片 (v2.0)
 * 
 * 纯 HTMLElement 实现，不依赖 LitElement
 * - 顶部余额+状态
 * - 阶梯用量进度条
 * - 月度柱状图（用气量+费用）
 * - 底部汇总
 *
 * 用法:
 *   type: custom:crcgas-statistics-card
 *   title: 我家燃气统计
 *   entity: sensor.chu_fang_hua_run_ran_qi_ran_qi_zhang_hu_yu_e
 */
const MONTHS_ZH = ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'];

class CrcgasStatisticsCard extends HTMLElement {
  setConfig(config) {
    if (!config) throw new Error('Invalid configuration');
    this._config = {
      title: config.title || '🔥 燃气统计',
      gasStatistic: config.gas_statistic || 'crcgas:monthly_gas_usage',
      billStatistic: config.bill_statistic || 'crcgas:monthly_bill_amount',
      balanceEntity: config.entity || '',
      year: config.year || new Date().getFullYear(),
    };
    this._year = this._config.year;
    this._showCost = true;
    this._loading = false;
    this._error = '';
    this._gasData = [];
    this._billData = [];
    this._totals = null;
    this._balance = null;
    this._step1Remain = null;
    this._step2Remain = null;
    this._status = null;
    this._cardId = 'crcgas-stats-' + Math.random().toString(36).substr(2, 9);
    this._render();
    this._loadData();
  }

  set hass(hass) {
    this._hass = hass;
    this._loadData();
  }

  connectedCallback() {
    if (this._hass) this._loadData();
  }

  async _loadData() {
    if (!this._hass || this._loading) return;
    this._loading = true;
    this._error = '';
    try {
      const start = new Date(this._year, 0, 1).toISOString();
      const end = new Date(this._year + 1, 0, 1).toISOString();
      const [gasResult, billResult] = await Promise.all([
        this._hass.callWS({
          type: 'recorder/statistics_during_period',
          start_time: start,
          end_time: end,
          statistic_ids: [this._config.gasStatistic],
          period: 'month',
        }),
        this._hass.callWS({
          type: 'recorder/statistics_during_period',
          start_time: start,
          end_time: end,
          statistic_ids: [this._config.billStatistic],
          period: 'month',
        }),
      ]);

      const gasStats = gasResult?.[this._config.gasStatistic] || [];
      const billStats = billResult?.[this._config.billStatistic] || [];

      const gasByMonth = {};
      for (const s of gasStats) {
        const d = new Date(s.start);
        gasByMonth[d.getMonth()] = s;
      }
      const billByMonth = {};
      for (const s of billStats) {
        const d = new Date(s.start);
        billByMonth[d.getMonth()] = s;
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
      this._totals = { totalGas: Number(totalGas.toFixed(1)), totalBill: Number(totalBill.toFixed(2)), monthsWithData };

      if (this._config.balanceEntity && this._hass.states[this._config.balanceEntity]) {
        this._balance = parseFloat(this._hass.states[this._config.balanceEntity].state) || 0;
      }
      const prefix = 'sensor.chu_fang_hua_run_ran_qi';
      const s1 = this._hass.states[`${prefix}_yi_dang_sheng_yu_qi_liang`];
      const s2 = this._hass.states[`${prefix}_er_dang_sheng_yu_qi_liang`];
      this._step1Remain = s1 ? parseFloat(s1.state) || 0 : null;
      this._step2Remain = s2 ? parseFloat(s2.state) || 0 : null;
      const st = this._hass.states[`${prefix}_ji_cheng_zhuang_tai`];
      this._status = st ? st.state : null;
    } catch (e) {
      console.error('crcgas-statistics-card: load failed', e);
      this._error = e.message || '数据加载失败';
    }
    this._loading = false;
    this._render();
  }

  _renderBars(values, unit, color, maxVal) {
    if (!values || values.length === 0) return '<div class="empty" style="padding:20px;text-align:center;color:var(--secondary-text-color);font-size:12px;">暂无数据</div>';
    const max = maxVal || Math.max(...values, 1);
    let html = '<div style="display:flex;align-items:flex-end;gap:4px;position:relative;min-height:140px;">';
    html += `<div style="position:absolute;top:0;right:0;font-size:10px;color:var(--secondary-text-color);">${max}${unit}</div>`;
    html += '<div style="display:flex;align-items:flex-end;gap:4px;flex:1;height:130px;padding-top:16px;">';
    for (let i = 0; i < values.length; i++) {
      const v = values[i];
      const h = max > 0 ? (v / max) * 120 : 0;
      const hasData = v > 0;
      html += `<div style="display:flex;flex-direction:column;align-items:center;flex:1;cursor:pointer;" onclick="this.closest('.chart-section').querySelector('.bar-value').click()">
        <div style="font-size:9px;color:var(--secondary-text-color);margin-bottom:2px;white-space:nowrap;opacity:${hasData ? 1 : 0.3}">${hasData ? v.toFixed(v % 1 === 0 ? 0 : 1) : '-'}</div>
        <div style="width:100%;max-width:24px;height:120px;background:var(--divider-color);border-radius:4px;position:relative;display:flex;align-items:flex-end;">
          <div style="width:100%;border-radius:4px;height:${Math.max(h, 2)}px;background:${color};opacity:${hasData ? 0.85 : 0.1};transition:height 0.3s;min-height:2px;"></div>
        </div>
        <div style="font-size:9px;color:var(--secondary-text-color);margin-top:3px;">${i + 1}</div>
      </div>`;
    }
    html += '</div></div>';
    return html;
  }

  _render() {
    const totalTier = (this._step1Remain !== null && this._step2Remain !== null) ? this._step1Remain + this._step2Remain : null;
    const css = `
      #${this._cardId} { --gas-color: #ff7043; --cost-color: #7c4dff; }
      #${this._cardId} ha-card { border-radius: 12px; overflow: hidden; }
      #${this._cardId} .body { padding: 16px; }
      #${this._cardId} .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
      #${this._cardId} .header-title { font-size: 16px; font-weight: 600; color: var(--primary-text-color); }
      #${this._cardId} .year-nav { display: flex; align-items: center; gap: 8px; }
      #${this._cardId} .nav-btn { background: var(--secondary-background-color); border: 1px solid var(--divider-color); border-radius: 6px; padding: 4px 10px; cursor: pointer; font-size: 16px; color: var(--primary-text-color); line-height: 1; }
      #${this._cardId} .nav-btn:hover { background: var(--primary-color); color: #fff; }
      #${this._cardId} .year-text { font-size: 14px; font-weight: 500; min-width: 44px; text-align: center; color: var(--primary-text-color); }
      #${this._cardId} .status-bar { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 14px; background: var(--secondary-background-color); border-radius: 10px; padding: 12px; }
      #${this._cardId} .stat-item { flex: 1; min-width: 70px; text-align: center; }
      #${this._cardId} .stat-value { font-size: 18px; font-weight: 700; color: var(--primary-text-color); }
      #${this._cardId} .stat-value.warn { color: #f44336; }
      #${this._cardId} .stat-label { font-size: 11px; color: var(--secondary-text-color); margin-top: 2px; }
      #${this._cardId} .status-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; margin: 4px 0; }
      #${this._cardId} .status-dot.ok { background: #4caf50; }
      #${this._cardId} .status-dot.err { background: #f44336; }
      #${this._cardId} .tier-section { margin-bottom: 14px; }
      #${this._cardId} .section-title { font-size: 12px; font-weight: 600; color: var(--secondary-text-color); margin-bottom: 6px; }
      #${this._cardId} .tier-track { display: flex; height: 16px; border-radius: 8px; overflow: hidden; background: var(--divider-color); }
      #${this._cardId} .tier-fill { transition: flex 0.3s; }
      #${this._cardId} .tier-1 { background: linear-gradient(90deg, #66bb6a, #43a047); }
      #${this._cardId} .tier-2 { background: linear-gradient(90deg, #ffa726, #f57c00); }
      #${this._cardId} .tier-labels { display: flex; justify-content: space-between; font-size: 10px; color: var(--secondary-text-color); margin-top: 4px; }
      #${this._cardId} .chart-section { margin-bottom: 14px; }
      #${this._cardId} .footer { border-top: 1px solid var(--divider-color); padding-top: 10px; margin-top: 4px; }
      #${this._cardId} .footer-row { display: flex; justify-content: space-between; padding: 3px 0; font-size: 12px; color: var(--primary-text-color); }
      #${this._cardId} .footer-val { font-weight: 600; }
      #${this._cardId} .loading { padding: 40px; text-align: center; color: var(--secondary-text-color); }
      #${this._cardId} .error { padding: 20px; text-align: center; color: #f44336; font-size: 13px; }
    `;

    const balanceBar = this._balance !== null ? `
      <div class="stat-item">
        <div class="stat-value ${this._balance < 10 ? 'warn' : ''}">&yen;${this._balance.toFixed(2)}</div>
        <div class="stat-label">账户余额</div>
      </div>` : '';
    const statusBar = this._status ? `
      <div class="stat-item">
        <div class="stat-value"><span class="status-dot ${this._status === '正常' || this._status === 'normal' ? 'ok' : 'err'}"></span></div>
        <div class="stat-label">${this._status}</div>
      </div>` : '';

    const tierSection = totalTier !== null ? `
      <div class="tier-section">
        <div class="section-title">阶梯用量</div>
        <div class="tier-track">
          <div class="tier-fill tier-1" style="flex:${this._step1Remain}"></div>
          <div class="tier-fill tier-2" style="flex:${this._step2Remain}"></div>
        </div>
        <div class="tier-labels">
          <span>一档余 ${this._step1Remain}m³</span>
          <span>二档余 ${this._step2Remain}m³</span>
        </div>
      </div>` : '';

    const content = !this._loading && !this._error ? `
      <div class="status-bar">
        ${balanceBar}
        <div class="stat-item"><div class="stat-value">${this._totals?.totalGas ?? '-'}</div><div class="stat-label">年用量 (m³)</div></div>
        <div class="stat-item"><div class="stat-value">&yen;${(this._totals?.totalBill ?? 0).toFixed(0)}</div><div class="stat-label">年费用</div></div>
        ${statusBar}
      </div>
      ${tierSection}
      <div class="chart-section">
        <div class="section-title">月度用气量 (m³)</div>
        ${this._renderBars(this._gasData, 'm³', 'var(--gas-color, #ff7043)', Math.max(...(this._gasData || [1]), 10))}
      </div>
      <div class="chart-section">
        <div class="section-title">月度燃气费 (CNY)</div>
        ${this._renderBars(this._billData, '¥', 'var(--cost-color, #7c4dff)', Math.max(...(this._billData || [1]), 10))}
      </div>
      <div class="footer">
        <div class="footer-row"><span>${this._year}年用气量</span><span class="footer-val">${this._totals?.totalGas ?? '-'} m³</span></div>
        <div class="footer-row"><span>${this._year}年费用</span><span class="footer-val">&yen;${(this._totals?.totalBill ?? 0).toFixed(2)}</span></div>
        <div class="footer-row"><span>有数据月数</span><span class="footer-val">${this._totals?.monthsWithData ?? 0} 个月</span></div>
      </div>` : '';

    this.innerHTML = `
      <style>${css}</style>
      <div id="${this._cardId}">
        <ha-card>
          <div class="body">
            <div class="header">
              <div class="header-title">${this._config.title}</div>
              <div class="year-nav">
                <button class="nav-btn" onclick="this.getRootNode().host._year--;this.getRootNode().host._loadData();this.getRootNode().host._render();">&lsaquo;</button>
                <span class="year-text">${this._year}</span>
                <button class="nav-btn" onclick="this.getRootNode().host._year++;this.getRootNode().host._loadData();this.getRootNode().host._render();">&rsaquo;</button>
              </div>
            </div>
            ${this._loading ? '<div class="loading"><ha-circular-progress indeterminate></ha-circular-progress></div>' : ''}
            ${this._error ? '<div class="error">⚠ ' + this._error + '</div>' : ''}
            ${content}
          </div>
        </ha-card>
      </div>`;
  }

  getCardSize() { return 6; }
}

customElements.define('crcgas-statistics-card', CrcgasStatisticsCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: 'crcgas-statistics-card',
  name: '华润燃气统计',
  description: '华润燃气月度用气量和费用趋势',
});
