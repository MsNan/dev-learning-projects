const KEY = 'token_' + location.port, v = document.getElementById('v'), G = ['剧情', '喜剧', '动作', '科幻', '爱情', '动画', '悬疑', '纪录片'], EMO = { 剧情: '🎭', 喜剧: '😂', 动作: '💥', 科幻: '🚀', 爱情: '💕', 动画: '🧸', 悬疑: '🕵️', 纪录片: '🌍' }
let user = JSON.parse(localStorage.getItem('u_' + location.port) || 'null'), page = 'rec', genre = ''
const hue = s => [...s].reduce((h, c) => h + c.charCodeAt(0), 0) % 360
function nav() { document.getElementById('nav').innerHTML = user ? [['rec', '为你推荐'], ['all', '全部电影'], ['viz', '数据可视化']].map(([k, t]) => `<a class="${k === page ? 'on' : ''}" onclick="page='${k}';render()">${t}</a>`).join(' ') + ` <a onclick="localStorage.removeItem(KEY);user=null;render()">退出（${esc(user.name)}）</a>` : '' }
const card = (m, my, extra = '') => `<div class="mv"><div class="poster" style="background:linear-gradient(135deg,hsl(${hue(m.title)},60%,40%),hsl(${hue(m.title) + 60},60%,25%))">${EMO[m.genre] || '🎬'}</div><div class="t">${esc(m.title)}</div><small>${m.genre} · ${m.year}${m.avg ? ' · ⭐' + m.avg + '（' + m.cnt + '）' : ''}</small>${extra}<div class="stars">${[1, 2, 3, 4, 5].map(s => `<span class="${(my[m.id] || 0) >= s ? 'on' : ''}" onclick="rate(${m.id},${s})">★</span>`).join('')}</div></div>`
async function render() {
  nav()
  if (!user) { v.innerHTML = `<div class="login"><h2>登录</h2><input id="un" value="demo" placeholder="用户名"><input id="pw" type="password" placeholder="密码（演示 demo123）"><button style="width:100%" onclick="login()">登录 / 自动注册</button></div>`; return }
  try { await views[page]() } catch (e) { if (e.status === 401) { localStorage.removeItem(KEY); user = null; render() } }
}
async function login() { const r = await API('/api/login', { method: 'POST', body: { username: un.value, password: pw.value } }); localStorage.setItem(KEY, r.token); localStorage.setItem('u_' + location.port, JSON.stringify(r.user)); user = r.user; render() }
async function rate(id, s) { await API('/api/ratings', { method: 'POST', body: { movieId: id, score: s } }); toast('已评分，推荐结果已更新'); render() }
const bars = (list, fmt = x => x) => { const mx = Math.max(1, ...list.map(x => x.value)); return list.map(x => `<div class="bar"><span style="width:70px">${esc(x.name)}</span><i style="width:${x.value / mx * 70}%"></i><span>${fmt(x.value)}</span></div>`).join('') }
const views = {
  async rec() {
    const [r, my] = await Promise.all([API('/api/recommend'), API('/api/my-ratings')])
    v.innerHTML = `<p style="color:#94a3b8">你已评价 ${Object.keys(my).length} 部电影，评分越多推荐越准。</p>
    <h3>🔥 热门高分（贝叶斯平均）</h3><div class="row">${r.hot.map(m => card(m, my)).join('')}</div>
    <h3>🎯 猜你喜欢（基于物品的协同过滤）</h3><div class="row">${r.itemCF.map(m => card(m, my, m.because ? `<div><small style="color:#f9a8d4">因为你喜欢《${esc(m.because)}》</small></div>` : '')).join('') || '<p>先给几部电影打分吧</p>'}</div>
    <h3>🧠 混合推荐（Item-CF + User-CF 加权融合）</h3>${r.hybrid ? `<div class="row">${r.hybrid.map(m => card(m, my, `<div><small>融合得分 ${m.score}</small></div>`)).join('')}</div>` : lockHtml('混合推荐 + 推荐解释')}`
  },
  async all() {
    const [list, my] = await Promise.all([API('/api/movies?genre=' + encodeURIComponent(genre)), API('/api/my-ratings')])
    v.innerHTML = `<div class="chips"><span class="${genre ? '' : 'on'}" onclick="genre='';render()">全部</span>${G.map(g => `<span class="${g === genre ? 'on' : ''}" onclick="genre='${g}';render()">${g}</span>`).join('')}</div><div class="row">${list.map(m => card(m, my)).join('')}</div>`
  },
  async viz() {
    const b = await API('/api/charts/basic')
    let h = `<div class="panel"><b>各类型评分人次（免费版基础图表）</b>${bars(b)}</div>`
    if (EDITION === 'pro') {
      const p = await API('/api/charts/pro'), mx = Math.max(...p.years.map(y => y.value)), W = 640, H = 160
      const pts = p.years.map((y, i) => `${i / (p.years.length - 1) * W},${H - y.value / mx * (H - 10)}`).join(' ')
      h = `<div class="kpi"><div><b>${p.users}</b>用户数</div><div><b>${p.ratings}</b>评分数</div><div><b>${(p.hit10 * 100).toFixed(1)}%</b>Hit@10（留一法，${p.evalUsers} 人）</div><div><b>${G.length}</b>电影类型</div></div>
      <div class="grid2">${h}<div class="panel"><b>评分分布（1~5 星）</b>${bars(p.dist.map((x, i) => ({ name: (i + 1) + ' 星', value: x })))}</div>
      <div class="panel"><b>各类型平均分</b>${bars(p.genreAvg, x => x.toFixed(2))}</div>
      <div class="panel"><b>按上映年份的评分人次趋势</b><svg viewBox="-10 -10 ${W + 20} ${H + 30}" style="width:100%"><polyline points="${pts}" fill="none" stroke="#ec4899" stroke-width="3"/>${p.years.map((y, i) => i % 3 ? '' : `<text x="${i / (p.years.length - 1) * W}" y="${H + 18}" fill="#94a3b8" font-size="12" text-anchor="middle">${y.name}</text>`).join('')}</svg></div></div>`
    } else h += '<div style="height:14px"></div>' + lockHtml('数据大屏（评分分布、类型均分、年份趋势、离线评估 Hit@10）')
    v.innerHTML = h
  }
}
initCommon().then(render)
