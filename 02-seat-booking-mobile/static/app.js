const KEY = 'token_' + location.port, v = document.getElementById('v')
let user = JSON.parse(localStorage.getItem('u_' + location.port) || 'null'), page = 'book', meta, st = { day: 0, slot: 0, room: 0, seat: null }
function tabs() { document.getElementById('tab').innerHTML = user ? [['book', '🪑 选座'], ['mine', '📋 我的预约']].map(([k, t]) => `<a class="${k === page ? 'on' : ''}" onclick="page='${k}';render()">${t}</a>`).join('') : '' }
async function render() {
  tabs()
  if (!user) {
    v.innerHTML = `<div class="box"><h3>学号登录</h3><input id="sid" placeholder="学号" value="2026001"><input id="pw" type="password" placeholder="密码（演示：123456）"><button class="btn" onclick="login()">登录 / 首次自动注册</button></div>`; return
  }
  try { await (page === 'book' ? bookView() : mineView()) } catch (e) { if (e.status === 401) { localStorage.removeItem(KEY); user = null; render() } }
}
async function login() { const r = await API('/api/login', { method: 'POST', body: { sid: document.getElementById('sid').value, password: document.getElementById('pw').value } }); localStorage.setItem(KEY, r.token); localStorage.setItem('u_' + location.port, JSON.stringify(r.user)); user = r.user; render() }
async function bookView() {
  meta ||= await API('/api/meta'); const room = meta.rooms[st.room], day = meta.days[st.day]
  const taken = new Set(await API(`/api/rooms/${room.id}/seats?day=${day}&slot=${st.slot}`))
  const heat = EDITION === 'pro' ? await API(`/api/rooms/${room.id}/heat`) : null, hmax = heat ? Math.max(1, ...Object.values(heat)) : 1
  const chip = (arr, key, lab) => `<div class="chips">${arr.map((x, i) => `<span class="chip ${st[key] === i ? 'on' : ''}" onclick="st.${key}=${i};st.seat=null;render()">${lab(x)}</span>`).join('')}</div>`
  let seats = ''; for (let r = 1; r <= room.rows; r++) for (let c = 1; c <= room.cols; c++) { const k = `${r}-${c}`, t = taken.has(k); seats += `<div class="seat ${t ? 't' : ''} ${st.seat === k ? 'sel' : ''}" ${t ? '' : `onclick="st.seat='${k}';render()"`} ${heat && !t && st.seat !== k ? `style="background:rgba(239,68,68,${0.1 + 0.6 * (heat[k] || 0) / hmax})"` : ''}>${k}</div>` }
  v.innerHTML = `<div class="box">${chip(meta.days, 'day', d => d.slice(5))}<div style="height:8px"></div>${chip(meta.slots, 'slot', s => s)}<div style="height:8px"></div>${chip(meta.rooms, 'room', r => r.name)}</div>
  <div class="box"><b>${esc(room.name)}</b> <small style="color:#888">剩余 ${room.rows * room.cols - taken.size} / ${room.rows * room.cols}</small><div class="grid" style="grid-template-columns:repeat(${room.cols},1fr)">${seats}</div>
  <div class="legend">🟩 可选　⬜ 已被预约　${heat ? '🟥 颜色越深越热门（高级版热力图）' : '<span class="dl-ed pro">座位热力图：高级版</span>'}</div>
  <button class="btn" ${st.seat ? '' : 'disabled style="opacity:.5"'} onclick="book()">${st.seat ? `预约 ${st.seat} 号座` : '请选择座位'}</button></div>`
}
async function book() { await API('/api/bookings', { method: 'POST', body: { day: meta.days[st.day], slot: st.slot, roomId: meta.rooms[st.room].id, seat: st.seat } }); toast('预约成功，请按时签到'); st.seat = null; page = 'mine'; render() }
async function mineView() {
  const list = await API('/api/bookings'), me = await API('/api/me')
  v.innerHTML = `<div class="box"><b>${esc(user.name)}</b>（${esc(user.sid)}）<div style="margin-top:6px">${me.credit !== null ? `信用分：<b style="color:#059669">${me.credit}</b>（低于 60 暂停预约）` : '<span class="dl-ed pro">信用分与违约管理：高级版</span>'}</div><button class="sm" style="margin:8px 0 0" onclick="localStorage.removeItem(KEY);user=null;render()">退出登录</button></div>
  <div class="box"><b>我的预约</b>${list.map(b => `<div class="item"><div>${esc(b.room)} · ${b.seat}<br><small>${b.day} ${b.slotText} · ${b.status}</small></div><div>${b.status === '已预约' ? `<button class="sm" onclick="op(${b.id},'checkin')">签到</button><button class="sm" onclick="op(${b.id},'cancel')">取消</button>${EDITION === 'pro' ? `<button class="sm" onclick="op(${b.id},'noshow')">模拟违约</button>` : ''}` : ''}</div></div>`).join('') || '<p style="color:#888">暂无预约</p>'}</div>`
}
async function op(id, a) { await API(`/api/bookings/${id}/${a}`, { method: 'POST' }); toast({ checkin: '签到成功', cancel: '已取消', noshow: '已记违约，扣 10 分' }[a]); render() }
initCommon().then(render)
