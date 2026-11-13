<!--
  聊天消息气泡组件
  组合展示用户问题、智能体回复、执行流程和结果表格
-->
<script setup lang="ts">
import { Bot, Copy, UserRound } from "lucide-vue-next";
import { computed } from "vue";
import { cn, formatTime, toClipboardText } from "../lib/format";
import type { ChatMessage } from "../types/agent";
import ResultTable from "./ResultTable.vue";
import SqlViewer from "./SqlViewer.vue";
import StepRail from "./StepRail.vue";

const props = defineProps<{
  message: ChatMessage;
}>();

const isUser = computed(() => props.message.role === "user");

const copy = async () => {
  const text = props.message.result ? toClipboardText(props.message.result) : props.message.content;
  await navigator.clipboard.writeText(text);
};
</script>

<template>
  <article :class="cn('group flex gap-3', isUser && 'justify-end')">
    <div
      v-if="!isUser"
      class="mt-1 grid h-9 w-9 shrink-0 place-items-center rounded-full bg-ink text-parchment"
    >
      <Bot class="h-4 w-4" aria-hidden="true" />
    </div>

    <div :class="cn('max-w-[920px] flex-1', isUser && 'flex max-w-[760px] justify-end')">
      <div
        :class="
          cn(
            'relative border px-5 py-4 shadow-line',
            isUser
              ? 'border-ink/80 bg-ink text-parchment'
              : 'border-ink/10 bg-[#fffaf1]/78 text-ink backdrop-blur',
          )
        "
      >
        <div class="flex items-start justify-between gap-3">
          <p class="whitespace-pre-wrap text-[15px] leading-7">{{ message.content }}</p>
          <button
            v-if="!isUser && message.status !== 'streaming'"
            type="button"
            class="shrink-0 rounded-full p-1.5 text-ink/45 opacity-0 outline-none transition hover:bg-ink/5 hover:text-ink focus:opacity-100 focus:ring-2 focus:ring-moss/40 group-hover:opacity-100"
            title="复制"
            aria-label="复制"
            @click="copy"
          >
            <Copy class="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        <div
          v-if="message.error"
          class="mt-3 border border-tomato/30 bg-tomato/10 px-3 py-2 text-sm text-tomato"
        >
          {{ message.error }}
        </div>

        <StepRail v-if="!isUser" :steps="message.steps" />
        <SqlViewer v-if="!isUser && message.sql" :sql="message.sql" />
        <ResultTable v-if="!isUser && message.result !== undefined" :data="message.result" />

        <div :class="cn('mt-3 text-xs', isUser ? 'text-parchment/55' : 'text-ink/45')">
          {{ formatTime(message.createdAt) }}
        </div>
      </div>
    </div>

    <div
      v-if="isUser"
      class="mt-1 grid h-9 w-9 shrink-0 place-items-center rounded-full bg-moss text-white"
    >
      <UserRound class="h-4 w-4" aria-hidden="true" />
    </div>
  </article>
</template>
