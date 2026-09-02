# -*- coding: utf-8 -*-
"""前端修复批: BUG-01~06(测试报告) — ID失配/假保存/口径/日期/accept/AI消息"""
import io

def patch(path, old, new, tag):
    s = io.open(path, encoding='utf-8').read()
    if new in s:
        print('⏭️ ' + tag)
        return
    if old not in s:
        print('❌ ' + tag + ' : 未匹配')
        return
    s = s.replace(old, new, 1)
    io.open(path, 'w', encoding='utf-8').write(s)
    print('✅ ' + tag)

P = 'frontend/demo/index.html'

# ── A. 全局类型安全查找器 + 日期格式化 ──
patch(P, 'const ROUTES = {',
"""function findTaskById(id){ const s=String(id); return (DATA.tasks||[]).find(t=>String(t.id)===s); }
function findPaperById(id){ const s=String(id); return (DATA.papers||[]).find(p=>String(p.id)===s); }
function findStudentById(id){ const s=String(id); return (DATA.students||[]).find(x=>String(x.id)===s); }
function findClassById(id){ const s=String(id); return (DATA.classes||[]).find(x=>String(x.id)===s); }
function findTeacherById(id){ const s=String(id); return (DATA.teachers||[]).find(x=>String(x.id)===s); }
function fmtClass(s){ if(!s) return '--'; return ((s.classCode||s.class_code||'')+' '+(s.className||'')).trim() || '--'; }
function fmtDT(v){ if(!v) return '--'; return String(v).replace('T',' ').slice(0,19); }
const ROUTES = {""", 'A-全局查找器')

# ── B. 12 处 ID 失配点 ──
pairs = [
 ("const selectedPaper = params.paperId ? DATA.papers.find(p => p.id === params.paperId) : null;",
  "const selectedPaper = params.paperId ? findPaperById(params.paperId) : null;"),
 ("const task = DATA.tasks.find(t => t.id === params.taskId) || DATA.tasks[0];",
  "const task = findTaskById(params.taskId);"),
 ("""const task = DATA.tasks.find(t => t.id === rp.taskId) || DATA.tasks[0];
  const paper = DATA.papers.find(p => p.id === task.paperId) || {};""",
  """const task = findTaskById(rp.taskId);
  if (!task) { return '<div class="page"><h2>任务不存在或已删除</h2><button class="btn" onclick="navigate(\'exam-task\')">← 返回任务列表</button></div>'; }
  const paper = findPaperById(task.paperId) || {};"""),
 ("const student = DATA.students.find(s => s.id === params.studentId) || DATA.students[0];",
  "const student = findStudentById(params.studentId);"),
 ("const student = DATA.students.find(s => s.id === rp.studentId) || DATA.students[0];",
  "const student = findStudentById(rp.studentId);"),
 ("let s = DATA.students.find(x => x.id === params.id) || DATA.students[0];",
  "let s = findStudentById(params.id);"),
 ("const c = DATA.classes.find(x => x.id === params.id) || DATA.classes[0];",
  "const c = findClassById(params.id);"),
 ("let t = DATA.teachers.find(x => x.id === params.id) || DATA.teachers[0];",
  "let t = findTeacherById(params.id);"),
]
# rp.taskId 的任务查找出现3次(上传页/重评分/学生考卷),逐一替换
for old, new in pairs:
    n = s_count = io.open(P, encoding='utf-8').read().count(old)
    if n > 1:
        s = io.open(P, encoding='utf-8').read()
        s = s.replace(old, new)
        io.open(P, 'w', encoding='utf-8').write(s)
        print('✅ B(×%d): ' % n + old[:44])
    else:
        patch(P, old, new, 'B:' + old[:44])

# ── C. saveStudentCreate → 真实API ──
patch(P, """function saveStudentCreate(autoCode) {
  const name = (document.getElementById('stuName') || {}).value || '';
  if (!name.trim()) { showToast('请填写姓名', 'error'); return; }
  const gender = (document.querySelector('input[name="gender"]:checked') || {}).value || 'male';
  const classId = (document.getElementById('stuClass') || {}).value || DATA.classes[0].id;
  const cls = DATA.classes.find(c => c.id === classId) || DATA.classes[0];
  const newId = 's' + Date.now();""",
"""async function saveStudentCreate(autoCode) {
  const nameEl = document.getElementById('stuName');
  const name = (nameEl || {}).value || '';
  if (!name.trim()) { showToast('请填写学生姓名', 'error'); if (nameEl) { nameEl.style.borderColor = 'var(--error)'; nameEl.focus(); } return; }
  const gender = (document.querySelector('input[name="gender"]:checked') || {}).value || 'male';
  const classId = Number((document.getElementById('stuClass') || {}).value) || Number((DATA.classes[0] || {}).id);
  if (!classId) { showToast('请选择班级', 'error'); return; }""", 'C1-学生创建真实化头部')

