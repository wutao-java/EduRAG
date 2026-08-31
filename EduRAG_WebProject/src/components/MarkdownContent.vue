<script setup>
import { computed } from "vue";
import MarkdownIt from "markdown-it";

const props = defineProps({
  content: {
    type: String,
    default: "",
  },
  streaming: {
    type: Boolean,
    default: false,
  },
});

const markdown = new MarkdownIt({
  breaks: true,
  html: false,
  linkify: true,
  typographer: false,
});

const renderedContent = computed(() => markdown.render(props.content));
</script>

<template>
  <div
    class="markdown-content"
    :class="{ 'typing-cursor': streaming }"
    v-html="renderedContent"
  ></div>
</template>
