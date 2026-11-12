<!--
  首页空状态组件
  展示产品入口信息和可点击的示例问数问题
-->
<script setup lang="ts">
import { LineChart, Search, ShoppingBag, Sparkles } from "lucide-vue-next";

defineProps<{
  examples: string[];
}>();

const emit = defineEmits<{
  useExample: [example: string];
}>();

const highlights = [
  { label: "混合检索", icon: Search },
  { label: "SQL 闭环", icon: LineChart },
  { label: "电商数仓", icon: ShoppingBag },
];
</script>

<template>
  <div class="mx-auto flex min-h-full max-w-5xl flex-col justify-center px-4 py-12">
    <div class="mb-10 max-w-3xl">
      <div
        class="mb-5 inline-flex items-center gap-2 border border-moss/25 bg-moss/10 px-3 py-1.5 text-sm font-semibold text-moss"
      >
        <Sparkles class="h-4 w-4" aria-hidden="true" />
        Shopkeeper Agent
      </div>
      <h1 class="text-balance text-4xl font-semibold leading-tight text-ink sm:text-6xl">
        电商问数
      </h1>
    </div>

    <div class="grid gap-3 sm:grid-cols-3">
      <div
        v-for="item in highlights"
        :key="item.label"
        class="border border-ink/10 bg-white/55 px-4 py-4"
      >
        <component :is="item.icon" class="mb-5 h-5 w-5 text-brass" aria-hidden="true" />
        <div class="text-sm font-semibold text-ink">{{ item.label }}</div>
      </div>
    </div>

    <div class="mt-6 grid gap-3 md:grid-cols-2">
      <button
        v-for="example in examples"
        :key="example"
        type="button"
        class="min-h-20 border border-ink/10 bg-[#fffaf1]/75 px-4 py-4 text-left text-[15px] leading-6 text-ink transition hover:-translate-y-0.5 hover:border-moss/35 hover:bg-white focus:outline-none focus:ring-2 focus:ring-moss/35"
        @click="emit('useExample', example)"
      >
        {{ example }}
      </button>
    </div>
  </div>
</template>
