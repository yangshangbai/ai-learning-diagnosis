<template>
  <div class="page">
    <PageHeader title="权限配置" :showBack="true" backPath="/admin/system" />

    <div class="page-body">
      <div class="notice">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
        <span>权限配置当前保存在本地浏览器，云端部署后将迁移至数据库</span>
      </div>

      <!-- Role Cards -->
      <div v-for="role in roles" :key="role.key" class="card">
        <div class="role-header" @click="toggleRole(role.key)">
          <div class="role-info">
            <span class="role-icon">{{ role.icon }}</span>
            <div>
              <div class="role-name">{{ role.label }}</div>
              <div class="role-desc">{{ role.desc }}</div>
            </div>
          </div>
          <span class="expand-icon" :class="{ expanded: expandedRoles.includes(role.key) }">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
          </span>
        </div>

        <div v-if="expandedRoles.includes(role.key)" class="perm-list">
          <div v-for="perm in permissionGroups" :key="perm.key" class="perm-group">
            <div class="perm-group-header">
              <span class="perm-group-name">{{ perm.label }}</span>
              <label class="toggle-all" @click.stop>
                <input
                  type="checkbox"
                  :checked="isGroupAllChecked(role.key, perm)"
                  @change="toggleGroupAll(role.key, perm, $event)"
                />
                <span class="toggle-all-label">全选</span>
              </label>
            </div>
            <div class="perm-actions">
              <div
                v-for="action in perm.actions"
                :key="action.key"
                class="switch-item"
                @click.stop>
                <span class="switch-label">{{ action.label }}</span>
                <label class="switch">
                  <input
                    type="checkbox"
                    :checked="getPermValue(role.key, perm.key, action.key)"
                    @change="setPerm(role.key, perm.key, action.key, $event.target.checked)"
                  />
                  <span class="slider"></span>
                </label>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Save Button -->
      <div class="save-bar">
        <button class="btn btn-primary btn-block" @click="saveConfig">
          保存配置
        </button>
      </div>
    </div>

    <BottomNav :items="navItems" active="system" @nav="onNav" />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import PageHeader from '@/components/PageHeader.vue'
import BottomNav from '@/components/BottomNav.vue'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'
import { icons } from '@/utils/icons'

const router = useRouter()
const authStore = useAuthStore()
const appStore = useAppStore()

const user = computed(() => authStore.user || JSON.parse(localStorage.getItem('user') || 'null'))

const roles = [
  { key: 'teacher', label: '教师', desc: '一线授课老师', icon: '👩‍🏫' },
  { key: 'admin', label: '管理员', desc: '校区管理员', icon: '🏫' },
  { key: 'research', label: '教研员', desc: '教研管理员', icon: '🔬' },
  { key: 'super', label: '超级管理员', desc: '系统最高权限', icon: '🛡️' }
]

const permissionGroups = [
  {
    key: 'students',
    label: '学生管理',
    actions: [
      { key: 'view', label: '查看' },
      { key: 'create', label: '新增' },
      { key: 'edit', label: '编辑' },
      { key: 'delete', label: '删除' }
    ]
  },
  {
    key: 'tasks',
    label: '任务管理',
    actions: [
      { key: 'view', label: '查看' },
      { key: 'create', label: '新增' },
      { key: 'edit', label: '编辑' },
      { key: 'delete', label: '删除' },
      { key: 'run_ai', label: '运行AI' }
    ]
  },
  {
    key: 'knowledge',
    label: '知识点管理',
    actions: [
      { key: 'view', label: '查看' },
      { key: 'create', label: '新增' },
      { key: 'edit', label: '编辑' },
      { key: 'delete', label: '删除' }
    ]
  },
  {
    key: 'qbank',
    label: '题库管理',
    actions: [
      { key: 'view', label: '查看' },
      { key: 'create', label: '新增' },
      { key: 'edit', label: '编辑' },
      { key: 'delete', label: '删除' }
    ]
  },
  {
    key: 'diagnosis',
    label: '诊断批改',
    actions: [
      { key: 'view', label: '查看' },
      { key: 'confirm', label: '确认' },
      { key: 'batch_confirm', label: '批量确认' }
    ]
  },
  {
    key: 'exercise',
    label: '练习计划',
    actions: [
      { key: 'view', label: '查看' },
      { key: 'create', label: '新增' },
      { key: 'edit', label: '编辑' },
      { key: 'delete', label: '删除' }
    ]
  },
  {
    key: 'system',
    label: '系统管理',
    actions: [
      { key: 'audit_log', label: '操作日志' },
      { key: 'remote', label: '远程协助' },
      { key: 'permissions', label: '权限配置' }
    ]
  },
  {
    key: 'dashboard',
    label: '数据总览',
    actions: [
      { key: 'view', label: '查看' }
    ]
  }
]

