import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/login' },
  { path: '/login', name: 'Login', component: () => import('@/views/LoginPage.vue') },
  // Teacher routes
  { path: '/teacher/students', name: 'TeacherStudents', component: () => import('@/views/teacher/StudentList.vue'), meta: { role: 'teacher' } },
  { path: '/teacher/student/:id', name: 'TeacherStudentProfile', component: () => import('@/views/teacher/StudentProfile.vue'), meta: { role: 'teacher' } },
  { path: '/teacher/tasks', name: 'TeacherTasks', component: () => import('@/views/teacher/TaskList.vue'), meta: { role: 'teacher' } },
  { path: '/teacher/upload', name: 'TeacherUpload', component: () => import('@/views/teacher/UploadPaper.vue'), meta: { role: 'teacher' } },
  { path: '/teacher/grading/:taskId', name: 'TeacherGrading', component: () => import('@/views/teacher/GradingConfirm.vue'), meta: { role: 'teacher' } },
  { path: '/teacher/exercise', name: 'TeacherExercise', component: () => import('@/views/teacher/ExercisePlan.vue'), meta: { role: 'teacher' } },
  { path: '/teacher/report/:studentId', name: 'TeacherReport', component: () => import('@/views/teacher/StageReport.vue'), meta: { role: 'teacher' } },
  { path: '/teacher/me', name: 'TeacherMe', component: () => import('@/views/teacher/TeacherProfile.vue'), meta: { role: 'teacher' } },
  // Admin routes
  { path: '/admin/dashboard', name: 'AdminDashboard', component: () => import('@/views/admin/Dashboard.vue'), meta: { role: ['admin', 'super'] } },
  { path: '/admin/org', name: 'AdminOrg', component: () => import('@/views/admin/Organization.vue'), meta: { role: ['admin', 'super'] } },
  { path: '/admin/tasks', name: 'AdminTasks', component: () => import('@/views/admin/TaskManage.vue'), meta: { role: ['admin', 'super'] } },
  { path: '/admin/knowledge', name: 'AdminKnowledge', component: () => import('@/views/admin/KnowledgeTree.vue'), meta: { role: ['research', 'super'] } },
  { path: '/admin/qbank', name: 'AdminQBank', component: () => import('@/views/admin/QuestionBank.vue'), meta: { role: ['research', 'super'] } },
  { path: '/admin/question-sources', name: 'AdminQuestionSources', component: () => import('@/views/admin/QuestionSources.vue'), meta: { role: ['research', 'super'] } },
  { path: '/admin/ai', name: 'AdminAI', component: () => import('@/views/admin/AIAssistant.vue'), meta: { role: ['research', 'super'] } },
  { path: '/admin/diagnosis', name: 'AdminDiagnosis', component: () => import('@/views/admin/DiagnosisBoard.vue'), meta: { role: ['admin', 'research', 'super'] } },
  { path: '/admin/system', name: 'AdminSystem', component: () => import('@/views/admin/SystemManage.vue'), meta: { role: 'super' } },
  { path: '/admin/audit', name: 'AdminAudit', component: () => import('@/views/admin/AuditLog.vue'), meta: { role: 'super' } },
  { path: '/admin/remote', name: 'AdminRemote', component: () => import('@/views/admin/RemoteHelp.vue'), meta: { role: 'super' } },
  { path: '/admin/permissions', name: 'AdminPermissions', component: () => import('@/views/admin/PermissionConfig.vue'), meta: { role: 'super' } },
  { path: '/admin/ai-settings', name: 'AdminAISettings', component: () => import('@/views/admin/AISettings.vue'), meta: { role: 'super' } },
  { path: '/admin/logs', name: 'AdminLogs', component: () => import('@/views/admin/LogWeb.vue'), meta: { role: 'super' } },
  { path: '/admin/tasks/:id', name: 'AdminTaskDetail', component: () => import('@/views/admin/TaskDetail.vue'), meta: { role: ['admin', 'super', 'research'] } },
  { path: '/admin/me', name: 'AdminMe', component: () => import('@/views/admin/AdminProfile.vue'), meta: { role: ['admin', 'research', 'super'] } },
  // Redirects
  { path: '/teacher/home', redirect: '/teacher/students' },
  { path: '/admin/question-bank', redirect: '/admin/qbank' },
  { path: '/admin/ai-assistant', redirect: '/admin/ai' },
  { path: '/admin/audit-log', redirect: '/admin/audit' },
  { path: '/admin/remote-help', redirect: '/admin/remote' },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
  scrollBehavior() { return { top: 0 } }
})

// Navigation guard: check auth via localStorage
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  const role = localStorage.getItem('role')
  if (to.path !== '/login' && !token) {
    next('/login')
  } else if (to.meta.role) {
    const roles = Array.isArray(to.meta.role) ? to.meta.role : [to.meta.role]
    if (!roles.includes(role)) {
      if (role === 'teacher') next('/teacher/students')
      else if (['admin', 'research', 'super'].includes(role)) next('/admin/dashboard')
      else next('/login')
    } else {
      next()
    }
  } else {
    next()
  }
})

export default router
