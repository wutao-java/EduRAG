<script setup>
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from "vue";

import MarkdownContent from "./components/MarkdownContent.vue";
import { apiRequest, streamAnswer } from "./services/api";

const defaultTitle = "新的学习问题";
const brandAvatarUrl = "/favicon.svg";
const welcomeText =
  "你好，我可以结合课程 FAQ 和知识库资料回答 IT 学习问题。\n\n你可以直接描述知识点，也可以把报错信息完整贴过来。";
const fallbackSuggestionQuestions = [
  "BM25 和向量检索有什么区别？",
  "Java 中 HashMap 为什么线程不安全？",
];
const suggestionDisplayLimit = 2;
const subjectLabels = {
  global: { label: "全局检索", fullLabel: "全局检索" },
  ai: { label: "AI", fullLabel: "人工智能" },
  java: { label: "Java", fullLabel: "Java 开发" },
  python: { label: "Python", fullLabel: "Python 开发" },
  运维: { label: "运维", fullLabel: "云计算运维" },
};

const sessions = ref([]);
const messages = ref([]);
const suggestionQuestions = ref([...fallbackSuggestionQuestions]);
const sourceOptions = ref([{ value: "global", label: "全局检索" }]);
const currentSessionId = ref("");
const selectedSource = ref("global");
const question = ref("");
const isAnswering = ref(false);
const isInitializing = ref(true);
const serviceReady = ref(false);
const sidebarOpen = ref(false);
const subjectOptionsOpen = ref(false);
const activeMenuSessionId = ref("");
const historyMenuStyle = ref({});
const toastMessage = ref("");
const questionInput = ref(null);
const chatLog = ref(null);
let messageSequence = 0;
let toastTimer;
let scrollFrame;

const currentSession = computed(() =>
  sessions.value.find(
    (session) => session.session_id === currentSessionId.value,
  ),
);
const conversationTitle = computed(
  () => currentSession.value?.title || defaultTitle,
);
const currentSubject = computed(() => {
  const profile = subjectLabels[selectedSource.value];
  return {
    value: selectedSource.value,
    label: profile?.label || selectedSource.value,
    fullLabel: profile?.fullLabel || selectedSource.value,
  };
});
function formatTime() {
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date());
}

function createMessage(role, content, options = {}) {
  messageSequence += 1;
  return {
    id: `${Date.now()}-${messageSequence}`,
    role,
    content,
    time: formatTime(),
    isAnswer: options.isAnswer || false,
    isStreaming: options.isStreaming || false,
    isError: options.isError || false,
    knowledgeTag: options.knowledgeTag || "",
  };
}

function setWelcomeMessage(content = welcomeText) {
  messages.value = [createMessage("assistant", content)];
  scheduleScroll();
}

function showToast(message) {
  window.clearTimeout(toastTimer);
  toastMessage.value = message;
  toastTimer = window.setTimeout(() => {
    toastMessage.value = "";
  }, 1800);
}

function scheduleScroll() {
  window.cancelAnimationFrame(scrollFrame);
  scrollFrame = window.requestAnimationFrame(async () => {
    await nextTick();
    chatLog.value?.scrollTo({
      top: chatLog.value.scrollHeight,
      behavior: "smooth",
    });
  });
}

function resizeQuestionInput() {
  if (!questionInput.value) {
    return;
  }
  questionInput.value.style.height = "auto";
  questionInput.value.style.height = `${Math.min(
    questionInput.value.scrollHeight,
    126,
  )}px`;
}

function closeOverlays() {
  subjectOptionsOpen.value = false;
  activeMenuSessionId.value = "";
}

function selectSource(sourceValue) {
  selectedSource.value = sourceValue;
  subjectOptionsOpen.value = false;
  showToast(`已切换到${currentSubject.value.fullLabel}`);
}

async function loadSources() {
  const response = await apiRequest("/api/sources");
  sourceOptions.value = [
    { value: "global", label: "全局检索" },
    ...response.sources.map((source) => ({
      value: source,
      label: subjectLabels[source]?.label || source,
    })),
  ];
}

async function loadSessions() {
  const response = await apiRequest("/api/sessions");
  sessions.value = response.sessions;
}

