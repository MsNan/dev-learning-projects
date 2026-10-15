"""图书馆座位预约（移动端 H5，学习示例，可对照移植为微信小程序/uni-app）
运行：python3 app.py      付费高级版：EDITION=pro python3 app.py"""
import os, sys, time, datetime
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'common'))
from web import App, HttpError, need_pro, is_pro, hash_pw, check_pw

HERE = os.path.dirname(os.path.abspath(__file__))
app = App('座位预约', os.path.join(HERE, 'static'), os.path.join(HERE, 'seats.db'))
SLOTS = ['08:00-12:00', '12:00-17:00', '17:00-22:00']
ROOMS = [('一楼自习室', 4, 8), ('二楼阅览室', 5, 6), ('三楼研讨区', 3, 6)]

def init():
    with app.db() as c:
        c.executescript('''
        create table if not exists users(id integer primary key, sid text unique, password text, name text, credit integer default 100);
        create table if not exists rooms(id integer primary key, name text, rows integer, cols integer);
        create table if not exists bookings(id integer primary key, user_id integer, room_id integer, seat text, day text, slot integer, status text, created_at integer);''')
        app.init_rewards(c)
        if not c.execute('select 1 from rooms').fetchone():
            c.executemany('insert into rooms(name,rows,cols) values(?,?,?)', ROOMS)
            c.execute('insert into users(sid,password,name) values(?,?,?)', ('2026001', hash_pw('123456'), '同学小王'))
            today = datetime.date.today().isoformat()
            import random; random.seed(7)
            for i in range(14):  # 演示占座
                c.execute('insert into users(sid,password,name) values(?,?,?)', (f'20269{i:02d}', hash_pw('123456'), f'演示同学{i}'))
                c.execute('insert into bookings(user_id,room_id,seat,day,slot,status,created_at) values(?,?,?,?,?,?,?)', (i + 2, 1, f'{random.randint(1,4)}-{random.randint(1,8)}', today, random.randint(0, 2), '已预约', int(time.time())))

@app.route('POST', '/api/login')
def login(r):
    sid, pw = r.body.get('sid', ''), r.body.get('password', '')
    with app.db() as c:
        u = c.execute('select * from users where sid=?', (sid,)).fetchone()
        if not u:  # 学习示例：首次登录自动注册
            if not sid.isdigit() or len(pw) < 6: raise HttpError(400, '学号需为数字，密码至少 6 位')
            c.execute('insert into users(sid,password,name) values(?,?,?)', (sid, hash_pw(pw), '同学' + sid[-3:]))
            u = c.execute('select * from users where sid=?', (sid,)).fetchone()
        elif not check_pw(pw, u['password']): raise HttpError(401, '学号或密码错误')
    user = {'id': u['id'], 'name': u['name'], 'sid': u['sid']}
    return {'token': app.login(user), 'user': user}

@app.route('GET', '/api/meta')
def meta(r):
    with app.db() as c:
        return {'slots': SLOTS, 'rooms': [dict(x) for x in c.execute('select * from rooms')], 'days': [(datetime.date.today() + datetime.timedelta(d)).isoformat() for d in range(3)]}

@app.route('GET', '/api/rooms/:id/seats')
def seats(r):
    day, slot = r.query.get('day'), int(r.query.get('slot', 0))
    with app.db() as c:
        taken = {x['seat'] for x in c.execute("select seat from bookings where room_id=? and day=? and slot=? and status in ('已预约','已签到')", (r.params['id'], day, slot))}
    return sorted(taken)

@app.route('POST', '/api/bookings')
def book(r):
    u = app.user(r); b = r.body
    day, slot, room, seat = b.get('day'), int(b.get('slot', -1)), int(b.get('roomId', 0)), b.get('seat', '')
    if slot not in range(len(SLOTS)): raise HttpError(400, '时段不正确')
    with app.db() as c:
        rm = c.execute('select * from rooms where id=?', (room,)).fetchone()
        try: rr, cc = map(int, seat.split('-'))
        except ValueError: raise HttpError(400, '座位不正确')
        if not rm or not (1 <= rr <= rm['rows'] and 1 <= cc <= rm['cols']): raise HttpError(400, '座位不存在')
        if is_pro():
            cr = c.execute('select credit from users where id=?', (u['id'],)).fetchone()[0]
            if cr < 60: raise HttpError(403, f'信用分 {cr} 低于 60，暂停预约')
        if c.execute("select 1 from bookings where user_id=? and day=? and slot=? and status in ('已预约','已签到')", (u['id'], day, slot)).fetchone(): raise HttpError(400, '该时段你已有预约')
        if c.execute("select 1 from bookings where room_id=? and seat=? and day=? and slot=? and status in ('已预约','已签到')", (room, seat, day, slot)).fetchone(): raise HttpError(400, '该座位已被预约')
        c.execute('insert into bookings(user_id,room_id,seat,day,slot,status,created_at) values(?,?,?,?,?,?,?)', (u['id'], room, seat, day, slot, '已预约', int(time.time())))
    return True

@app.route('GET', '/api/bookings')
def mine(r):
    u = app.user(r)
    with app.db() as c:
        return [dict(x) | {'slotText': SLOTS[x['slot']]} for x in c.execute('select b.*, r.name room from bookings b join rooms r on r.id=b.room_id where user_id=? order by b.id desc', (u['id'],))]

def act(r, frm, to):
    u = app.user(r)
    with app.db() as c:
        b = c.execute('select * from bookings where id=? and user_id=?', (r.params['id'], u['id'])).fetchone()
        if not b or b['status'] not in frm: raise HttpError(400, '当前状态不可操作')
        c.execute('update bookings set status=? where id=?', (to, b['id']))
    return True

@app.route('POST', '/api/bookings/:id/checkin')
def checkin(r): return act(r, ('已预约',), '已签到')

@app.route('POST', '/api/bookings/:id/cancel')
def cancel(r): return act(r, ('已预约',), '已取消')

# ---------- 付费高级版 ----------
@app.route('GET', '/api/me')
def me(r):
    u = app.user(r)
    with app.db() as c:
        return {'credit': c.execute('select credit from users where id=?', (u['id'],)).fetchone()[0] if is_pro() else None}

@app.route('POST', '/api/bookings/:id/noshow')
def noshow(r):
    """演示“未签到违约”：真实系统应由定时任务在时段开始 30 分钟后自动处理"""
    need_pro('违约扣分'); u = app.user(r)
    act(r, ('已预约',), '违约')
    with app.db() as c: c.execute('update users set credit=credit-10 where id=?', (u['id'],))
    return True

@app.route('GET', '/api/rooms/:id/heat')
def heat(r):
    need_pro('座位热力图')
    with app.db() as c:
        return {x['seat']: x['n'] for x in c.execute("select seat, count(*) n from bookings where room_id=? and status!='已取消' group by seat", (r.params['id'],))}

if __name__ == '__main__':
    init(); app.run(int(os.environ.get('PORT', 8002)))
