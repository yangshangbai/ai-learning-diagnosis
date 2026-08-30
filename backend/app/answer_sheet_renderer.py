"""答题卡 HTML 渲染器（前端 renderAnswerSheetPreviewHtml / downloadTaskAnswerSheetsPdf 后端化）。

输入约定：本模块不依赖 ORM，只接收已解析的纯 dict（由 exam.py 组装）：
  - paper:    {"code", "name", "subject"}
  - task:     {"code", "name"}            （可 None，试卷级预览）
  - student:  {"id", "code", "name", "className"}  （可 None）
  - questions:[{"type", "options", "score", "stem"}]

输出：
  - render_sheet_html()     单学生答题卡 HTML 片段
  - render_multi_sheet_html() 完整可打印 HTML 文档（每学生一页，@media print 分页）
"""
import base64
import io
import json
from typing import List, Optional

import qrcode


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------
def _esc(v) -> str:
    """HTML 转义（比前端更严格，防 XSS）。"""
    from html import escape

    return escape(str(v if v is not None else ""), quote=True)


def _safe_str(o) -> str:
    """等价前端 safeStr：把选项等对象字段安全转字符串，禁止 [object Object]。"""
    if o is None:
        return ""
    if isinstance(o, str):
        return o
    if isinstance(o, (int, float, bool)):
        return str(o)
    if isinstance(o, (list, tuple)):
        return " ".join(x for x in (_safe_str(v) for v in o) if x)
    if isinstance(o, dict):
        parts = []
        for k in ("label", "content", "text", "value"):
            v = o.get(k)
            if v is not None:
                parts.append(v if isinstance(v, str) else _safe_str(v))
        if parts:
            return "".join(parts).lstrip(".:")
        try:
            return json.dumps(o, ensure_ascii=False)
        except Exception:
            return str(o)
    try:
        return json.dumps(o, ensure_ascii=False)
    except Exception:
        return str(o)


def generate_qr_data_url(payload: str) -> str:
    """Python qrcode 生成 base64 dataURL（等价前端 _generateQRDataUrl，qrcode(0,'M') 级别 M）。"""
    try:
        img = qrcode.make(payload)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        return ""


# 题型排序（照抄前端 QUESTION_TYPE_SORT）
_TYPE_SORT = {
    "single_choice": 0,
    "multi_choice": 0,
    "true_false": 0,
    "fill_blank": 1,
    "essay": 2,
}

# 分区定义（照抄前端 renderAnswerSheetPreviewHtml 的 groups）
_TYPE_GROUPS = [
    (("single_choice", "multi_choice", "true_false"), "一、选择题（涂点区）"),
    (("fill_blank",), "二、填空题（填空框）"),
    (("essay",), "三、解答题（方格稿纸）"),
]


def _sort_questions(questions: List[dict]) -> List[dict]:
    return sorted(questions, key=lambda q: _TYPE_SORT.get(q.get("type", ""), 9))