function pickRandomSuggestions(suggestions) {
  const shuffledSuggestions = [
    ...new Set(
      suggestions
        .map((suggestion) => suggestion.trim())
        .filter(Boolean),
    ),
  ];

  for (let index = shuffledSuggestions.length - 1; index > 0; index -= 1) {
    const randomIndex = Math.floor(Math.random() * (index + 1));
    [shuffledSuggestions[index], shuffledSuggestions[randomIndex]] = [
      shuffledSuggestions[randomIndex],
      shuffledSuggestions[index],
    ];
  }

  return shuffledSuggestions.slice(0, suggestionDisplayLimit);
}

async function loadFaqSuggestions() {
  try {
    const response = await apiRequest("/api/faq/suggestions");
    if (Array.isArray(response.suggestions) && response.suggestions.length) {
      suggestionQuestions.value = pickRandomSuggestions(response.suggestions);
    }
  } catch {
    suggestionQuestions.value = [...fallbackSuggestionQuestions];
  }
}

async function createNewSession(showSuccessToast = true) {
  if (isAnswering.value) {
    showToast("请等待当前回答完成");
    return;
  }

  const createdSession = await apiRequest("/api/sessions", {
    method: "POST",
    body: { title: defaultTitle },
  });
  sessions.value = [
    createdSession,
    ...sessions.value.filter(
      (session) => session.session_id !== createdSession.session_id,
    ),
  ];
  currentSessionId.value = createdSession.session_id;
  setWelcomeMessage(
    "新会话已创建。选择学科后，直接输入你正在学习的问题即可。",
  );
  sidebarOpen.value = false;
  await nextTick();
  questionInput.value?.focus();
  if (showSuccessToast) {
    showToast("已创建新会话");
  }
}

async function activateSession(session) {
  if (isAnswering.value) {
    showToast("请等待当前回答完成");
    return;
  }

  currentSessionId.value = session.session_id;
  activeMenuSessionId.value = "";
  sidebarOpen.value = false;
  const response = await apiRequest(`/api/history/${session.session_id}`);
  const historyMessages = response.history.flatMap((entry) => [
    createMessage("user", entry.question),
    createMessage("assistant", entry.answer, {
      isAnswer: true,
      knowledgeTag: "历史回答",
    }),
  ]);
  messages.value = historyMessages.length
    ? historyMessages
    : [createMessage("assistant", welcomeText)];
  scheduleScroll();
}

function openHistoryMenu(sessionId, event) {
  if (activeMenuSessionId.value === sessionId) {
    activeMenuSessionId.value = "";
    return;
  }

  const rect = event.currentTarget.getBoundingClientRect();
  const menuWidth = 152;
  historyMenuStyle.value = {
    left: `${Math.max(8, Math.min(rect.left, window.innerWidth - menuWidth - 8))}px`,
    top: `${Math.min(rect.bottom + 6, window.innerHeight - 112)}px`,
  };
  activeMenuSessionId.value = sessionId;
}

async function renameSession() {
  const session = sessions.value.find(
    (item) => item.session_id === activeMenuSessionId.value,
  );
  if (!session) {
    return;
  }

  const nextTitle = window.prompt("重命名会话", session.title)?.trim();
  if (!nextTitle) {
    activeMenuSessionId.value = "";
    return;
  }

  await apiRequest(`/api/sessions/${session.session_id}`, {
    method: "PATCH",
    body: { title: nextTitle },
  });
  session.title = nextTitle.slice(0, 80);
  activeMenuSessionId.value = "";
  showToast("会话已重命名");
}

async function deleteSession() {
  const sessionId = activeMenuSessionId.value;
  const session = sessions.value.find((item) => item.session_id === sessionId);
  if (!session) {
    return;
  }

  await apiRequest(`/api/sessions/${sessionId}`, { method: "DELETE" });
  sessions.value = sessions.value.filter(
    (item) => item.session_id !== sessionId,
  );
  activeMenuSessionId.value = "";

  if (currentSessionId.value === sessionId) {
    if (sessions.value.length) {
      await activateSession(sessions.value[0]);
    } else {
      await createNewSession(false);
    }
  }
  showToast(`已删除“${session.title}”`);
}

function buildSessionTitle(questionText) {
  const normalizedQuestion = questionText.replace(/\s+/g, " ").trim();
  return normalizedQuestion.length > 24
    ? `${normalizedQuestion.slice(0, 24)}…`
    : normalizedQuestion;
}

async function renameDefaultSession(questionText) {
  if (!currentSession.value || currentSession.value.title !== defaultTitle) {
    return;
  }

  const title = buildSessionTitle(questionText);
  currentSession.value.title = title;
  try {
    await apiRequest(`/api/sessions/${currentSessionId.value}`, {
      method: "PATCH",
      body: { title },
    });
  } catch {
    currentSession.value.title = defaultTitle;
  }
}

