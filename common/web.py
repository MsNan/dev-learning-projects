"""极简 Web 框架（仅用 Python 标准库），三个学习项目共用。
功能：路由、JSON 读写、静态文件、Token 登录、免费版/付费版开关、打赏接口。"""
import json, os, re, hmac, hashlib, secrets, sqlite3, time, mimetypes
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EDITION = 'pro' if os.environ.get('EDITION', 'free').lower() == 'pro' else 'free'

def is_pro():
    return EDITION == 'pro'

class HttpError(Exception):
    def __init__(self, status, msg):
        self.status, self.msg = status, msg

def need_pro(name='该功能'):
    if not is_pro():
        raise HttpError(402, f'{name}属于付费高级版，设置 EDITION=pro 后可体验')

class App:
    def __init__(self, name, static_dir, db_path):
        self.name, self.static_dir, self.routes = name, static_dir, []
        self.db_path = db_path
        self.sessions = {}
        self.route('GET', '/api/edition')(lambda r: {'edition': EDITION})
        self.route('GET', '/api/rewards')(self._rewards)
        self.route('POST', '/api/rewards')(self._reward_add)

    def db(self):
        c = sqlite3.connect(self.db_path); c.row_factory = sqlite3.Row
        return c

    def init_rewards(self, c):
        c.execute('create table if not exists rewards(id integer primary key, channel text, amount real, nickname text, message text, created_at integer)')

    def _rewards(self, r):
        with self.db() as c:
            return [dict(x) for x in c.execute('select * from rewards order by id desc limit 50')]

    def _reward_add(self, r):
        b = r.body
        if b.get('channel') not in ('微信', '支付宝'): raise HttpError(400, '请选择渠道')
        try: amt = round(float(b.get('amount', 0)), 2)
        except ValueError: raise HttpError(400, '金额不正确')
        if not 0 < amt <= 10000: raise HttpError(400, '金额不正确')
        with self.db() as c:
            c.execute('insert into rewards(channel,amount,nickname,message,created_at) values(?,?,?,?,?)',
                      (b['channel'], amt, str(b.get('nickname') or '匿名')[:20], str(b.get('message') or '')[:200], int(time.time())))
        return True

    def route(self, method, pattern):
        rx = re.compile('^' + re.sub(r':(\w+)', r'(?P<\1>[^/]+)', pattern) + '$')
        def deco(fn):
            self.routes.append((method, rx, fn)); return fn
        return deco

    # 简单 token 会话（内存）
    def login(self, user):
        t = secrets.token_hex(16); self.sessions[t] = user; return t

    def user(self, r, role=None):
        u = self.sessions.get((r.headers.get('Authorization') or '').replace('Bearer ', ''))
        if not u: raise HttpError(401, '请先登录')
        if role and u.get('role') != role: raise HttpError(403, '没有权限')
        return u

    def run(self, port):
        app = self
        class H(BaseHTTPRequestHandler):
            def log_message(self, *a): pass
            def _send(self, status, body, ctype='application/json; charset=utf-8', extra=None):
                data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
                self.send_response(status); self.send_header('Content-Type', ctype); self.send_header('Content-Length', str(len(data)))
                for k, v in (extra or {}).items(): self.send_header(k, v)
                self.end_headers(); self.wfile.write(data)
            def _handle(self, method):
                u = urlparse(self.path); self.query = {k: v[0] for k, v in parse_qs(u.query).items()}
                if u.path.startswith('/api/'):
                    n = int(self.headers.get('Content-Length') or 0)
                    try: self.body = json.loads(self.rfile.read(n) or b'{}') if n else {}
                    except ValueError: return self._send(400, {'code': 400, 'message': 'JSON 格式错误'})
                    for m, rx, fn in app.routes:
                        mt = rx.match(u.path)
                        if m == method and mt:
                            self.params = mt.groupdict()
                            try:
                                res = fn(self)
                                if isinstance(res, tuple) and res[0] == 'file':  # ('file', bytes, ctype, filename)
                                    return self._send(200, res[1], res[2], {'Content-Disposition': f'attachment; filename={res[3]}'})
                                return self._send(200, {'code': 0, 'data': res})
                            except HttpError as e:
                                return self._send(e.status, {'code': e.status, 'message': e.msg})
                    return self._send(404, {'code': 404, 'message': '接口不存在'})
                # 静态文件
                p = u.path
                if p.startswith('/common/'): base, p = os.path.join(ROOT, 'static-common'), p[len('/common/'):]
                else: base, p = app.static_dir, (p.lstrip('/') or 'index.html')
                f = os.path.realpath(os.path.join(base, p))
                if not f.startswith(os.path.realpath(base)) or not os.path.isfile(f): return self._send(404, b'Not Found', 'text/plain')
                with open(f, 'rb') as fh: self._send(200, fh.read(), (mimetypes.guess_type(f)[0] or 'application/octet-stream') + ('; charset=utf-8' if f.endswith(('.html', '.js', '.css')) else ''))
            def do_GET(self): self._handle('GET')
            def do_POST(self): self._handle('POST')
            def do_PUT(self): self._handle('PUT')
            def do_DELETE(self): self._handle('DELETE')
        print(f'{app.name} [{EDITION}] → http://localhost:{port}')
        ThreadingHTTPServer(('0.0.0.0', port), H).serve_forever()

def hash_pw(pw, salt=None):
    salt = salt or secrets.token_hex(8)
    return salt + '$' + hashlib.pbkdf2_hmac('sha256', pw.encode(), salt.encode(), 100_000).hex()

def check_pw(pw, stored):
    salt = stored.split('$')[0]
    return hmac.compare_digest(hash_pw(pw, salt), stored)

def csv_bytes(rows):
    import csv, io
    s = io.StringIO(); csv.writer(s).writerows(rows); return ('\ufeff' + s.getvalue()).encode()
