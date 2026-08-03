<template>
  <div class="tree-node" :style="{ paddingLeft: depth * 20 + 'px' }">
    <div class="tree-label" @click="toggleExpand">
      <span class="tree-arrow" v-if="hasChildren">
        <svg :class="{ expanded: expanded }" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M9 18l6-6-6-6"/>
        </svg>
      </span>
      <span class="tree-arrow" v-else style="visibility:hidden">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M9 18l6-6-6-6"/>
        </svg>
      </span>
      <span class="tree-name">{{ node.name || node.label }}</span>
      <button class="tree-edit-btn" @click.stop="$emit('edit', node)" title="编辑">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>
          <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
        </svg>
      </button>
    </div>
    <div v-if="expanded && hasChildren" class="tree-children">
      <TreeNode
        v-for="child in node.children"
        :key="child.id || child.name"
        :node="child"
        :depth="depth + 1"
        @edit="(n) => $emit('edit', n)"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  node: { type: Object, required: true },
  depth: { type: Number, default: 0 }
})

defineEmits(['edit'])

const expanded = ref(true)

const hasChildren = computed(() => {
  return props.node.children && props.node.children.length > 0
})

function toggleExpand() {
  expanded.value = !expanded.value
}
</script>

<style scoped>
.tree-node { user-select: none }
.tree-label {
  display: flex; align-items: center; gap: 4px;
  padding: 8px 12px; border-radius: var(--radius-sm); cursor: pointer;
  transition: background .2s;
}
.tree-label:hover { background: var(--gray-100) }
.tree-arrow {
  display: flex; align-items: center; color: var(--gray-400);
  transition: transform .2s;
}
.tree-arrow svg.expanded { transform: rotate(90deg) }
.tree-name { flex: 1; font-size: 14px; color: var(--gray-700) }
.tree-edit-btn {
  background: none; border: none; cursor: pointer;
  color: var(--gray-400); padding: 2px; display: flex;
  align-items: center; opacity: 0; transition: opacity .2s;
}
.tree-label:hover .tree-edit-btn { opacity: 1 }
.tree-children { border-left: 1px solid var(--gray-200); margin-left: 14px }
</style>
