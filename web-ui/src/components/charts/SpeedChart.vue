<template>
  <VChart :option="option" :style="{ height: height + 'px' }" autoresize />
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { useRobotStore } from '@/stores/robot'

use([LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const props = defineProps({
  height: { type: Number, default: 100 },
})

const store = useRobotStore()
const linearHistory  = ref([])
const angularHistory = ref([])

watch(() => store.robotVelocity, (vel) => {
  if (!vel) return
  linearHistory.value.push(parseFloat(vel.linear.toFixed(3)))
  angularHistory.value.push(parseFloat(vel.angular.toFixed(3)))
  if (linearHistory.value.length > 60)  linearHistory.value.shift()
  if (angularHistory.value.length > 60) angularHistory.value.shift()
}, { deep: true })

const option = computed(() => ({
  backgroundColor: 'transparent',
  grid: { top: 6, bottom: 18, left: 34, right: 8 },
  legend: {
    top: 'bottom',
    textStyle: { color: '#71717a', fontSize: 9 },
    itemWidth: 10, itemHeight: 2,
    data: ['Linear', 'Angular'],
  },
  xAxis: {
    type: 'category',
    show: false,
    boundaryGap: false,
  },
  yAxis: {
    type: 'value',
    axisLabel: {
      color: '#71717a',
      fontSize: 9,
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
    formatter: (params) => params.map(p => `${p.seriesName}: ${p.value}`).join('<br/>'),
  },
  series: [
    {
      name: 'Linear',
      data: linearHistory.value.length ? linearHistory.value : [0],
      type: 'line',
      smooth: true,
      showSymbol: false,
      lineStyle: { color: '#06b6d4', width: 2 },   // amr-data cyan
      areaStyle: { color: '#06b6d41a' },
    },
    {
      name: 'Angular',
      data: angularHistory.value.length ? angularHistory.value : [0],
      type: 'line',
      smooth: true,
      showSymbol: false,
      lineStyle: { color: '#eab308', width: 1.5 },  // amr-warning yellow
      areaStyle: { color: '#eab3081a' },
    },
  ],
}))
</script>
