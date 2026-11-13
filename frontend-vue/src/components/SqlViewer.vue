<!--
  SQL 语句高亮与查看组件
  支持展开/收起、代码语法高亮与一键复制
-->
<script setup lang="ts">
import { Check, ChevronDown, ChevronRight, Code2, Copy } from "lucide-vue-next";
import { computed, ref } from "vue";

const props = defineProps<{
  sql: string;
}>();

const isExpanded = ref(true);
const copied = ref(false);
let timer: ReturnType<typeof setTimeout> | null = null;

const toggleExpand = () => {
  isExpanded.value = !isExpanded.value;
};

const copySql = async () => {
  if (!props.sql) return;
  try {
    await navigator.clipboard.writeText(props.sql);
    copied.value = true;
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => {
      copied.value = false;
    }, 2000);
  } catch (err) {
    console.error("复制失败:", err);
  }
};

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

/**
 * 轻量且高效的 SQL 语法高亮转换
 */
const highlightedHtml = computed(() => {
  const sql = props.sql;
  if (!sql) return "";

  // 匹配模式：单行注释、多行注释、字符串、核心关键字、常用函数、数字
  const tokenRegex =
    /(--[^\n]*|\/\*[\s\S]*?\*\/)|('(?:''|[^'\\]|\\.)*')|("(?:""|[^"\\]|\\.)*")|(\b(?:SELECT|FROM|WHERE|AND|OR|NOT|IN|AS|JOIN|LEFT|RIGHT|INNER|FULL|OUTER|CROSS|ON|GROUP\s+BY|ORDER\s+BY|ASC|DESC|LIMIT|OFFSET|HAVING|UNION(?:\s+ALL)?|CASE|WHEN|THEN|ELSE|END|WITH|DISTINCT|LIKE|BETWEEN|IS(?:\s+NOT)?|NULL|TRUE|FALSE|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|TABLE|VIEW|SET|VALUES|INTO|BY)\b)|(\b(?:SUM|COUNT|AVG|MIN|MAX|ROUND|DATE_FORMAT|NOW|CONCAT|COALESCE|IFNULL|DATEDIFF|YEAR|MONTH|DAY|QUARTER|SUBSTRING|TRIM|LOWER|UPPER|ABS|FLOOR|CEIL)\b)|(\b\d+(?:\.\d+)?\b)/gi;

  let lastIndex = 0;
  let html = "";
  let match: RegExpExecArray | null;

  while ((match = tokenRegex.exec(sql)) !== null) {
    if (match.index > lastIndex) {
      html += escapeHtml(sql.slice(lastIndex, match.index));
    }

    const [raw, comment, singleStr, doubleStr, keyword, func, num] = match;

    if (comment) {
      html += `<span class="text-stone-400 italic">${escapeHtml(raw)}</span>`;
    } else if (singleStr || doubleStr) {
      html += `<span class="text-[#86efac] font-medium">${escapeHtml(raw)}</span>`;
    } else if (keyword) {
      html += `<span class="text-[#e59441] font-bold">${escapeHtml(raw)}</span>`;
    } else if (func) {
      html += `<span class="text-[#38bdf8] font-semibold">${escapeHtml(raw)}</span>`;
    } else if (num) {
      html += `<span class="text-[#c084fc]">${escapeHtml(raw)}</span>`;
    } else {
      html += escapeHtml(raw);
    }

    lastIndex = tokenRegex.lastIndex;
  }

  if (lastIndex < sql.length) {
    html += escapeHtml(sql.slice(lastIndex));
  }

  return html;
});
</script>

<template>
  <section class="mt-4 overflow-hidden border border-ink/10 bg-[#1e1e1e] shadow-line">
    <!-- 头部工具栏 -->
    <div
      class="flex select-none items-center justify-between border-b border-ink/10 bg-[#efe6d8] px-4 py-2.5 transition"
    >
      <button
        type="button"
        class="flex items-center gap-2 text-sm font-semibold text-ink outline-none hover:text-moss"
        @click="toggleExpand"
      >
        <component
          :is="isExpanded ? ChevronDown : ChevronRight"
          class="h-4 w-4 text-ink/60 transition-transform"
          aria-hidden="true"
        />
        <Code2 class="h-4 w-4 text-moss" aria-hidden="true" />
        <span>执行 SQL</span>
        <span class="rounded bg-ink/10 px-1.5 py-0.5 text-[11px] font-normal text-ink/60">
          SQL
        </span>
      </button>

      <div class="flex items-center gap-2">
        <button
          type="button"
          :class="[
            'inline-flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium transition focus:outline-none focus:ring-1 focus:ring-moss/40',
            copied
              ? 'bg-moss/15 text-moss'
              : 'border border-ink/10 bg-white/70 text-ink/70 hover:bg-white hover:text-ink',
          ]"
          :title="copied ? '已复制' : '复制 SQL'"
          @click="copySql"
        >
          <Check v-if="copied" class="h-3.5 w-3.5 text-moss" aria-hidden="true" />
          <Copy v-else class="h-3.5 w-3.5 text-ink/60" aria-hidden="true" />
          <span>{{ copied ? "已复制" : "复制" }}</span>
        </button>
      </div>
    </div>

    <!-- 高亮代码框主体 -->
    <div v-show="isExpanded" class="max-h-[320px] overflow-auto p-4 text-[13px] leading-relaxed">
      <pre
        class="m-0 font-mono text-[#e6edf3] whitespace-pre-wrap break-all"
        v-html="highlightedHtml"
      ></pre>
    </div>
  </section>
</template>
