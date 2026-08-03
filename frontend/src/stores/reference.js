/**
 * Reference Data Store — API-driven grades, classes, subjects
 * Replaces hardcoded GRADES constant with dynamic API data.
 * All pages should use this store instead of constants.js GRADES.
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { classesAPI } from '@/api/classes'
import { GRADES as FALLBACK_GRADES, SUBJECTS as FALLBACK_SUBJECTS } from '@/utils/constants'
import { useAuthStore } from '@/stores/auth'

export const useReferenceStore = defineStore('reference', () => {
  const grades = ref([])           // [{id, name, sort_order}]
  const classes = ref([])          // [{id, name, grade_id, grade_name, ...}]
  const loaded = ref(false)
  const loading = ref(false)

  // ── Computed: grade names only (for select dropdowns) ──
  const gradeNames = computed(() => grades.value.map(g => g.name))

  // ── Computed: classes filtered by user's permission scope ──
  const userClasses = computed(() => {
    const auth = useAuthStore()
    const userClassIds = (auth.user?.classes || []).map(c => Number(c))
    if (!userClassIds.length) return classes.value  // admin/super sees all
    return classes.value.filter(c => userClassIds.includes(Number(c.id)))
  })

  // ── Computed: classes filtered by grade ──
  function classesByGrade(gradeName) {
    return classes.value.filter(c => c.grade_name === gradeName)
  }

  // ── Grade name → id mapping ──
  function gradeId(name) {
    const g = grades.value.find(x => x.name === name)
    return g ? g.id : null
  }

  function gradeName(id) {
    const g = grades.value.find(x => x.id === id)
    return g ? g.name : ''
  }

  // ── Fetch from API ──
  async function fetchAll() {
    if (loaded.value && grades.value.length > 0) return  // Already loaded
    loading.value = true
    try {
      const [gradeRes, classRes] = await Promise.allSettled([
        classesAPI.getGrades(),
        classesAPI.getList(),
      ])
      if (gradeRes.status === 'fulfilled') {
        const data = gradeRes.value
        grades.value = Array.isArray(data) ? data : (data?.data || [])
      } else {
        // Fallback: convert hardcoded names to objects
        grades.value = FALLBACK_GRADES.map((name, i) => ({ id: i + 1, name, sort_order: i + 1 }))
      }
      if (classRes.status === 'fulfilled') {
        const data = classRes.value
        classes.value = data?.items || data?.data || (Array.isArray(data) ? data : [])
      } else {
        classes.value = []
      }
      loaded.value = true
    } catch {
      grades.value = FALLBACK_GRADES.map((name, i) => ({ id: i + 1, name, sort_order: i + 1 }))
      classes.value = []
      loaded.value = true
    } finally {
      loading.value = false
    }
  }

  // ── Refresh (after CRUD operations) ──
  async function refresh() {
    loaded.value = false
    await fetchAll()
  }

  return {
    grades, classes, gradeNames, userClasses,
    loaded, loading,
    classesByGrade, gradeId, gradeName,
    fetchAll, refresh,
  }
})
