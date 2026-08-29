# -*- coding: utf-8 -*-
"""
教研云精品题库 同步爬虫（生产级）
=================================
运行环境：本机（复用已登录的 Chrome，白名单 IP 才能访问 fz 数据网关）

原理：
  1. 通过 CDP 接管本机已登录的 Chrome（--remote-debugging-port=9222 --user-data-dir=副本）
  2. 从真实 XHR 请求头里动态抓取 Authorization(UUID) 令牌
  3. POST /xbresource-pub/v1/question/page 分页拉列表（data.data[] 为题目数组）
  4. 批量 POST /v1/question/detailByIds 取完整答案/解析/选项
  5. 转存 tiku-pro-cdn 图片到本地，提取 MathJax SVG 的 LaTeX
  6. 归一化为本系统题库模型（位置编码 + 题型 + 难度 + 知识点 + 来源）

用法：
  python jiaoyanyun_sync.py --cdp http://127.0.0.1:9222 --sid 2 --gid 2 --max 40 --out ./jiaoyanyun_export

合规：仅同步授权账号可见资源；内置限流；勿商用转发。
"""
import argparse, json, os, re, time, uuid, sys, urllib.request, ssl

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    raise ImportError("playwright 未安装，仅离线模式可用（pip install playwright）")

API_BASE = "https://app-pub.jiaoyanyun.com/xbresource-pub"
HEADERS_TEMPLATE = {
    "Content-Type": "application/json",
    "X-SCHOOL-ID": "1", "X-Client-Id": "501103", "X-Version-Num": "1",
    "X-APP-ID": "console", "X-Device-Id": "TAL1118F17683FD1D7AD12A0BC36C9A2C1B460C",
}
CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE


class JiaoyanyunSyncer:
    def __init__(self, cdp_url, out_dir, rate=0.25):
        self.cdp_url = cdp_url
        self.out_dir = out_dir
        self.rate = rate
        self.auth = None
        self.b = None
        self.ctx = None
        self.pg = None

    def connect(self):
        self.p = sync_playwright().start()
        self.b = self.p.chromium.connect_over_cdp(self.cdp_url)
        self.ctx = self.b.contexts[0]
        self.pg = self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()
        return self.pg

    def ensure_auth(self):
        """从已登录页面读取 Authorization 令牌（window.$CKEDITOR_TOKEN / localStorage），不依赖网络抓取"""
        if self.auth:
            return self.auth
        self.pg.goto("https://xbresource.jiaoyanyun.com/#/boutique?sid=2&gid=2",
                     wait_until="domcontentloaded", timeout=30000)
        self.pg.wait_for_timeout(2000)
        tok = self.pg.evaluate("""() => {
          const uuid = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/;
          if (window.$CKEDITOR_TOKEN && uuid.test(window.$CKEDITOR_TOKEN)) return window.$CKEDITOR_TOKEN;
          try { if (localStorage.getItem('token') && uuid.test(localStorage.getItem('token'))) return localStorage.getItem('token'); } catch(e){}
          for (const s of [localStorage, sessionStorage]) {
            try { for (let i=0;i<s.length;i++){ const v=s.getItem(s.key(i)); if(v&&uuid.test(v)) return v; } } catch(e){}
          }
          return null;
        }""")
        if not tok:
            raise RuntimeError("未能读取 Authorization 令牌，请确认 Chrome 已登录 jiaoyanyun")
        self.auth = tok
        return self.auth

    def call_api(self, path, body):
        self.ensure_auth()
        js = """async (a)=>{const [url,body,auth]=a;
          const r=await fetch(url,{method:'POST',credentials:'include',
            headers:Object.assign({'Content-Type':'application/json','Authorization':auth},__H__),
            body:JSON.stringify(body)});
          return {status:r.status, text:await r.text()};}"""
        # 注入固定头
        js = js.replace("__H__", json.dumps(HEADERS_TEMPLATE))
        url = API_BASE + path
        res = self.pg.evaluate(js, [url, body, self.auth])
        if res["status"] != 200:
            raise RuntimeError(f"{path} HTTP {res['status']}: {res['text'][:200]}")
        obj = json.loads(res["text"])
        if obj.get("code") not in (200, 20000, "200", "20000") and obj.get("msg") not in (None, "", "ok"):
            # code 可能是 200 或字符串，做容错
            if str(obj.get("code")) not in ("200", "20000"):
                print(f"  ⚠ {path} code={obj.get('code')} msg={obj.get('msg')}")
        time.sleep(self.rate)
        return obj

    def fetch_page(self, sid, gid, page_no, page_size=10, extra=None):
        body = {
            "sortOrderList": [{"order": 1, "name": "综合", "sortName": "comprehensive_score",
                                 "sortOrder": "desc", "functionPointCode": "SORT_ZongHePaiXu"}],
            "subjectId": str(sid), "gradeGroupId": str(gid),
            "matchField": [], "onlyCheck": "0",
            "subjectName": extra.get("subjectName", "") if extra else "",
            "gradeGroupName": extra.get("gradeGroupName", "") if extra else "",
            "pageSize": page_size, "pageNo": page_no,
            "labelType": "", "searchId": uuid.uuid4().hex,
        }
        if extra:
            body.update(extra.get("filters", {}))
        return self.call_api("/v1/question/page", body)

    def fetch_details(self, ids, batch=20):
        out = []
        for i in range(0, len(ids), batch):
            chunk = ids[i:i + batch]
            obj = self.call_api("/v1/question/detailByIds", {"idList": chunk})
            data = obj.get("data") or []
            out.extend(data if isinstance(data, list) else [data])
        return out

    def close(self):
        try:
            self.b.close()
        except Exception:
            pass
        try:
            self.p.stop()
        except Exception:
            pass


