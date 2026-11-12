<!--
  查询结果表格组件
  将后端返回的结构化数据归一化为可滚动表格
-->
<script setup lang="ts">
import { Database, FileJson } from "lucide-vue-next";
import { computed } from "vue";

const props = defineProps<{
  data: unknown;
}>();

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

const rows = computed(() => normalizeRows(props.data));

const columns = computed(() =>
  Array.from(
    rows.value.reduce((keys, row) => {
      Object.keys(row).forEach((key) => keys.add(key));
      return keys;
    }, new Set<string>()),
  ),
);
</script>

<template>
  <section
    v-if="columns.length > 0"
    class="mt-4 overflow-hidden border border-ink/10 bg-white/70 shadow-line"
  >
    <div class="flex items-center justify-between border-b border-ink/10 px-4 py-3">
      <div class="flex items-center gap-2 text-sm font-semibold text-ink">
        <Database class="h-4 w-4 text-moss" aria-hidden="true" />
        查询结果
      </div>
      <div class="flex items-center gap-2 text-xs text-ink/55">
        <FileJson class="h-3.5 w-3.5" aria-hidden="true" />
        {{ rows.length }} 行
      </div>
    </div>
    <div class="max-h-[360px] overflow-auto">
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
  </section>
</template>
