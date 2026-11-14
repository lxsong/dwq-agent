<!--
  前端应用主组件
  负责聊天会话状态、SSE 事件消费和整体页面布局
-->
<script setup lang="ts">
import {
  Activity,
  BarChart3,
  Eraser,
  History,
  Leaf,
  MessageSquarePlus,
  Server,
} from "lucide-vue-next";
import { computed, nextTick, ref, watch } from "vue";
import Composer from "./components/Composer.vue";
import EmptyState from "./components/EmptyState.vue";
import MessageBubble from "./components/MessageBubble.vue";
import { streamQuery } from "./lib/agentApi";
import { cn, summarizeResult } from "./lib/format";
import type { AgentEvent, ChatMessage, StepState } from "./types/agent";

const examples = [
  "统计 2025 年第一季度各大区的 GMV，并按 GMV 从高到低排序",
  "统计 2025 年 3 月各商品品类的销量和销售额",
  "查询华东地区 2025 年第一季度销售额最高的前 5 个商品",
  "按会员等级统计 2025 年第一季度的订单数和销售额",
];

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "Vite /api proxy";

function makeId() {
  return crypto.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function upsertStep(steps: StepState[] = [], event: Extract<AgentEvent, { type: "progress" }>) {
  const next = steps.filter((item) => item.step !== event.step);
  next.push({
    step: event.step,
    status: event.status,
    updatedAt: Date.now(),
  });
  return next;
}

const messages = ref<ChatMessage[]>([]);
const draft = ref("");
const activeController = ref<AbortController | null>(null);
const scrollRef = ref<HTMLDivElement | null>(null);

const isStreaming = computed(() => Boolean(activeController.value));
const canSubmit = computed(() => draft.value.trim().length > 0 && !isStreaming.value);

const completedCount = computed(
  () => messages.value.filter((message) => message.role === "assistant" && message.status === "done").length,
);

watch(
  messages,
  async () => {
    await nextTick();
    scrollRef.value?.scrollTo({
      top: scrollRef.value.scrollHeight,
      behavior: "smooth",
    });
  },
  { deep: true },
);

const startQuery = async (rawQuery = draft.value) => {
  const query = rawQuery.trim();
  if (!query || isStreaming.value) return;

  const userMessage: ChatMessage = {
    id: makeId(),
    role: "user",
    content: query,
    createdAt: Date.now(),
  };

  const assistantId = makeId();
  const assistantMessage: ChatMessage = {
    id: assistantId,
    role: "assistant",
    content: "正在连接问数智能体...",
    createdAt: Date.now(),
    status: "streaming",
    steps: [],
  };

  const controller = new AbortController();
  activeController.value = controller;
  draft.value = "";
  messages.value = [...messages.value, userMessage, assistantMessage];

  const onEvent = (event: AgentEvent) => {
    messages.value = messages.value.map((message) => {
      if (message.id !== assistantId) return message;

      if (event.type === "progress") {
        return {
          ...message,
          content: event.status === "running" ? `正在执行：${event.step}` : message.content,
          steps: upsertStep(message.steps, event),
        };
      }

      if (event.type === "sql") {
        return {
          ...message,
          sql: event.sql,
        };
      }

      if (event.type === "result") {
        return {
          ...message,
          status: "done",
          content: summarizeResult(event.data),
          result: event.data,
        };
      }

      return {
        ...message,
        status: "error",
        content: "这次查询没有成功。",
        error: event.message,
      };
    });
  };

  try {
    await streamQuery(query, { signal: controller.signal, onEvent });
    messages.value = messages.value.map((message) =>
      message.id === assistantId && message.status === "streaming"
        ? { ...message, status: "done", content: "流程已结束，后端未返回查询结果。" }
        : message,
    );
  } catch (error) {
    const isAbort = error instanceof DOMException && error.name === "AbortError";
    messages.value = messages.value.map((message) =>
      message.id === assistantId
        ? {
            ...message,
            status: isAbort ? "done" : "error",
            content: isAbort ? "已停止本次查询。" : "无法连接问数接口。",
            error: isAbort ? undefined : error instanceof Error ? error.message : String(error),
          }
        : message,
    );
  } finally {
    activeController.value = null;
  }
};

const stopQuery = () => {
  activeController.value?.abort();
};

const clearConversation = () => {
  if (isStreaming.value) return;
  messages.value = [];
  draft.value = "";
};
</script>

<template>
  <div class="h-dvh overflow-hidden bg-parchment text-ink">
    <div
      class="pointer-events-none fixed inset-0 bg-[linear-gradient(90deg,rgba(32,32,29,0.045)_1px,transparent_1px),linear-gradient(rgba(32,32,29,0.035)_1px,transparent_1px)] bg-[size:48px_48px]"
    />
    <div class="pointer-events-none fixed inset-0 grain" />

    <div class="relative grid h-full min-h-0 overflow-hidden lg:grid-cols-[300px_minmax(0,1fr)]">
      <aside class="hidden min-h-0 border-r border-ink/10 bg-[#efe6d8]/85 backdrop-blur lg:flex lg:flex-col">
        <div class="border-b border-ink/10 px-5 py-5">
          <div class="flex items-center gap-3">
            <div class="grid h-10 w-10 place-items-center bg-ink text-parchment">
              <BarChart3 class="h-5 w-5" aria-hidden="true" />
            </div>
            <div>
              <div class="text-base font-semibold tracking-[0.02em]">电商问数</div>
            </div>
          </div>
        </div>

        <div class="min-h-0 flex-1 space-y-5 overflow-y-auto px-4 py-4">
          <button
            type="button"
            :disabled="isStreaming"
            class="flex h-11 w-full items-center justify-center gap-2 bg-ink text-sm font-semibold text-parchment transition hover:bg-soot disabled:cursor-not-allowed disabled:bg-ink/35"
            @click="clearConversation"
          >
            <MessageSquarePlus class="h-4 w-4" aria-hidden="true" />
            新会话
          </button>

          <section>
            <div class="mb-2 flex items-center gap-2 px-1 text-xs font-semibold uppercase tracking-[0.16em] text-ink/45">
              <History class="h-3.5 w-3.5" aria-hidden="true" />
              样例
            </div>
            <div class="space-y-2">
              <button
                v-for="example in examples"
                :key="example"
                type="button"
                :disabled="isStreaming"
                class="w-full border border-ink/10 bg-white/42 px-3 py-3 text-left text-sm leading-5 text-ink/75 transition hover:border-moss/35 hover:bg-white/75 disabled:cursor-not-allowed disabled:opacity-55"
                @click="startQuery(example)"
              >
                {{ example }}
              </button>
            </div>
          </section>
        </div>

        <div class="border-t border-ink/10 p-4">
          <div class="grid gap-2 text-xs text-ink/55">
            <div class="flex items-center justify-between gap-3">
              <span class="inline-flex items-center gap-2">
                <Server class="h-3.5 w-3.5" aria-hidden="true" />
                API
              </span>
              <span class="truncate font-mono">{{ API_BASE_URL }}</span>
            </div>
            <div class="flex items-center justify-between">
              <span class="inline-flex items-center gap-2">
                <Activity class="h-3.5 w-3.5" aria-hidden="true" />
                完成
              </span>
              <span>{{ completedCount }}</span>
            </div>
          </div>
        </div>
      </aside>

      <main class="flex min-h-0 min-w-0 flex-col overflow-hidden">
        <header
          class="flex h-16 shrink-0 items-center justify-between border-b border-ink/10 bg-parchment/88 px-4 backdrop-blur lg:px-6"
        >
          <div class="flex min-w-0 items-center gap-3">
            <div class="grid h-9 w-9 shrink-0 place-items-center bg-moss text-white lg:hidden">
              <BarChart3 class="h-4 w-4" aria-hidden="true" />
            </div>
            <div class="min-w-0">
              <div class="truncate text-sm font-semibold text-ink">智能数据分析 Agent</div>
              <div class="truncate text-xs text-ink/45">FastAPI SSE / LangGraph</div>
            </div>
          </div>
          <button
            type="button"
            :disabled="messages.length === 0 || isStreaming"
            :class="
              cn(
                'grid h-9 w-9 place-items-center rounded-full text-ink/55 transition hover:bg-ink/5 hover:text-ink disabled:cursor-not-allowed disabled:opacity-35',
              )
            "
            title="清空"
            aria-label="清空"
            @click="clearConversation"
          >
            <Eraser class="h-4 w-4" aria-hidden="true" />
          </button>
        </header>

        <div ref="scrollRef" class="min-h-0 flex-1 overflow-y-auto overscroll-contain">
          <EmptyState v-if="messages.length === 0" :examples="examples" @use-example="draft = $event" />
          <div v-else class="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-6 lg:px-8">
            <MessageBubble v-for="message in messages" :key="message.id" :message="message" />
          </div>
        </div>

        <div class="border-t border-ink/10 bg-[#efe6d8]/45 px-4 py-2 text-center text-xs text-ink/45">
          <span class="inline-flex items-center gap-2">
            <Leaf class="h-3.5 w-3.5 text-moss" aria-hidden="true" />
            {{ isStreaming ? "运行中" : "就绪" }}
          </span>
        </div>
        <Composer
          v-model="draft"
          :disabled="!canSubmit"
          :is-streaming="isStreaming"
          @submit="startQuery()"
          @stop="stopQuery"
        />
      </main>
    </div>
  </div>
</template>
