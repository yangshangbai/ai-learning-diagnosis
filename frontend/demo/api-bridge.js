/* ================================================================
   API Bridge — 连接 FastAPI 后端 (http://127.0.0.1:8000)
   --------------------------------------------------------------
   - 仅在登录成功后由 doLogin() 调用 loadBackendData() 填充 DATA
   - 任何网络错误都返回 null，绝不抛出，保证 Demo 离线可用
   - 后端字段名 (snake_case) → Demo DATA 字段名 (camelCase)
   - 每个端点失败时保留现有 mock DATA，不覆盖
   ================================================================ */
(function () {
  'use strict';

  // 本地开发(127.0.0.1)直连 8000；云端走同源 /api（nginx 反代 8001）
// 统一用相对路径（nginx 代理到真实后端）；若页面端口>1024（如本地 python -m http.server 5174）
// 才有真正的 nginx 代理，否则本地走 8000 绝对路径
const API_BASE = (typeof location !== 'undefined' && (location.port === '5174' || location.port === '5173'))
  ? 'http://127.0.0.1:8000/api/v1'
  : '/api/v1';  // 生产 nginx 80/443 代理 /api/ → 8001

  // ---- token 管理（localStorage 持久化，刷新不掉登录）----
  const TOKEN_KEY = 'wb_api_token';
  let _token = null;
  function setApiToken(t) {
    _token = t || null;
    try {
      if (t) localStorage.setItem(TOKEN_KEY, t);
      else localStorage.removeItem(TOKEN_KEY);
    } catch (e) {}
  }
  function getApiToken() {
    if (_token) return _token;
    try { return localStorage.getItem(TOKEN_KEY) || null; } catch (e) { return null; }
  }

  // ---- 通用请求（永不抛出，失败返回 null）----
  async function apiGet(path) {
    try {
      const headers = { 'Accept': 'application/json' };
      if (getApiToken()) headers['Authorization'] = 'Bearer ' + getApiToken();
      const res = await fetch(API_BASE + path, { headers });
      if (!res.ok) return null;
      return await res.json();
    } catch (e) { return null; }
  }

  // 记录最后一次 API 错误（供前端提示区分 403 权限/网络错误/接口异常）
  window._lastApiError = null;
  // 把后端错误详情格式化为人话：pydantic 422 detail 是数组 [{loc,msg,type},...]
  function _fmtErrDetail(d) {
    if (!d) return '';
    if (typeof d === 'string') return d;
    if (Array.isArray(d)) {
      const msgs = d.map(e => {
        const loc = Array.isArray(e.loc) ? e.loc.slice(1).join('.') : (e.loc || '');
        const msg = e.msg || e.message || '';
        return loc ? (loc + '：' + msg) : msg;
      }).filter(Boolean);
      return msgs.slice(0, 3).join('；') + (msgs.length > 3 ? '…' : '');
    }
    if (typeof d === 'object') return d.message || d.msg || JSON.stringify(d);
    return String(d);
  }
  async function _apiError(res, path) {
    let status = 0, message = '';
    try { status = res.status; } catch (e) {}
    try { const d = await res.json(); message = _fmtErrDetail(d.detail || d.message || ''); } catch (e) {}
    window._lastApiError = { status, message, path };
    return null;
  }
  async function apiPost(path, body) {
    try {
      const headers = { 'Content-Type': 'application/json', 'Accept': 'application/json' };
      if (getApiToken()) headers['Authorization'] = 'Bearer ' + getApiToken();
      const res = await fetch(API_BASE + path, {
        method: 'POST', headers, body: JSON.stringify(body || {})
      });
      if (!res.ok) return await _apiError(res, path);
      window._lastApiError = null;
      return await res.json();
    } catch (e) {
      window._lastApiError = { status: 0, message: 'network', path };
      return null;
    }
  }

  async function apiPatch(path, body) {
    try {
      const headers = { 'Content-Type': 'application/json', 'Accept': 'application/json' };
      if (getApiToken()) headers['Authorization'] = 'Bearer ' + getApiToken();
      const res = await fetch(API_BASE + path, {
        method: 'PATCH', headers, body: JSON.stringify(body || {})
      });
      if (!res.ok) return null;
      return await res.json();
    } catch (e) { return null; }
  }

  async function apiDelete(path) {
    try {
      const headers = { 'Accept': 'application/json' };
      if (getApiToken()) headers['Authorization'] = 'Bearer ' + getApiToken();
      const res = await fetch(API_BASE + path, { method: 'DELETE', headers });
      if (!res.ok) return null;
      return await res.json();
    } catch (e) { return null; }
  }

  async function apiPut(path, body) {
    try {
      const headers = { 'Content-Type': 'application/json', 'Accept': 'application/json' };
      if (getApiToken()) headers['Authorization'] = 'Bearer ' + getApiToken();
      const res = await fetch(API_BASE + path, {
        method: 'PUT', headers, body: JSON.stringify(body || {})
      });
      if (!res.ok) return null;
      return await res.json();
    } catch (e) { return null; }
  }

  // ---- 工具：snake_case → camelCase ----
  function camelize(key) {
    if (!key || typeof key !== 'string') return key;
    return key.replace(/_([a-z])/g, (_, c) => c.toUpperCase());
  }
  // 把对象的所有 snake_case 键转成 camelCase（浅拷贝）
  function camelKeys(obj) {
    if (!obj || typeof obj !== 'object' || Array.isArray(obj)) return obj;
    const out = {};
    for (const k in obj) out[camelize(k)] = obj[k];
    return out;
  }

  // ---- 字段映射：后端实体 → Demo DATA 形状 ----
  // 对每个实体先做 camelCase 转换，再补齐 Demo 期望的特定字段名/默认值
  function mapBackendToDemoShape(entity, type) {
    if (!entity || typeof entity !== 'object') return entity;
    const c = camelKeys(entity);

    switch (type) {
      case 'question': {
        // 后端: ques_type → Demo: type, subject_name → subject, grade_name → grade, category_name → category
        // 兼容教研云简写题型（历史脏数据兜底）
        const _tn = { single: 'single_choice', multi: 'multi_choice', judge: 'true_false', fill: 'fill_blank' };
        const rawType = c.quesType || c.type || c.questionType || 'essay';
        return Object.assign({}, c, {
          type: _tn[rawType] || rawType,
          code: c.questionCode || c.code || c.positionCode || '',
          subject: c.subjectName || c.subject_name || c.subject || '',
          grade: c.gradeName || c.grade_name || c.grade || '',
          score: c.score != null ? Number(c.score) : 0,
          difficulty: c.difficulty != null ? Number(c.difficulty) : 3,
          options: Array.isArray(c.options) ? c.options : [],
          knowledge: Array.isArray(c.knowledge) ? c.knowledge : (Array.isArray(c.knowledgeIds) ? c.knowledgeIds : []),
          category: c.category || c.categoryName || c.category_name || '',
          tags: Array.isArray(c.tags) ? c.tags.map(String) : [],
          source: c.source || 'backend',
          sourceId: c.sourceId || c.source_id || null,   // 教研云 queId/positionCode，供批量操作回查后端 id
          status: c.status || 'active',
        });
      }
      case 'paper': {
        // 后端: paper_code → code, total_score → totalScore
        const qIds = Array.isArray(c.questions) ? c.questions : (Array.isArray(c.questionIds) ? c.questionIds : []);
        return Object.assign({}, c, {
          code: c.paperCode || c.code || '',
          totalScore: c.totalScore != null ? Number(c.totalScore) : 0,
          questionCount: c.questionCount != null ? Number(c.questionCount) : qIds.length,
          questions: qIds,
          category: c.category || '',
          subject: c.subject || '',
          grade: c.grade || '',
          status: c.status || 'active',
          createdAt: c.createdAt || '',
        });
      }
      case 'class': {
        // 后端: class_code → code
        return Object.assign({}, c, {
          code: c.classCode || c.code || '',
          stage: c.stage || 'middle',
          studentCount: c.studentCount != null ? Number(c.studentCount) : 0,
          examCount: c.examCount != null ? Number(c.examCount) : 0,
          headTeacher: c.headTeacher || c.headTeacherName || '',
          teachers: Array.isArray(c.teachers) ? c.teachers : [],
          remark: c.remark || '',
          status: c.status || 'active',
        });
      }
      case 'student': {
        // 后端: student_code → code, class_id → classId, class_name → className
        return Object.assign({}, c, {
          code: c.studentCode || c.code || '',
          classId: c.classId || c.class_id || '',
          className: c.className || c.class_name || '',
          gender: c.gender || 'male',
          examCount: c.examCount != null ? Number(c.examCount) : 0,
          avgScore: c.avgScore != null ? Number(c.avgScore) : 0,
          maxScore: c.maxScore != null ? Number(c.maxScore) : 0,
          minScore: c.minScore != null ? Number(c.minScore) : 0,
          participationRate: c.participationRate != null ? Number(c.participationRate) : 0,
          classRank: c.classRank != null ? Number(c.classRank) : 0,
          lastScore: c.lastScore != null ? Number(c.lastScore) : 0,
          lastRank: c.lastRank != null ? Number(c.lastRank) : 0,
          improvement: c.improvement || 'stable',
          status: c.status || 'active',
        });
      }
      case 'teacher': {
        // 后端: teacher_code → code
        return Object.assign({}, c, {
          code: c.teacherCode || c.code || '',
          gender: c.gender || 'male',
          subjects: Array.isArray(c.subjects) ? c.subjects : [],
          classes: Array.isArray(c.classes) ? c.classes : [],
          paperCount: c.paperCount != null ? Number(c.paperCount) : 0,
          taskCount: c.taskCount != null ? Number(c.taskCount) : 0,
          status: c.status || 'active',
        });
      }
      case 'task': {
        // 后端: task_code → code, paper_id → paperId, paper_name → paperName
        return Object.assign({}, c, {
          code: c.taskCode || c.code || '',
          paperId: c.paperId || c.paper_id || '',
          paperName: c.paperName || c.paper_name || '',
          category: c.category || '',
          creator: c.creator || c.creatorName || '',
          studentCount: c.studentCount != null ? Number(c.studentCount) : 0,
          uploadedCount: c.uploadedCount != null ? Number(c.uploadedCount) : 0,
          scoredCount: c.scoredCount != null ? Number(c.scoredCount) : 0,
          confirmedCount: c.confirmedCount != null ? Number(c.confirmedCount) : 0,
          avgScore: c.avgScore != null ? Number(c.avgScore) : 0,
          maxScore: c.maxScore != null ? Number(c.maxScore) : 0,
          minScore: c.minScore != null ? Number(c.minScore) : 0,
          medianScore: c.medianScore != null ? Number(c.medianScore) : 0,
          stdDev: c.stdDev != null ? Number(c.stdDev) : 0,
          passRate: c.passRate != null ? Number(c.passRate) : 0,
          excellentRate: c.excellentRate != null ? Number(c.excellentRate) : 0,
          classIds: Array.isArray(c.classIds) ? c.classIds : [],
          status: c.status || 'pending',
          createdAt: c.createdAt || '',
        });
      }
      case 'answerSheet': {
        return Object.assign({}, c, {
          taskId: c.taskId || c.task_id || '',
          studentId: c.studentId || c.student_id || '',
          studentName: c.studentName || c.student_name || '',
          studentCode: c.studentCode || c.student_code || '',
          className: c.className || c.class_name || '',
          images: Array.isArray(c.images) ? c.images : (Array.isArray(c.imageUrls) ? c.imageUrls : []),
          uploadType: c.uploadType || 'file',
          uploadDevice: c.uploadDevice || 'pc',
          aiStatus: c.aiStatus || 'pending',
          aiTotalScore: c.aiTotalScore != null ? Number(c.aiTotalScore) : 0,
          teacherTotalScore: c.teacherTotalScore != null ? Number(c.teacherTotalScore) : 0,
          finalScore: c.finalScore != null ? Number(c.finalScore) : 0,
          confirmed: !!c.confirmed,
        });
      }
      case 'questionScore': {
        // 后端: question_number→number, ai_max_score→maxScore, score_status→status
        return Object.assign({}, c, {
          number: c.questionNumber != null ? Number(c.questionNumber) : 0,
          maxScore: c.aiMaxScore != null ? Number(c.aiMaxScore) : 0,
          studentAnswer: c.studentAnswer || '',
          correctAnswer: c.correctAnswer || '',
          aiScore: c.aiScore != null ? Number(c.aiScore) : 0,
          aiConfidence: c.aiConfidence != null ? Number(c.aiConfidence) : null,
          teacherScore: c.teacherScore != null ? Number(c.teacherScore) : null,
          finalScore: c.finalScore != null ? Number(c.finalScore) : 0,
          status: c.scoreStatus || c.status || 'ai_scored',
          aiExplanation: c.aiExplanation || '',
        });
      }
      case 'user': {
        return Object.assign({}, c, {
          role: c.role || 'teacher',
          status: c.status || 'active',
          lastLogin: c.lastLogin || c.last_login || '',
        });
      }
      case 'importLog': {
        return Object.assign({}, c, {
          fileName: c.fileName || c.file_name || '',
          format: c.format || 'Word',
          totalQuestions: c.totalQuestions != null ? Number(c.totalQuestions) : 0,
          successCount: c.successCount != null ? Number(c.successCount) : 0,
          failCount: c.failCount != null ? Number(c.failCount) : 0,
          status: c.status || 'completed',
          createdAt: c.createdAt || c.created_at || '',
        });
      }
      case 'systemLog': {
        // 后端系统日志 {level, source, module, message, username, created_at} → Demo {user, action, target, time}
        return {
          user: c.username || c.user || c.userName || '--',
          action: c.module || c.source || c.level || c.action || '--',
          target: c.message || c.target || c.detail || '',
          time: c.createdAt || c.created_at || c.time || '',
        };
      }
      case 'category': {
        // Demo 期望 {id, name, count}
        return {
          id: c.id != null ? String(c.id) : '',
          name: c.name || '',
          count: c.count != null ? Number(c.count)
               : (c.questionCount != null ? Number(c.questionCount)
               : (c.paperCount != null ? Number(c.paperCount)
               : (c.taskCount != null ? Number(c.taskCount) : 0))),
        };
      }
      case 'tag': {
        // 后端 Tag {id, name, color} → Demo {id: string, name, color}
        return {
          id: c.id != null ? String(c.id) : '',
          name: c.name || '',
          color: c.color || 'blue',
        };
      }
      default:
        return c;
    }
  }

  // 从 {items, total} 响应中取 items 数组
  function takeItems(resp) {
    if (!resp) return null;
    if (Array.isArray(resp)) return resp;
    if (Array.isArray(resp.items)) return resp.items;
    if (Array.isArray(resp.data)) return resp.data;
    return null;
  }

  // ---- 主加载：并行拉取所有列表端点，映射后写入 DATA ----
  async function loadBackendData() {
    const loaded = [];
    const failed = [];
    // DATA 由 index.html 主脚本以 const 声明于全局词法环境，
    // 此处直接引用（loadBackendData 仅在登录后调用，DATA 已存在）。
    const D = (typeof DATA !== 'undefined') ? DATA : (window.DATA = window.DATA || {});

    // 全量加载：所有实体都从后端真实落表数据加载（去 mock，只显示真实数据）
    const endpoints = [
      { key: 'questions',               path: '/questions?page=1&page_size=200',  type: 'question' },
      { key: 'papers',                  path: '/papers?page=1&page_size=200',      type: 'paper' },
      { key: 'classes',                 path: '/classes?page=1&page_size=200',     type: 'class' },
      { key: 'students',                path: '/students?page=1&page_size=200',    type: 'student' },
      { key: 'teachers',                path: '/teachers?page=1&page_size=200',    type: 'teacher' },
      { key: 'tasks',                   path: '/exam-tasks?page=1&page_size=200',  type: 'task' },
      { key: 'users',                   path: '/users?page=1&page_size=200',       type: 'user' },
      { key: 'importLogs',              path: '/import-logs?page=1&page_size=200', type: 'importLog' },
      { key: 'systemLogs',               path: '/system-logs?page=1&page_size=200', type: 'systemLog' },
      { key: 'questionBankCategories',  path: '/categories?type=question',         type: 'category' },
      { key: 'paperCategories',         path: '/categories?type=paper',            type: 'category' },
      { key: 'taskCategories',          path: '/categories?type=task',             type: 'category' },
      { key: 'tags',                    path: '/tags',                             type: 'tag' },
      { key: 'meta',                    path: '/meta',                             type: 'meta' },
    ];

    const results = await Promise.allSettled(
      endpoints.map(e => apiGet(e.path))
    );

    endpoints.forEach((e, i) => {
      const r = results[i];
      if (r.status === 'fulfilled' && r.value) {
        if (e.type === 'meta') {
          // meta 是一个对象，含 subjects/grades/questionTypes/difficulties
          const m = r.value;
          if (Array.isArray(m.subjects) && m.subjects.length)      D.subjects = normalizeMetaList(m.subjects, 'subject');
          if (Array.isArray(m.grades) && m.grades.length)          D.grades = normalizeMetaList(m.grades, 'grade');
          if (Array.isArray(m.questionTypes) && m.questionTypes.length) D.questionTypes = normalizeMetaList(m.questionTypes, 'qtype');
          if (Array.isArray(m.difficulties) && m.difficulties.length)   D.difficulties = normalizeMetaList(m.difficulties, 'diff');
          loaded.push('meta');
        } else {
          const items = takeItems(r.value);
          if (Array.isArray(items)) {
            // 真实数据模式：空数组也覆盖（去 mock，后端空就是空）
            D[e.key] = items.map(it => mapBackendToDemoShape(it, e.type));
            loaded.push(e.key);
          } else {
            failed.push(e.key);
          }
        }
      } else {
        failed.push(e.key);
      }
    });

    // 答题卡需要按任务拉取，这里尝试拉取所有任务的答题卡汇总
    try {
      const taskIds = (D.tasks || []).map(t => t.id).filter(Boolean);
      if (taskIds.length) {
        const sheetResults = await Promise.allSettled(
          taskIds.slice(0, 20).map(id => apiGet('/exam-tasks/' + encodeURIComponent(id) + '/answer-sheets'))
        );
        const allSheets = [];
        sheetResults.forEach(sr => {
          if (sr.status === 'fulfilled' && sr.value) {
            const items = takeItems(sr.value);
            if (Array.isArray(items)) allSheets.push(...items);
          }
        });
        if (allSheets.length) {
          D.answerSheets = allSheets.map(s => mapBackendToDemoShape(s, 'answerSheet'));
          loaded.push('answerSheets');
        } else {
          failed.push('answerSheets');
        }
      } else {
        failed.push('answerSheets');
      }
    } catch (err) {
      failed.push('answerSheets');
    }

    // 每题评分 + 看板统计：为每张答题卡拉取逐题评分，并为任务/学生/班级预拉看板
    D.questionScores = [];
    try {
      const sheets = D.answerSheets || [];
      await Promise.all(sheets.map(async (as, idx) => {
        const sc = await apiGet('/exam-tasks/answer-sheets/' + encodeURIComponent(as.id) + '/scores');
        if (Array.isArray(sc)) {
          as.questionScores = sc.map(s => mapBackendToDemoShape(s, 'questionScore'));
          D.questionScores.push(...as.questionScores);
        }
      }));
      if (D.questionScores.length) loaded.push('questionScores');
      else failed.push('questionScores');
    } catch (err) {
      failed.push('questionScores');
    }

    // 预拉取任务/学生/班级看板（详情页同步读缓存）
    const dash = { task: {}, student: {}, class: {} };
    try {
      await Promise.all((D.tasks || []).map(async t => {
        const d = await apiGet('/exam-tasks/' + encodeURIComponent(t.id) + '/dashboard');
        if (d) dash.task[t.id] = camelKeys(d);
      }));
      await Promise.all((D.students || []).map(async s => {
        const d = await apiGet('/students/' + encodeURIComponent(s.id) + '/dashboard');
        if (d) dash.student[s.id] = camelKeys(d);
      }));
      await Promise.all((D.classes || []).map(async c => {
        const d = await apiGet('/classes/' + encodeURIComponent(c.id) + '/dashboard');
        if (d) dash.class[c.id] = camelKeys(d);
      }));
      D._dash = dash;
      loaded.push('dashboards');
    } catch (err) {
      failed.push('dashboards');
    }

    return { loaded, failed };
  }

  // ---- meta 列表归一化：兼容字符串数组与对象数组 ----
  // Demo 期望:
  //   subjects:    {id, code, name}
  //   grades:      {id, code, name, stage}
  //   questionTypes: {code, name, short}
  //   difficulties: {level, name}
  function normalizeMetaList(arr, kind) {
    if (!Array.isArray(arr)) return arr;
    return arr.map((item, i) => {
      if (typeof item === 'string') {
        if (kind === 'subject')   return { id: 's' + i, code: item, name: item };
        if (kind === 'grade')     return { id: 'g' + i, code: item, name: item, stage: 'middle' };
        if (kind === 'qtype')     return { code: item, name: item, short: item };
        if (kind === 'diff')      return { level: i + 1, name: item };
        return item;
      }
      // 对象：camelCase 后补默认
      const c = camelKeys(item);
      if (kind === 'subject') return { id: c.id || ('s' + i), code: c.code || c.name || '', name: c.name || c.code || '' };
      if (kind === 'grade')   return { id: c.id || ('g' + i), code: c.code || c.name || '', name: c.name || c.code || '', stage: c.stage || 'middle' };
      if (kind === 'qtype')   return { code: c.code || c.name || '', name: c.name || c.code || '', short: c.short || c.name || c.code || '' };
      if (kind === 'diff')    return { level: c.level != null ? Number(c.level) : (i + 1), name: c.name || ('L' + (i + 1)) };
      return c;
    });
  }

  // ---- 暴露到 window ----
  window.API_BASE = API_BASE;
  window.setApiToken = setApiToken;
  window.getApiToken = getApiToken;
  window.apiGet = apiGet;
  window.apiPost = apiPost;
  window.apiPatch = apiPatch;
  window.apiPut = apiPut;
  window.apiDelete = apiDelete;
  // 登录专用：返回 {status, ok, data}，区分 401(密码错) / 网络错误(后端未连接)
  window.apiLogin = async function (path, body) {
    try {
      const headers = { 'Content-Type': 'application/json', 'Accept': 'application/json' };
      const res = await fetch(API_BASE + path, {
        method: 'POST', headers, body: JSON.stringify(body || {})
      });
      if (res.status === 200 || res.status === 201) {
        return { status: res.status, ok: true, data: await res.json() };
      }
      let msg = '';
      try { msg = (await res.json()).message || msg; } catch (e) {}
      return { status: res.status, ok: false, data: null, message: msg };
    } catch (e) {
      return { status: 0, ok: false, data: null, message: 'network' };  // 0 = 网络异常
    }
  };
  window.mapBackendToDemoShape = mapBackendToDemoShape;
  window.loadBackendData = loadBackendData;
})();
