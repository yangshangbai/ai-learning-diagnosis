<template>
  <div class="page">
    <PageHeader title="组织管理" />
    <div class="page-body">
      <div style="display:flex;gap:6px;margin-bottom:10px;overflow-x:auto">
        <button
          v-for="t in ['年级', '班级', '老师', '学生']"
          :key="t"
          class="btn btn-sm"
          :class="tab === t ? 'btn-primary' : 'btn-outline'"
          @click="tab = t"
        >{{ t }}</button>
      </div>

      <!-- ==================== 年级 Tab ==================== -->
      <div v-if="tab === '年级'">
        <div v-if="grades.length === 0" style="text-align:center;color:var(--gray-400);padding:20px">暂无年级</div>
        <div v-for="g in grades" :key="g.id" class="card" style="display:flex;justify-content:space-between;align-items:center">
          <div>
            <div style="font-weight:600">{{ g.name }}</div>
            <div style="font-size:11px;color:var(--gray-400)">
              班级：{{ classCountByGrade(g) }}个
              <span v-if="g.sort !== undefined"> · 排序：{{ g.sort }}</span>
            </div>
          </div>
          <div style="display:flex;gap:4px">
            <button class="btn btn-sm btn-outline" @click="openGradeModal(g)">编辑</button>
            <button class="btn btn-sm btn-outline" style="color:var(--danger)" @click="deleteGrade(g)">删除</button>
          </div>
        </div>
        <!-- spacer for fixed add bar -->
        <div style="height:60px"></div>
      </div>

      <!-- ==================== 班级 Tab ==================== -->
      <div v-if="tab === '班级'">
        <div style="margin-bottom:8px">
          <select class="input select" v-model="classGradeFilter" style="width:100%">
            <option value="">全部年级</option>
            <option v-for="g in grades" :value="g.id" :key="g.id">{{ g.name }}</option>
          </select>
        </div>
        <div v-if="filteredClasses.length === 0" style="text-align:center;color:var(--gray-400);padding:20px">暂无班级</div>
        <div v-for="c in filteredClasses" :key="c.id" class="card" style="display:flex;justify-content:space-between;align-items:center">
          <div>
            <div style="font-weight:600">{{ c.name }}</div>
            <div style="font-size:11px;color:var(--gray-400)">
              {{ c.grade_name || getGradeName(c.grade_id || c.grade) }}
              <span v-if="c.student_count !== undefined"> · {{ c.student_count }}名学生</span>
            </div>
          </div>
          <div style="display:flex;gap:4px">
            <button class="btn btn-sm btn-outline" @click="openClassModal(c)">编辑</button>
            <button class="btn btn-sm btn-outline" style="color:var(--danger)" @click="deleteClass(c)">删除</button>
          </div>
        </div>
        <div style="height:60px"></div>
      </div>

      <!-- ==================== 老师 Tab ==================== -->
      <div v-if="tab === '老师'">
        <div v-if="teachers.length === 0" style="text-align:center;color:var(--gray-400);padding:20px">暂无老师</div>
        <div v-for="t in teachers" :key="t.id" class="card" style="display:flex;align-items:center;gap:10px">
          <div :style="{ width:'40px',height:'40px',borderRadius:'50%',background: t.role === 'teacher' ? 'var(--primary)' : 'var(--gray-500)', color:'#fff',display:'flex',alignItems:'center',justifyContent:'center',fontWeight:'600',fontSize:'16px' }">{{ (t.name || '?')[0] }}</div>
          <div style="flex:1">
            <div style="font-weight:600">{{ t.name }}</div>
            <div style="font-size:11px;color:var(--gray-400)">{{ roleLabelText(t.role) }} · {{ t.phone }}</div>
          </div>
          <div style="display:flex;gap:4px">
            <button class="btn btn-sm btn-outline" @click="openTeacherModal(t)">编辑</button>
            <button v-if="t.role === 'teacher'" class="btn btn-sm btn-outline" style="color:var(--danger)" @click="deleteTeacher(t)">删除</button>
          </div>
        </div>
        <div style="height:60px"></div>
      </div>

      <!-- ==================== 学生 Tab ==================== -->
      <div v-if="tab === '学生'">
        <div style="margin-bottom:8px;display:flex;gap:6px">
          <select class="input select" v-model="stuGradeFilter" style="flex:1">
            <option value="">全部年级</option>
            <option v-for="g in grades" :value="g.id" :key="g.id">{{ g.name }}</option>
          </select>
          <select class="input select" v-model="stuClassFilter" style="flex:1">
            <option value="">全部班级</option>
            <option v-for="c in availableClasses" :value="c.id" :key="c.id">{{ c.name }}</option>
          </select>
        </div>
        <div v-if="filteredStudents.length === 0" style="text-align:center;color:var(--gray-400);padding:20px">暂无学生</div>
        <div v-for="s in filteredStudents" :key="s.id" class="card" style="display:flex;align-items:center;gap:10px">
          <div :style="{ width:'36px',height:'36px',borderRadius:'50%',background: masteryColor(s.mastery || 50), color:'#fff',display:'flex',alignItems:'center',justifyContent:'center',fontWeight:'700',fontSize:'14px' }">{{ (s.name || '?')[0] }}</div>
          <div style="flex:1">
            <div style="font-weight:500">{{ s.name }}</div>
            <div style="font-size:11px;color:var(--gray-400)">
              {{ s.class_name || s.className || '' }} · 掌握度{{ s.mastery || 50 }}%
            </div>
          </div>
          <span class="tag" :class="masteryTagClass(s.mastery || 50)">{{ masteryLabel(s.mastery || 50) }}</span>
          <div style="display:flex;gap:4px;margin-left:4px">
            <button class="btn btn-sm btn-outline" @click="openStudentModal(s)">编辑</button>
            <button class="btn btn-sm btn-outline" style="color:var(--danger)" @click="deleteStudent(s)">删除</button>
          </div>
        </div>
        <div style="height:60px"></div>
      </div>

      <!-- ==================== Grade Create/Edit Modal ==================== -->
      <CrudModal :show="showGradeModal" :title="editingGrade ? '编辑年级' : '添加年级'" @close="showGradeModal = false" @save="saveGrade">
        <div class="input-group">
          <label>年级名称 <span style="color:var(--danger)">*</span></label>
          <input class="input" v-model="gradeForm.name" placeholder="如：五年级" />
        </div>
      </CrudModal>

      <!-- ==================== Class Create/Edit Modal ==================== -->
      <CrudModal :show="showClassModal" :title="editingClass ? '编辑班级' : '添加班级'" @close="showClassModal = false" @save="saveClass">
        <div class="input-group">
          <label>班级名称 <span style="color:var(--danger)">*</span></label>
          <input class="input" v-model="classForm.name" placeholder="如：五(3)班" />
        </div>
        <div class="input-group">
          <label>年级 <span style="color:var(--danger)">*</span></label>
          <select class="input select" v-model="classForm.grade">
            <option v-for="g in grades" :value="g.id" :key="g.id">{{ g.name }}</option>
          </select>
        </div>
        <div class="input-group">
          <label>排序</label>
          <input class="input" type="number" v-model.number="classForm.sort" placeholder="数字越小越靠前" />
        </div>
      </CrudModal>

      <!-- ==================== Teacher Create/Edit Modal ==================== -->
      <CrudModal :show="showTeacherModal" :title="editingTeacher ? '编辑老师' : '添加老师'" @close="showTeacherModal = false" @save="saveTeacher">
        <div class="input-group">
          <label>姓名 <span style="color:var(--danger)">*</span></label>
          <input class="input" v-model="teacherForm.name" placeholder="老师姓名" />
        </div>
        <div class="input-group">
          <label>手机号 <span style="color:var(--danger)">*</span></label>
          <input class="input" v-model="teacherForm.phone" placeholder="手机号" />
        </div>
        <div class="input-group">
          <label>密码<span v-if="editingTeacher">（留空则不修改）</span><span v-else> <span style="color:var(--danger)">*</span></span></label>
          <input class="input" type="password" v-model="teacherForm.password" placeholder="密码" />
        </div>
        <div class="input-group">
          <label>角色 <span style="color:var(--danger)">*</span></label>
          <select class="input select" v-model="teacherForm.role">
            <option v-for="r in roleOptions" :value="r.value" :key="r.value">{{ r.label }}</option>
          </select>
        </div>
        <div class="input-group">
          <label>年级</label>
          <div class="checkbox-group">
            <label v-for="g in grades" :key="g.id" class="checkbox-item">
              <input type="checkbox" :value="g.id" v-model="teacherForm.grade_ids" />
              <span>{{ g.name }}</span>
            </label>
          </div>
        </div>
        <div class="input-group">
          <label>学科</label>
          <div class="checkbox-group">
            <label v-for="s in subjectOptions" :key="s.id" class="checkbox-item">
              <input type="checkbox" :value="s.id" v-model="teacherForm.subjects" />
              <span>{{ s.name }}</span>
            </label>
          </div>
        </div>
        <div class="input-group">
          <label>负责班级</label>
          <div class="checkbox-group">
            <label v-for="c in classes" :key="c.id" class="checkbox-item">
              <input type="checkbox" :value="c.id" v-model="teacherForm.class_ids" />
              <span>{{ c.name }}</span>
            </label>
          </div>
        </div>
      </CrudModal>

      <!-- ==================== Student Create/Edit Modal ==================== -->
      <CrudModal :show="showStudentModal" :title="editingStudent ? '编辑学生' : '添加学生'" @close="showStudentModal = false" @save="saveStudent">
        <div class="input-group">
          <label>姓名 <span style="color:var(--danger)">*</span></label>
          <input class="input" v-model="studentForm.name" placeholder="学生姓名" />
        </div>
        <div class="input-group">
          <label>班级 <span style="color:var(--danger)">*</span></label>
          <select class="input select" v-model="studentForm.class_id">
            <option disabled value="">请选择班级</option>
            <option v-for="c in classes" :value="c.id" :key="c.id">{{ c.name }}</option>
          </select>
        </div>
        <div class="input-group">
          <label>掌握度：{{ studentForm.mastery }}%</label>
          <input class="input" type="range" min="0" max="100" v-model.number="studentForm.mastery" style="padding:0;height:auto" />
        </div>
        <div class="input-group">
          <label>趋势</label>
          <select class="input select" v-model="studentForm.trend">
            <option v-for="o in trendOptions" :value="o.value" :key="o.value">{{ o.label }}</option>
          </select>
        </div>
        <div class="input-group">
          <label>薄弱点（逗号分隔）</label>
          <input class="input" v-model="studentForm.weaknesses" placeholder="如：勾股定理,分数运算" />
        </div>
      </CrudModal>
    </div>

    <!-- Fixed Add Button Bar — always visible above BottomNav -->
    <div class="fixed-add-bar">
      <button class="btn btn-primary btn-block" @click="handleAddClick">
        + 添加{{ tab }}
      </button>
    </div>

    <BottomNav :items="navItems" active="org" @nav="onNav" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import PageHeader from '@/components/PageHeader.vue'
