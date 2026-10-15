"""图书管理系统（学习示例）— Python 标准库 + SQLite + 原生前端
运行：python3 app.py      付费高级版：EDITION=pro python3 app.py"""
import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'common'))
from web import App, HttpError, need_pro, is_pro, hash_pw, check_pw, csv_bytes

HERE = os.path.dirname(os.path.abspath(__file__))
app = App('图书管理系统', os.path.join(HERE, 'static'), os.path.join(HERE, 'library.db'))
LOAN_DAYS, FINE_PER_DAY = 30, 0.5
DAY = 86400

def init():
    with app.db() as c:
        c.executescript('''
        create table if not exists users(id integer primary key, username text unique, password text, name text, role text);
        create table if not exists books(id integer primary key, isbn text, title text, author text, category text, total integer, available integer);
        create table if not exists loans(id integer primary key, book_id integer, user_id integer, borrowed_at integer, due_at integer, returned_at integer, fine real default 0);''')
        app.init_rewards(c)
        if not c.execute('select 1 from users').fetchone():
            c.execute('insert into users(username,password,name,role) values(?,?,?,?)', ('admin', hash_pw(os.environ.get('ADMIN_PASSWORD', 'admin123')), '管理员', 'admin'))
            c.execute('insert into users(username,password,name,role) values(?,?,?,?)', ('reader', hash_pw('reader123'), '读者小明', 'reader'))
            books = [('9787111213826', 'Java编程思想', 'Bruce Eckel', '编程', 5), ('9787115428028', 'Python编程：从入门到实践', 'Eric Matthes', '编程', 4),
                     ('9787302423287', '数据结构（C语言版）', '严蔚敏', '计算机基础', 6), ('9787111544937', '深入理解计算机系统', 'Randal E. Bryant', '计算机基础', 3),
                     ('9787115352118', '算法（第4版）', 'Robert Sedgewick', '算法', 3), ('9787121360978', '机器学习实战', 'Peter Harrington', '人工智能', 2),
                     ('9787508647357', '人类简史', '尤瓦尔·赫拉利', '人文社科', 4), ('9787544253994', '百年孤独', '加西亚·马尔克斯', '文学', 5)]
            c.executemany('insert into books(isbn,title,author,category,total,available) values(?,?,?,?,?,?)', [b + (b[4],) for b in books])
            now = int(time.time())  # 演示数据：一条正常借阅 + 一条逾期借阅
            c.execute('insert into loans(book_id,user_id,borrowed_at,due_at) values(1,2,?,?)', (now - 5 * DAY, now + 25 * DAY))
            c.execute('insert into loans(book_id,user_id,borrowed_at,due_at) values(3,2,?,?)', (now - 40 * DAY, now - 10 * DAY))
            c.execute('update books set available=available-1 where id in (1,3)')