async function ensureSession() {
  if (!currentSessionId.value) {
    await createNewSession(false);
  }
}

async function submitQuestion() {
  const questionText = question.value.trim();
  if (!questionText || isAnswering.value) {
    questionInput.value?.focus();
    return;
  }

  try {
    await ensureSession();
  } catch (error) {
    showToast(error.message);
    return;
  }

  isAnswering.value = true;
  messages.value.push(createMessage("user", questionText));
  question.value = "";
  await nextTick();
  resizeQuestionInput();
  scheduleScroll();
  void renameDefaultSession(questionText);

  const sourceFilter =
    selectedSource.value === "global" ? null : selectedSource.value;

  try {
    const response = await apiRequest("/api/query", {
      method: "POST",
      body: {
        query: questionText,
        source_filter: sourceFilter,
        session_id: currentSessionId.value,
      },
    });

    if (!response.is_streaming) {
      messages.value.push(
        createMessage("assistant", response.answer, {
          isAnswer: true,
          knowledgeTag: `${currentSubject.value.label}知识库`,
        }),
      );
      scheduleScroll();
      return;
    }

    const streamedMessage = createMessage("assistant", "", {
      isAnswer: true,
      isStreaming: true,
      knowledgeTag: `${currentSubject.value.label}知识库`,
    });
    messages.value.push(streamedMessage);
    scheduleScroll();

    await streamAnswer(
      {
        query: questionText,
        source_filter: sourceFilter,
        session_id: currentSessionId.value,
      },
      {
        onToken(token) {
          streamedMessage.content += token;
          scheduleScroll();
        },
      },
    );
    streamedMessage.isStreaming = false;
  } catch (error) {
    messages.value.push(
      createMessage("assistant", error.message, { isError: true }),
    );
    serviceReady.value = false;
    scheduleScroll();
  } finally {
    isAnswering.value = false;
    await nextTick();
    questionInput.value?.focus();
  }
}

function useSuggestion(suggestion) {
  question.value = suggestion;
  nextTick(() => {
    resizeQuestionInput();
    submitQuestion();
  });
}

function handleQuestionKeydown(event) {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    submitQuestion();
  }
}

async function copyMessage(content, successMessage) {
  try {
    await navigator.clipboard.writeText(content);
    if (successMessage) {
      showToast(successMessage);
    }
  } catch {
    showToast("浏览器未允许复制，请手动选择文本");
  }
}

function handleWindowClick(event) {
  if (!event.target.closest("#historyMenu") && !event.target.closest(".history-more")) {
    activeMenuSessionId.value = "";
  }
  if (!event.target.closest("#subjectPicker")) {
    subjectOptionsOpen.value = false;
  }
}

function handleWindowKeydown(event) {
  if (event.key === "Escape") {
    closeOverlays();
    sidebarOpen.value = false;
  }
}

async function initialize() {
  try {
    await Promise.all([
      loadSources(),
      loadSessions(),
      loadFaqSuggestions(),
    ]);
    serviceReady.value = true;
    if (sessions.value.length) {
      await activateSession(sessions.value[0]);
    } else {
      await createNewSession(false);
    }
  } catch (error) {
    serviceReady.value = false;
    setWelcomeMessage(`无法连接后端服务：${error.message}`);
  } finally {
    isInitializing.value = false;
  }
}

watch(sidebarOpen, (isOpen) => {
  document.body.classList.toggle("sidebar-open", isOpen);
});

onMounted(() => {
  window.addEventListener("click", handleWindowClick);
  window.addEventListener("keydown", handleWindowKeydown);
  window.addEventListener("resize", closeOverlays);
  initialize();
});