import BottomNav from '@/components/BottomNav.vue'
import CrudModal from '@/components/CrudModal.vue'
import { classesAPI } from '@/api/classes'
import { studentsAPI } from '@/api/students'
import { teachersAPI } from '@/api/teachers'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'
import { useReferenceStore } from '@/stores/reference'
import { icons } from '@/utils/icons'
import { roleLabel } from '@/utils/helpers'
import { ROLES, TREND_OPTIONS, SUBJECTS } from '@/utils/constants'

const router = useRouter()
const authStore = useAuthStore()
const appStore = useAppStore()
const refStore = useReferenceStore()

const user = computed(() => authStore.user || JSON.parse(localStorage.getItem('user') || 'null'))
const role = computed(() => user.value?.role || 'admin')

const tab = ref('年级')
const classGradeFilter = ref('')
const stuGradeFilter = ref('')
const stuClassFilter = ref('')

const grades = ref([])
const classes = ref([])
const teachers = ref([])
const students = ref([])

// ── Grade modal state ──
const showGradeModal = ref(false)
const editingGrade = ref(null)
const gradeForm = ref({ name: '' })

// ── Class modal state ──
const showClassModal = ref(false)
const editingClass = ref(null)
const classForm = ref({ name: '', grade: '', sort: 0 })