patch(P, """  const student = {
    id: newId, code: autoCode || ('S' + String(DATA.students.length + 1).padStart(3, '0')),
    name: name.trim(), gender: gender, classId: classId, className: cls.code + ' ' + cls.name,
    birthDate: (document.getElementById('stuBirthDate') || {}).value || '',
    enrollmentDate: (document.getElementById('stuEnrollmentDate') || {}).value || '',
    parentName: (document.getElementById('stuParentName') || {}).value || '',
    parentPhone: (document.getElementById('stuParentPhone') || {}).value || '',
    initialEvaluation: (document.getElementById('stuInitialEvaluation') || {}).value || '',
    examCount: 0, avgScore: 0, maxScore: 0, minScore: 0, participationRate: 0,
    classRank: 0, lastScore: 0, lastExamDate: '', improvement: 'stable', lastRank: 0,
    remark: (document.getElementById('stuRemark') || {}).value || '', status: 'active'
  };
  DATA.students.push(student);
  saveLocalStudents();   // 持久化学生数据，防止刷新丢失
  // 班级学生数 +1
  cls.studentCount = (cls.studentCount || 0) + 1;
  STATE.filteredStudents = null;
  showToast('学生创建成功！编号 ' + student.code);
  navigate('student');
}""",
"""  const val = (id) => { const el = document.getElementById(id); const v = el ? el.value : ''; return (v && v.trim) ? v.trim() : v; };
  const payload = {
    name: name.trim(), gender: gender === 'female' ? 'female' : 'male', class_id: classId,
    birth_date: val('stuBirthDate') || null, enrollment_date: val('stuEnrollmentDate') || null,
    parent_name: val('stuParentName') || null, parent_phone: val('stuParentPhone') || null,
    initial_evaluation: val('stuInitialEvaluation') || null, remark: val('stuRemark') || null,
  };
  const saved = await apiPost('/students', payload);
  if (!saved || !saved.id) { showToast('保存失败：服务端未确认写入，请检查网络后重试', 'error'); return; }
  await loadBackendData();   // 以后端为准刷新列表与班级人数
  STATE.filteredStudents = null;
  showToast('学生创建成功！学号 ' + (saved.studentCode || saved.student_code || ''));
  navigate('student');
}""", 'C2-学生创建真实化提交')

# ── D. saveTaskCreate → 真实API ──
patch(P, """function saveTaskCreate(defaultCode) {
  const name = (document.getElementById('taskName') || {}).value || '';
  if (!name.trim()) { showToast('请填写任务名称', 'error'); return; }
  const category = (document.getElementById('taskCategory') || {}).value || (DATA.taskCategories[0] && DATA.taskCategories[0].name) || '';
  const paperId = (document.getElementById('taskPaper') || {}).value;
  const paper = DATA.papers.find(p => p.id === paperId) || DATA.papers[0];
  if (!paper) { showToast('请选择试卷', 'error'); return; }""",
"""async function saveTaskCreate(defaultCode) {
  const name = (document.getElementById('taskName') || {}).value || '';
  if (!name.trim()) { showToast('请填写任务名称', 'error'); return; }
  const categoryName = (document.getElementById('taskCategory') || {}).value || (DATA.taskCategories[0] && DATA.taskCategories[0].name) || '';
  const cat = (DATA.taskCategories || []).find(c => c.name === categoryName);
  const paper = findPaperById((document.getElementById('taskPaper') || {}).value);
  if (!paper) { showToast('请选择试卷', 'error'); return; }""", 'D1-任务创建真实化头部')

