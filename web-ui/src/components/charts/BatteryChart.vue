<template>
  <VChart :option="option" :style="{ height: height + 'px' }" autoresize />
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { useRobotStore } from '@/stores/robot'

use([LineChart, GridComponent, TooltipComponent, CanvasRenderer])

const props = defineProps({
  height: { type: Number, default: 100 },
})

const store = useRobotStore()
const history = ref([])

watch(() => store.batteryPercent, (val) => {
  if (val === null || val === undefined) return
  history.value.push(val)
  if (history.value.length > 60) history.value.shift()
})

const batteryColor = computed(() => {
  const v = store.batteryPercent ?? 100
  if (v > 50) return '#22c55e'   // amr-ok
  if (v > 20) return '#eab308'   // amr-warning
  return '#ef4444'               // amr-danger
})

const option = computed(() => ({
  backgroundColor: 'transparent',
  grid: { top: 6, bottom: 18, left: 30, right: 8 },
  xAxis: {
    type: 'category',
    show: false,
    boundaryGap: false,
  },
  yAxis: {
    type: 'value',
    min: 0,
    max: 100,
    splitNumber: 2,
    axisLabel: {
      color: '#71717a',
      fontSize: 9,
      formatter: '{value}%',
    },
    splitLine: {
      lineStyle: { color: 'rgba(255,255,255,0.04)' },
    },
  },
  tooltip: {
    trigger: 'axis',
    backgroundColor: 'rgba(9,9,11,0.9)',
    borderColor: '#27272a',
    textStyle: { color: '#fafafa', fontSize: 10 },
    formatter: (params) => `${params[0].value}%`,
  },
  series: [{
    data: history.value.length ? history.value : [0],
    type: 'line',
    smooth: true,
    showSymbol: false,
    lineStyle: { color: batteryColor.value, width: 2 },
    areaStyle: { color: batteryColor.value + '1a' },
  }],
}))
</script>
