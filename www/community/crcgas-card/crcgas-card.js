/**
 * 华润燃气 Lovelace 自定义卡片 - v1.2.0
 * 新增 v1.2.0:
 *   - 阶梯用气量进度条可视化
 *   - 预估本月账单显示
 *   - 当前阶梯指示
 *   - 与均值对比
 * 用法示例:
 *   type: custom:crcgas-card
 *   entity: sensor.crcgas_account_balance
 *   title: 华润燃气
 */
(function () {
  'use strict';

  const CARD_VERSION = '1.2.0';

  class CrcgasCard extends HTMLElement {
    setConfig(config) {
      if (!config.entity) {
        throw new Error('请指定 entity 参数');
      }
      this._config = {
        title: config.title || '华润燃气',
        entity: config.entity,
        ...config,
      };
      this._hass = null;
      this._cardId = 'crcgas-' + Math.random().toString(36).substr(2, 9);

      if (this._cardEl) return;
      const card = document.createElement('div');
      card.id = this._cardId;
      card.className = 'cc-container';
      card.innerHTML = `
        <div class="cc-header">
          <div class="cc-title">
            <span class="cc-icon">🔥</span>
            <span class="cc-title-text">${this._config.title}</span>
          </div>
          <div class="cc-status-dot" id="${this._cardId}-dot"></div>
        </div>
        <div class="cc-grid">
          <div class="cc-card cc-card-balance" id="${this._cardId}-balance">
            <div class="cc-card-label">账户余额</div>
            <div class="cc-card-value cc-value-balance">--</div>
            <div class="cc-card-unit">¥</div>
          </div>
          <div class="cc-card cc-card-gas" id="${this._cardId}-gas">
            <div class="cc-card-label">本期用气</div>
            <div class="cc-card-value cc-value-gas">--</div>
            <div class="cc-card-unit">m³</div>
          </div>
          <div class="cc-card cc-card-step" id="${this._cardId}-step">
            <div class="cc-card-label">当前阶梯</div>
            <div class="cc-card-value cc-value-step">--</div>
          </div>
          <div class="cc-card cc-card-estimated" id="${this._cardId}-estimated">
            <div class="cc-card-label">预估账单</div>
            <div class="cc-card-value cc-value-estimated">--</div>
            <div class="cc-card-unit">¥</div>
          </div>
        </div>
        <div class="cc-progress-section" id="${this._cardId}-progress">
          <div class="cc-progress-label">
            <span>阶梯用气进度</span>
            <span id="${this._cardId}-progress-text">--</span>
          </div>
          <div class="cc-progress-bar">
            <div class="cc-progress-fill" id="${this._cardId}-progress-fill"></div>
          </div>
          <div class="cc-step-info" id="${this._cardId}-step-info">
            <div class="cc-step-item"><span class="cc-step-num">一</span><span class="cc-step-val" id="${this._cardId}-s1">--</span></div>
            <div class="cc-step-item"><span class="cc-step-num">二</span><span class="cc-step-val" id="${this._cardId}-s2">--</span></div>
            <div class="cc-step-item"><span class="cc-step-num">三</span><span class="cc-step-val" id="${this._cardId}-s3">--</span></div>
          </div>
        </div>
        <div class="cc-info-row">
          <div class="cc-info-item">
            <span class="cc-info-label">上月用气</span>
            <span class="cc-info-value" id="${this._cardId}-last-month">--</span>
          </div>
          <div class="cc-info-item">
            <span class="cc-info-label">年均用气</span>
            <span class="cc-info-value" id="${this._cardId}-avg">--</span>
          </div>
          <div class="cc-info-item">
            <span class="cc-info-label">对比均值</span>
            <span class="cc-info-value" id="${this._cardId}-vs-avg">--</span>
          </div>
        </div>
        <div class="cc-footer">
          <span id="${this._cardId}-update">--</span>
        </div>
      `;
      this.appendChild(card);
      this._cardEl = card;
      this._injectStyles();
    }

    _injectStyles() {
      if (document.getElementById('crcgas-card-styles')) return;
      const style = document.createElement('style');
      style.id = 'crcgas-card-styles';
      style.textContent = `
        .cc-container {
          background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
          border-radius: 16px;
          padding: 16px;
          color: #fff;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
          box-shadow: 0 4px 20px rgba(0,0,0,0.3);
          transition: all 0.3s ease;
          height: 100%;
          box-sizing: border-box;
        }
        .cc-container:hover {
          transform: translateY(-2px);
          box-shadow: 0 6px 25px rgba(0,0,0,0.4);
        }
        .cc-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 16px;
        }
        .cc-title { display: flex; align-items: center; gap: 8px; }
        .cc-icon { font-size: 24px; }
        .cc-title-text { font-size: 16px; font-weight: 600; }
        .cc-status-dot {
          width: 10px; height: 10px; border-radius: 50%;
          background: #4ade80;
          box-shadow: 0 0 8px #4ade80;
        }
        .cc-status-dot.warning { background: #fbbf24; box-shadow: 0 0 8px #fbbf24; }
        .cc-status-dot.error { background: #ef4444; box-shadow: 0 0 8px #ef4444; }
        .cc-grid {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 12px;
          margin-bottom: 16px;
        }
        .cc-card {
          background: rgba(255,255,255,0.1);
          border-radius: 12px;
          padding: 12px;
          text-align: center;
          transition: all 0.3s ease;
        }
        .cc-card:hover { background: rgba(255,255,255,0.15); }
        .cc-card-label { font-size: 11px; color: rgba(255,255,255,0.7); margin-bottom: 4px; }
        .cc-card-value { font-size: 20px; font-weight: 700; }
        .cc-card-unit { font-size: 11px; color: rgba(255,255,255,0.5); }
        .cc-value-balance { color: #4ade80; }
        .cc-value-gas { color: #f97316; }
        .cc-value-step { color: #a78bfa; }
        .cc-value-estimated { color: #38bdf8; }
        .cc-progress-section {
          background: rgba(255,255,255,0.05);
          border-radius: 12px;
          padding: 12px;
          margin-bottom: 12px;
        }
        .cc-progress-label {
          display: flex;
          justify-content: space-between;
          font-size: 12px;
          color: rgba(255,255,255,0.7);
          margin-bottom: 8px;
        }
        .cc-progress-bar {
          height: 8px;
          background: rgba(255,255,255,0.1);
          border-radius: 4px;
          overflow: hidden;
          margin-bottom: 8px;
        }
        .cc-progress-fill {
          height: 100%;
          border-radius: 4px;
          background: linear-gradient(90deg, #3b82f6, #8b5cf6, #ef4444);
          transition: width 0.5s ease;
        }
        .cc-step-info {
          display: flex;
          justify-content: space-around;
          font-size: 12px;
        }
        .cc-step-item {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 2px;
        }
        .cc-step-num { color: rgba(255,255,255,0.5); font-size: 10px; }
        .cc-step-val { color: #fff; font-weight: 600; }
        .cc-info-row {
          display: flex;
          justify-content: space-between;
          padding: 8px 0;
          border-top: 1px solid rgba(255,255,255,0.1);
        }
        .cc-info-item {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 2px;
        }
        .cc-info-label { font-size: 10px; color: rgba(255,255,255,0.5); }
        .cc-info-value { font-size: 13px; color: #fff; }
        .cc-footer {
          text-align: center;
          font-size: 10px;
          color: rgba(255,255,255,0.4);
          margin-top: 8px;
        }
      `;
      document.head.appendChild(style);
    }

    set hass(hass) {
      this._hass = hass;
      this._update();
    }

    _getEntity(entityId) {
      return this._hass?.states[entityId];
    }

    _getState(state) {
      return state ? state.state : 'unknown';
    }

    _formatNumber(val, decimals = 1) {
      const n = parseFloat(val);
      return isNaN(n) ? '--' : n.toFixed(decimals);
    }

    _update() {
      if (!this._hass || !this._cardEl) return;

      // 获取实体数据
      const balance = this._getEntity(`sensor.crcgas_account_balance`);
      const gasUsed = this._getEntity(`sensor.crcgas_gas_used`);
      const currentStep = this._getEntity(`sensor.crcgas_current_step`);
      const estimated = this._getEntity(`sensor.crcgas_estimated_bill_amount`);
      const s1 = this._getEntity(`sensor.crcgas_step1_gas_used`);
      const s2 = this._getEntity(`sensor.crcgas_step2_gas_used`);
      const s3 = this._getEntity(`sensor.crcgas_step3_gas_used`);
      const avg = this._getEntity(`sensor.crcgas_history_avg_usage`);
      const vsAvg = this._getEntity(`sensor.crcgas_usage_vs_avg`);
      const status = this._getEntity(`sensor.crcgas_integration_status`);
      const updateTime = this._getEntity(`sensor.crcgas_last_update_time`);
      const lastMonth = this._getEntity(`sensor.crcgas_last_month_gas`);

      // 更新数值
      const setVal = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.textContent = val;
      };

      setVal(`${this._cardId}-balance`, '¥' + this._formatNumber(balance?.state));
      setVal(`${this._cardId}-gas`, this._formatNumber(gasUsed?.state));
      setVal(`${this._cardId}-step`, currentStep?.state || '--');
      setVal(`${this._cardId}-estimated`, '¥' + this._formatNumber(estimated?.state));
      setVal(`${this._cardId}-s1`, this._formatNumber(s1?.state, 2));
      setVal(`${this._cardId}-s2`, this._formatNumber(s2?.state, 2));
      setVal(`${this._cardId}-s3`, this._formatNumber(s3?.state, 2));
      setVal(`${this._cardId}-avg`, this._formatNumber(avg?.state) + 'm³');
      setVal(`${this._cardId}-vs-avg`, vsAvg?.state || '--');
      setVal(`${this._cardId}-last-month`, this._formatNumber(lastMonth?.state) + 'm³');
      setVal(`${this._cardId}-update`, '更新: ' + (updateTime?.state || '--'));

      // 状态指示灯
      const dot = document.getElementById(`${this._cardId}-dot`);
      const st = status?.state || 'normal';
      dot.className = 'cc-status-dot';
      if (st !== 'normal') {
        dot.classList.add(st.includes('error') ? 'error' : 'warning');
      }

      // 阶梯进度条
      const totalGas = parseFloat(gasUsed?.state) || 0;
      const step1 = parseFloat(s1?.state) || 0;
      const step2 = parseFloat(s2?.state) || 0;
      const step3 = parseFloat(s3?.state) || 0;

      // 假设阈值：一阶5m³，二阶10m³，三阶无限
      const t1 = 5, t2 = 10;
      let percent = 0;
      if (totalGas <= t1) {
        percent = (totalGas / t1) * 33;
      } else if (totalGas <= t2) {
        percent = 33 + ((totalGas - t1) / (t2 - t1)) * 33;
      } else {
        percent = 66 + Math.min(((totalGas - t2) / t2) * 34, 34);
      }

      const fill = document.getElementById(`${this._cardId}-progress-fill`);
      if (fill) fill.style.width = Math.min(percent, 100) + '%';

      setVal(`${this._cardId}-progress-text`, this._formatNumber(totalGas, 2) + '/' +
        (totalGas <= t2 ? t2 : (totalGas <= t2 * 2 ? t2 * 2 : '∞')) + 'm³');
    }
  }

  customElements.define('crcgas-card', CrcgasCard);
})();