patch(P, """  if (assignMode === 'class') {
    classIds = Array.from(document.querySelectorAll('.task-class-cb:checked')).map(cb => cb.value);
    if (classIds.length === 0) { showToast('请至少选择一个班级', 'error'); return; }
    studentCount = classIds.reduce((sum, cid) => {
      const c = DATA.classes.find(x => x.id === cid);
      return sum + (c ? c.studentCount : 0);
    }, 0);
  } else {
    const studentIds = Array.from(document.querySelectorAll('.task-student-cb:checked')).map(cb => cb.value);
    if (studentIds.length === 0) { showToast('请至少选择一名学生', 'error'); return; }
    studentCount = studentIds.length;
    // infer classIds from selected students
    const set = new Set();
    studentIds.forEach(sid => {
      const s = DATA.students.find(x => x.id === sid);
      if (s) set.add(s.classId);
    });
    classIds = Array.from(set);
  }
  const today = new Date();
  const ymd = today.getFullYear() + '-' + String(today.getMonth()+1).padStart(2,'0') + '-' + String(today.getDate()).padStart(2,'0');
  const newId = 't' + Date.now();
  const task = {
    id: newId, code: defaultCode, name: name.trim(),
    paperId: paper.id, paperName: paper.name,
    category: category, creator: STATE.userName || '管理员', status: 'pending',
    studentCount: studentCount, uploadedCount: 0, scoredCount: 0, confirmedCount: 0,
    avgScore: 0, maxScore: 0, minScore: 0, medianScore: 0, stdDev: 0, passRate: 0, excellentRate: 0,
    createdAt: ymd, classIds: classIds
  };
  DATA.tasks.push(task);
  STATE.filteredTasks = null;
  showToast('任务创建成功！编码 ' + defaultCode);
  navigate('exam-task');
}""",
"""  if (assignMode === 'class') {
    classIds = Array.from(document.querySelectorAll('.task-class-cb:checked')).map(cb => Number(cb.value));
    if (classIds.length === 0) { showToast('请至少选择一个班级', 'error'); return; }
    studentCount = (DATA.students || []).filter(s => classIds.includes(Number(s.classId))).length;
  } else {
    studentIds = Array.from(document.querySelectorAll('.task-student-cb:checked')).map(cb => Number(cb.value));
    if (studentIds.length === 0) { showToast('请至少选择一名学生', 'error'); return; }
    studentCount = studentIds.length;
  }
  const payload = {
    name: name.trim(), paper_id: Number(paper.id),
    category_id: cat ? Number(cat.id) : null,
    student_ids: studentIds || [],
  };
  const saved = await apiPost('/exam-tasks', payload);
  if (!saved || !saved.id) { showToast('创建失败：服务端未确认写入，请检查网络后重试', 'error'); return; }
  await loadBackendData();   // 以后端为准刷新任务与统计
  STATE.filteredTasks = null;
  showToast('任务创建成功！编码 ' + (saved.taskCode || saved.task_code || ''));
  navigate('exam-task');
}""", 'D2-任务创建真实化提交')

# ── E. 本地学生回灌封堵(后端为唯一事实源) ──
patch(P, """    const saved = localStorage.getItem('students');
    if (!saved) return;
    const list = JSON.parse(saved);
    if (!Array.isArray(list)) return;""",
"""    // BUG修复：学生数据以后端为唯一事实源，本地暂存不再回灌（历史假数据会污染列表与班级人数）
    return;""", 'E-本地学生回灌封堵')

# ── F. 班级展示统一(编码+名称) ──
patch(P, "<td>${s.code}</td><td>${s.name}</td><td>${s.className || '--'}</td>",
      "<td>${s.code}</td><td>${s.name}</td><td>${fmtClass(s)}</td>", 'F1-学生列表口径')
patch(P, "<td>${s.className}</td>", "<td>${fmtClass(s)}</td>", 'F2-任务上传列表口径')
patch(P, "${student.code || ''} ${student.name || ''}（${student.className || ''}）",
      "${student.code || ''} ${student.name || ''}（${fmtClass(student)}）", 'F3-学生考卷头部口径')

# ── G. 日期格式化 ──
patch(P, '<td class="table-mobile-hide" style="font-size:12px;">${t.createdAt}</td>',
      '<td class="table-mobile-hide" style="font-size:12px;">${fmtDT(t.createdAt)}</td>', 'G1-任务列表时间')
patch(P, '<tr><td style="color:var(--text-sub);">创建时间</td><td>${paper.createdAt}</td>',
      '<tr><td style="color:var(--text-sub);">创建时间</td><td>${fmtDT(paper.createdAt)}</td>', 'G2-试卷详情时间')

