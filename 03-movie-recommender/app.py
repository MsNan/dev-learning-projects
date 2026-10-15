"""电影推荐与数据可视化系统（学习示例）— 协同过滤 + 原生 SVG/CSS 图表
运行：python3 app.py      付费高级版：EDITION=pro python3 app.py
数据为程序随机生成的模拟数据，电影名为虚构。"""
import os, sys, time, math, random
from collections import defaultdict
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'common'))
from web import App, HttpError, need_pro, is_pro, hash_pw, check_pw

HERE = os.path.dirname(os.path.abspath(__file__))
app = App('电影推荐', os.path.join(HERE, 'static'), os.path.join(HERE, 'movies.db'))
GENRES = ['剧情', '喜剧', '动作', '科幻', '爱情', '动画', '悬疑', '纪录片']
WORDS = ['星辰', '远方', '归途', '迷城', '少年', '夏日', '暗夜', '风暴', '回响', '边境', '记忆', '光年', '旧梦', '长街', '海潮', '彼岸']

def init():
    with app.db() as c:
        c.executescript('''
        create table if not exists users(id integer primary key, username text unique, password text);
        create table if not exists movies(id integer primary key, title text, genre text, year integer);
        create table if not exists ratings(user_id integer, movie_id integer, score integer, ts integer, primary key(user_id, movie_id));''')
        app.init_rewards(c)
        if c.execute('select 1 from movies').fetchone(): return
        rnd = random.Random(42)
        for i in range(48):
            c.execute('insert into movies(title,genre,year) values(?,?,?)', (rnd.choice(WORDS) + rnd.choice(WORDS) + ('' if i % 3 else '之' + rnd.choice(WORDS)), GENRES[i % len(GENRES)], 2005 + rnd.randint(0, 20)))
        c.execute('insert into users(username,password) values(?,?)', ('demo', hash_pw('demo123')))
        for u in range(2, 82):  # 80 个模拟用户，各自偏好 2 个类型
            c.execute('insert into users(username,password) values(?,?)', (f'sim{u}', hash_pw(os.urandom(8).hex())))
            fav = rnd.sample(GENRES, 2)
            for m in rnd.sample(range(1, 49), rnd.randint(8, 20)):
                g = GENRES[(m - 1) % len(GENRES)]
                s = min(5, max(1, round(rnd.gauss(4.3 if g in fav else 2.6, 0.8))))
                c.execute('insert into ratings values(?,?,?,?)', (u, m, s, int(time.time()) - rnd.randint(0, 365 * 86400)))
        for m, s in [(1, 5), (9, 5), (4, 4), (12, 2)]: c.execute('insert into ratings values(1,?,?,?)', (m, s, int(time.time())))

def load(c):
    R = defaultdict(dict)
    for x in c.execute('select * from ratings'): R[x['user_id']][x['movie_id']] = x['score']
    return R

def item_cf(R, uid, k=10):
    """基于物品的协同过滤：余弦相似度，按用户已评分物品加权"""
    by_item = defaultdict(dict)
    for u, rs in R.items():
        for m, s in rs.items(): by_item[m][u] = s
    norm = {m: math.sqrt(sum(v * v for v in us.values())) for m, us in by_item.items()}
    def sim(a, b):
        common = by_item[a].keys() & by_item[b].keys()
        return sum(by_item[a][u] * by_item[b][u] for u in common) / (norm[a] * norm[b]) if common else 0
    mine = R.get(uid, {}); score, why = defaultdict(float), {}
    for m in by_item:
        if m in mine: continue
        best = 0
        for j, s in mine.items():
            w = sim(m, j) * (s - 2.5)
            score[m] += w
            if w > best: best, why[m] = w, j
    return sorted(score.items(), key=lambda x: -x[1])[:k], why

def user_cf(R, uid, k=10, n=15):
    """基于用户的协同过滤（Pearson 相关），取最相似的 n 个邻居"""
    mine = R.get(uid, {})
    if not mine: return []
    mu = sum(mine.values()) / len(mine)
    def pearson(o):
        common = mine.keys() & o.keys()
        if len(common) < 2: return 0
        mo = sum(o.values()) / len(o)
        num = sum((mine[m] - mu) * (o[m] - mo) for m in common)
        den = math.sqrt(sum((mine[m] - mu) ** 2 for m in common) * sum((o[m] - mo) ** 2 for m in common))
        return num / den if den else 0
    nb = sorted(((pearson(o), v) for v, o in R.items() if v != uid), key=lambda x: -x[0])[:n]
    score = defaultdict(float)
    for s, v in nb:
        if s <= 0: continue
        mo = sum(R[v].values()) / len(R[v])
        for m, r in R[v].items():
            if m not in mine: score[m] += s * (r - mo)
    return sorted(score.items(), key=lambda x: -x[1])[:k]