# ---------------------------------------------------------------------------
# 答题卡 HTML 渲染
# ---------------------------------------------------------------------------
SHEET_CSS = """
.answer-sheet-preview{padding:20px;border:1px solid #D9D9D9;border-radius:4px;background:#fff;position:relative;}
.reg-mark{position:absolute;width:16px;height:16px;border:0 solid #000;border-width:0;}
.reg-mark.rm-tl{top:6px;left:6px;border-top-width:3px;border-left-width:3px;}
.reg-mark.rm-tr{top:6px;right:6px;border-top-width:3px;border-right-width:3px;}
.reg-mark.rm-bl{bottom:6px;left:6px;border-bottom-width:3px;border-left-width:3px;}
.reg-mark.rm-br{bottom:6px;right:6px;border-bottom-width:3px;border-right-width:3px;}
.answer-sheet-header{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;font-size:13px;color:#262626;margin-bottom:12px;padding:10px 12px;border:1px solid #D9D9D9;border-radius:4px;background:#FAFAFA;}
.answer-sheet-header .ah-info{display:flex;flex-direction:column;gap:4px;}
.answer-sheet-header b{font-weight:700;color:#000;}
.answer-sheet-header .ah-qr{text-align:center;flex-shrink:0;}
.answer-sheet-header .ah-qr img{width:64px;height:64px;display:block;}
.answer-sheet-header .qr-placeholder{width:64px;height:64px;border:1px dashed #999;display:flex;align-items:center;justify-content:center;color:#999;font-size:12px;}
.answer-sheet-header .qr-caption{font-size:10px;color:#8C8C8C;margin-top:2px;}
.answer-sheet-section{margin-bottom:16px;}
.answer-sheet-section h4{font-size:14px;margin:8px 0;font-weight:700;}
.answer-sheet-choice{display:flex;align-items:center;flex-wrap:wrap;gap:8px;margin:8px 0;font-size:13px;}
.answer-sheet-choice .qno{font-weight:600;min-width:24px;}
.bubble{display:inline-flex;align-items:center;justify-content:center;width:24px;height:24px;border:1.5px solid #333;border-radius:50%;font-size:12px;background:#fff;}
.bubble.square{border-radius:2px;}
.blank-row{display:flex;align-items:center;gap:10px;margin:8px 0;font-size:13px;}
.blank-row .qno{font-weight:600;min-width:24px;}
.blank{display:inline-block;width:120px;height:20px;border-bottom:1.5px solid #333;}
.grid-paper{background-image:linear-gradient(#e8e8e8 1px,transparent 1px),linear-gradient(90deg,#e8e8e8 1px,transparent 1px);background-size:16px 16px;border:1px solid #ccc;min-height:60px;width:100%;}
"""


def render_sheet_html(
    paper: dict,
    questions: List[dict],
    task: Optional[dict] = None,
    student: Optional[dict] = None,
) -> str:
    """单页答题卡 HTML 片段（等价前端 renderAnswerSheetPreviewHtml）。

    - 机读带：任务码/试卷码/学生（task/student 为空时跳过）
    - QR dataURL：payload = JY|tk=...|pp=...|st=...|sb=...|pg=1/1
    - 四角对位标记 + 选择涂点/填空框/解答方格分区
    """
    ordered = _sort_questions(questions)
    subject = (
        paper.get("subject")
        or (ordered[0].get("subject") if ordered else None)
        or "数学"
    )
    # QR payload 与 Word 通道（template_engine.build_sheet_qr_payload）同构：任务/试卷/班级/学生
    qr_payload = "JY|tk={}|pp={}|cl={}|st={}|pg=1/1".format(
        (task or {}).get("code", "") or "",
        paper.get("code", "") or "",
        (student or {}).get("classCode", "") or "",
        (student or {}).get("code", "") or "",
    )
    qr_data_url = generate_qr_data_url(qr_payload)

    h: List[str] = []
    h.append('<div class="answer-sheet-preview">')
    # 四角对位标记（┌ ┐ └ ┘，拍照后透视校正）
    h.append(
        '<span class="reg-mark rm-tl"></span><span class="reg-mark rm-tr"></span>'
        '<span class="reg-mark rm-bl"></span><span class="reg-mark rm-br"></span>'
    )
    # 机读带：任务/试卷/学生信息 + 二维码
    h.append('<div class="answer-sheet-header">')
    h.append('<div class="ah-info">')
    if task:
        h.append(
            f'<span><b>任务：</b>{_esc(task.get("code") or "")} {_esc(task.get("name") or "")}</span>'
        )
    h.append(
        f'<span><b>试卷：</b>{_esc(paper.get("code") or paper.get("name") or "")}</span>'
    )
    if student:
        h.append(
            f'<span><b>学生：</b>{_esc(student.get("code") or "")} '
            f'{_esc(student.get("name") or "")}（{_esc(student.get("className") or "")}）</span>'
        )
    h.append("</div>")
    if qr_data_url:
        h.append(
            f'<div class="ah-qr"><img src="{qr_data_url}" alt="QR">'
            '<div class="qr-caption">扫码识别</div></div>'
        )
    else:
        h.append(
            '<div class="ah-qr"><div class="qr-placeholder">QR</div>'
            '<div class="qr-caption">扫码识别</div></div>'
        )
    h.append("</div>")

    # 按 选择 → 填空 → 解答 分组并重新连续编号
    seq = 0
    for types, label in _TYPE_GROUPS:
        items: List[tuple] = []
        for q in ordered:
            if q.get("type") in types:
                seq += 1
                items.append((seq, q))
        if not items:
            continue
        h.append(f'<div class="answer-sheet-section"><h4>{_esc(label)}（共{len(items)}题）</h4>')
        for no, q in items:
            qt = q.get("type")
            if qt in ("single_choice", "multi_choice"):
                opts = q.get("options") or []
                letters = [_safe_str(o)[:1] for o in opts]
                cls = "bubble square" if qt == "multi_choice" else "bubble"
                h.append(f'<div class="answer-sheet-choice"><span class="qno">{no}.</span>')
                for letter in letters:
                    h.append(f'<span class="{cls}">{_esc(letter)}</span>')
                h.append("</div>")
            elif qt == "true_false":
                h.append(
                    f'<div class="answer-sheet-choice"><span class="qno">{no}.</span>'
                    '<span class="bubble">√</span><span class="bubble">×</span></div>'
                )
            elif qt == "fill_blank":
                h.append(
                    f'<div class="blank-row"><span class="qno">{no}.</span>'
                    '<span class="blank">　</span><span class="blank">　</span></div>'
                )
            elif qt == "essay":
                height = max(60, int(q.get("score") or 0) * 8)
                h.append(
                    f'<div style="margin-bottom:8px;"><span class="qno">{no}.</span>'
                    f'<div class="grid-paper" style="min-height:{height}px;"></div></div>'
                )
        h.append("</div>")
    h.append("</div>")
    return "".join(h)


