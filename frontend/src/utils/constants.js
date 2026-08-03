// Reference data constants - single source of truth
// When the backend API is available, pages should prefer API data.
// These constants serve as fallbacks and for static enums.

export const GRADES = ['五年级', '六年级', '初一', '初二', '初三']

export const SUBJECTS = ['数学', '物理', '化学']

export const TASK_TYPES = [
  '日常作业', '周测', '阶段测', '期中模拟', '期末模拟', '专项练习', '订正检测'
]

export const DIFFICULTY_LEVELS = ['基础', '中等', '拔高']

export const QUESTION_TYPES = ['计算题', '应用题', '解答题', '填空题', '纠错题', '开放题']

export const ROLES = [
  { value: 'teacher', label: '教师' },
  { value: 'admin', label: '管理员' },
  { value: 'research', label: '教研员' },
  { value: 'super', label: '超级管理员' },
]

export const TREND_OPTIONS = [
  { value: 'up', label: '上升' },
  { value: 'down', label: '下降' },
  { value: 'stable', label: '平稳' },
]

export const VERDICT_OPTIONS = [
  { value: 'correct', label: '正确' },
  { value: 'incorrect', label: '错误' },
  { value: 'partially_correct', label: '部分正确' },
  { value: 'uncertain', label: '不确定' },
]

export const ERROR_CAUSES_K = [
  '概念混淆', '知识遗忘', '知识迁移失败', '前置知识缺失',
  '计算失误', '建模失败', '审题偏差', '策略不当', '需人工判断'
]

export const ERROR_CAUSES_S = [
  'S型-计算细节错误', '审题偏差', '表达不规范',
  '程序性知识错误', '逻辑推理缺陷', '低置信度-需人工补录'
]

export const ABILITY_DIMENSIONS = [
  '运算能力', '概念理解', '逻辑推理', '几何直观',
  '应用建模', '审题能力', '表达规范'
]

export const EXERCISE_FREQUENCIES = ['每天1次', '每周3次', '每周1次']

export const QUESTION_COUNTS = [8, 10, 15, 20]

export const SOURCE_TYPES = ['本地题库', '教研云']

export const STAGES = ['小学', '初中']

export const RECOMMENDATION_TYPES = [
  { value: 'consolidate', label: '继续巩固' },
  { value: 'breakthrough', label: '重点突破' },
  { value: 'expand', label: '拓展提升' },
  { value: 'frequency', label: '频率建议' },
]
