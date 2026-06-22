/**
 * crcgas-statistics-card v3.1 — 华润燃气对比统计卡片
 * - 双年对比折线图（SVG 绘制）
 * - 用气量/费用切换
 * - 阶梯用量进度条
 * - 本月用量及费用
 * - 年汇总
 */
const MONTHS_SHORT = ['1','2','3','4','5','6','7','8','9','10','11','12'];

class CrcgasStatisticsCard extends HTMLElement {
  setConfig(config) {
    if (!config) throw new Error('Invalid configuration');
    this._config = {
      title: config.title || '🔥 燃气统计',
      historyEntity: config.history_entity || 'sensor.hua_run_ran_qi_ran_qi_biao_li_shi_lei_ji',
      balanceEntity: config.entity || 'sensor.chu_fang_hua_run_ran_qi_ran_qi_zhang_hu_yu_e',
    };
    this._year = new Date().getFullYear();
    this._viewMode = 'gas';
    this._cardId = 'crcgas-v3-' + Math.random().toString(36).substr(2, 9);
    this._yearData = {};
    this._liveData = {};
    this._loading = false;
    this._loaded = false;
    this._render();
    if (this._hass) this._loadData();
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._loaded) this._loadData();
    else this._loadCurrentState();
  }

  connectedCallback() {
    if (this._hass && !this._loaded) this._loadData();
  }

  async _loadData() {
    if (!this._hass || this._loaded) return;
    this._loaded = true;
    this._loading = true;
    this._render();
    this._loadCurrentState();
    try {
      if (!this._yearData[this._year]) await this._loadYear(this._year);
      if (!this._yearData[this._year - 1]) await this._loadYear(this._year - 1);
    } catch (e) {
      console.error('crcgas: load error', e);
    }
    this._loading = false;
    this._render();
  }

  async _loadYear(year) {
    if (this._yearData[year]) return;
    const start = new Date(year, 0, 1).toISOString();
    const end = new Date(year + 1, 0, 1).toISOString();
    try {
      const result = await this._hass.callWS({
        type: 'recorder/statistics_during_period',
        start_time: start,
        end_time: end,
        statistic_ids: [this._config.historyEntity],
        period: 'month',
      });
      const stats = result?.[this._config.historyEntity] || [];
      const byMonth = {};
      for (const s of stats) {
        const d = new Date(s.start);
        const m = d.getMonth();
        byMonth[m] = { change: s.change || 0, sum: s.sum || s.state || 0, state: s.state || 0 };
      }
      this._yearData[year] = byMonth;
    } catch (e) {
      this._yearData[year] = {};
    }
  }

  _loadCurrentState() {
    if (!this._hass) return;
    const prefix = 'sensor.chu_fang_hua_run_ran_qi';
    this._liveData = {
      balance: this._hass.states[this._config.balanceEntity] ? Number(this._hass.states[this._config.balanceEntity].state) || 0 : null,
      monthlyUsage: this._hass.states[`${prefix}_ben_yue_lei_ji_yong_qi_liang`] ? Number(this._hass.states[`${prefix}_ben_yue_lei_ji_yong_qi_liang`].state) || 0 : null,
      monthlyCost: this._hass.states[`${prefix}_yu_gu_ran_qi_zhang_dan`] ? Number(this._hass.states[`${prefix}_yu_gu_ran_qi_zhang_dan`].state) || 0 : null,
      step1Remain: this._hass.states[`${prefix}_yi_dang_sheng_yu_qi_liang`] ? Number(this._hass.states[`${prefix}_yi_dang_sheng_yu_qi_liang`].state) || 0 : null,
      step2Remain: this._hass.states[`${prefix}_er_dang_sheng_yu_qi_liang`] ? Number(this._hass.states[`${prefix}_er_dang_sheng_yu_qi_liang`].state) || 0 : null,
      status: this._hass.states[`${prefix}_ji_cheng_zhuang_tai`] ? this._hass.states[`${prefix}_ji_cheng_zhuang_tai`].state : null,
      step1Price: this._hass.states[`${prefix}_yi_dang_qi_jie`] ? Number(this._hass.states[`${prefix}_yi_dang_qi_jie`].state) || 3.1 : 3.1,
      step1Used: this._hass.states[`${prefix}_yi_dang_yong_qi_liang`] ? Number(this._hass.states[`${prefix}_yi_dang_yong_qi_liang`].state) || 0 : null,
      step2Used: this._hass.states[`${prefix}_er_dang_yong_qi_liang`] ? Number(this._hass.states[`${prefix}_er_dang_yong_qi_liang`].state) || 0 : null,
    };
    if (!this._loading) this._render();
  }

  _renderChart(y1, y2, mode) {
    const d1 = this._yearData[y1] || {};
    const d2 = this._yearData[y2] || {};
    const p = this._liveData?.step1Price || 3.1;
    const v1 = [], v2 = [];
    for (let m = 0; m < 12; m++) {
      let a = d1[m] ? d1[m].change : 0, b = d2[m] ? d2[m].change : 0;
      if (mode === 'cost') { a *= p; b *= p; }
      v1.push(Math.max(0, a));
      v2.push(Math.max(0, b));
    }
    const maxV = Math.max(...v1, ...v2, 1);
    const W = 280, H = 140, PT = 16, PB = 22, PL = 6, PR = 8;
    const CW = W - PL - PR, CH = H - PT - PB;
    const SX = CW / 11;
    const C1 = '#ff7043', C2 = '#7c4dff';

    const px = (i) => PL + i * SX;
    const py = (v) => PT + CH - (v / maxV) * CH * 0.85;

    const lineSVG = (vals, color) => {
      let pts = '', dots = '', area = '';
      for (let i = 0; i < 12; i++) {
        const x = px(i), y = Math.max(PT, Math.min(H - PB, py(vals[i])));
        pts += (i === 0 ? 'M' : 'L') + x.toFixed(1) + ',' + y.toFixed(1);
        if (vals[i] > 0) dots += `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="2.5" fill="${color}" stroke="#fff" stroke-width="1"/>`;
      }
      area = pts + ` L${px(11).toFixed(1)},${(H-PB).toFixed(1)} L${PL.toFixed(1)},${(H-PB).toFixed(1)} Z`;
      return `<path d="${pts}" fill="none" stroke="${color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
<path d="${area}" fill="${color}" opacity="0.08"/>
${dots}`;
    };

    let grid = '';
    for (let i = 0; i < 4; i++) {
      const y = PT + (CH / 3) * i;
      grid += `<line x1="${PL}" y1="${y.toFixed(1)}" x2="${W-PR}" y2="${y.toFixed(1)}" stroke="var(--divider-color)" stroke-width="0.5"/>`;
    }
    let labels = '';
    for (let i = 0; i < 12; i += 2) {
      labels += `<text x="${px(i).toFixed(1)}" y="${H-4}" text-anchor="middle" fill="var(--secondary-text-color)" font-size="9">${i+1}月</text>`;
    }
    return `<svg viewBox="0 0 ${W} ${H}" style="width:100%;height:100%;display:block;">${grid}${lineSVG(v1, C1)}${lineSVG(v2, C2)}${labels}</svg>`;
  }

  _render() {
    const y1 = this._year, y2 = this._year - 1, mode = this._viewMode;
    const d1 = this._yearData[y1] || {}, d2 = this._yearData[y2] || {};
    const ld = this._liveData || {};
    const p = ld.step1Price || 3.1;
    const y1Total = Object.values(d1).reduce((s, v) => s + Math.max(0, v.change || 0), 0);
    const y2Total = Object.values(d2).reduce((s, v) => s + Math.max(0, v.change || 0), 0);
    const y1Cost = y1Total * p, y2Cost = y2Total * p;
    const unit = mode === 'gas' ? 'm³' : '元';
    const unitLabel = mode === 'gas' ? '用气量' : '费用';
    const y1Val = mode === 'gas' ? y1Total.toFixed(1) : '¥' + y1Cost.toFixed(0);
    const y2Val = mode === 'gas' ? y2Total.toFixed(1) : '¥' + y2Cost.toFixed(0);
    const diff = mode === 'gas' ? y1Total - y2Total : y1Cost - y2Cost;
    const diffColor = diff > 0 ? '#f44336' : diff < 0 ? '#4caf50' : 'var(--secondary-text-color)';
    const diffSym = diff > 0 ? '↑' : diff < 0 ? '↓' : '→';

    this.innerHTML = `
<style>#${this._cardId}{font-family:var(--paper-font-body1_-_font-family)}#${this._cardId} ha-card{border-radius:12px;overflow:hidden}#${this._cardId} .b{padding:14px}#${this._cardId} .h{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}#${this._cardId} .ht{font-size:16px;font-weight:600;color:var(--primary-text-color)}#${this._cardId} .ha{display:flex;align-items:center;gap:6px}#${this._cardId} .nb{background:var(--secondary-background-color);border:1px solid var(--divider-color);border-radius:6px;padding:3px 8px;cursor:pointer;font-size:14px;color:var(--primary-text-color);line-height:1.4}#${this._cardId} .nb:hover{background:var(--primary-color);color:#fff}#${this._cardId} .nb.a{background:var(--primary-color);color:#fff;border-color:var(--primary-color)}#${this._cardId} .yt{font-size:14px;font-weight:500;min-width:44px;text-align:center;color:var(--primary-text-color)}#${this._cardId} .cl{display:flex;justify-content:center;gap:20px;font-size:11px;margin-bottom:4px}#${this._cardId} .li{display:flex;align-items:center;gap:4px}#${this._cardId} .ld{width:8px;height:8px;border-radius:50%}#${this._cardId} .ca{margin-bottom:8px}#${this._cardId} .sr{display:flex;gap:6px;margin-bottom:10px}#${this._cardId} .sc{flex:1;background:var(--secondary-background-color);border-radius:8px;padding:8px 6px;text-align:center;min-width:0}#${this._cardId} .sv{font-size:15px;font-weight:700;color:var(--primary-text-color)}#${this._cardId} .sv.w{color:#f44336}#${this._cardId} .sl{font-size:10px;color:var(--secondary-text-color);margin-top:1px}#${this._cardId} .sd{font-size:10px;margin-top:1px}#${this._cardId} .ts{margin-bottom:10px}#${this._cardId} .tt{font-size:11px;font-weight:600;color:var(--secondary-text-color);margin-bottom:4px}#${this._cardId} .tr{display:flex;height:14px;border-radius:7px;overflow:hidden;background:var(--divider-color)}#${this._cardId} .t1{background:linear-gradient(90deg,#66bb6a,#43a047)}#${this._cardId} .t2{background:linear-gradient(90deg,#ffa726,#f57c00)}#${this._cardId} .tl{display:flex;justify-content:space-between;font-size:9px;color:var(--secondary-text-color);margin-top:2px}#${this._cardId} .f{border-top:1px solid var(--divider-color);padding-top:8px}#${this._cardId} .fr{display:flex;justify-content:space-between;padding:2px 0;font-size:11px;color:var(--primary-text-color)}#${this._cardId} .fv{font-weight:600}#${this._cardId} .ldg{padding:40px;text-align:center;color:var(--secondary-text-color);font-size:13px}</style>
<div id="${this._cardId}"><ha-card><div class="b">
<div class="h"><span class="ht">${this._config.title}</span>
<div class="ha"><button class="nb${mode==='gas'?' a':''}" onclick="this.getRootNode().host._sw('gas')">m³</button><button class="nb${mode==='cost'?' a':''}" onclick="this.getRootNode().host._sw('cost')">¥</button></div></div>
${this._loading?'<div class="ldg">加载中...</div>':''}
${!this._loading?`
<div class="ha" style="justify-content:center;margin-bottom:6px;gap:8px"><button class="nb" onclick="this.getRootNode().host._cy(-1)">&lsaquo;</button><span class="yt">${this._year}</span><button class="nb" onclick="this.getRootNode().host._cy(1)">&rsaquo;</button></div>
<div class="cl"><span class="li"><span class="ld" style="background:#ff7043"></span> ${y1}年</span><span class="li"><span class="ld" style="background:#7c4dff"></span> ${y2}年</span></div>
<div class="ca">${this._renderChart(y1,y2,mode)}</div>
<div class="sr">
<div class="sc"><div class="sv">${y1Val}</div><div class="sl">${y1}年${unitLabel}</div><div class="sd" style="color:${diffColor}">${diffSym} ${Math.abs(diff).toFixed(mode==='gas'?1:0)}${unit}</div></div>
<div class="sc"><div class="sv">${y2Val}</div><div class="sl">${y2}年${unitLabel}</div></div>
<div class="sc"><div class="sv${ld.balance!==null&&ld.balance<10?' w':''}">${ld.balance!==null?'¥'+ld.balance.toFixed(2):'--'}</div><div class="sl">余额</div></div>
<div class="sc"><div class="sv">${ld.monthlyUsage!==null?ld.monthlyUsage.toFixed(1)+'m³':'--'}</div><div class="sl">本月用气</div></div>
<div class="sc"><div class="sv">${ld.monthlyCost!==null?'¥'+ld.monthlyCost.toFixed(0):'--'}</div><div class="sl">本月费用</div></div>
</div>
${ld.step1Remain!==null&&ld.step2Remain!==null?`
<div class="ts"><div class="tt">阶梯用量 · 一档${ld.step1Used??'--'}m³ / 二档${ld.step2Used??'--'}m³</div>
<div class="tr"><div class="t1" style="flex:${ld.step1Remain}"></div><div class="t2" style="flex:${ld.step2Remain}"></div></div>
<div class="tl"><span>一档余 ${ld.step1Remain}m³</span><span>二档余 ${ld.step2Remain}m³</span></div></div>`:''}
<div class="f">
<div class="fr"><span>${y1}年用气总计</span><span class="fv">${y1Total.toFixed(1)} m³</span></div>
<div class="fr"><span>${y1}年费用估算</span><span class="fv">¥${y1Cost.toFixed(0)}</span></div>
${ld.status?`<div class="fr"><span>集成状态</span><span class="fv" style="color:${ld.status==='正常'?'#4caf50':'#f44336'}">${ld.status}</span></div>`:''}
</div>`:''}
</div></ha-card></div>`;
  }

  _sw(m) { this._viewMode = m; this._render(); }
  _cy(d) {
    this._year += d;
    this._loading = true;
    this._render();
    Promise.all([
      this._loadYear(this._year).catch(() => {}),
      !this._yearData[this._year-1] ? this._loadYear(this._year-1).catch(() => {}) : Promise.resolve()
    ]).then(() => { this._loading = false; this._render(); });
  }

  getCardSize() { return 7; }
}

customElements.define('crcgas-statistics-card', CrcgasStatisticsCard);
window.customCards = window.customCards || [];
window.customCards.push({ type: 'crcgas-statistics-card', name: '华润燃气统计', description: '华润燃气年度对比统计' });
