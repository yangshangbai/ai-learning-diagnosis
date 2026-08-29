"""第一批模块冒烟：基础数据 / 教师 / 班级 / 学生。

覆盖：登录、枚举 seed、分类树、教师(含User)、班级(code生成)、学生(code生成)、列表、越权(teacher禁建教师)。
"""
import json
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"
ok = True


def req(method, path, body=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}


def check(name, cond, extra=""):
    global ok
    print(("PASS" if cond else "FAIL"), name, extra)
    if not cond:
        ok = False


# 登录
st, data = req("POST", "/api/v1/auth/login", {"username": "admin", "password": "admin123"})
check("admin login", st == 200 and "access_token" in data, str(st))
token = data["access_token"]

# 枚举 seed
st, data = req("GET", "/api/v1/categories?type=subject", token=token)
check("seed subjects=5", st == 200 and data["total"] == 5, str(data.get("total")))
st, data = req("GET", "/api/v1/categories?type=grade", token=token)
check("seed grades=12", st == 200 and data["total"] == 12, str(data.get("total")))
st, data = req("GET", "/api/v1/categories?type=question_type", token=token)
check("seed question_types=5", st == 200 and data["total"] == 5, str(data.get("total")))

# 创建知识点分类
st, data = req("POST", "/api/v1/categories", {"name": "代数", "category_type": "knowledge", "code": "KP001"}, token=token)
check("create knowledge category", st == 201, str(st))

# 教师（含 User）
st, data = req("POST", "/api/v1/teachers", {"name": "张老师", "username": "zhang", "password": "zhang123", "classes": []}, token=token)
check("create teacher+T001", st == 201 and data.get("teacher_code") == "T0001", str(data.get("teacher_code")))
tid = data["id"]

# 班级 code A01
st, data = req("POST", "/api/v1/classes", {"name": "一年级1班", "stage": "primary"}, token=token)
check("create class A01", st == 201 and data.get("class_code") == "A01", str(data.get("class_code")))
cid = data["id"]

# 学生 code A01
st, data = req("POST", "/api/v1/students", {"name": "小明", "class_id": cid}, token=token)
check("create student A01", st == 201 and data.get("student_code") == "A01", str(data.get("student_code")))
sid = data["id"]

# 列表
st, data = req("GET", "/api/v1/students", token=token)
check("list students>=1", st == 200 and data["total"] >= 1, str(data.get("total")))
st, data = req("GET", "/api/v1/classes", token=token)
check("list classes>=1", st == 200 and data["total"] >= 1, str(data.get("total")))

# 学生看板
st, data = req("GET", f"/api/v1/students/{sid}/dashboard", token=token)
check("student dashboard", st == 200, str(st))

# 越权：teacher 禁建教师
st, tdata = req("POST", "/api/v1/auth/login", {"username": "zhang", "password": "zhang123"})
t_token = tdata["access_token"]
st, _ = req("POST", "/api/v1/teachers", {"name": "y", "username": "y2", "password": "y123456"}, token=t_token)
check("teacher forbidden create teacher(403)", st == 403, str(st))

print("ALL PASS" if ok else "SOME FAILED")
