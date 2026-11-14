<!--
  查询结果组件
  支持二维数据表格与 ECharts 交互式 BI 图表（柱状图 / 折线图）自由切换
-->
<script setup lang="ts">
import { BarChart2, Database, FileJson, LineChart, Table } from "lucide-vue-next";
import * as echarts from "echarts";
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

type ViewMode = "table" | "bar" | "line";

const props = defineProps<{
  data: unknown;
}>();

const viewMode = ref<ViewMode>("table");
const chartContainer = ref<HTMLDivElement | null>(null);
let chartInstance: echarts.ECharts | null = null;
let resizeObserver: ResizeObserver | null = null;

function normalizeRows(data: unknown): Array<Record<string, unknown>> {
  if (Array.isArray(data)) {
    return data.map((item, index) =>
      item && typeof item === "object" && !Array.isArray(item)
        ? (item as Record<string, unknown>)
        : { 序号: index + 1, 值: item },
    );
  }

  if (data && typeof data === "object") {
    return [data as Record<string, unknown>];
  }

  return [{ 值: data ?? "" }];
}

function formatCell(value: unknown) {
  if (value === null || value === undefined) return "-";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function parseNumeric(val: unknown): number | null {
  if (val === null || val === undefined || val === "") return null;
  if (typeof val === "number") return Number.isNaN(val) ? null : val;
  if (typeof val === "string") {
    const trimmed = val.trim();
    // 排除常见日期与时间格式（如 2025-01 或 2025-01-15）
    if (/^\d{4}[-/.]\d{1,2}([-/.]\d{1,2})?$/.test(trimmed)) return null;
    const n = Number(trimmed);
    return Number.isNaN(n) ? null : n;
  }
  return null;
}

const rows = computed(() => normalizeRows(props.data));

const columns = computed(() =>
  Array.from(
    rows.value.reduce((keys, row) => {
      Object.keys(row).forEach((key) => keys.add(key));
      return keys;
    }, new Set<string>()),
  ),
);

/**
 * 判断列是否为数值度量列
 */
function isNumericColumn(col: string, list: Array<Record<string, unknown>>): boolean {
  let validCount = 0;
  let numericCount = 0;
  for (const row of list) {
    const val = row[col];
    if (val !== null && val !== undefined && val !== "") {
      validCount++;
      if (parseNumeric(val) !== null) {
        numericCount++;
      }
    }
  }
  return validCount > 0 && numericCount === validCount;
}

/**
 * 自动识别列类型：
 * 1. 第 1 个字符串/日期列作为 X 轴分类维度（Category）
 * 2. 数值类型列作为 Y 轴度量序列（Series）
 */
const chartDimensionInfo = computed(() => {
  const allCols = columns.value;
  const rowList = rows.value;

  const numericCols = allCols.filter((col) => isNumericColumn(col, rowList));
  const categoryCols = allCols.filter((col) => !isNumericColumn(col, rowList));

  // X 轴维度：优先取第 1 个字符串/日期分类列，若全是数值列则兜底取第 1 列
  const xAxisCol = categoryCols.length > 0 ? categoryCols[0] : allCols[0] ?? null;

  // Y 轴度量：取排除 X 轴后的所有数值列
  const seriesCols = numericCols.filter((col) => col !== xAxisCol);

  return {
    xAxisCol,
    seriesCols,
    canRender: Boolean(xAxisCol && seriesCols.length > 0 && rowList.length > 0),
  };
});

const canRenderChart = computed(() => chartDimensionInfo.value.canRender);

/**
 * 渲染或更新 ECharts 图表
 */
function renderChart() {
  if (viewMode.value === "table") return;
  if (!chartContainer.value || !canRenderChart.value) return;

  if (!chartInstance) {
    chartInstance = echarts.init(chartContainer.value);
  }

  const { xAxisCol, seriesCols } = chartDimensionInfo.value;
  if (!xAxisCol) return;

  const xData = rows.value.map((r) => formatCell(r[xAxisCol]));
  const isBar = viewMode.value === "bar";

  const colors = ["#2f6b4f", "#b48638", "#d64e3a", "#2d2925", "#3a86ff", "#8338ec"];

  const series: echarts.SeriesOption[] = seriesCols.map((col) => ({
    name: col,
    type: isBar ? "bar" : "line",
    data: rows.value.map((r) => parseNumeric(r[col]) ?? 0),
    ...(isBar
      ? {
          barMaxWidth: 36,
          itemStyle: {
            borderRadius: [4, 4, 0, 0],
          },
        }
      : {
          smooth: true,
          symbol: "circle",
          symbolSize: 6,
          areaStyle: {
            opacity: 0.12,
          },
        }),
  }));

  const option: echarts.EChartsOption = {
    color: colors,
    tooltip: {
      trigger: "axis",
      backgroundColor: "rgba(32, 32, 29, 0.92)",
      borderColor: "rgba(32, 32, 29, 0.2)",
      padding: [8, 12],
      textStyle: {
        color: "#f7f1e8",
        fontSize: 12,
      },
      axisPointer: {
        type: isBar ? "shadow" : "line",
        shadowStyle: {
          color: "rgba(47, 107, 79, 0.08)",
        },
      },
    },
    legend: {
      show: seriesCols.length > 1,
      top: 8,
      right: 16,
      textStyle: {
        color: "#20201d",
        fontSize: 12,
      },
    },
    grid: {
      left: "3%",
      right: "4%",
      bottom: "6%",
      top: seriesCols.length > 1 ? 44 : 24,
      containLabel: true,
    },
    xAxis: {
      type: "category",
      data: xData,
      axisLine: {
        lineStyle: {
          color: "rgba(32, 32, 29, 0.2)",
        },
      },
      axisLabel: {
        color: "#20201d",
        fontSize: 11,
        interval: 0,
        rotate: xData.length > 6 ? 25 : 0,
      },
    },
    yAxis: {
      type: "value",
      splitLine: {
        lineStyle: {
          color: "rgba(32, 32, 29, 0.08)",
          type: "dashed",
        },
      },
      axisLabel: {
        color: "rgba(32, 32, 29, 0.6)",
        fontSize: 11,
      },
    },
    series,
  };

  chartInstance.setOption(option, true);
  chartInstance.resize();
}

watch(viewMode, async (newMode) => {
  if (newMode !== "table") {
    await nextTick();
    renderChart();
  }
});

watch(
  () => props.data,
  async () => {
    if (viewMode.value !== "table") {
      await nextTick();
      renderChart();
    }
  },
  { deep: true },
);

onMounted(() => {
  if (chartContainer.value) {
    resizeObserver = new ResizeObserver(() => {
      chartInstance?.resize();
    });
    resizeObserver.observe(chartContainer.value);
  }
});

onBeforeUnmount(() => {
  resizeObserver?.disconnect();
  chartInstance?.dispose();
  chartInstance = null;
});
</script>

<template>
  <section
    v-if="columns.length > 0"
    class="mt-4 overflow-hidden border border-ink/10 bg-white/70 shadow-line"
  >
    <!-- 头部工具栏 -->
    <div class="flex flex-wrap items-center justify-between gap-2 border-b border-ink/10 px-4 py-2.5">
      <div class="flex items-center gap-2 text-sm font-semibold text-ink">
        <Database class="h-4 w-4 text-moss" aria-hidden="true" />
        <span>查询结果</span>
      </div>

      <div class="flex items-center gap-3">
        <div class="hidden items-center gap-1.5 text-xs text-ink/55 sm:flex">
          <FileJson class="h-3.5 w-3.5" aria-hidden="true" />
          <span>{{ rows.length }} 行</span>
        </div>

        <!-- [表格 | 柱状图 | 折线图] 视图切换按钮组 -->
        <div class="inline-flex items-center rounded border border-ink/10 bg-[#efe6d8]/70 p-0.5 shadow-sm">
          <button
            type="button"
            :class="[
              'flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium transition',
              viewMode === 'table'
                ? 'bg-ink text-parchment shadow-sm'
                : 'text-ink/65 hover:bg-black/5 hover:text-ink',
            ]"
            title="表格视图"
            @click="viewMode = 'table'"
          >
            <Table class="h-3.5 w-3.5" aria-hidden="true" />
            <span>表格</span>
          </button>
          <button
            type="button"
            :class="[
              'flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium transition',
              viewMode === 'bar'
                ? 'bg-ink text-parchment shadow-sm'
                : 'text-ink/65 hover:bg-black/5 hover:text-ink',
            ]"
            title="柱状图"
            @click="viewMode = 'bar'"
          >
            <BarChart2 class="h-3.5 w-3.5" aria-hidden="true" />
            <span>柱状图</span>
          </button>
          <button
            type="button"
            :class="[
              'flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium transition',
              viewMode === 'line'
                ? 'bg-ink text-parchment shadow-sm'
                : 'text-ink/65 hover:bg-black/5 hover:text-ink',
            ]"
            title="折线图"
            @click="viewMode = 'line'"
          >
            <LineChart class="h-3.5 w-3.5" aria-hidden="true" />
            <span>折线图</span>
          </button>
        </div>
      </div>
    </div>

    <!-- 表格视图 -->
    <div v-show="viewMode === 'table'" class="max-h-[360px] overflow-auto">
      <table class="min-w-full border-separate border-spacing-0 text-left text-sm">
        <thead class="sticky top-0 z-10 bg-[#efe6d8]">
          <tr>
            <th
              v-for="column in columns"
              :key="column"
              scope="col"
              class="border-b border-ink/10 px-4 py-3 font-semibold text-ink/70"
            >
              {{ column }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(row, rowIndex) in rows"
            :key="rowIndex"
            class="odd:bg-white/45 even:bg-white/20"
          >
            <td
              v-for="column in columns"
              :key="column"
              class="border-b border-ink/5 px-4 py-3 text-ink/80"
            >
              {{ formatCell(row[column]) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 图表视图 (柱状图 / 折线图) -->
    <div v-show="viewMode !== 'table'" class="relative min-h-[340px] bg-white/40">
      <div
        v-if="!canRenderChart"
        class="flex h-[340px] flex-col items-center justify-center gap-2 text-xs text-ink/50"
      >
        <BarChart2 class="h-8 w-8 text-ink/20" aria-hidden="true" />
        <span>当前数据行不足或缺少数值度量列，建议切换至表格查看</span>
      </div>
      <div
        v-else
        ref="chartContainer"
        class="h-[340px] w-full p-2"
      ></div>
    </div>
  </section>
</template>
