<!--
  聊天输入区组件
  处理问题输入、发送和停止当前流式请求
-->
<script setup lang="ts">
import { ArrowUp, Square, WandSparkles } from "lucide-vue-next";
import { ref } from "vue";
import { cn } from "../lib/format";

const props = defineProps<{
  modelValue: string;
  disabled: boolean;
  isStreaming: boolean;
}>();

const emit = defineEmits<{
  "update:modelValue": [value: string];
  submit: [];
  stop: [];
}>();

const textareaRef = ref<HTMLTextAreaElement | null>(null);

const submit = () => {
  if (!props.disabled) emit("submit");
};

const onKeyDown = (event: KeyboardEvent) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    if (!props.disabled) emit("submit");
  }
};

const onInput = (event: Event) => {
  emit("update:modelValue", (event.target as HTMLTextAreaElement).value);
};
</script>

<template>
  <form
    class="border-t border-ink/10 bg-parchment/80 px-4 py-4 backdrop-blur"
    @submit.prevent="submit"
  >
    <div class="mx-auto flex max-w-5xl items-end gap-3 border border-ink/15 bg-white/75 p-2 shadow-panel">
      <div class="hidden h-11 w-11 shrink-0 place-items-center bg-moss/10 text-moss sm:grid">
        <WandSparkles class="h-5 w-5" aria-hidden="true" />
      </div>
      <textarea
        ref="textareaRef"
        :value="modelValue"
        rows="1"
        placeholder="问一个电商数据问题..."
        class="max-h-36 min-h-11 flex-1 resize-none bg-transparent px-2 py-3 text-[15px] leading-6 text-ink outline-none placeholder:text-ink/35"
        @input="onInput"
        @keydown="onKeyDown"
      />
      <button
        :type="isStreaming ? 'button' : 'submit'"
        :disabled="!isStreaming && disabled"
        :class="
          cn(
            'grid h-11 w-11 shrink-0 place-items-center rounded-full text-white transition focus:outline-none focus:ring-2 focus:ring-moss/40 focus:ring-offset-2',
            isStreaming
              ? 'bg-tomato hover:bg-tomato/90'
              : 'bg-ink hover:bg-soot disabled:cursor-not-allowed disabled:bg-ink/25',
          )
        "
        :title="isStreaming ? '停止' : '发送'"
        :aria-label="isStreaming ? '停止' : '发送'"
        @click="isStreaming ? emit('stop') : undefined"
      >
        <Square v-if="isStreaming" class="h-4 w-4 fill-current" aria-hidden="true" />
        <ArrowUp v-else class="h-5 w-5" aria-hidden="true" />
      </button>
    </div>
  </form>
</template>