// Default permissions per role
const defaultPerms = {
  teacher: {
    students: { view: true, create: false, edit: false, delete: false },
    tasks: { view: true, create: true, edit: true, delete: false, run_ai: true },
    knowledge: { view: false, create: false, edit: false, delete: false },
    qbank: { view: false, create: false, edit: false, delete: false },
    diagnosis: { view: true, confirm: true, batch_confirm: false },
    exercise: { view: true, create: true, edit: true, delete: false },
    system: { audit_log: false, remote: false, permissions: false },
    dashboard: { view: true }
  },
  admin: {
    students: { view: true, create: true, edit: true, delete: false },
    tasks: { view: true, create: true, edit: true, delete: true, run_ai: true },
    knowledge: { view: false, create: false, edit: false, delete: false },
    qbank: { view: false, create: false, edit: false, delete: false },
    diagnosis: { view: true, confirm: true, batch_confirm: true },
    exercise: { view: true, create: true, edit: true, delete: true },
    system: { audit_log: false, remote: false, permissions: false },
    dashboard: { view: true }
  },
  research: {
    students: { view: true, create: false, edit: false, delete: false },
    tasks: { view: true, create: true, edit: true, delete: false, run_ai: true },
    knowledge: { view: true, create: true, edit: true, delete: true },
    qbank: { view: true, create: true, edit: true, delete: true },
    diagnosis: { view: true, confirm: true, batch_confirm: true },
    exercise: { view: true, create: true, edit: true, delete: true },
    system: { audit_log: false, remote: false, permissions: false },
    dashboard: { view: true }
  },
  super: {
    students: { view: true, create: true, edit: true, delete: true },
    tasks: { view: true, create: true, edit: true, delete: true, run_ai: true },
    knowledge: { view: true, create: true, edit: true, delete: true },
    qbank: { view: true, create: true, edit: true, delete: true },
    diagnosis: { view: true, confirm: true, batch_confirm: true },
    exercise: { view: true, create: true, edit: true, delete: true },
    system: { audit_log: true, remote: true, permissions: true },
    dashboard: { view: true }
  }
}

const expandedRoles = ref(['super'])
const permState = reactive(loadFromStorage())

function loadFromStorage() {
  try {
    const saved = localStorage.getItem('perm_config')
    return saved ? JSON.parse(saved) : {}
  } catch {
    return {}
  }
}

function saveToStorage() {
  localStorage.setItem('perm_config', JSON.stringify(permState))
}

function toggleRole(roleKey) {
  const idx = expandedRoles.value.indexOf(roleKey)
  if (idx >= 0) {
    expandedRoles.value.splice(idx, 1)
  } else {
    expandedRoles.value.push(roleKey)
  }
}

function getPermValue(roleKey, groupKey, actionKey) {
  // Check custom state first, then defaults
  if (permState[roleKey]?.[groupKey]?.[actionKey] !== undefined) {
    return permState[roleKey][groupKey][actionKey]
  }
  return defaultPerms[roleKey]?.[groupKey]?.[actionKey] ?? false
}

function setPerm(roleKey, groupKey, actionKey, value) {
  if (!permState[roleKey]) permState[roleKey] = {}
  if (!permState[roleKey][groupKey]) permState[roleKey][groupKey] = {}
  permState[roleKey][groupKey][actionKey] = value
}

function isGroupAllChecked(roleKey, group) {
  return group.actions.every(a => getPermValue(roleKey, group.key, a.key))
}

function toggleGroupAll(roleKey, group, event) {
  const checked = event.target.checked
  group.actions.forEach(a => {
    setPerm(roleKey, group.key, a.key, checked)
  })
}

function saveConfig() {
  saveToStorage()
  appStore.showToast('权限配置已保存')
}

const navItems = [
  { key: 'dashboard', label: '总览', icon: icons.dashboard },
  { key: 'org', label: '组织', icon: icons.org },
  { key: 'system', label: '系统', icon: icons.settings },
  { key: 'diagnosis', label: '诊断', icon: icons.diagnosis },
  { key: 'me', label: '我的', icon: icons.home }
]

function onNav(key) {
  const map = {
    dashboard: '/admin/dashboard',
    org: '/admin/org',
    diagnosis: '/admin/diagnosis',
    system: '/admin/system',
    me: '/admin/me'
  }
  if (map[key]) router.push(map[key])
}

onMounted(() => {
  Object.assign(permState, loadFromStorage())
})
</script>

<style scoped>
.notice {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: var(--warning-light);
  border: 1px solid var(--warning);
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: var(--gray-700);
  margin-bottom: 12px;
}
.notice svg {
  flex-shrink: 0;
  color: var(--warning);
}

.role-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  user-select: none;
}
.role-info {
  display: flex;
  align-items: center;
  gap: 10px;
}
.role-icon {
  font-size: 24px;
}
.role-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--gray-900);
}
.role-desc {
  font-size: 11px;
  color: var(--gray-400);
}
.expand-icon {
  transition: transform .2s ease;
  color: var(--gray-400);
  display: flex;
}
.expand-icon.expanded {
  transform: rotate(180deg);
}

.perm-list {
  margin-top: 12px;
  border-top: 1px solid var(--gray-100);
  padding-top: 12px;
}
.perm-group {
  margin-bottom: 12px;
}
.perm-group:last-child {
  margin-bottom: 0;
}
.perm-group-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.perm-group-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--gray-700);
}
.toggle-all {
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
}
.toggle-all input {
  width: 14px;
  height: 14px;
  accent-color: var(--primary);
  cursor: pointer;
}
.toggle-all-label {
  font-size: 11px;
  color: var(--gray-500);
}

.perm-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.switch-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 6px 10px;
  background: var(--gray-50);
  border-radius: var(--radius-sm);
  min-width: 100px;
  flex: 1;
}
.switch-label {
  font-size: 12px;
  color: var(--gray-600);
}

/* Toggle Switch */
.switch {
  position: relative;
  display: inline-block;
  width: 36px;
  height: 20px;
  flex-shrink: 0;
}
.switch input {
  opacity: 0;
  width: 0;
  height: 0;
}
.slider {
  position: absolute;
  cursor: pointer;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: var(--gray-300);
  border-radius: 20px;
  transition: .2s;
}
.slider::before {
  content: '';
  position: absolute;
  height: 16px;
  width: 16px;
  left: 2px;
  bottom: 2px;
  background: #fff;
  border-radius: 50%;
  transition: .2s;
}
.switch input:checked + .slider {
  background: var(--primary);
}
.switch input:checked + .slider::before {
  transform: translateX(16px);
}

.save-bar {
  margin-top: 12px;
  margin-bottom: 60px;
}
.btn-block {
  width: 100%;
  justify-content: center;
}
</style>