// ── Teacher modal state ──
const showTeacherModal = ref(false)
const editingTeacher = ref(null)
const teacherForm = ref({ name: '', phone: '', password: '', role: 'teacher', grade_ids: [], subjects: [], class_ids: [] })

// ── Student modal state ──
const showStudentModal = ref(false)
const editingStudent = ref(null)
const studentForm = ref({ name: '', class_id: '', mastery: 50, trend: 'stable', weaknesses: '' })

// ── Options ──
const roleOptions = ROLES
const SUBJECT_ID_MAP = { '数学': 'math', '物理': 'physics', '化学': 'chemistry' }
const subjectOptions = computed(() => SUBJECTS.map(name => ({ id: SUBJECT_ID_MAP[name] || name, name })))
const trendOptions = TREND_OPTIONS

// ── Navigation ──
const adminNav = [
  { key: 'dashboard', label: '总览', icon: icons.dashboard },
  { key: 'org', label: '组织', icon: icons.org },
  { key: 'tasks', label: '任务', icon: icons.tasks },
  { key: 'diagnosis', label: '诊断', icon: icons.diagnosis },
  { key: 'me', label: '我的', icon: icons.home },
]

const superNav = [
  { key: 'dashboard', label: '总览', icon: icons.dashboard },
  { key: 'org', label: '组织', icon: icons.org },
  { key: 'system', label: '系统', icon: icons.settings },
  { key: 'diagnosis', label: '诊断', icon: icons.diagnosis },
  { key: 'me', label: '我的', icon: icons.home },
]

