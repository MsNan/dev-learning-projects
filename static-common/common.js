// 公共前端：请求封装 + 打赏弹窗 + 版本徽标 + 学习声明
const API = async (url, opt = {}) => {
  const t = localStorage.getItem('token_' + location.port)
  const r = await fetch(url, { method: opt.method || 'GET', headers: { 'Content-Type': 'application/json', ...(t ? { Authorization: 'Bearer ' + t } : {}) }, body: opt.body && JSON.stringify(opt.body) })
  const j = await r.json().catch(() => ({}))
  if (j.code !== 0) { toast(j.message || '请求失败'); throw Object.assign(new Error(j.message), { status: r.status }) }
  return j.data
}
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))
function toast(m) { const d = document.createElement('div'); d.className = 'dl-toast'; d.textContent = m; document.body.appendChild(d); setTimeout(() => d.remove(), 2200) }
let EDITION = 'free'
async function initCommon() {
  const css = document.createElement('style'); css.textContent = `
  .dl-toast{position:fixed;top:18px;left:50%;transform:translateX(-50%);background:#111d;color:#fff;padding:8px 16px;border-radius:6px;z-index:99}
  .dl-fab{position:fixed;right:18px;bottom:18px;background:#ff6a00;color:#fff;border:0;border-radius:24px;padding:10px 16px;font-size:14px;box-shadow:0 4px 12px #0003;cursor:pointer;z-index:50}
  .dl-mask{position:fixed;inset:0;background:#0007;display:flex;align-items:center;justify-content:center;z-index:60}
  .dl-box{background:#fff;border-radius:12px;padding:20px;width:min(560px,92vw);max-height:92vh;overflow:auto;color:#222}
  .dl-qr{display:flex;gap:12px;justify-content:center}.dl-qr figure{margin:0;text-align:center;flex:1}.dl-qr img{width:100%;max-width:220px;border-radius:8px}
  .dl-box input,.dl-box textarea,.dl-box select{width:100%;box-sizing:border-box;margin:4px 0;padding:7px;border:1px solid #ddd;border-radius:6px}
  .dl-ed{display:inline-block;padding:1px 8px;border-radius:10px;font-size:12px;margin-left:8px}.dl-ed.free{background:#dbeafe;color:#1d4ed8}.dl-ed.pro{background:#fef3c7;color:#b45309}
  .dl-note{font-size:12px;color:#888;text-align:center;padding:16px 8px 70px}.pro-lock{border:1px dashed #f59e0b;background:#fffbeb;color:#92400e;padding:16px;border-radius:8px;text-align:center}`
  document.head.appendChild(css)
  EDITION = (await API('/api/edition').catch(() => ({ edition: 'free' }))).edition
  document.querySelectorAll('[data-edition]').forEach(e => (e.innerHTML = `<span class="dl-ed ${EDITION}">${EDITION === 'pro' ? '付费高级版' : '免费版'}</span>`))
  const b = document.createElement('button'); b.className = 'dl-fab'; b.textContent = '☕ 打赏支持'; b.onclick = showReward; document.body.appendChild(b)
  const n = document.createElement('div'); n.className = 'dl-note'; n.innerHTML = '本项目仅供软件开发学习与源码参考，请勿直接用于提交课程作业或毕业设计。'; document.body.appendChild(n)
}
function lockHtml(name) { return `<div class="pro-lock">🔒 「${name}」属于付费高级版功能（启动时设置 EDITION=pro 体验）</div>` }
function showReward() {
  const m = document.createElement('div'); m.className = 'dl-mask'
  m.innerHTML = `<div class="dl-box"><h3 style="margin-top:0">☕ 觉得有帮助？打赏支持一下</h3><div class="dl-qr"><figure><img src="/common/wechat.jpg"><figcaption>微信</figcaption></figure><figure><img src="/common/alipay.jpg"><figcaption>支付宝</figcaption></figure></div>
  <p style="font-size:13px;color:#666">打赏全凭自愿。扫码后可留个言（选填）：</p><select id="rc"><option>微信</option><option>支付宝</option></select><input id="ra" type="number" step="0.01" value="6.66" placeholder="金额"><input id="rn" placeholder="昵称（选填）"><textarea id="rm" placeholder="留言（选填）"></textarea>
  <div style="text-align:right;margin-top:8px"><button id="rx">关闭</button> <button id="rs" style="background:#ff6a00;color:#fff;border:0;padding:6px 14px;border-radius:6px">我已打赏，提交留言</button></div></div>`
  document.body.appendChild(m); m.querySelector('#rx').onclick = () => m.remove(); m.onclick = e => e.target === m && m.remove()
  m.querySelector('#rs').onclick = async () => { await API('/api/rewards', { method: 'POST', body: { channel: m.querySelector('#rc').value, amount: m.querySelector('#ra').value, nickname: m.querySelector('#rn').value, message: m.querySelector('#rm').value } }); toast('感谢支持！'); m.remove() }
}