def render_multi_sheet_html(
    task: dict,
    students: List[dict],
    paper: dict,
    questions: List[dict],
) -> str:
    """多学生答题卡合并 HTML 文档（每生一页，@media print 分页）。

    返回完整 HTML，前端/新窗口 window.print 即可另存为 PDF。
    """
    pages = []
    for stu in students:
        pages.append(
            f'<div class="answer-sheet-page">{render_sheet_html(paper, questions, task=task, student=stu)}</div>'
        )
    total = len(students)
    task_name = _esc(task.get("name") or "答题卡")
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>{task_name} - 学生答题卡</title>
<style>
body{{font-family:-apple-system,'Microsoft YaHei',sans-serif;padding:24px;color:#262626;}}
h2{{margin-top:0;text-align:center;}}
{SHEET_CSS}
.answer-sheet-page{{page-break-after:always;}}
.answer-sheet-page:last-child{{page-break-after:auto;}}
@media print{{body{{padding:0;}} .no-print{{display:none;}}}}
.print-bar{{position:fixed;top:0;left:0;right:0;background:#1677FF;color:#fff;padding:8px 16px;font-size:13px;display:flex;align-items:center;gap:12px;z-index:10;}}
.print-bar button{{background:#fff;color:#1677FF;border:none;padding:6px 16px;border-radius:4px;cursor:pointer;font-size:13px;}}
</style>
</head>
<body onload="setTimeout(function(){{try{{window.focus();window.print();}}catch(e){{}}}},400)">
<div class="print-bar no-print"><span>已生成 {total} 名学生的答题卡，请在"目标"选择"另存为 PDF"</span><button onclick="window.print()">重新打印</button></div>
<h2>{task_name} · 答题卡（共 {total} 人，每学生一页）</h2>
{''.join(pages)}
</body>
</html>"""