const navItems = computed(() => role.value === 'super' ? superNav : adminNav)

// ── Computed ──
const filteredClasses = computed(() => {
  if (!classGradeFilter.value) return classes.value
  return classes.value.filter(c => c.grade === classGradeFilter.value || c.grade_id === classGradeFilter.value)
})

const availableClasses = computed(() => {
  if (!stuGradeFilter.value) return classes.value
  return classes.value.filter(c => c.grade === stuGradeFilter.value || c.grade_id === stuGradeFilter.value)
})

const filteredStudents = computed(() => {
  let list = students.value
  if (stuGradeFilter.value) {
    list = list.filter(s => s.grade === stuGradeFilter.value || s.grade_id === stuGradeFilter.value)
  }
  if (stuClassFilter.value) {
    list = list.filter(s => s.class_id === stuClassFilter.value || s.classId === stuClassFilter.value)
  }
  return list
})

// ── Helpers ──
function roleLabelText(r) {
  return roleLabel(r)
}

function getGradeName(gradeId) {
  if (!gradeId) return ''
  const g = grades.value.find(x => x.id === gradeId)
  return g ? g.name : gradeId
}

function classCountByGrade(g) {
  const id = g.id || g
  return classes.value.filter(c => c.grade === id || c.grade_id === id).length
}

function masteryColor(m) {
  if (m >= 80) return '#10B981'
  if (m >= 60) return '#F59E0B'
  return '#EF4444'
}

function masteryTagClass(m) {
  if (m >= 80) return 'tag-green'
  if (m >= 60) return 'tag-yellow'
  return 'tag-red'
}

function masteryLabel(m) {
  if (m >= 80) return '优秀'
  if (m >= 60) return '一般'
  return '薄弱'
}

function showToast(msg) {
  appStore.showToast(msg)
}

// ── API fetch ──
async function fetchGrades() {
  try {
    const res = await classesAPI.getGrades()
    grades.value = Array.isArray(res) ? res : (res?.data || [])
  } catch (e) {
    console.warn('Failed to fetch grades:', e)
  }
}

async function fetchClasses() {
  try {
    const res = await classesAPI.getList()
    classes.value = res?.items || res?.data || (Array.isArray(res) ? res : [])
  } catch (e) {
    console.warn('Failed to fetch classes:', e)
  }
}

async function fetchTeachers() {
  try {
    const res = await teachersAPI.getList()
    teachers.value = res?.items || res?.data || (Array.isArray(res) ? res : [])
  } catch (e) {
    console.warn('Failed to fetch teachers:', e)
  }
}

async function fetchStudents() {
  try {
    const res = await studentsAPI.getList()
    students.value = res?.items || res?.data || (Array.isArray(res) ? res : [])
  } catch (e) {
    console.warn('Failed to fetch students:', e)
  }
}

function onNav(key) {
  const map = {
    dashboard: '/admin/dashboard',
    org: '/admin/org',
    tasks: '/admin/tasks',
    diagnosis: '/admin/diagnosis',
    system: '/admin/system',
    me: '/admin/me'
  }
  if (map[key]) router.push(map[key])
}

function handleAddClick() {
  if (tab.value === '年级') openGradeModal(null)
  else if (tab.value === '班级') openClassModal(null)
  else if (tab.value === '老师') openTeacherModal(null)
  else if (tab.value === '学生') openStudentModal(null)
}

// ════════════════════════════════════════════
//  GRADE  CRUD
// ════════════════════════════════════════════
function openGradeModal(g) {
  if (g) {
    editingGrade.value = g
    gradeForm.value = { name: g.name || '' }
  } else {
    editingGrade.value = null
    gradeForm.value = { name: '' }
  }
  showGradeModal.value = true
}

