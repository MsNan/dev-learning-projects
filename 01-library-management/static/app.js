const KEY = 'token_' + location.port, v = document.getElementById('v')
let me = JSON.parse(localStorage.getItem('user_' + location.port) || 'null'), tab = 'books'
const d = t => t ? new Date(t * 1000).toLocaleDateString('zh-CN') : '-'
function nav() {
  const tabs = me ? [['books', '图书检索'], ['loans', me.role === 'admin' ? '借阅管理' : '我的借阅'], ...(me.role === 'admin' ? [['stats', '统计看板']] : [])] : []
  document.getElementById('nav').innerHTML = tabs.map(([k, t]) => `<a class="${k === tab ? 'on' : ''}" onclick="tab='${k}';render()">${t}</a>`).join('')
  document.getElementById('who').innerHTML = me ? `${esc(me.name)}（${me.role === 'admin' ? '管理员' : '读者'}） <a style="color:#fff;cursor:pointer" onclick="logout()">退出</a>` : ''
}
function logout() { localStorage.removeItem(KEY); localStorage.removeItem('user_' + location.port); me = null; render() }
async function render() {
  nav()
  if (!me) {
    v.innerHTML = `<form class="login" id="f"><h2>登录</h2><input name="username" placeholder="用户名" value="admin"><input name="password" type="password" placeholder="密码"><button class="p" style="width:100%;padding:9px">登录</button><p style="color:#888;font-size:12px">演示账号：admin / admin123（管理员）、reader / reader123（读者）</p></form>`
    document.getElementById('f').onsubmit = async e => { e.preventDefault(); const r = await API('/api/login', { method: 'POST', body: Object.fromEntries(new FormData(e.target)) }); localStorage.setItem(KEY, r.token); localStorage.setItem('user_' + location.port, JSON.stringify(r.user)); me = r.user; render() }
    return
  }
  try { await views[tab]() } catch (e) { if (e.status === 401) logout() }
}
const views = {
  async books() {
    const q = sessionStorage.q || '', list = await API('/api/books?q=' + encodeURIComponent(q)), admin = me.role === 'admin'
    v.innerHTML = `<div class="bar"><input id="q" placeholder="书名 / 作者 / ISBN" value="${esc(q)}"><button onclick="sessionStorage.q=document.getElementById('q').value;render()">搜索</button>${admin ? '<button class="p" onclick="edit()">+ 新增图书</button>' : ''}</div>
    <table><tr><th>ISBN</th><th>书名</th><th>作者</th><th>分类</th><th>馆藏/可借</th><th>操作</th></tr>${list.map(b => `<tr><td>${esc(b.isbn)}</td><td>${esc(b.title)}</td><td>${esc(b.author)}</td><td>${esc(b.category)}</td><td>${b.total} / ${b.available}</td><td><button class="p" ${b.available ? '' : 'disabled'} onclick="borrow(${b.id})">借阅</button>${admin ? `<button onclick='edit(${JSON.stringify(b).replace(/'/g, '&#39;')})'>编辑</button><button class="red" onclick="del(${b.id})">删除</button>` : ''}</td></tr>`).join('')}</table>`
  },
  async loans() {
    const list = await API('/api/loans'), admin = me.role === 'admin'
    v.innerHTML = `<div class="bar">${admin ? (EDITION === 'pro' ? '<button onclick="exportCsv()">导出 CSV</button>' : '<span class="dl-ed pro">导出 CSV / 逾期罚金：付费高级版</span>') : ''}</div>
    <table><tr><th>书名</th>${admin ? '<th>读者</th>' : ''}<th>借出</th><th>应还</th><th>归还</th><th>状态</th><th>罚金</th><th>操作</th></tr>${list.map(l => `<tr><td>${esc(l.title)}</td>${admin ? `<td>${esc(l.reader)}</td>` : ''}<td>${d(l.borrowed_at)}</td><td>${d(l.due_at)}</td><td>${d(l.returned_at)}</td><td>${l.returned_at ? '已归还' : l.overdue ? '<b class="red">已逾期</b>' : '借阅中'}</td><td>${EDITION === 'pro' ? '¥' + l.fine : '-'}</td><td>${l.returned_at ? '' : `<button class="p" onclick="giveBack(${l.id})">归还</button>`}</td></tr>`).join('') || '<tr><td colspan=8>暂无记录</td></tr>'}</table>`
  },
  async stats() {
    if (EDITION !== 'pro') return (v.innerHTML = lockHtml('统计看板（借阅分类占比、热门图书、逾期统计）'))
    const s = await API('/api/stats'), max = Math.max(1, ...s.top.map(x => x.value)), tot = s.byCategory.reduce((t, x) => t + x.value, 0) || 1
    const colors = ['#2563eb', '#f59e0b', '#10b981', '#ef4444', '#8b5cf6', '#06b6d4']; let a = 0
    const pie = s.byCategory.map((x, i) => { const s0 = a; a += x.value / tot * 360; return `${colors[i % 6]} ${s0}deg ${a}deg` }).join(',')
    v.innerHTML = `<div class="cards">${[['馆藏总量', s.books], ['借阅中', s.lent], ['读者数', s.readers], ['逾期未还', s.overdue]].map(([k, x]) => `<div class="card"><div class="v">${x}</div>${k}</div>`).join('')}</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px"><div class="card"><b>借阅分类占比</b><div style="display:flex;gap:20px;align-items:center;margin-top:10px"><div style="width:160px;height:160px;border-radius:50%;background:conic-gradient(${pie})"></div><div>${s.byCategory.map((x, i) => `<div><span style="color:${colors[i % 6]}">■</span> ${esc(x.name)} ${x.value}</div>`).join('')}</div></div></div>
    <div class="card"><b>热门图书 TOP5</b>${s.top.map(x => `<div style="margin:8px 0">${esc(x.name)}<div style="background:#dbeafe;height:10px;border-radius:5px"><div style="background:#2563eb;height:10px;border-radius:5px;width:${x.value / max * 100}%"></div></div></div>`).join('')}</div></div>`
  }
}
async function borrow(id) { await API(`/api/books/${id}/borrow`, { method: 'POST' }); toast('借阅成功，30 天内归还'); render() }
async function giveBack(id) { const r = await API(`/api/loans/${id}/return`, { method: 'POST' }); toast(r.fine ? `已归还，逾期罚金 ¥${r.fine}` : '已归还'); render() }
async function del(id) { if (confirm('确定删除？')) { await API('/api/books/' + id, { method: 'DELETE' }); render() } }
async function edit(b = {}) {
  const f = ['isbn', 'title', 'author', 'category', 'total'], lab = { isbn: 'ISBN', title: '书名', author: '作者', category: '分类', total: '馆藏数量' }, o = {}
  for (const k of f) { const x = prompt(lab[k], b[k] ?? (k === 'total' ? 1 : '')); if (x === null) return; o[k] = k === 'total' ? Number(x) : x }
  await API(b.id ? '/api/books/' + b.id : '/api/books', { method: b.id ? 'PUT' : 'POST', body: o }); toast('已保存'); render()
}
async function exportCsv() { const r = await fetch('/api/export/loans', { headers: { Authorization: 'Bearer ' + localStorage.getItem(KEY) } }); const a = document.createElement('a'); a.href = URL.createObjectURL(await r.blob()); a.download = 'loans.csv'; a.click() }
initCommon().then(render)