# ---------- 归一化 ----------
def extract_latex(html):
    """从 MathJax SVG 的 <title> 提取 LaTeX 列表"""
    if not html:
        return []
    if not isinstance(html, str):
        html = to_html(html)
    return re.findall(r'<title[^>]*>(.*?)</title>', html, re.S)


def download_image(url, out_dir):
    """下载 tiku-pro-cdn 图片到本地，返回相对路径；失败返回原 URL"""
    if not url or "tiku-pro-cdn" not in url:
        return url
    try:
        fn = re.sub(r'[^\w.-]', '_', url.split("?")[0].split("/")[-1]) or (uuid.uuid4().hex + ".png")
        dest = os.path.join(out_dir, "images", fn)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        req = urllib.request.Request(url, headers={"Referer": "https://xbresource.jiaoyanyun.com/",
                                                     "User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20, context=CTX) as r:
            with open(dest, "wb") as f:
                f.write(r.read())
        return "images/" + fn
    except Exception as e:
        return url  # 保留原 URL


def get_biz_type(q):
    """从 examOptionList 取业务题型(主)"""
    if not q.get("examOptionList"):
        return ""
    for opt in q["examOptionList"]:
        if opt.get("name") == "业务题型":
            for c in opt.get("childList", []):
                if c.get("isMain") == 1:
                    return c.get("name", "")
    return ""


def get_knowledge(q):
    """从 examOptionList 取知识点名称列表"""
    kps = []
    if q.get("examOptionList"):
        for opt in q["examOptionList"]:
            for c in opt.get("childList", []):
                for kl in (c.get("labelKnowList") or []):
                    n = kl.get("name")
                    if n and n not in kps:
                        kps.append(n)
    return kps


def _name_of(obj):
    """从 {id,name} 或裸字符串取名称"""
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        return obj.get("name") or obj.get("value") or ""
    return ""


def get_source(q):
    """从 questionSourceList 取来源(城市/区县/教材/年份/考试类型)，detail 响应为嵌套结构"""
    src = []
    for s in (q.get("questionSourceList") or []):
        if not isinstance(s, dict):
            continue
        for key in ("city", "area", "bookSeries", "examType", "abcStage", "year", "province"):
            v = _name_of(s.get(key))
            if v and v not in src:
                src.append(v)
        # 顶层 name/value 兜底
        for key in ("name", "value", "sourceName"):
            v = s.get(key)
            if v and v not in src:
                src.append(v)
    return src


def map_type(written_type):
    """教研云题型 -> 本系统题型枚举（detail 响应用无'题'后缀，需覆盖两种写法）"""
    if not written_type:
        return "essay"
    wt = written_type.replace("题", "")  # 填空/填空题 -> 填空
    m = {"选择": "single", "单选": "single", "多选": "multi", "判断": "judge",
         "填空": "fill", "解答": "essay", "计算": "essay", "证明": "essay", "应用": "essay",
         "实验": "experiment", "作文": "composition", "阅读": "reading"}
    return m.get(wt, "essay")


def to_html(v):
    """教研云字段可能是 字符串 / 嵌套列表([["<p>..</p>"]]) / 对象，统一拍平为 HTML 字符串。
    对象优先取 content/text/value 等正文字段，禁止 str(dict)（会产出 {…} 或 [object Object] 乱码）。"""
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, list):
        parts = []
        for sub in v:
            parts.append(to_html(sub))
        return "".join(parts)
    if isinstance(v, dict):
        for k in ("content", "text", "value", "html", "name"):
            if v.get(k):
                return to_html(v[k])
        return json.dumps(v, ensure_ascii=False)
    return str(v)


def _flatten(v):
    """把嵌套列表拍平一层(list of lists -> list)。教研云字段常是 [[...]] 结构"""
    out = []
    if isinstance(v, list):
        for x in v:
            if isinstance(x, list):
                out.extend(x)
            else:
                out.append(x)
    elif v is not None:
        out.append(v)
    return out


def parse_options(raw):
    """解析选择题选项。answerOptionList/optionList 形如 [[{aoVal,content},...]]"""
    src = raw.get("answerOptionList") or raw.get("optionList")
    opts = []
    if src:
        for o in _flatten(src):
            if isinstance(o, dict):
                opts.append({
                    "label": o.get("aoVal") or o.get("optionLabel") or o.get("label"),
                    "content": to_html(o.get("content") or o.get("optionContent")),
                })
    return opts


def download_images_in_html(html, out_dir):
    """把 HTML 里所有 tiku-pro-cdn 图片换成本地路径"""
    if not html:
        return ""
    if not isinstance(html, str):
        html = to_html(html)
    urls = re.findall(r'(https://[^\s"\']*?tiku-pro-cdn[^\s"\']*?)["\']', html)
    for u in set(urls):
        local = download_image(u, out_dir)
        if local != u:
            html = html.replace(u, local)
    return html


def normalize(raw, out_dir, idx, subject_code="MAT", grade_code="G7"):
    """教研云题目 -> 本系统题库模型(含位置编码)"""
    written = raw.get("writtenQuesTypeName") or raw.get("logicQuesTypeName") or "解答题"
    qtype = map_type(written)
    # 答案结构: answer 是嵌套列表 [["<p>..</p>"]]
    ans_raw = raw.get("answer") or raw.get("normalAnswer") or []
    # 展平为分步答案
    steps = []
    if isinstance(ans_raw, list):
        for sub in ans_raw:
            if isinstance(sub, list):
                steps.extend([x for x in sub if x])
            elif sub:
                steps.append(sub)
    # 选择题选项
    options = parse_options(raw)
    content_html = download_images_in_html(to_html(raw.get("content")), out_dir)
    analysis_html = download_images_in_html(to_html(raw.get("analysis")), out_dir)
    seq = f"{idx:04d}"
    pos_code = f"{subject_code}-{grade_code}-KP{qidx(raw):03d}-{seq}"
    return {
        "queId": raw.get("queId"),
        "positionCode": pos_code,
        "type": qtype,
        "writtenType": written,
        "bizType": get_biz_type(raw) or written,
        "subjectId": raw.get("subjectId"),
        "subjectName": raw.get("subjectName"),
        "gradeGroupId": raw.get("gradeGroupId"),
        "gradeGroupName": raw.get("gradeGroupName"),
        "difficulty": raw.get("difficulty"),
        "degree": raw.get("degree"),
        "stem": content_html,
        "stemLatex": extract_latex(content_html),
        "options": options,
        "answer": steps,
        "normalAnswer": _flatten(raw.get("normalAnswer") or []),
        "bxAnswer": raw.get("bxAnswer"),
        "blankAnswer": raw.get("blankAnswer"),
        "analysis": analysis_html,
        "analysisLatex": extract_latex(analysis_html),
        "isHaveAnalysis": raw.get("isHaveAnalysis"),
        "knowledgePoints": get_knowledge(raw),
        "source": get_source(raw),
        "createDate": raw.get("createDate"),
    }


def qidx(raw):
    """简单知识点序号映射(按 queId 哈希稳定)"""
    return (abs(hash(raw.get("queId", ""))) % 900) + 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cdp", default="http://127.0.0.1:9222")
    ap.add_argument("--sid", type=int, default=2, help="学科ID(2=数学)")
    ap.add_argument("--gid", type=int, default=2, help="年级组ID(2=初中)")
    ap.add_argument("--subjectName", default="数学")
    ap.add_argument("--gradeGroupName", default="初中")
    ap.add_argument("--max", type=int, default=40, help="最多拉取题目数")
    ap.add_argument("--pageSize", type=int, default=10)
    ap.add_argument("--out", default="./jiaoyanyun_export")
    ap.add_argument("--subjectCode", default="MAT")
    ap.add_argument("--gradeCode", default="G7")
    ap.add_argument("--rate", type=float, default=0.3, help="每次请求间隔秒")
    ap.add_argument("--from-raw", action="store_true",
                    help="跳过 API 拉取，直接复用已缓存的 raw_questions.json 重新归一化(用于迭代解析逻辑)")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)

    if args.from_raw:
        raw_path = os.path.join(args.out, "raw_questions.json")
        collected = json.load(open(raw_path, encoding="utf-8"))
        print(f"▶ 复用缓存 {raw_path}（{len(collected)} 题），跳过 API 拉取 ...", flush=True)
    else:
        syncer = JiaoyanyunSyncer(args.cdp, args.out, rate=args.rate)
        print("▶ 连接本机 Chrome ...", flush=True)
        syncer.connect()
        syncer.ensure_auth()
        print("✓ Authorization 令牌已获取:", syncer.auth[:12] + "...", flush=True)

        collected = []
        page_no = 1
        seen = set()
        extra = {"subjectName": args.subjectName, "gradeGroupName": args.gradeGroupName}
        while len(collected) < args.max:
            print(f"▶ 拉取第 {page_no} 页 ...", flush=True)
            obj = syncer.fetch_page(args.sid, args.gid, page_no, args.pageSize, extra)
            items = (obj.get("data") or {}).get("data") or []
            if not items:
                print("  无更多数据，停止。", flush=True)
                break
            ids = [q["queId"] for q in items if q.get("queId") and q["queId"] not in seen]
            for i in ids:
                seen.add(i)
            if ids:
                details = syncer.fetch_details(ids)
                for d in details:
                    collected.append(d)
                    if len(collected) >= args.max:
                        break
            page_no += 1
            if len(items) < args.pageSize:
                break
        syncer.close()

    print(f"✓ 共拉取 {len(collected)} 道题目，开始归一化 ...", flush=True)
    normalized = [normalize(q, args.out, i + 1, args.subjectCode, args.gradeCode)
                  for i, q in enumerate(collected)]
    out_path = os.path.join(args.out, "questions.json")
    json.dump(normalized, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    # 原始数据也存一份（非 --from-raw 时覆盖；--from-raw 时保持原样）
    if not args.from_raw:
        json.dump(collected, open(os.path.join(args.out, "raw_questions.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
    # 统计
    from collections import Counter
    tc = Counter(n["writtenType"] for n in normalized)
    print("✓ 题型分布:", dict(tc))
    print("✓ 已保存:", out_path, "（图片存于", os.path.join(args.out, "images"), "）")
    print("✓ 样例位置编码:", normalized[0]["positionCode"] if normalized else "无")


if __name__ == "__main__":
    main()