def movies_map(c): return {x['id']: dict(x) for x in c.execute('select * from movies')}

@app.route('POST', '/api/login')
def login(r):
    un, pw = r.body.get('username', '').strip(), r.body.get('password', '')
    with app.db() as c:
        u = c.execute('select * from users where username=?', (un,)).fetchone()
        if not u:
            if len(un) < 3 or len(pw) < 6: raise HttpError(400, '用户名至少 3 位，密码至少 6 位')
            c.execute('insert into users(username,password) values(?,?)', (un, hash_pw(pw))); u = c.execute('select * from users where username=?', (un,)).fetchone()
        elif not check_pw(pw, u['password']): raise HttpError(401, '用户名或密码错误')
    user = {'id': u['id'], 'name': u['username']}
    return {'token': app.login(user), 'user': user}

@app.route('GET', '/api/movies')
def movies(r):
    g = r.query.get('genre', '')
    with app.db() as c:
        sql = 'select m.*, round(avg(r.score),2) avg, count(r.score) cnt from movies m left join ratings r on r.movie_id=m.id ' + ('where m.genre=? ' if g else '') + 'group by m.id order by m.id'
        return [dict(x) for x in c.execute(sql, (g,) if g else ())]

@app.route('POST', '/api/ratings')
def rate(r):
    u = app.user(r); m, s = int(r.body.get('movieId', 0)), int(r.body.get('score', 0))
    if not 1 <= s <= 5: raise HttpError(400, '评分为 1-5')
    with app.db() as c:
        if not c.execute('select 1 from movies where id=?', (m,)).fetchone(): raise HttpError(404, '电影不存在')
        c.execute('insert or replace into ratings values(?,?,?,?)', (u['id'], m, s, int(time.time())))
    return True

@app.route('GET', '/api/my-ratings')
def my(r):
    u = app.user(r)
    with app.db() as c: return {x['movie_id']: x['score'] for x in c.execute('select * from ratings where user_id=?', (u['id'],))}

@app.route('GET', '/api/recommend')
def recommend(r):
    u = app.user(r)
    with app.db() as c:
        R, M = load(c), movies_map(c)
        hot = [dict(x) for x in c.execute('select m.*, avg(r.score) a, count(*) n from movies m join ratings r on r.movie_id=m.id group by m.id having n>=5 order by (a*n+3*10)/(n+10) desc limit 8')]
        items, why = item_cf(R, u['id'])
        res = {'hot': hot, 'itemCF': [M[m] | {'score': round(s, 2), 'because': M[why[m]]['title'] if m in why else None} for m, s in items]}
        if is_pro():
            uc = dict(user_cf(R, u['id'], 20)); ic = dict(item_cf(R, u['id'], 20)[0])
            mx = lambda d: max([abs(v) for v in d.values()] + [1e-9])
            hyb = defaultdict(float)
            for m, s in ic.items(): hyb[m] += 0.5 * s / mx(ic)
            for m, s in uc.items(): hyb[m] += 0.5 * s / mx(uc)
            res['hybrid'] = [M[m] | {'score': round(s, 3)} for m, s in sorted(hyb.items(), key=lambda x: -x[1])[:8]]
        return res

@app.route('GET', '/api/charts/basic')
def basic(r):
    with app.db() as c:
        return [dict(x) for x in c.execute('select m.genre name, count(*) value from ratings r join movies m on m.id=r.movie_id group by m.genre order by value desc')]

@app.route('GET', '/api/charts/pro')
def pro(r):
    need_pro('数据大屏')
    with app.db() as c:
        R = load(c)
        dist = [c.execute('select count(*) from ratings where score=?', (s,)).fetchone()[0] for s in range(1, 6)]
        gavg = [dict(x) for x in c.execute('select m.genre name, round(avg(r.score),2) value from ratings r join movies m on m.id=r.movie_id group by m.genre order by value desc')]
        years = [dict(x) for x in c.execute('select m.year name, count(*) value from ratings r join movies m on m.id=r.movie_id group by m.year order by m.year')]
        # 离线评估：留一法 Hit@10（每个用户隐藏一条高分评分）
        hits = tot = 0; rnd = random.Random(1)
        for u in list(R)[:40]:
            good = [m for m, s in R[u].items() if s >= 4]
            if len(good) < 2: continue
            h = rnd.choice(good); s = R[u].pop(h)
            rec = [m for m, _ in item_cf(R, u, 10)[0]]; hits += h in rec; tot += 1; R[u][h] = s
        return {'dist': dist, 'genreAvg': gavg, 'years': years, 'users': len(R), 'ratings': sum(map(len, R.values())), 'hit10': round(hits / tot, 3) if tot else 0, 'evalUsers': tot}

if __name__ == '__main__':
    init(); app.run(int(os.environ.get('PORT', 8003)))
