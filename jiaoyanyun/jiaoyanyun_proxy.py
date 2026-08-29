# -*- coding: utf-8 -*-
"""
教研云同步代理（教研管理平台 Demo 用，零依赖：仅标准库 + 可选 playwright）
=========================================================================
职责：
  1. 暴露本地 HTTP 接口给 Demo 前端调用（解决 CORS + 教研云鉴权 + IP 白名单问题）
  2. /api/filters  返回教研云权威筛选 schema（静态，覆盖全部筛选条件）
  3. /api/search   按筛选条件检索题目
       - live 模式：接管本机已登录 Chrome(CDP) 调教研云 question/page+detailByIds
       - offline 模式：用 jiaoyanyun_export/questions.json 内存筛选（无 Chrome 也可用）
  4. /api/bank     返回本地题库
  5. /api/bank/add 把题目并入本地题库（按 positionCode 去重，已存在则替换）

运行（与本机 Chrome 同机）：
  python jiaoyanyun_proxy.py            # 默认 127.0.0.1:8787
  python jiaoyanyun_proxy.py --port 8787 --cdp http://127.0.0.1:9222

前端调用：fetch('http://127.0.0.1:8787/api/...')
合规：仅同步授权账号可见资源；内置限流；勿商用转发。
"""
import argparse, json, os, re, sys, time, uuid, urllib.parse, urllib.request, ssl
from http.server import BaseHTTPRequestHandler, HTTPServer

BASE = os.path.dirname(os.path.abspath(__file__))
CACHE_Q = os.path.join(BASE, "jiaoyanyun_export", "questions.json")
BANK_Q = os.path.join(BASE, "demo", "local_bank.json")
FILTERS_JS = os.path.join(BASE, "demo", "jiaoyanyun_filters.js")
CDP_DEFAULT = "http://127.0.0.1:9222"

# 登录态持久化（保存到"服务器"=本代理同目录）
CRED_FILE = os.path.join(BASE, "jiaoyanyun_credentials.json")   # 账号密码（本机 localhost 工具，明文存盘，仅自建账号）
TOKEN_FILE = os.path.join(BASE, "jiaoyanyun_token.json")        # 捕获到的 Authorization 令牌（UUID）
LOGIN_URL = "https://login.jiaoyanyun.com/#/loginDlg?pageFrom=tiku"

# ---------------- 同步专用日志（独立于代理运行日志）----------------
SYNC_LOG_FILE = os.path.join(BASE, "logs", "jiaoyanyun_sync.log")

def sync_log(event, detail=""):
    """把同步动作写入独立日志 logs/jiaoyanyun_sync.log。event: search/add/login/capture/chrome 等。"""
    try:
        os.makedirs(os.path.dirname(SYNC_LOG_FILE), exist_ok=True)
        line = "%s [%s] %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), event, detail)
        with open(SYNC_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line.rstrip() + "\n")
    except Exception:
        pass

def read_sync_log(limit=100):
    try:
        if not os.path.exists(SYNC_LOG_FILE):
            return []
        with open(SYNC_LOG_FILE, "r", encoding="utf-8") as f:
            lines = [l.rstrip("\n") for l in f.readlines()]
        return lines[-limit:]
    except Exception:
        return []

def _chrome_manager():
    """懒加载 Chrome CDP 看护器（chrome_cdp_manager.py，跨平台启动/重启/看护）。"""
    try:
        import chrome_cdp_manager as m
        return m
    except Exception:
        return None

# ---------------- 筛选 schema（复用 demo/jiaoyanyun_filters.js 的同一份）----------------
def load_filters_schema():
    txt = open(FILTERS_JS, encoding="utf-8").read()
    m = re.search(r"window\.JIAOYANYUN_FILTERS\s*=\s*(.*);\s*$", txt, re.S)
    return json.loads(m.group(1))

# ---------------- 离线缓存题库 ----------------
def load_cache():
    if os.path.exists(CACHE_Q):
        return json.load(open(CACHE_Q, encoding="utf-8"))
    return []

# ---------------- 本地题库持久化 ----------------
def load_bank():
    if os.path.exists(BANK_Q):
        return json.load(open(BANK_Q, encoding="utf-8"))
    rj = os.path.join(BASE, "demo", "questions_data.js")
    if os.path.exists(rj):
        txt = open(rj, encoding="utf-8").read()
        m = re.search(r"window\.REAL_QUESTIONS\s*=\s*(.*?);\n\nwindow\.REAL_PAPERS", txt, re.S)
        if m:
            return json.loads(m.group(1))
    return []

