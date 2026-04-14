import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from "https://unpkg.com/vue@3/dist/vue.esm-browser.prod.js";
import { generateCode, parseCodeError } from "../api/codeApi.js";

const LANGUAGE_OPTIONS = [
  { value: "javascript", label: "JavaScript" },
  { value: "nodejs", label: "Node.js" },
  { value: "php", label: "PHP" },
  { value: "python", label: "Python" },
  { value: "typescript", label: "TypeScript" },
  { value: "go", label: "Go" },
];

const FRAMEWORK_OPTIONS = {
  javascript: ["Node.js", "Express", "React", "Vanilla JS"],
  nodejs: ["Node.js", "Express", "NestJS", "Fastify"],
  php: ["Laravel", "Symfony", "CodeIgniter", "Plain PHP"],
  python: ["Flask", "FastAPI", "Django", "Script"],
  typescript: ["Node.js", "Next.js", "React", "NestJS"],
  go: ["Standard Library", "Gin", "Fiber"],
};

export default {
  name: "CodePage",
  setup() {
    const form = reactive({
      prompt: "",
      language: "python",
      framework: "Flask",
    });
    const loading = ref(false);
    const error = ref("");
    const result = ref("");
    const visibleText = ref("");
    const conversationId = ref("");
    const lastActivityAt = ref(0);
    const freshNotice = ref("");
    const outputRef = ref(null);
    let renderTimer = null;
    let inactivityTimer = null;

    const conversationTimeoutMs = 5 * 60 * 1000;

    const frameworkOptions = computed(() => FRAMEWORK_OPTIONS[form.language] || []);
    const hasActiveConversation = computed(() => Boolean(conversationId.value));

    function onLanguageChange() {
      form.framework = frameworkOptions.value[0] || "";
    }

    function startFreshConversation(showNotice = true) {
      conversationId.value = "";
      lastActivityAt.value = 0;
      result.value = "";
      visibleText.value = "";
      if (renderTimer) {
        clearInterval(renderTimer);
        renderTimer = null;
      }
      if (showNotice) {
        freshNotice.value = "Started a fresh conversation.";
        window.setTimeout(() => {
          freshNotice.value = "";
        }, 1800);
      }
    }

    function resetInactiveConversation() {
      if (!conversationId.value || !lastActivityAt.value) {
        return;
      }
      if (Date.now() - lastActivityAt.value < conversationTimeoutMs) {
        return;
      }
      startFreshConversation(false);
      freshNotice.value = "Context expired after 5 minutes of inactivity. Started fresh.";
      window.setTimeout(() => {
        freshNotice.value = "";
      }, 2400);
    }

    async function generatePlaceholder() {
      error.value = "";
      if (!form.prompt.trim()) {
        error.value = "Enter what you want to generate.";
        return;
      }

      resetInactiveConversation();

      loading.value = true;
      result.value = "";
      visibleText.value = "";

      try {
        const response = await generateCode({
          task: form.prompt.trim(),
          language: form.language,
          framework: form.framework,
          conversation_id: conversationId.value,
          fresh_conversation: !conversationId.value,
        });

        if (!response.ok) {
          error.value = await parseCodeError(response);
          return;
        }

        result.value = await response.json();
        conversationId.value = result.value.conversation_id || "";
        lastActivityAt.value = Date.now();
        if (result.value.is_fresh_conversation) {
          freshNotice.value = "Fresh conversation started.";
          window.setTimeout(() => {
            freshNotice.value = "";
          }, 1600);
        }
        renderResultCode(result.value.content || "");
      } catch (requestError) {
        error.value = "Could not generate results right now. Try again.";
      } finally {
        loading.value = false;
      }
    }

    function renderResultCode(code) {
      if (renderTimer) {
        clearInterval(renderTimer);
        renderTimer = null;
      }

      const tokens = String(code || "").match(/\S+|\s+/g) || [];
      let index = 0;
      visibleText.value = "";

      renderTimer = window.setInterval(() => {
        if (index >= tokens.length) {
          clearInterval(renderTimer);
          renderTimer = null;
          return;
        }

        visibleText.value += tokens[index];
        index += 1;
        nextTick(() => {
          if (outputRef.value) {
            outputRef.value.scrollTop = outputRef.value.scrollHeight;
            outputRef.value.scrollIntoView({ block: "end", behavior: "smooth" });
          }
        });
      }, 30);
    }

    async function copyResult() {
      const content = String(result.value?.content || "").trim();
      if (!content || !navigator.clipboard) {
        return;
      }
      await navigator.clipboard.writeText(content);
    }

    onMounted(() => {
      inactivityTimer = window.setInterval(resetInactiveConversation, 10000);
    });

    onBeforeUnmount(() => {
      if (renderTimer) {
        clearInterval(renderTimer);
      }
      if (inactivityTimer) {
        clearInterval(inactivityTimer);
      }
    });

    return {
      copyResult,
      conversationId,
      error,
      form,
      freshNotice,
      frameworkOptions,
      generatePlaceholder,
      hasActiveConversation,
      loading,
      onLanguageChange,
      outputRef,
      result,
      startFreshConversation,
      visibleText,
      LANGUAGE_OPTIONS,
    };
  },
  template: `
    <section class="mb-6">
      <a href="/" class="mb-4 inline-flex items-center gap-2 rounded-full border border-slate-700 bg-slate-900 px-4 py-2 text-sm font-medium text-slate-200 transition hover:border-slate-600 hover:text-white">
        Back to Tools
      </a> &nbsp;
      <span class="mb-3 inline-flex items-center rounded-full border border-slate-700/80 bg-slate-900 px-3 py-1 text-xs font-medium text-slate-200">AI Code Generator</span>
      <h1 class="text-3xl font-bold tracking-tight text-slate-50 md:text-4xl">Generate code from one prompt</h1>
      <p class="mt-2 text-sm text-slate-400 md:text-base">This is the new entry point for the code generation module.</p>

      <form class="mt-4 grid gap-3 rounded-2xl border border-slate-700 bg-gradient-to-br from-slate-900 to-slate-800 p-4" @submit.prevent="generatePlaceholder">
        <div class="grid gap-3 md:grid-cols-2">
          <div>
            <label class="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Language</label>
            <select class="h-12 w-full rounded-xl border border-slate-700 bg-slate-800 px-3 text-slate-100 focus:border-blue-500 focus:outline-none" v-model="form.language" @change="onLanguageChange">
              <option v-for="option in LANGUAGE_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option>
            </select>
          </div>
          <div>
            <label class="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Framework</label>
            <select class="h-12 w-full rounded-xl border border-slate-700 bg-slate-800 px-3 text-slate-100 focus:border-blue-500 focus:outline-none" v-model="form.framework">
              <option v-for="option in frameworkOptions" :key="option" :value="option">{{ option }}</option>
            </select>
          </div>
        </div>

        <div>
          <label class="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Prompt</label>
          <textarea
            class="min-h-[160px] w-full rounded-2xl border border-slate-700 bg-slate-800 px-4 py-3 text-slate-100 placeholder:text-slate-500 focus:border-blue-500 focus:outline-none"
            v-model="form.prompt"
            placeholder="Example: Build a Flask API route that accepts a prompt and returns generated Python code with validation."
          ></textarea>
        </div>

        <div class="grid gap-3 md:grid-cols-[1fr_180px]">
          <button class="h-12 rounded-xl bg-gradient-to-r from-blue-500 to-blue-600 font-semibold text-white transition hover:from-blue-400 hover:to-blue-500 disabled:cursor-not-allowed disabled:opacity-70" type="submit" :disabled="loading">
            {{ loading ? 'Preparing...' : 'Generate code' }}
          </button>
          <button type="button" class="h-12 rounded-xl border border-slate-600 bg-slate-900 font-semibold text-slate-100 transition hover:border-slate-500 hover:text-white disabled:cursor-not-allowed disabled:opacity-70" @click="startFreshConversation()" :disabled="loading && !hasActiveConversation">
            Start Fresh
          </button>
        </div>
      </form>

      <p class="mt-2 text-sm text-rose-400" v-if="error">{{ error }}</p>
      <p class="mt-2 text-sm text-emerald-300" v-if="freshNotice">{{ freshNotice }}</p>
      <p class="mt-2 text-xs text-slate-500" v-if="conversationId">Conversation ID: {{ conversationId }}</p>
    </section>

    <section v-if="visibleText" class="rounded-2xl border border-slate-700 bg-slate-900 p-4">
      <div class="mb-3 flex items-center justify-between gap-3">
        <h2 class="text-xl font-semibold text-white">Output</h2>
        <button type="button" class="rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-slate-100 transition hover:border-slate-500" @click="copyResult">Copy</button>
      </div>
      <pre ref="outputRef" class="overflow-auto whitespace-pre-wrap rounded-xl border border-slate-700 bg-slate-800 p-4 text-sm text-slate-100 max-h-96">{{ visibleText }}</pre>
    </section>
  `,
};