async function saveGrade() {
  if (!gradeForm.value.name.trim()) {
    showToast('请输入年级名称')
    return
  }
  try {
    if (editingGrade.value) {
      await classesAPI.updateGrade(editingGrade.value.id, {
        name: gradeForm.value.name.trim(),
        sort_order: editingGrade.value.sort_order ?? editingGrade.value.sort ?? 0
      })
    } else {
      await classesAPI.createGrade({
        name: gradeForm.value.name.trim(),
        sort_order: grades.value.length + 1
      })
    }
    showGradeModal.value = false
    await fetchGrades()
    await refStore.refresh()
    showToast(editingGrade.value ? '年级已更新' : '年级已添加')
  } catch (e) {
    showToast('操作失败: ' + (e?.response?.data?.detail || e?.message || ''))
  }
}

async function deleteGrade(g) {
  if (!confirm('确定删除年级「' + g.name + '」？此操作不可撤销。')) return
  try {
    await classesAPI.removeGrade(g.id)
    await fetchGrades()
    await refStore.refresh()
    showToast('已删除')
  } catch (e) {
    showToast('删除失败')
  }
}

// ════════════════════════════════════════════
//  CLASS  CRUD
// ════════════════════════════════════════════
function openClassModal(c) {
  if (c) {
    editingClass.value = c
    classForm.value = { name: c.name || '', grade: c.grade_id || c.grade || '', sort: c.sort_order ?? c.sort ?? 0 }
  } else {
    editingClass.value = null
    classForm.value = { name: '', grade: grades.value[0]?.id || '', sort: 0 }
  }
  showClassModal.value = true
}

async function saveClass() {
  if (!classForm.value.name.trim()) {
    showToast('请输入班级名称')
    return
  }
  if (!classForm.value.grade) {
    showToast('请选择年级')
    return
  }
  try {
    if (editingClass.value) {
      await classesAPI.update(editingClass.value.id, {
        name: classForm.value.name.trim(),
        grade_id: classForm.value.grade
      })
    } else {
      await classesAPI.create({
        name: classForm.value.name.trim(),
        grade_id: classForm.value.grade
      })
    }
    showClassModal.value = false
    await fetchClasses()
    showToast(editingClass.value ? '班级已更新' : '班级已添加')
  } catch (e) {
    showToast('操作失败')
  }
}

async function deleteClass(c) {
  if (!confirm('确定删除班级「' + c.name + '」？此操作不可撤销。')) return
  try {
    await classesAPI.remove(c.id)
    await fetchClasses()
    showToast('已删除')
  } catch (e) {
    showToast('删除失败')
  }
}

// ════════════════════════════════════════════
//  TEACHER  CRUD
// ════════════════════════════════════════════
function openTeacherModal(t) {
  if (t) {
    editingTeacher.value = t
    // Map backend fields to form: grades (names) → grade_ids, subjects (names) → subject codes
    const backendGrades = t.grades || t.grade_names || []
    const backendSubjects = t.subjects || t.subject_names || []
    teacherForm.value = {
      name: t.name || '',
      phone: t.phone || '',
      password: '',
      role: t.role || 'teacher',
      grade_ids: backendGrades.map(name => grades.value.find(g => g.name === name)?.id).filter(Boolean),
      subjects: backendSubjects.map(name => SUBJECT_ID_MAP[name] || name).filter(Boolean),
      class_ids: t.class_ids || t.classes || []
    }
  } else {
    editingTeacher.value = null
    teacherForm.value = { name: '', phone: '', password: '', role: 'teacher', grade_ids: [], subjects: [], class_ids: [] }
  }
  showTeacherModal.value = true
}