def save_bank(bank):
    json.dump(bank, open(BANK_Q, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

# ---------------- 登录态持久化（账号密码 + 捕获的令牌）----------------
def load_creds():
    if os.path.exists(CRED_FILE):
        try:
            return json.load(open(CRED_FILE, encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_creds(username, password):
    # 明文存盘（localhost 自用工具，仅用于本账号资源同步）；如需更强保护可改为系统钥匙串
    json.dump({"username": username, "password": password},
              open(CRED_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def load_token():
    if os.path.exists(TOKEN_FILE):
        try:
            return json.load(open(TOKEN_FILE, encoding="utf-8")).get("token")
        except Exception:
            return None
    return None

def save_token(tok, username=None):
    c = load_creds()
    json.dump({"token": tok, "username": username or c.get("username"),
               "captured_at": time.strftime("%Y-%m-%d %H:%M:%S")},
              open(TOKEN_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def cdp_reachable(url=CDP_DEFAULT, timeout=3):
    # localhost 探测需绕过可能的 HTTP_PROXY（curl 走 no_proxy，urllib 默认会代理 localhost 导致误判）
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for _ in range(2):
        try:
            with opener.open(url + "/json/version", timeout=timeout) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.3)
    return False

def capture_token_cdp(force_refresh=True):
    """经 CDP 从本机已登录 Chrome 读取 Authorization 令牌并持久化。返回令牌或 None。
    force_refresh=True 时强制重新导航 xbresource 页面并读取最新令牌（自愈过期令牌）；
    否则仅用已连接 syncer 的当前 auth（可能为 stale）。
    """
    if not ensure_live(CDP_DEFAULT):
        return None
    s = _live["syncer"]
    if force_refresh:
        # 重新导航到已登录页面并读取最新 window.$CKEDITOR_TOKEN（令牌可能已过期需刷新）
        try:
            s.pg.goto("https://xbresource.jiaoyanyun.com/#/boutique?sid=2&gid=2",
                      wait_until="domcontentloaded", timeout=30000)
            s.pg.wait_for_timeout(1800)
            tok = s.pg.evaluate("""() => {
              const uuid = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/;
              if (window.$CKEDITOR_TOKEN && uuid.test(window.$CKEDITOR_TOKEN)) return window.$CKEDITOR_TOKEN;
              try { if (localStorage.getItem('token') && uuid.test(localStorage.getItem('token'))) return localStorage.getItem('token'); } catch(e){}
              for (const st of [localStorage, sessionStorage]) {
                try { for (let i=0;i<st.length;i++){ const v=st.getItem(st.key(i)); if(v&&uuid.test(v)) return v; } } catch(e){}
              }
              return null;
            }""")
            if tok:
                s.auth = tok
                save_token(tok, load_creds().get("username"))
                return tok
        except Exception as e:
            sys.stderr.write("[capture] 重新读取失败: %s\n" % e)
        # 退化：用已存令牌
        tok = load_token()
        if tok:
            s.auth = tok
        return tok
    tok = s.auth or load_token()
    if tok:
        save_token(tok, load_creds().get("username"))
    return tok

def prefill_login_cdp(username, password):
    """在本机 Chrome 打开教研云登录页并自动填好账号密码（滑块仍需人工过）。返回 (ok, msg)。"""
    if not ensure_live(CDP_DEFAULT):
        return False, "本机 Chrome 未连接（请先以 --remote-debugging-port=9222 启动已登录的 Chrome）"
    try:
        ctx = _live["syncer"].ctx
        pg = ctx.new_page()
        pg.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
        pg.wait_for_timeout(2500)
        # 默认是微信扫码页：切到「手机登录」表单
        pg.evaluate("""()=>{ function c(t){const e=Array.from(document.querySelectorAll('button,a,span,div,li')).find(x=>x.innerText&&x.innerText.trim()===t); if(e){e.click();return true;} return false;} c('其他登录方式'); c('手机登录'); }""")
        pg.wait_for_timeout(2000)
        fill_js = """(args)=>{
          const [u,p]=args;
          function set(el,val){ if(!el) return false;
            try{ const proto=Object.getPrototypeOf(el);
              const d=Object.getOwnPropertyDescriptor(proto,'value')||Object.getOwnPropertyDescriptor(el,'value');
              if(d&&d.set){ d.set.call(el,val);} else { el.value=val; }
            }catch(e){ el.value=val; }
            el.dispatchEvent(new Event('input',{bubbles:true}));
            el.dispatchEvent(new Event('change',{bubbles:true}));
            try{ el.focus(); el.blur(); }catch(e){}
            return true; }
          function findUser(doc){ const ins=Array.from(doc.querySelectorAll('input'));
            let e=ins.find(i=>i.type==='text'||i.type==='tel'||i.type==='email'||i.type==='number'||i.type==='phone');
            if(!e) e=ins.find(i=>!i.type||i.type==='text');
            if(!e) e=ins.find(i=>i.type!=='password'&&i.type!=='hidden'&&i.type!=='checkbox'&&i.type!=='radio');
            return e; }
          function findPass(doc){ return doc.querySelector('input[type="password"]'); }
          function tryDoc(doc){ if(!doc) return null; const ue=findUser(doc), pe=findPass(doc);
            if(ue||pe){ set(ue,u); set(pe,p); return {u:!!ue,p:!!pe}; } return null; }
          let r=tryDoc(document);
          if(!r){ for(const f of document.querySelectorAll('iframe')){ try{ r=tryDoc(f.contentDocument); }catch(e){} if(r) break; } }
          return r || {u:false,p:false};
        }"""
        res = pg.evaluate(fill_js, [username, password])
        filled = res.get("u") and res.get("p")
        note = "已填好账号密码" if filled else "已打开登录页（自动填表未命中，请手填或确认在手机登录表单）"
        return True, "已在本机 Chrome 打开教研云登录页并%s（%s）。请在浏览器完成滑块验证，然后点「捕获登录态」。" % (note, json.dumps(res, ensure_ascii=False))
    except Exception as e:
        return False, "打开登录页失败: %s（可手动在 Chrome 登录教研云后点「捕获登录态」）" % e

# 题型 id -> 本系统 type（用于离线筛选匹配 writtenType 名称）
NAME_TO_TYPE = {"单选": "single_choice", "填空": "fill_blank", "解答题": "essay",
                "操作与探究": "essay", "作图题": "essay", "判断题": "judge",
                "多选": "multi_choice", "连线": "essay", "排序": "essay"}

def _norm(s):
    return re.sub(r"\s+", "", s or "")

def offline_filter(items, f):
    """内存筛选（离线模式）。"""
    SCH = load_filters_schema()
    want_type = set(f.get("writtenQuesType") or [])
    want_diff = set(str(x) for x in (f.get("difficulty") or []))
    want_kp = f.get("knowledge") or []
    kw = (f.get("keyword") or "").strip()
    flags = f.get("quality") or {}
    out = []
    for q in items:
        if want_type:
            wt = q.get("writtenType") or ""
            hit = any((t["id"] in want_type and NAME_TO_TYPE.get(t["name"]) and t["name"] in wt)
                      for t in SCH["writtenQuesTypes"])
            if not hit:
                continue
        if want_diff:
            d = q.get("difficulty")
            if str(d) not in want_diff:
                continue
        if want_kp:
            kps = " ".join(q.get("knowledgePoints") or [])
            if not any(kp in kps for kp in want_kp):
                continue
        if kw:
            hay = (q.get("stem") or "") + " " + (q.get("code") or "")
            if kw not in hay:
                continue
        if flags.get("hasImage"):
            if not re.search(r"<img|images/|tiku-pro-cdn", q.get("stem") or ""):
                continue
        if flags.get("isHaveAnalysis"):
            if not (q.get("analysis") or "").strip():
                continue
        if flags.get("isSubjective"):
            if q.get("type") in ("single_choice", "multi_choice", "judge", "fill_blank"):
                continue
        out.append(q)
    return out

# ---------------- Live 模式（CDP 接管本机 Chrome）----------------
_live = {"syncer": None, "ok": False}
def _close_live():
    """关闭已连接的 syncer（停止 playwright 的 asyncio 循环），避免重复连接时报
    'Sync API inside the asyncio loop'。"""
    s = _live.get("syncer")
    if s is not None:
        try:
            s.close()
        except Exception:
            pass
    _live["syncer"] = None
    _live["ok"] = False
def ensure_live(cdp_url):
    if _live["syncer"] is not None:
        s = _live["syncer"]
        # 校验连接仍有效（Chrome 可能被看护器重启/被关闭），失效则重连
        try:
            if s.pg is None or s.pg.is_closed():
                raise RuntimeError("page closed")
            s.pg.evaluate("() => 1")
            tok = load_token()
            if tok:
                s.auth = tok            # 复用已持久化的令牌
            _live["ok"] = True
            return True
        except Exception:
            _close_live()               # 连接失效，释放后走下面重连
    try:
        from jiaoyanyun_sync import JiaoyanyunSyncer
        s = JiaoyanyunSyncer(cdp_url, os.path.join(BASE, "jiaoyanyun_export"), rate=0.3)
        s.connect()
        saved = load_token()
        if saved:
            s.auth = saved            # 有令牌则跳过导航直接复用
        else:
            s.ensure_auth()
        if s.auth and s.auth != saved:
            save_token(s.auth, load_creds().get("username"))
        _live["syncer"] = s
        _live["ok"] = True
        return True
    except Exception as e:
        sys.stderr.write("[live] 不可用: %s\n" % e)
        _live["ok"] = False
        return False

def live_search(f, sid, gid, subjectName, gradeGroupName, pageSize, pageNo):
    s = _live["syncer"]
    SCH = load_filters_schema()
    body_filters = {}
    if f.get("writtenQuesType"):
        wqt = [t for t in SCH["writtenQuesTypes"] if t["id"] in f["writtenQuesType"]]
        body_filters["writtenQuesType"] = [{"name": t["name"], "id": t["id"], "code": "writtenQuesType"} for t in wqt]
        body_filters["writtenQuesTypeIdList"] = f["writtenQuesType"]
    if f.get("difficulty"):
        diffs = [t for t in SCH["difficulties"] if t["id"] in f["difficulty"]]
        body_filters["difficulty"] = [{"name": t["name"], "id": t["id"], "code": "difficulty"} for t in diffs]
        body_filters["difficultyIdList"] = f["difficulty"]
    qi = {}
    if f.get("examType"):
        qi["examTypeIdList"] = f["examType"]
    if f.get("cup"):
        qi["cupIdList"] = f["cup"]
    if f.get("province"):
        qi["provinceIdList"] = f["province"]
    if qi:
        body_filters["qi"] = qi
    if f.get("schoolYear"):
        body_filters["schoolYearIdList"] = f["schoolYear"]
    if f.get("semester"):
        body_filters["semesterIdList"] = f["semester"]
    if f.get("grade"):
        body_filters["gradeIdList"] = f["grade"]
    mf = []
    if f.get("bookSeries"):
        mf.append(f["bookSeries"])
    if f.get("bookVolume"):
        mf.append(f["bookVolume"])
    if f.get("knowledge"):
        for k in f["knowledge"]:
            mf.append(k)
    if mf:
        body_filters["matchField"] = mf
    for k in ("isLast", "isAccCheck", "isFrequency", "isHaveAnalysis", "queryJfLabel", "isSubjective", "hasImage"):
        if f.get("quality", {}).get(k):
            body_filters[k] = 1
    extra = {"subjectName": subjectName, "gradeGroupName": gradeGroupName, "filters": body_filters}
    # 教研云 question/page 接口每页硬上限 10 条：pageSize>10 时循环翻页聚合，凑满 pageSize
    REAL_PAGE = 10
    if pageSize <= REAL_PAGE:
        pages = [(pageNo, pageSize)]
    else:
        start_global = (pageNo - 1) * pageSize          # 全局起始偏移
        first_real = start_global // REAL_PAGE + 1      # 教研云页码
        pages = []
        for i in range(first_real, first_real + max(1, -(-pageSize // REAL_PAGE))):
            pages.append((i, REAL_PAGE))
    raw_all, seen_ids, total = [], set(), 0
    for p_no, p_size in pages:
        obj = s.fetch_page(sid, gid, page_no=p_no, page_size=p_size, extra=extra)
        data = (obj.get("data") or {})
        rows = data.get("data") or []
        if not rows:
            break
        total = data.get("total") or total or len(rows)
        for q in rows:
            qid = q.get("queId")
            if qid and qid in seen_ids:
                continue
            if qid:
                seen_ids.add(qid)
            raw_all.append(q)
            if len(raw_all) >= pageSize:
                break
        if len(raw_all) >= pageSize:
            break
    ids = [q["queId"] for q in raw_all if q.get("queId")]
    details = s.fetch_details(ids) if ids else []
    from jiaoyanyun_sync import normalize
    code = "MAT" if subjectName == "数学" else subjectName[:3].upper()
    # 图片下载到 demo/images/（与 docx 导入一致），使题目 stem 里相对路径 images/xxx.png 能被 Demo 静态服务正确解析
    norm = [normalize(d, os.path.join(BASE, "demo"), i + 1,
                    subject_code=code, grade_code="G7") for i, d in enumerate(details)]
    return norm, total

def live_search_all(f, sid, gid, subjectName, gradeGroupName, max_n=200, page_size=10):
    """分页拉取教研云筛选结果（最多 max_n 道），归一化后一次性返回。用于"下载全部筛选结果"。"""
    all_items, seen = [], set()
    page_no = 1
    while len(all_items) < max_n:
        items, total = live_search(f, sid, gid, subjectName, gradeGroupName, page_size, page_no)
        if not items:
            break
        for q in items:
            k = q.get("queId") or q.get("positionCode")
            if k and k not in seen:
                seen.add(k); all_items.append(q)
        if len(items) < page_size or len(all_items) >= max_n:
            break
        page_no += 1
    return all_items[:max_n], len(all_items)

# ---------------- 限流（内存滑动窗口，满足"内置限流"声明 + 保护教研云）----------------
_RATE = {}
def rate_ok(path, limit=6, window=1.0):
    now = time.time()
    ts = _RATE.setdefault(path, [])
    ts[:] = [x for x in ts if now - x < window]
    if len(ts) >= limit:
        return False
    ts.append(now)
    return True

# ---------------- HTTP 处理 ----------------
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
    def _json(self, obj, code=200):
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(obj, ensure_ascii=False).encode("utf-8"))
    def do_OPTIONS(self):
        self.send_response(204); self._cors(); self.end_headers()
    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        p = u.path
        q = urllib.parse.parse_qs(u.query)
        gv = lambda k: q.get(k, [""])[0]
        gvl = lambda k: [x for x in q.get(k, [""])[0].split(",") if x]
        if p == "/api/mode":
            reach = cdp_reachable()
            return self._json({"mode": "live" if reach else "offline", "chrome_reachable": reach})
        if p == "/api/auth":
            tok = load_token()
            creds = load_creds()
            reach = cdp_reachable()
            return self._json({"authed": bool(tok), "method": "token" if tok else "none",
                               "username": creds.get("username"), "hasCdp": reach,
                               "mode": "live" if reach else "offline"})
        if p == "/api/filters":
            return self._json(load_filters_schema())
        if p == "/api/subjects":
            # 动态学段→学科映射（权威：basic/querySubGgList）
            if not ensure_live(CDP_DEFAULT):
                sch = load_filters_schema()
                return self._json({"ok": False, "mode": "offline", "grade_groups": sch.get("grade_groups", []),
                                   "subjects_by_group": sch.get("subjects_by_group", {})})
            try:
                obj = _live["syncer"].call_api("/v1/basic/querySubGgList", {})
                data = obj.get("data") or []
                groups, subs = [], {}
                for g in data:
                    gname = g.get("ggName") or g.get("name") or ""
                    gid = str(g.get("ggId") or g.get("id") or "")
                    groups.append({"id": gid, "name": gname})
                    subs[gname] = [s.get("subName") or s.get("name") for s in (g.get("subjectList") or g.get("list") or [])]
                return self._json({"ok": True, "mode": "live", "grade_groups": groups, "subjects_by_group": subs})
            except Exception as e:
                sys.stderr.write("[subjects fail] %s\n" % e)
                sch = load_filters_schema()
                return self._json({"ok": False, "mode": "fallback", "grade_groups": sch.get("grade_groups", []),
                                   "subjects_by_group": sch.get("subjects_by_group", {})})
        if p == "/api/books":
            # 动态教材版本（权威：label/queryTabList，按 学段+学科 联动）
            sid = gv("subjectId") or "2"; gid = gv("gradeGroupId") or "2"
            subjName = gv("subjectName") or "数学"; ggName = gv("gradeGroupName") or "初中"
            if not ensure_live(CDP_DEFAULT):
                sch = load_filters_schema()
                return self._json({"ok": False, "mode": "offline", "books": [{"name": b, "childList": []} for b in sch.get("bookSeries", [])]})
            try:
                obj = _live["syncer"].call_api("/v1/label/queryTabList", {
                    "subjectId": str(sid), "gradeGroupId": str(gid),
                    "subjectName": subjName, "gradeGroupName": ggName,
                })
                data = obj.get("data") or []
                books = []
                for g in data:
                    if g.get("name") != "教材":
                        continue
                    for b in (g.get("data") or []):
                        books.append({"name": b.get("name"),
                                      "id": b.get("id"),
                                      "childList": [{"name": c.get("name"), "id": c.get("id")} for c in (b.get("childList") or [])]})
                return self._json({"ok": True, "mode": "live", "books": books})
            except Exception as e:
                sys.stderr.write("[books fail] %s\n" % e)
                sch = load_filters_schema()
                return self._json({"ok": False, "mode": "fallback", "books": [{"name": b, "childList": []} for b in sch.get("bookSeries", [])]})
        if p == "/api/grade-options":
            # 动态年级（权威：question/searchOptions，按 学段+学科 联动）
            sid = gv("subjectId") or "2"; gid = gv("gradeGroupId") or "2"
            subjName = gv("subjectName") or "数学"; ggName = gv("gradeGroupName") or "初中"
            try:
                obj = _live["syncer"].call_api("/v1/question/searchOptions", {
                    "resourcePrefix": "JP", "subjectId": str(sid), "gradeGroupId": str(gid),
                    "subjectName": subjName, "gradeGroupName": ggName,
                })
                data = obj.get("data") or []
                grades = []
                for g in data:
                    if g.get("code") != "grade":
                        continue
                    grades = [{"id": str(x.get("id")), "name": x.get("name")} for x in (g.get("data") or [])]
                return self._json({"ok": True, "mode": "live", "grades": grades})
            except Exception as e:
                sys.stderr.write("[grade-options fail] %s\n" % e)
                sch = load_filters_schema()
                return self._json({"ok": False, "mode": "fallback", "grades": sch.get("grades", [])})
        if p == "/api/knowledge-tree":
            # 动态知识点树（权威：label/queryCatalogueKnowTree，按 教材册 csId+学段+学科）
            csId = gv("csId"); sid = gv("subjectId") or "2"; gid = gv("gradeGroupId") or "2"
            subjName = gv("subjectName") or "数学"; ggName = gv("gradeGroupName") or "初中"
            if not csId:
                return self._json({"ok": False, "message": "缺少 csId（教材册 id）"}, 400)
            try:
                obj = _live["syncer"].call_api("/v1/label/queryCatalogueKnowTree", {
                    "csId": str(csId), "subjectId": str(sid), "gradeGroupId": str(gid),
                    "subjectName": subjName, "gradeGroupName": ggName,
                })
                data = obj.get("data") or []
                return self._json({"ok": True, "mode": "live", "tree": data})
            except Exception as e:
                sys.stderr.write("[knowledge-tree fail] %s\n" % e)
                return self._json({"ok": False, "mode": "fallback", "tree": []})
        if p == "/api/bank":
            bank = load_bank()
            return self._json({"total": len(bank), "questions": bank})
        if p == "/api/search":
            if not rate_ok("/api/search", limit=6, window=1.0):
                return self._json({"error": "请求过于频繁，请稍后再试", "code": 429}, 429)
            f = {
                "writtenQuesType": gvl("writtenQuesTypeId"),
                "difficulty": gvl("difficultyId"),
                "examType": gvl("examTypeId"),
                "cup": gvl("cupId"),
                "province": gvl("provinceId"),
                "schoolYear": gvl("schoolYearId"),
                "semester": gvl("semesterId"),
                "grade": gvl("gradeId"),
                "bookSeries": gv("bookSeries"),
                "bookVolume": gv("bookVolume"),
                "knowledge": gvl("knowledge"),
                "keyword": gv("keyword"),
                "quality": {k: 1 for k in ("isLast", "isAccCheck", "isFrequency", "isHaveAnalysis",
                                           "queryJfLabel", "isSubjective", "hasImage") if gv(k) in ("1", "true")},
            }
            sid = int(gv("subjectId") or 2); gid = int(gv("gradeGroupId") or 2)
            subjectName = gv("subjectName") or "数学"; gradeGroupName = gv("gradeGroupName") or "初中"
            pageSize = int(gv("pageSize") or 20); pageNo = int(gv("pageNo") or 1)
            if ensure_live(CDP_DEFAULT):
                try:
                    items, total = live_search(f, sid, gid, subjectName, gradeGroupName, pageSize, pageNo)
                    sync_log("search", "mode=live sid=%s gid=%s page=%d size=%d total=%d" % (sid, gid, pageNo, pageSize, total))
                    return self._json({"mode": "live", "total": total, "page": pageNo,
                                       "pageSize": pageSize, "questions": items})
                except Exception as e:
                    sys.stderr.write("[live search fail] %s\n" % e)
                    # 令牌可能过期：尝试重新捕获一次再重试
                    if cdp_reachable():
                        try:
                            capture_token_cdp()
                            items, total = live_search(f, sid, gid, subjectName, gradeGroupName, pageSize, pageNo)
                            return self._json({"mode": "live", "total": total, "page": pageNo,
                                               "pageSize": pageSize, "questions": items})
                        except Exception as e2:
                            sys.stderr.write("[live retry fail] %s\n" % e2)
            items = offline_filter(load_cache(), f)
            start = (pageNo - 1) * pageSize
            sync_log("search", "mode=offline sid=%s gid=%s page=%d size=%d total=%d" % (sid, gid, pageNo, pageSize, len(items)))
            return self._json({"mode": "offline", "total": len(items), "page": pageNo,
                               "pageSize": pageSize, "questions": items[start:start + pageSize]})
            return self._json({"error": "not found"}, 404)
        if p == "/api/search/all":
            if not rate_ok("/api/search/all", limit=2, window=3.0):
                return self._json({"error": "批量下载过于频繁，请稍后再试", "code": 429}, 429)
            f = {
                "writtenQuesType": gvl("writtenQuesTypeId"),
                "difficulty": gvl("difficultyId"),
                "examType": gvl("examTypeId"),
                "cup": gvl("cupId"),
                "province": gvl("provinceId"),
                "schoolYear": gvl("schoolYearId"),
                "semester": gvl("semesterId"),
                "grade": gvl("gradeId"),
                "bookSeries": gv("bookSeries"),
                "bookVolume": gv("bookVolume"),
                "knowledge": gvl("knowledge"),
                "keyword": gv("keyword"),
                "quality": {k: 1 for k in ("isLast", "isAccCheck", "isFrequency", "isHaveAnalysis",
                                           "queryJfLabel", "isSubjective", "hasImage") if gv(k) in ("1", "true")},
            }
            sid = int(gv("subjectId") or 2); gid = int(gv("gradeGroupId") or 2)
            subjectName = gv("subjectName") or "数学"; gradeGroupName = gv("gradeGroupName") or "初中"
            max_n = max(1, min(int(gv("max") or 200), 5000))
            if ensure_live(CDP_DEFAULT):
                try:
                    items, got = live_search_all(f, sid, gid, subjectName, gradeGroupName, max_n=max_n)
                    return self._json({"mode": "live", "max": max_n, "fetched": len(items),
                                       "questions": items})
                except Exception as e:
                    sys.stderr.write("[live search/all fail] %s\n" % e)
                    if cdp_reachable():
                        try:
                            capture_token_cdp()
                            items, got = live_search_all(f, sid, gid, subjectName, gradeGroupName, max_n=max_n)
                            return self._json({"mode": "live", "max": max_n, "fetched": len(items),
                                               "questions": items})
                        except Exception as e2:
                            sys.stderr.write("[live search/all retry fail] %s\n" % e2)
            return self._json({"mode": "offline", "fetched": 0, "questions": [],
                               "message": "本机 Chrome 未连接或登录态失效，无法批量拉取实时题"}, 200)
        if p == "/api/sync-logs":
            limit = max(1, min(int(gv("limit") or 100), 1000))
            return self._json({"logs": read_sync_log(limit)})
        return self._json({"error": "not found"}, 404)
    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        if u.path == "/api/chrome/restart":
            m = _chrome_manager()
            if not m:
                sync_log("chrome", "restart 失败：chrome_cdp_manager 不可用")
                return self._json({"ok": False, "error": "chrome_cdp_manager 不可用"}, 500)
            sync_log("chrome", "用户触发重启 Chrome CDP")
            try:
                ok = m.restart()
            except Exception as e:
                sync_log("chrome", "restart 异常: %s" % e)
                return self._json({"ok": False, "error": "重启异常: %s" % e}, 500)
            time.sleep(1.5)
            alive = m.cdp_alive()
            sync_log("chrome", "重启后 cdp_reachable=%s" % alive)
            return self._json({"ok": ok, "cdp_reachable": alive})
        if u.path == "/api/chrome/start":
            m = _chrome_manager()
            if not m:
                return self._json({"ok": False, "error": "chrome_cdp_manager 不可用"}, 500)
            try:
                ok = m.start()
            except Exception as e:
                return self._json({"ok": False, "error": "启动异常: %s" % e}, 500)
            time.sleep(1.5)
            return self._json({"ok": ok, "cdp_reachable": m.cdp_alive()})
        if u.path == "/api/bank/add":
            if not rate_ok("/api/bank/add", limit=10, window=1.0):
                return self._json({"error": "请求过于频繁，请稍后再试", "code": 429}, 429)
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            incoming = body.get("questions", [])
            bank = load_bank()
            def key_of(q):
                return q.get("queId") or q.get("positionCode") or q.get("code")
            by_key = {}
            for i, q in enumerate(bank):
                by_key[key_of(q) or ("_i%d" % i)] = i
            added = updated = 0
            for q in incoming:
                # 补齐身份字段，保证题库种子(REAL_QUESTIONS)与同步题同一键空间
                q["positionCode"] = q.get("positionCode") or q.get("code") or q.get("queId")
                q["code"] = q.get("code") or q.get("positionCode")
                q["id"] = q.get("id") or q.get("code") or q.get("queId")
                q.setdefault("source", "jiaoyanyun")
                key = key_of(q)
                if key in by_key:
                    bank[by_key[key]] = q          # 已存在 -> 直接替换
                    updated += 1
                else:
                    bank.append(q); added += 1
            save_bank(bank)
            sync_log("add", "added=%d updated=%d total=%d" % (added, updated, len(bank)))
            return self._json({"ok": True, "added": added, "updated": updated, "total": len(bank)})
        if u.path == "/api/login":
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            uname = (body.get("username") or "").strip()
            pwd = body.get("password") or ""
            if not uname:
                return self._json({"ok": False, "error": "用户名不能为空"}, 400)
            save_creds(uname, pwd)                      # 保存登录验证信息到服务器
            if cdp_reachable():
                ok, msg = prefill_login_cdp(uname, pwd)
                return self._json({"ok": True, "saved": True, "prefilled": ok,
                                   "needCaptcha": True, "message": msg})
            return self._json({"ok": True, "saved": True, "needBrowser": True,
                "message": "凭据已保存到服务器。本机 Chrome 未连接：请先以 --remote-debugging-port=9222 启动已登录的 Chrome，再在本页点「捕获登录态」。"})
        if u.path == "/api/auth/capture":
            tok = capture_token_cdp()
            if tok:
                sync_log("capture", "成功捕获登录态 tokenPrefix=%s" % tok[:8])
                return self._json({"ok": True, "authed": True,
                                   "tokenPrefix": tok[:8] + "...", "method": "captured"})
            sync_log("capture", "捕获失败")
            return self._json({"ok": False, "authed": False,
                "message": "未能捕获登录态：请确认本机 Chrome 已登录教研云（或先用账号密码登录并过滑块），再点「捕获登录态」。"}, 400)
        if u.path == "/api/logout":
            # 置空令牌文件（覆盖写比 os.remove 更稳，避免 Windows 文件锁导致删除失败）
            try:
                with open(TOKEN_FILE, "w", encoding="utf-8") as f:
                    json.dump({"token": None, "username": load_creds().get("username"),
                               "captured_at": None}, f)
            except Exception:
                pass
            _close_live()                   # 关闭 syncer（停 playwright 循环），下次检索需重新鉴权
            return self._json({"ok": True, "authed": False})
        return self._json({"error": "not found"}, 404)

def main():
    global CDP_DEFAULT
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--cdp", default=CDP_DEFAULT)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    CDP_DEFAULT = args.cdp
    print("教研云同步代理启动: http://%s:%d" % (args.host, args.port))
    print("离线缓存题: %d 道 | 本地题库: %d 道" % (len(load_cache()), len(load_bank())))
    try:
        HTTPServer((args.host, args.port), Handler).serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")

if __name__ == "__main__":
    main()
