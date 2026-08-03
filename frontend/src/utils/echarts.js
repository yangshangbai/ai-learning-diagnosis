import * as echarts from 'echarts'

export function safeChart(dom) {
  if (!dom) return null
  try {
    const chart = echarts.init(dom)
    return chart
  } catch (e) {
    console.warn('ECharts init failed:', e.message)
    return null
  }
}

export function disposeChart(chart) {
  if (chart) {
    try { chart.dispose() } catch (e) {}
  }
}

export { echarts }