def fine_of(l, now=None):
    end = l['returned_at'] or (now or time.time())
    return round(max(0, (end - l['due_at']) // DAY) * FINE_PER_DAY, 2) if is_pro() else 0

@app.route('POST', '/api/login')
def login(r):
    with app.db() as c:
        u = c.execute('select * from users where username=?', (r.body.get('username', ''),)).fetchone()
    if not u or not check_pw(r.body.get('password', ''), u['password']): raise HttpError(401, '账号或密码错误')
    user = {'id': u['id'], 'name': u['name'], 'role': u['role']}
    return {'token': app.login(user), 'user': user}

@app.route('POST', '/api/register')
def register(r):
    un, pw, name = r.body.get('username', '').strip(), r.body.get('password', ''), r.body.get('name', '').strip()
    if len(un) < 3 or len(pw) < 6: raise HttpError(400, '用户名至少 3 位，密码至少 6 位')
    with app.db() as c:
        if c.execute('select 1 from users where username=?', (un,)).fetchone(): raise HttpError(400, '用户名已存在')
        c.execute('insert into users(username,password,name,role) values(?,?,?,?)', (un, hash_pw(pw), name or un, 'reader'))
    return True

@app.route('GET', '/api/books')
def books(r):
    q, cat = '%' + r.query.get('q', '') + '%', r.query.get('category', '')
    with app.db() as c:
        sql = 'select * from books where (title like ? or author like ? or isbn like ?)' + (' and category=?' if cat else '') + ' order by id'
        return [dict(x) for x in c.execute(sql, (q, q, q) + ((cat,) if cat else ()))]

@app.route('POST', '/api/books')
def book_add(r):
    app.user(r, 'admin'); b = r.body
    if not b.get('title'): raise HttpError(400, '请填写书名')
    n = max(0, int(b.get('total') or 1))
    with app.db() as c:
        c.execute('insert into books(isbn,title,author,category,total,available) values(?,?,?,?,?,?)', (b.get('isbn', ''), b['title'], b.get('author', ''), b.get('category', '其他'), n, n))
    return True

@app.route('PUT', '/api/books/:id')
def book_edit(r):
    app.user(r, 'admin'); b = r.body
    with app.db() as c:
        old = c.execute('select * from books where id=?', (r.params['id'],)).fetchone()
        if not old: raise HttpError(404, '图书不存在')
        total = int(b.get('total', old['total'])); lent = old['total'] - old['available']
        if total < lent: raise HttpError(400, f'已借出 {lent} 本，总数不能小于借出数')
        c.execute('update books set isbn=?,title=?,author=?,category=?,total=?,available=? where id=?', (b.get('isbn', old['isbn']), b.get('title', old['title']), b.get('author', old['author']), b.get('category', old['category']), total, total - lent, old['id']))
    return True

@app.route('DELETE', '/api/books/:id')
def book_del(r):
    app.user(r, 'admin')
    with app.db() as c:
        if c.execute('select 1 from loans where book_id=? and returned_at is null', (r.params['id'],)).fetchone(): raise HttpError(400, '该书还有未归还的借阅')
        c.execute('delete from books where id=?', (r.params['id'],))
    return True

@app.route('POST', '/api/books/:id/borrow')
def borrow(r):
    u = app.user(r); now = int(time.time())
    with app.db() as c:
        b = c.execute('select * from books where id=?', (r.params['id'],)).fetchone()
        if not b or b['available'] <= 0: raise HttpError(400, '该书暂无库存')
        if c.execute('select count(*) from loans where user_id=? and returned_at is null', (u['id'],)).fetchone()[0] >= 5: raise HttpError(400, '最多同时借 5 本')
        c.execute('insert into loans(book_id,user_id,borrowed_at,due_at) values(?,?,?,?)', (b['id'], u['id'], now, now + LOAN_DAYS * DAY))
        c.execute('update books set available=available-1 where id=?', (b['id'],))
    return True

@app.route('POST', '/api/loans/:id/return')
def give_back(r):
    u = app.user(r)
    with app.db() as c:
        l = c.execute('select * from loans where id=?', (r.params['id'],)).fetchone()
        if not l or l['returned_at']: raise HttpError(400, '借阅记录不存在或已归还')
        if u['role'] != 'admin' and l['user_id'] != u['id']: raise HttpError(403, '没有权限')
        now = int(time.time()); f = fine_of(dict(l), now)
        c.execute('update loans set returned_at=?, fine=? where id=?', (now, f, l['id']))
        c.execute('update books set available=available+1 where id=?', (l['book_id'],))
    return {'fine': f}

def loan_rows(c, where='', args=()):
    rows = c.execute('select l.*, b.title, u.name as reader from loans l join books b on b.id=l.book_id join users u on u.id=l.user_id ' + where + ' order by l.id desc', args)
    now = time.time(); out = []
    for x in rows:
        d = dict(x); d['overdue'] = not d['returned_at'] and now > d['due_at']; d['fine'] = d['fine'] if d['returned_at'] else fine_of(d, now); out.append(d)
    return out

@app.route('GET', '/api/loans')
def loans(r):
    u = app.user(r)
    with app.db() as c:
        return loan_rows(c) if u['role'] == 'admin' else loan_rows(c, 'where l.user_id=?', (u['id'],))

# ---------- 付费高级版 ----------
@app.route('GET', '/api/stats')
def stats(r):
    app.user(r, 'admin'); need_pro('统计看板')
    with app.db() as c:
        by_cat = [dict(x) for x in c.execute('select b.category name, count(*) value from loans l join books b on b.id=l.book_id group by b.category order by value desc')]
        top = [dict(x) for x in c.execute('select b.title name, count(*) value from loans l join books b on b.id=l.book_id group by b.id order by value desc limit 5')]
        cnt = lambda s: c.execute(s).fetchone()[0]
        return {'books': cnt('select sum(total) from books'), 'lent': cnt('select count(*) from loans where returned_at is null'),
                'readers': cnt("select count(*) from users where role='reader'"), 'overdue': sum(1 for l in loan_rows(c) if l['overdue']),
                'byCategory': by_cat, 'top': top}

@app.route('GET', '/api/export/loans')
def export(r):
    app.user(r, 'admin'); need_pro('导出 CSV')
    with app.db() as c:
        rows = [['ID', '书名', '读者', '借出', '应还', '归还', '逾期', '罚金']] + [[l['id'], l['title'], l['reader'], time.strftime('%Y-%m-%d', time.localtime(l['borrowed_at'])), time.strftime('%Y-%m-%d', time.localtime(l['due_at'])), l['returned_at'] and time.strftime('%Y-%m-%d', time.localtime(l['returned_at'])) or '', '是' if l['overdue'] else '', l['fine']] for l in loan_rows(c)]
    return ('file', csv_bytes(rows), 'text/csv; charset=utf-8', 'loans.csv')

if __name__ == '__main__':
    init(); app.run(int(os.environ.get('PORT', 8001)))
