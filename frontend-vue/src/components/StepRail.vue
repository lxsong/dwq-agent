<!--
  智能体执行流程图组件
  按 LangGraph 节点拓扑展示各步骤状态
-->
<script setup lang="ts">
import { Check, Circle, LoaderCircle, X } from "lucide-vue-next";
import { computed } from "vue";
import { cn } from "../lib/format";
import type { ProgressStatus, StepState } from "../types/agent";

type FlowStatus = ProgressStatus | "pending";

type FlowNode = {
  step: string;
  x: number;
  y: number;
  w?: number;
};

const props = withDefaults(
  defineProps<{
    steps?: StepState[];
  }>(),
  {
    steps: () => [],
  },
);

const nodes: FlowNode[] = [
  { step: "抽取关键词", x: 410, y: 20 },
  { step: "召回字段信息", x: 150, y: 112 },
  { step: "召回指标信息", x: 410, y: 112 },
  { step: "召回字段取值", x: 670, y: 112 },
  { step: "合并召回信息", x: 410, y: 214 },
  { step: "过滤指标信息", x: 290, y: 318 },
  { step: "过滤表信息", x: 530, y: 318 },
  { step: "增加额外上下文", x: 410, y: 422, w: 176 },
  { step: "生成SQL", x: 410, y: 526 },
  { step: "校验SQL", x: 410, y: 630 },
  { step: "校正SQL", x: 670, y: 630 },
  { step: "执行SQL", x: 410, y: 724 },
];

const connectors = [
  "M410 60 L410 84 L150 84 L150 106",
  "M410 60 L410 106",
  "M410 60 L410 84 L670 84 L670 106",
  "M150 152 L150 178 L410 178 L410 208",
  "M410 152 L410 208",
  "M670 152 L670 178 L410 178 L410 208",
  "M410 254 L410 282 L290 282 L290 312",
  "M410 254 L410 282 L530 282 L530 312",
  "M290 358 L290 386 L410 386 L410 416",
  "M530 358 L530 386 L410 386 L410 416",
  "M410 462 L410 520",
  "M410 566 L410 624",
  "M410 670 L410 718",
  "M488 650 L586 650",
  "M670 670 L670 696 L410 696 L410 718",
];

const branchLabels = [
  { text: "有误", x: 530, y: 642 },
  { text: "无误", x: 366, y: 704 },
];

const statusMap = computed(() =>
  props.steps.reduce<Record<string, StepState>>((map, item) => {
    map[item.step] = item;
    return map;
  }, {}),
);

function statusFor(step: string): FlowStatus {
  return statusMap.value[step]?.status ?? "pending";
}
</script>

<template>
  <section
    v-if="steps.length > 0"
    class="mt-4 border border-ink/10 bg-white/40 px-3 py-4 shadow-line"
  >
    <div class="mb-3 flex items-center justify-between gap-3 px-1">
      <div class="text-sm font-semibold text-ink">执行流程</div>
      <div class="text-xs text-ink/45">LangGraph</div>
    </div>

    <div class="overflow-x-auto">
      <div class="relative mx-auto h-[780px] w-[820px]">
        <svg
          class="pointer-events-none absolute inset-0 h-full w-full"
          viewBox="0 0 820 780"
          fill="none"
          aria-hidden="true"
        >
          <defs>
            <marker
              id="flow-arrow"
              markerHeight="8"
              markerWidth="8"
              orient="auto"
              refX="6"
              refY="4"
            >
              <path d="M0 0 L8 4 L0 8 Z" fill="rgba(32,32,29,0.58)" />
            </marker>
          </defs>
          <path
            v-for="path in connectors"
            :key="path"
            :d="path"
            stroke="rgba(32,32,29,0.5)"
            stroke-width="1.5"
            marker-end="url(#flow-arrow)"
          />
          <text
            v-for="label in branchLabels"
            :key="label.text"
            :x="label.x"
            :y="label.y"
            fill="rgba(32,32,29,0.62)"
            font-size="13"
            font-weight="600"
          >
            {{ label.text }}
          </text>
        </svg>

        <div
          v-for="node in nodes"
          :key="node.step"
          class="absolute -translate-x-1/2"
          :style="{
            left: `${node.x}px`,
            top: `${node.y}px`,
            width: `${node.w ?? 156}px`,
          }"
        >
          <div
            :class="
              cn(
                'flex h-10 items-center gap-2 border px-3 text-sm font-semibold shadow-line transition',
                statusFor(node.step) === 'pending' && 'border-ink/10 bg-white/55 text-ink/45',
                statusFor(node.step) === 'running' && 'border-brass/45 bg-brass/15 text-ink',
                statusFor(node.step) === 'success' && 'border-moss/25 bg-moss/10 text-ink',
                statusFor(node.step) === 'error' && 'border-tomato/35 bg-tomato/10 text-tomato',
              )
            "
          >
            <span
              :class="
                cn(
                  'grid h-6 w-6 shrink-0 place-items-center rounded-full',
                  statusFor(node.step) === 'pending' && 'bg-ink/5 text-ink/35',
                  statusFor(node.step) === 'running' && 'bg-brass/20 text-brass',
                  statusFor(node.step) === 'success' && 'bg-moss/15 text-moss',
                  statusFor(node.step) === 'error' && 'bg-tomato/15 text-tomato',
                )
              "
            >
              <LoaderCircle
                v-if="statusFor(node.step) === 'running'"
                class="h-3.5 w-3.5 animate-spin"
                aria-hidden="true"
              />
              <Check
                v-else-if="statusFor(node.step) === 'success'"
                class="h-3.5 w-3.5"
                aria-hidden="true"
              />
              <X
                v-else-if="statusFor(node.step) === 'error'"
                class="h-3.5 w-3.5"
                aria-hidden="true"
              />
              <Circle v-else class="h-3.5 w-3.5" aria-hidden="true" />
            </span>
            <span class="min-w-0 flex-1 truncate">{{ node.step }}</span>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>