onBeforeUnmount(() => {
  window.clearTimeout(toastTimer);
  window.cancelAnimationFrame(scrollFrame);
  window.removeEventListener("click", handleWindowClick);
  window.removeEventListener("keydown", handleWindowKeydown);
  window.removeEventListener("resize", closeOverlays);
  document.body.classList.remove("sidebar-open");
});
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar" aria-label="会话导航">
      <div class="brand-block">
        <div class="brand-mark" aria-hidden="true">
          <img :src="brandAvatarUrl" alt="" />
        </div>
        <div>
          <p class="brand-name">EduRAG</p>
          <p class="brand-subtitle">IT 学习问答助手</p>
        </div>
      </div>

      <button class="new-chat-button" type="button" @click="createNewSession()">
        <svg aria-hidden="true" viewBox="0 0 24 24">
          <path d="M12 5v14M5 12h14" />
        </svg>
        开始新问题
      </button>

      <section class="sidebar-section" aria-labelledby="recentTitle">
        <div class="section-heading">
          <h2 id="recentTitle">最近访问</h2>
          <span>{{ sessions.length }}</span>
        </div>
        <nav class="history-list" aria-label="最近会话">
          <div
            v-for="session in sessions"
            :key="session.session_id"
            class="history-entry"
          >
            <button
              class="history-item"
              :class="{ active: session.session_id === currentSessionId }"
              type="button"
              @click="activateSession(session)"
            >
              <span class="history-copy"><strong>{{ session.title }}</strong></span>
            </button>
            <button
              class="history-more"
              type="button"
              :aria-label="`打开会话操作：${session.title}`"
              aria-haspopup="menu"
              :aria-expanded="activeMenuSessionId === session.session_id"
              @click.stop="openHistoryMenu(session.session_id, $event)"
            >
              <svg aria-hidden="true" viewBox="0 0 24 24">
                <circle cx="5" cy="12" r="1.5" />
                <circle cx="12" cy="12" r="1.5" />
                <circle cx="19" cy="12" r="1.5" />
              </svg>
            </button>
          </div>
        </nav>
      </section>

      <div class="sidebar-note">
        <div class="note-icon" aria-hidden="true">?</div>
        <div>
          <strong>不知道怎么问？</strong>
          <p>描述课程、报错信息或知识点，我会自动选择 FAQ 或知识库回答。</p>
        </div>
      </div>

      <div class="demo-account">
        <div class="student-avatar" aria-hidden="true">学</div>
        <div>
          <strong>本地学习账号</strong>
          <span>{{ serviceReady ? "API 联调模式" : "等待后端服务" }}</span>
        </div>
        <span class="demo-dot" :class="{ offline: !serviceReady }"></span>
      </div>
    </aside>

    <button
      class="sidebar-scrim"
      type="button"
      aria-label="关闭导航"
      @click="sidebarOpen = false"
    ></button>

    <main class="workspace">
      <header class="workspace-header">
        <button
          class="icon-button mobile-menu"
          type="button"
          aria-label="打开导航"
          @click="sidebarOpen = true"
        >
          <svg aria-hidden="true" viewBox="0 0 24 24">
            <path d="M4 7h16M4 12h16M4 17h16" />
          </svg>
        </button>
        <div class="conversation-title"><h1>{{ conversationTitle }}</h1></div>
      </header>

      <section class="chat-panel" aria-label="问答内容">
        <div ref="chatLog" class="chat-log" aria-live="polite">
          <div class="date-divider"><span>今天</span></div>

          <article
            v-for="message in messages"
            :key="message.id"
            class="message"
            :class="[
              message.role === 'user' ? 'user-message' : 'assistant-message',
              { 'error-message': message.isError },
            ]"
          >
            <div
              class="message-avatar"
              :class="message.role === 'user' ? 'user-avatar' : 'assistant-avatar'"
              aria-hidden="true"
            >
              {{ message.role === "user" ? "我" : "E" }}
            </div>
            <div class="message-content">
              <div v-if="message.role !== 'user'" class="message-meta">
                <strong>EduRAG 助手</strong>
                <span>{{ message.time }}</span>
              </div>
              <div
                class="message-bubble"
                :class="{ 'answer-bubble': message.isAnswer }"
              >
                <div v-if="message.isAnswer" class="answer-mode">
                  <span></span> 知识库增强回答
                </div>
                <MarkdownContent
                  v-if="message.isAnswer"
                  :content="message.content"
                  :streaming="message.isStreaming"
                />
                <p v-else :class="{ 'typing-cursor': message.isStreaming }">
                  {{ message.content }}
                </p>
              </div>
              <div
                v-if="message.role === 'user'"
                class="user-message-tools"
                aria-label="问题操作"
              >
                <span class="user-message-time">{{ message.time }}</span>
                <button
                  type="button"
                  class="user-message-copy"
                  aria-label="复制问题"
                  @click="copyMessage(message.content)"
                >
                  <svg aria-hidden="true" viewBox="0 0 24 24">
                    <path d="M9 8h10v11H9zM5 5h10v3M5 5v11h4" />
                  </svg>
                </button>
              </div>
              <div
                v-if="message.isAnswer && !message.isStreaming"
                class="message-tools"
                aria-label="回答操作"
              >
                <button
                  type="button"
                  class="text-action copy-answer"
                  @click="copyMessage(message.content, '回答已复制')"
                >
                  <svg aria-hidden="true" viewBox="0 0 24 24">
                    <path d="M9 8h10v11H9zM5 5h10v3M5 5v11h4" />
                  </svg>
                  复制
                </button>
                <span class="knowledge-tag">{{ message.knowledgeTag }}</span>
              </div>
            </div>
          </article>
        </div>

        <div class="composer-area">
          <div class="suggestion-row" aria-label="示例问题">
            <span>试着问</span>
            <button
              v-for="suggestion in suggestionQuestions"
              :key="suggestion"
              type="button"
              class="suggestion-chip"
              :disabled="isAnswering"
              @click="useSuggestion(suggestion)"
            >
              {{ suggestion }}
            </button>
          </div>
          <form class="composer" @submit.prevent="submitQuestion">
            <div class="composer-main">
              <textarea
                ref="questionInput"
                v-model="question"
                rows="1"
                maxlength="2000"
                placeholder="输入你的 IT 学习问题，Shift + Enter 换行"
                aria-label="输入问题"
                :disabled="isAnswering"
                @input="resizeQuestionInput"
                @keydown="handleQuestionKeydown"
              ></textarea>
              <div class="composer-footer">
                <div id="subjectPicker" class="subject-select">
                  <button
                    class="subject-trigger"
                    type="button"
                    aria-label="选择检索范围"
                    aria-haspopup="listbox"
                    :aria-expanded="subjectOptionsOpen"
                    :disabled="isAnswering"
                    @click.stop="subjectOptionsOpen = !subjectOptionsOpen"
                  >
                    <i aria-hidden="true"></i>
                    <span>{{ currentSubject.label }}</span>
                    <svg aria-hidden="true" viewBox="0 0 24 24">
                      <path d="m7 10 5 5 5-5" />
                    </svg>
                  </button>
                  <div
                    class="subject-options"
                    :class="{ show: subjectOptionsOpen }"
                    role="listbox"
                    aria-label="检索范围"
                    :aria-hidden="!subjectOptionsOpen"
                  >
                    <button
                      v-for="source in sourceOptions"
                      :key="source.value"
                      class="subject-option"
                      type="button"
                      role="option"
                      :aria-selected="source.value === selectedSource"
                      @click="selectSource(source.value)"
                    >
                      {{ source.label }}
                    </button>
                  </div>
                </div>
                <span class="input-hint">Enter 发送</span>
              </div>
              <button
                class="send-button"
                type="submit"
                aria-label="发送问题"
                :disabled="isAnswering || !question.trim()"
              >
                <svg aria-hidden="true" viewBox="0 0 24 24">
                  <path d="m5 12 14-7-4 14-3-6-7-1Z" />
                  <path d="m12 13 7-8" />
                </svg>
              </button>
            </div>
          </form>
        </div>
      </section>
    </main>
  </div>

  <div
    id="historyMenu"
    class="history-menu"
    :class="{ show: activeMenuSessionId }"
    :style="historyMenuStyle"
    role="menu"
    :aria-hidden="!activeMenuSessionId"
    @click.stop
  >
    <button
      class="history-menu-item"
      type="button"
      role="menuitem"
      @click="renameSession"
    >
      <svg aria-hidden="true" viewBox="0 0 24 24">
        <path d="m4 20 4.5-1 10-10-3.5-3.5-10 10L4 20Z" />
        <path d="m13.5 6.5 3.5 3.5M4 20h7" />
      </svg>
      <span>重命名</span>
    </button>
    <div class="history-menu-divider" role="separator"></div>
    <button
      class="history-menu-item danger"
      type="button"
      role="menuitem"
      @click="deleteSession"
    >
      <svg aria-hidden="true" viewBox="0 0 24 24">
        <path d="M5 7h14M9 7V4h6v3m-8 0 1 13h8l1-13M10 11v5M14 11v5" />
      </svg>
      <span>删除</span>
    </button>
  </div>

  <div class="toast" :class="{ show: toastMessage }" role="status" aria-live="polite">
    {{ toastMessage }}
  </div>
</template>