# ── H. 上传控件 accept + 类型校验 ──
patch(P, 'accept="image/*" capture="environment" multiple',
      'accept="image/jpeg,image/png,.jpg,.jpeg,.png" capture="environment" multiple', 'H1-拍照accept')
patch(P, 'accept="image/*" multiple onchange="showPhotoPreview(this)"',
      'accept="image/jpeg,image/png,.jpg,.jpeg,.png" multiple onchange="showPhotoPreview(this)"', 'H2-文件accept')
patch(P, """function showPhotoPreview(input) {
  const files = input.files;""",
"""function showPhotoPreview(input) {
  const all = Array.from(input.files || []);
  const bad = all.filter(f => !/^image\\/(jpeg|png)$/.test(f.type) && !/\\.(jpe?g|png)$/i.test(f.name));
  const files = all.filter(f => !bad.includes(f));
  if (bad.length) showToast('仅支持 JPG/JPEG/PNG 格式，已跳过 ' + bad.length + ' 个文件', 'error');
  if (!files.length) { input.value = ''; return; }""", 'H3-类型校验')

# ── I. AI识别矛盾提示修复(状态拆分) ──
patch(P, """  const rows = results.map((r, i) => {
    if (r.error) return `<div style="padding:6px 0;border-bottom:1px solid var(--border-light);font-size:13px;color:var(--error);">❌ 第 ${i + 1} 张：${r.error}</div>`;
    const nm = r.student ? `<b>${r.student.code} ${r.student.name}</b>（${r.student.className}）` : `<b>${r.recCode || '未匹配'}</b>`;
    return `<div style="padding:6px 0;border-bottom:1px solid var(--border-light);font-size:13px;">✅ ${nm}：识别 ${r.n} 题，答案已入库并完成客观题判分</div>`;
  }).join('');
  content.innerHTML = `
    <div style="margin-bottom:8px;font-size:14px;">🤖 AI 识别完成（真实视觉模型识别）</div>
    ${rows}
    <div style="margin-top:10px;font-size:13px;color:var(--text-sub);">识别答案已提交服务端入库（重复上传自动替换旧卡），客观题已按标准答案自动判分，主观题请到「学生考卷详情」人工评分。</div>
  `;
  showToast(`已识别 ${results.filter(r => !r.error).length} 名学生`);""",
"""  const okRows = results.filter(r => !r.error);
  const rows = results.map((r, i) => {
    if (r.error) return `<div style="padding:6px 0;border-bottom:1px solid var(--border-light);font-size:13px;color:var(--error);">❌ 第 ${i + 1} 张：${r.error}</div>`;
    const nm = r.student ? `<b>${r.student.code} ${r.student.name}</b>（${r.student.className}）` : `<b>${r.recCode || '未匹配'}</b>`;
    return `<div style="padding:6px 0;border-bottom:1px solid var(--border-light);font-size:13px;">✅ ${nm}：识别 ${r.n} 题，答案已入库并完成客观题判分</div>`;
  }).join('');
  const banner = okRows.length
    ? `<div style="margin-bottom:8px;font-size:14px;">🤖 AI 识别完成：成功入库 ${okRows.length} 张${results.length > okRows.length ? '，失败 ' + (results.length - okRows.length) + ' 张' : ''}</div>`
    : `<div style="margin-bottom:8px;font-size:14px;color:var(--error);">❌ AI 识别失败：未入库任何答题卡（共 ${results.length} 张全部失败）</div>`;
  const footer = okRows.length
    ? `<div style="margin-top:10px;font-size:13px;color:var(--text-sub);">成功各张的识别答案已提交服务端入库（重复上传自动替换旧卡），客观题已按标准答案自动判分，主观题请到「学生考卷详情」人工评分。失败各张请修正后重新上传。</div>`
    : `<div style="margin-top:10px;font-size:13px;color:var(--error);">请根据上方失败原因处理后重试（失败的照片不会入库，学生状态保持待上传）。</div>`;
  content.innerHTML = banner + rows + footer;
  showToast(okRows.length ? '已入库 ' + okRows.length + ' 名学生答题卡' : 'AI 识别失败，未入库任何答题卡', okRows.length ? undefined : 'error');""", 'I-AI消息状态拆分')

print('FRONTEND DONE')
