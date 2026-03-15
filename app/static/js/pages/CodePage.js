import { computed, reactive, ref } from "https://unpkg.com/vue@3/dist/vue.esm-browser.prod.js";
import { generateCode, parseCodeError } from "../api/codeApi";

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

    const frameworkOptions = computed(() => FRAMEWORK_OPTIONS[form.language] || []);

    function onLanguageChange() {
      form.framework = frameworkOptions.value[0] || "";
    }

    async function generatePlaceholder() {
      error.value = "";
      if (!form.prompt.trim()) {
        error.value = "Enter what you want to generate.";
        return;
      }

      loading.value = true;
      result.value = "";

      try {
          const response = await generateCode({
            task: form.prompt.trim(),
            language: form.language,
            framework: form.framework,
          });
  
          if (!response.ok) {
            error.value = await parseCodeError(response);
            return;
          }
  
          result.value = await response.json();
        } catch (requestError) {
          error.value = "Could not generate results right now. Try again.";
        } finally {
          loading.value = false;
        }
    }

    async function copyResult() {
      if (!result.value.trim() || !navigator.clipboard) {
        return;
      }
      await navigator.clipboard.writeText(result.value);
    }

    return {
      copyResult,
      error,
      form,
      frameworkOptions,
      generatePlaceholder,
      loading,
      onLanguageChange,
      result,
      LANGUAGE_OPTIONS,
    };
  },
  template: `
    <section class="mb-6">
      <span class="mb-3 inline-flex items-center rounded-full border border-slate-700/80 bg-slate-900 px-3 py-1 text-xs font-medium text-slate-200">AI Code Generator</span>
      <h1 class="text-3xl font-bold tracking-tight text-slate-50 md:text-4xl">Generate code from one prompt</h1>
      <p class="mt-2 text-sm text-slate-400 md:text-base">This is the new entry point for the code generation module. The frontend shell is ready; backend generation can plug into this next.</p>

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

        <div class="grid gap-3 md:grid-cols-[1fr_220px]">
          <div class="rounded-2xl border border-slate-700 bg-slate-900/80 px-4 py-3 text-sm text-slate-400">
            Start with the frontend shell, then wire the backend code-generation API behind this module.
          </div>
          <button class="h-12 rounded-xl bg-gradient-to-r from-blue-500 to-blue-600 font-semibold text-white transition hover:from-blue-400 hover:to-blue-500 disabled:cursor-not-allowed disabled:opacity-70" type="submit" :disabled="loading">
            {{ loading ? 'Preparing...' : 'Generate code' }}
          </button>
        </div>
      </form>

      <p class="mt-2 text-sm text-rose-400" v-if="error">{{ error }}</p>
    </section>

    <section v-if="result" class="rounded-2xl border border-slate-700 bg-slate-900 p-4">
      <div class="mb-3 flex items-center justify-between gap-3">
        <h2 class="text-xl font-semibold text-white">Module Output</h2>
        <button type="button" class="rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-slate-100 transition hover:border-slate-500" @click="copyResult">Copy</button>
      </div>
      <pre class="overflow-x-auto whitespace-pre-wrap rounded-xl border border-slate-700 bg-slate-800 p-4 text-sm text-slate-100">{{ result }}</pre>
    </section>
  `,
};