async function saveTeacher() {
  if (!teacherForm.value.name.trim()) { showToast('请输入姓名'); return }
  if (!teacherForm.value.phone.trim()) { showToast('请输入手机号'); return }
  if (!editingTeacher.value && !teacherForm.value.password) { showToast('请输入密码'); return }
  if (!/^1[3-9]\d{9}$/.test(teacherForm.value.phone.trim())) { showToast('手机号格式不正确'); return }

  // Map frontend form fields to backend API field names
  // grade_ids (checkbox values) → grades (array of grade names)
  const gradeNames = teacherForm.value.grade_ids
    .map(gid => grades.value.find(g => g.id === gid)?.name)
    .filter(Boolean)
  // subjects (checkbox values = subject codes) → subject names
  const subjectNames = teacherForm.value.subjects
    .map(code => SUBJECTS.find(s => SUBJECT_ID_MAP[s] === code) || code)
    .filter(Boolean)

  const payload = {
    name: teacherForm.value.name.trim(),
    phone: teacherForm.value.phone.trim(),
    role: teacherForm.value.role,
    grades: gradeNames,
    subjects: subjectNames,
    class_ids: teacherForm.value.class_ids,
  }
  if (teacherForm.value.password) {
    payload.password = teacherForm.value.password
  }

  try {
    if (editingTeacher.value) {
      await teachersAPI.update(editingTeacher.value.id, payload)
    } else {
      await teachersAPI.create(payload)
    }
    showTeacherModal.value = false
    await fetchTeachers()
    showToast(editingTeacher.value ? '老师已更新' : '老师已添加')
  } catch (e) {
    showToast('操作失败: ' + (e?.response?.data?.detail || e?.message || ''))
  }
}

async function deleteTeacher(t) {
  if (!confirm('确定删除老师「' + t.name + '」？此操作不可撤销。')) return
  try {
    await teachersAPI.remove(t.id)
    await fetchTeachers()
    showToast('已删除')
  } catch (e) {
    showToast('删除失败')
  }
}

// ════════════════════════════════════════════
//  STUDENT  CRUD
// ════════════════════════════════════════════
function openStudentModal(s) {
  if (s) {
    editingStudent.value = s
    studentForm.value = {
      name: s.name || '',
      class_id: s.class_id || s.classId || '',
      mastery: s.mastery ?? 50,
      trend: s.trend || 'stable',
      weaknesses: Array.isArray(s.weaknesses) ? s.weaknesses.join(',') : (s.weaknesses || '')
    }
  } else {
    editingStudent.value = null
    studentForm.value = { name: '', class_id: '', mastery: 50, trend: 'stable', weaknesses: '' }
  }
  showStudentModal.value = true
}

async function saveStudent() {
  if (!studentForm.value.name.trim()) { showToast('请输入姓名'); return }
  if (!studentForm.value.class_id) { showToast('请选择班级'); return }

  const weaknessesArr = studentForm.value.weaknesses
    ? studentForm.value.weaknesses.split(',').map(s => s.trim()).filter(Boolean)
    : []

  const payload = {
    name: studentForm.value.name.trim(),
    class_id: studentForm.value.class_id,
    mastery: studentForm.value.mastery,
    trend: studentForm.value.trend,
    weaknesses: weaknessesArr,
  }

  try {
    if (editingStudent.value) {
      await studentsAPI.update(editingStudent.value.id, payload)
    } else {
      await studentsAPI.create(payload)
    }
    showStudentModal.value = false
    await fetchStudents()
    showToast(editingStudent.value ? '学生已更新' : '学生已添加')
  } catch (e) {
    showToast('操作失败')
  }
}

async function deleteStudent(s) {
  if (!confirm('确定删除学生「' + s.name + '」？此操作不可撤销。')) return
  try {
    await studentsAPI.remove(s.id)
    await fetchStudents()
    showToast('已删除')
  } catch (e) {
    showToast('删除失败')
  }
}

// ── Init ──
onMounted(() => {
  fetchGrades()
  fetchClasses()
  fetchTeachers()
  fetchStudents()
})
</script>

<style scoped>
.input-group {
  margin-bottom: 12px;
}
.input-group label {
  display: block;
  font-size: 12px;
  color: var(--gray-500);
  margin-bottom: 4px;
}
.input {
  width: 100%;
  height: 40px;
  border: 1px solid var(--gray-200);
  border-radius: var(--radius-sm);
  padding: 0 12px;
  font-size: 14px;
  box-sizing: border-box;
}
.select {
  appearance: auto;
}
.checkbox-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.checkbox-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: var(--gray-700);
  cursor: pointer;
}
.checkbox-item input[type="checkbox"] {
  margin: 0;
}
.fixed-add-bar {
  position: fixed;
  bottom: 62px;  /* above BottomNav (~56px) */
  left: 50%;
  transform: translateX(-50%);
  width: 100%;
  max-width: 420px;
  background: #fff;
  border-top: 1px solid var(--gray-200);
  padding: 8px 16px;
  z-index: 90;
  box-shadow: 0 -2px 8px rgba(0,0,0,.06);
}
.fixed-add-bar .btn {
  height: 44px;
  font-size: 15px;
  font-weight: 600;
}
</style>
