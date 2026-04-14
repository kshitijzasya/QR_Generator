import { computed, reactive, ref } from "https://unpkg.com/vue@3/dist/vue.esm-browser.prod.js";
import { analyzeAssets, parseAssetsError } from "../api/assetsApi.js";
import { convertAssets, parseAssetsConvertError } from "../api/assetsConvertApi.js";
import { copyTextValue } from "../utils/copyText.js";

const TARGET_STACKS = [
  { value: "react", label: "React" },
  { value: "nextjs", label: "Next.js" },
  { value: "vue", label: "Vue" },
  { value: "nuxt", label: "Nuxt" },
  { value: "svelte", label: "Svelte" },
  { value: "html", label: "Plain HTML" },
];

function scoreClass(score) {
  if (score >= 85) {
    return "text-emerald-300 border-emerald-500/40 bg-emerald-500/10";
  }
  if (score >= 65) {
    return "text-amber-200 border-amber-500/40 bg-amber-500/10";
  }
  return "text-rose-200 border-rose-500/40 bg-rose-500/10";
}

function shortHost(url) {
  try {
    return new URL(url).host;
  } catch (error) {
    return url;
  }
}

function joinLines(items) {
  return (items || []).filter(Boolean).join("\n");
}

export default {
  name: "AssetsPage",
  setup() {
    const form = reactive({
      mode: "url",
      url: "",
      baseUrl: "",
      html: "",
    });
    const loading = ref(false);
    const converting = ref(false);
    const error = ref("");
    const result = ref(null);
    const conversionError = ref("");
    const conversion = ref(null);
    const copyNotice = ref("");
    const conversionForm = reactive({
      targetStack: "react",
      notes: "",
    });
    let copyNoticeTimer = null;

    const scoreCards = computed(() => {
      if (!result.value) {
        return [];
      }
      return [
        { label: "Overall", value: result.value.scores.overall },
        { label: "SEO", value: result.value.scores.seo },
        { label: "Performance", value: result.value.scores.performance },
      ];
    });

    async function onSubmit() {
      if (loading.value) {
        return;
      }

      error.value = "";
      result.value = null;

      if (form.mode === "url" && !form.url.trim()) {
        error.value = "Enter a page URL.";
        return;
      }
      if (form.mode === "html" && !form.html.trim()) {
        error.value = "Paste HTML to analyze.";
        return;
      }

      loading.value = true;
      try {
        const response = await analyzeAssets({
          url: form.mode === "url" ? form.url.trim() : "",
          html: form.mode === "html" ? form.html : "",
          base_url: form.mode === "html" ? form.baseUrl.trim() : "",
        });
        if (!response.ok) {
          error.value = await parseAssetsError(response);
          return;
        }
        result.value = await response.json();
        conversion.value = null;
        conversionError.value = "";
      } catch (requestError) {
        error.value = "Could not analyze the page right now. Try again.";
      } finally {
        loading.value = false;
      }
    }

    function resetForm() {
      form.mode = "url";
      form.url = "";
      form.baseUrl = "";
      form.html = "";
      error.value = "";
      result.value = null;
      conversionError.value = "";
      conversion.value = null;
      conversionForm.targetStack = "react";
      conversionForm.notes = "";
    }

    async function copyText(value) {
      const copied = await copyTextValue(value);
      copyNotice.value = copied ? "Copied to clipboard." : "Copy failed in this browser.";
      if (copyNoticeTimer) {
        clearTimeout(copyNoticeTimer);
      }
      copyNoticeTimer = window.setTimeout(() => {
        copyNotice.value = "";
        copyNoticeTimer = null;
      }, 1600);
    }

    async function convertToStack() {
      if (!result.value || converting.value) {
        return;
      }

      conversionError.value = "";
      conversion.value = null;
      converting.value = true;

      try {
        const response = await convertAssets({
          html: result.value.page.html_source,
          target_stack: conversionForm.targetStack,
          notes: conversionForm.notes,
        });
        if (!response.ok) {
          conversionError.value = await parseAssetsConvertError(response);
          return;
        }
        conversion.value = await response.json();
      } catch (requestError) {
        conversionError.value = "Could not convert the page right now. Try again.";
      } finally {
        converting.value = false;
      }
    }

    return {
      copyText,
      conversion,
      conversionError,
      conversionForm,
      convertToStack,
      converting,
      copyNotice,
      error,
      form,
      loading,
      onSubmit,
      resetForm,
      result,
      scoreCards,
      scoreClass,
      shortHost,
      TARGET_STACKS,
      joinLines,
    };
  },
  template: `
    <section class="mb-8">
      <a href="/" class="mb-4 inline-flex items-center gap-2 rounded-full border border-slate-700 bg-slate-900 px-4 py-2 text-sm font-medium text-slate-200 transition hover:border-slate-600 hover:text-white">
        Back to Tools
      </a>
      <div class="mt-4 inline-flex items-center rounded-full border border-cyan-500/30 bg-cyan-500/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-cyan-200">Asset Extractor</div>
      <h1 class="mt-4 text-3xl font-bold tracking-tight text-white md:text-5xl">Inspect a page from HTML or URL</h1>
      <p class="mt-3 max-w-3xl text-sm leading-6 text-slate-400 md:text-base">
        Extract markup, scripts, stylesheets, images, and structural signals. Scores are heuristic and based on what can be observed from the page source.
      </p>
    </section>

    <section class="grid gap-6 lg:grid-cols-[1.05fr_0.95fr]">
      <form class="rounded-3xl border border-slate-800 bg-slate-900/90 p-5 shadow-2xl shadow-slate-950/40" @submit.prevent="onSubmit">
        <div class="grid gap-3 sm:grid-cols-2">
          <button
            type="button"
            class="rounded-2xl border px-4 py-3 text-left transition"
            :class="form.mode === 'url' ? 'border-cyan-500/40 bg-cyan-500/10 text-white' : 'border-slate-700 bg-slate-950 text-slate-300'"
            @click="form.mode = 'url'"
          >
            <div class="text-sm font-semibold">Analyze URL</div>
            <div class="mt-1 text-xs text-slate-400">Fetch the page and inspect its public markup.</div>
          </button>
          <button
            type="button"
            class="rounded-2xl border px-4 py-3 text-left transition"
            :class="form.mode === 'html' ? 'border-cyan-500/40 bg-cyan-500/10 text-white' : 'border-slate-700 bg-slate-950 text-slate-300'"
            @click="form.mode = 'html'"
          >
            <div class="text-sm font-semibold">Paste HTML</div>
            <div class="mt-1 text-xs text-slate-400">Inspect a snapshot without making a network request.</div>
          </button>
        </div>

        <div v-if="form.mode === 'url'" class="mt-5">
          <label class="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Page URL</label>
          <input
            v-model="form.url"
            type="url"
            placeholder="https://example.com/landing-page"
            class="h-12 w-full rounded-2xl border border-slate-700 bg-slate-950 px-4 text-slate-100 placeholder:text-slate-500 focus:border-cyan-500 focus:outline-none"
          />
        </div>

        <template v-else>
          <div class="mt-5">
            <label class="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Base URL (optional)</label>
            <input
              v-model="form.baseUrl"
              type="url"
              placeholder="https://example.com"
              class="h-12 w-full rounded-2xl border border-slate-700 bg-slate-950 px-4 text-slate-100 placeholder:text-slate-500 focus:border-cyan-500 focus:outline-none"
            />
          </div>
          <div class="mt-4">
            <label class="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">HTML Source</label>
            <textarea
              v-model="form.html"
              rows="14"
              placeholder="<html>...</html>"
              class="w-full rounded-3xl border border-slate-700 bg-slate-950 px-4 py-3 font-mono text-sm text-slate-100 placeholder:text-slate-500 focus:border-cyan-500 focus:outline-none"
            ></textarea>
          </div>
        </template>

        <div class="mt-5 flex flex-wrap gap-3">
          <button type="submit" class="rounded-2xl bg-cyan-500 px-5 py-3 font-semibold text-slate-950 transition hover:bg-cyan-400" :disabled="loading">
            {{ loading ? 'Analyzing...' : 'Analyze page' }}
          </button>
          <button type="button" class="rounded-2xl border border-slate-700 bg-slate-950 px-5 py-3 font-semibold text-slate-200 transition hover:border-slate-600" @click="resetForm">
            Reset
          </button>
        </div>
        <p v-if="error" class="mt-4 text-sm text-rose-300">{{ error }}</p>
      </form>

      <div class="rounded-3xl border border-slate-800 bg-gradient-to-br from-slate-900 via-slate-900 to-cyan-950/50 p-5">
        <h2 class="text-lg font-semibold text-white">What this module returns</h2>
        <div class="mt-4 grid gap-3 text-sm text-slate-300">
          <div class="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
            Structural signals: title, meta description, canonical, headings, links, word count.
          </div>
          <div class="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
            Asset map: external scripts, stylesheets, images, fonts, preload hints, inline JS/CSS snippets.
          </div>
          <div class="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
            Heuristic scores: SEO and performance estimates from extracted markup, not browser timings.
          </div>
        </div>
      </div>
    </section>

    <section v-if="result" class="mt-8 space-y-6">
      <div class="grid gap-4 md:grid-cols-3">
        <div v-for="card in scoreCards" :key="card.label" class="rounded-3xl border p-5" :class="scoreClass(card.value)">
          <div class="text-xs font-semibold uppercase tracking-[0.18em]">{{ card.label }}</div>
          <div class="mt-3 text-4xl font-bold">{{ card.value }}</div>
        </div>
      </div>

      <div class="rounded-3xl border border-slate-800 bg-slate-900 p-5">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 class="text-xl font-semibold text-white">{{ result.page.title || 'Untitled page' }}</h2>
            <p class="mt-1 text-sm text-slate-400">{{ result.scores.note }}</p>
          </div>
          <button type="button" class="rounded-2xl border border-slate-700 px-4 py-2 text-sm text-slate-200 transition hover:border-slate-600" @click="copyText(result.page.html_preview)">
            Copy HTML preview
          </button>
        </div>

        <div class="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <div class="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
            <div class="text-xs uppercase tracking-[0.18em] text-slate-500">Input</div>
            <div class="mt-2 text-sm text-white">{{ result.input.mode === 'url' ? 'Fetched from URL' : 'Pasted HTML' }}</div>
            <div class="mt-1 text-xs text-slate-400">{{ result.fetch.final_url || result.input.base_url || 'No base URL' }}</div>
          </div>
          <div class="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
            <div class="text-xs uppercase tracking-[0.18em] text-slate-500">Document</div>
            <div class="mt-2 text-sm text-white">{{ result.page.word_count }} words</div>
            <div class="mt-1 text-xs text-slate-400">{{ result.fetch.html_bytes }} bytes of HTML</div>
          </div>
          <div class="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
            <div class="text-xs uppercase tracking-[0.18em] text-slate-500">Links</div>
            <div class="mt-2 text-sm text-white">{{ result.page.internal_links }} internal / {{ result.page.external_links }} external</div>
            <div class="mt-1 text-xs text-slate-400">Canonical: {{ result.page.canonical || 'missing' }}</div>
          </div>
          <div class="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
            <div class="text-xs uppercase tracking-[0.18em] text-slate-500">Headers</div>
            <div class="mt-2 text-sm text-white">H1: {{ result.page.h1_count }} | H2: {{ result.page.h2_count }}</div>
            <div class="mt-1 text-xs text-slate-400">Lang: {{ result.page.lang || 'missing' }}</div>
          </div>
        </div>
      </div>

      <div class="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
        <div class="rounded-3xl border border-slate-800 bg-slate-900 p-5">
          <div class="flex flex-wrap items-center justify-between gap-3">
            <h3 class="text-lg font-semibold text-white">Findings</h3>
            <button type="button" class="rounded-2xl border border-slate-700 px-4 py-2 text-sm text-slate-200 transition hover:border-slate-600" @click="copyText(joinLines(result.findings))">
              Copy findings
            </button>
          </div>
          <ul class="mt-4 max-h-80 space-y-2 overflow-auto pr-1 text-sm text-slate-300">
            <li v-for="item in result.findings" :key="item" class="rounded-2xl border border-slate-800 bg-slate-950/70 px-4 py-3">{{ item }}</li>
          </ul>
        </div>

        <div class="rounded-3xl border border-slate-800 bg-slate-900 p-5">
          <div class="flex flex-wrap items-center justify-between gap-3">
            <h3 class="text-lg font-semibold text-white">Checks</h3>
            <button type="button" class="rounded-2xl border border-slate-700 px-4 py-2 text-sm text-slate-200 transition hover:border-slate-600" @click="copyText(joinLines([...result.scores.seo_checks.map((check) => 'SEO: ' + check.label + ' - ' + (check.passed ? 'Pass' : 'Needs work') + ' (' + check.weight + ' pts)'), ...result.scores.performance_checks.map((check) => 'Performance: ' + check.label + ' - ' + (check.passed ? 'Pass' : 'Needs work') + ' (' + check.weight + ' pts)')]))">
              Copy checks
            </button>
          </div>
          <div class="mt-4 grid gap-4 md:grid-cols-2">
            <div>
              <div class="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">SEO checks</div>
              <div class="max-h-80 space-y-2 overflow-auto pr-1">
                <div v-for="check in result.scores.seo_checks" :key="check.label" class="rounded-2xl border border-slate-800 bg-slate-950/70 px-4 py-3 text-sm">
                  <div class="font-medium text-white">{{ check.label }}</div>
                  <div class="mt-1 text-xs" :class="check.passed ? 'text-emerald-300' : 'text-rose-300'">{{ check.passed ? 'Pass' : 'Needs work' }} · {{ check.weight }} pts</div>
                </div>
              </div>
            </div>
            <div>
              <div class="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Performance checks</div>
              <div class="max-h-80 space-y-2 overflow-auto pr-1">
                <div v-for="check in result.scores.performance_checks" :key="check.label" class="rounded-2xl border border-slate-800 bg-slate-950/70 px-4 py-3 text-sm">
                  <div class="font-medium text-white">{{ check.label }}</div>
                  <div class="mt-1 text-xs" :class="check.passed ? 'text-emerald-300' : 'text-rose-300'">{{ check.passed ? 'Pass' : 'Needs work' }} · {{ check.weight }} pts</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="rounded-3xl border border-slate-800 bg-slate-900 p-5">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 class="text-lg font-semibold text-white">Convert to your stack</h3>
            <p class="mt-1 text-sm text-slate-400">Generate a copyable component version from the extracted page markup.</p>
          </div>
          <div class="rounded-full border border-slate-700 bg-slate-950 px-3 py-1 text-xs font-medium text-slate-300">
            Uses AI when configured, otherwise falls back to a deterministic wrapper.
          </div>
        </div>

        <div class="mt-5 grid gap-4 lg:grid-cols-[220px_1fr_auto]">
          <div>
            <label class="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Target stack</label>
            <select v-model="conversionForm.targetStack" class="h-12 w-full rounded-2xl border border-slate-700 bg-slate-950 px-4 text-slate-100 focus:border-cyan-500 focus:outline-none">
              <option v-for="option in TARGET_STACKS" :key="option.value" :value="option.value">{{ option.label }}</option>
            </select>
          </div>
          <div>
            <label class="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Conversion notes</label>
            <input
              v-model="conversionForm.notes"
              type="text"
              placeholder="Example: keep Tailwind classes, split hero section later"
              class="h-12 w-full rounded-2xl border border-slate-700 bg-slate-950 px-4 text-slate-100 placeholder:text-slate-500 focus:border-cyan-500 focus:outline-none"
            />
          </div>
          <div class="flex items-end">
            <button type="button" class="h-12 rounded-2xl bg-cyan-500 px-5 font-semibold text-slate-950 transition hover:bg-cyan-400" @click="convertToStack" :disabled="converting">
              {{ converting ? 'Converting...' : 'Convert' }}
            </button>
          </div>
        </div>

        <p v-if="conversionError" class="mt-4 text-sm text-rose-300">{{ conversionError }}</p>
        <p v-if="copyNotice" class="mt-3 text-sm text-cyan-300">{{ copyNotice }}</p>

        <div v-if="conversion" class="mt-5 rounded-3xl border border-slate-800 bg-slate-950/80 p-5">
          <div class="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div class="text-sm font-semibold text-white">{{ conversion.file_name }}</div>
              <div class="mt-1 text-xs text-slate-400">Source: {{ conversion.source }} · Language: {{ conversion.language }}</div>
            </div>
            <button type="button" class="rounded-2xl border border-slate-700 px-4 py-2 text-sm text-slate-200 transition hover:border-slate-600" @click="copyText(conversion.output)">
              Copy output
            </button>
          </div>
          <pre class="mt-4 max-h-[32rem] overflow-auto rounded-2xl border border-slate-800 bg-black/30 p-4 text-xs leading-6 text-slate-200">{{ conversion.output }}</pre>
        </div>
      </div>

      <div class="grid gap-6 xl:grid-cols-2">
        <div class="rounded-3xl border border-slate-800 bg-slate-900 p-5">
          <div class="flex flex-wrap items-center justify-between gap-3">
            <h3 class="text-lg font-semibold text-white">Asset counts</h3>
            <button type="button" class="rounded-2xl border border-slate-700 px-4 py-2 text-sm text-slate-200 transition hover:border-slate-600" @click="copyText(joinLines(['Scripts: ' + result.assets.scripts.count, 'Stylesheets: ' + result.assets.stylesheets.count, 'Images: ' + result.assets.images.count, 'Fonts: ' + result.assets.fonts.count, 'Preloads: ' + result.assets.preloads.count, 'Other assets: ' + result.assets.other.count]))">
              Copy counts
            </button>
          </div>
          <div class="mt-4 grid gap-3 sm:grid-cols-2">
            <div class="rounded-2xl border border-slate-800 bg-slate-950/70 p-4 text-sm text-slate-300">Scripts: <span class="font-semibold text-white">{{ result.assets.scripts.count }}</span></div>
            <div class="rounded-2xl border border-slate-800 bg-slate-950/70 p-4 text-sm text-slate-300">Stylesheets: <span class="font-semibold text-white">{{ result.assets.stylesheets.count }}</span></div>
            <div class="rounded-2xl border border-slate-800 bg-slate-950/70 p-4 text-sm text-slate-300">Images: <span class="font-semibold text-white">{{ result.assets.images.count }}</span></div>
            <div class="rounded-2xl border border-slate-800 bg-slate-950/70 p-4 text-sm text-slate-300">Fonts: <span class="font-semibold text-white">{{ result.assets.fonts.count }}</span></div>
            <div class="rounded-2xl border border-slate-800 bg-slate-950/70 p-4 text-sm text-slate-300">Preloads: <span class="font-semibold text-white">{{ result.assets.preloads.count }}</span></div>
            <div class="rounded-2xl border border-slate-800 bg-slate-950/70 p-4 text-sm text-slate-300">Other assets: <span class="font-semibold text-white">{{ result.assets.other.count }}</span></div>
          </div>
        </div>

        <div class="rounded-3xl border border-slate-800 bg-slate-900 p-5">
          <div class="flex flex-wrap items-center justify-between gap-3">
            <h3 class="text-lg font-semibold text-white">Markup preview</h3>
            <button type="button" class="rounded-2xl border border-slate-700 px-4 py-2 text-sm text-slate-200 transition hover:border-slate-600" @click="copyText(result.page.html_preview)">
              Copy markup
            </button>
          </div>
          <pre class="mt-4 max-h-80 overflow-auto rounded-2xl border border-slate-800 bg-slate-950/80 p-4 text-xs leading-6 text-slate-300">{{ result.page.html_preview }}</pre>
        </div>
      </div>

      <div class="grid gap-6 xl:grid-cols-2">
        <div class="rounded-3xl border border-slate-800 bg-slate-900 p-5">
          <div class="flex flex-wrap items-center justify-between gap-3">
            <h3 class="text-lg font-semibold text-white">Scripts</h3>
            <button type="button" class="rounded-2xl border border-slate-700 px-4 py-2 text-sm text-slate-200 transition hover:border-slate-600" @click="copyText(joinLines(result.assets.scripts.urls))">
              Copy scripts
            </button>
          </div>
          <div class="mt-4 max-h-80 space-y-2 overflow-auto pr-1">
            <div v-for="item in result.assets.scripts.urls" :key="item" class="rounded-2xl border border-slate-800 bg-slate-950/70 px-4 py-3 text-sm text-slate-300">
              {{ item }} <span class="text-xs text-slate-500">({{ shortHost(item) }})</span>
            </div>
            <div v-if="!result.assets.scripts.urls.length" class="text-sm text-slate-500">No external scripts found.</div>
          </div>
        </div>

        <div class="rounded-3xl border border-slate-800 bg-slate-900 p-5">
          <div class="flex flex-wrap items-center justify-between gap-3">
            <h3 class="text-lg font-semibold text-white">Stylesheets</h3>
            <button type="button" class="rounded-2xl border border-slate-700 px-4 py-2 text-sm text-slate-200 transition hover:border-slate-600" @click="copyText(joinLines(result.assets.stylesheets.urls))">
              Copy stylesheets
            </button>
          </div>
          <div class="mt-4 max-h-80 space-y-2 overflow-auto pr-1">
            <div v-for="item in result.assets.stylesheets.urls" :key="item" class="rounded-2xl border border-slate-800 bg-slate-950/70 px-4 py-3 text-sm text-slate-300">
              {{ item }} <span class="text-xs text-slate-500">({{ shortHost(item) }})</span>
            </div>
            <div v-if="!result.assets.stylesheets.urls.length" class="text-sm text-slate-500">No stylesheets found.</div>
          </div>
        </div>

        <div class="rounded-3xl border border-slate-800 bg-slate-900 p-5">
          <div class="flex flex-wrap items-center justify-between gap-3">
            <h3 class="text-lg font-semibold text-white">Images</h3>
            <button type="button" class="rounded-2xl border border-slate-700 px-4 py-2 text-sm text-slate-200 transition hover:border-slate-600" @click="copyText(joinLines(result.assets.images.urls))">
              Copy images
            </button>
          </div>
          <div class="mt-4 max-h-80 space-y-2 overflow-auto pr-1">
            <div v-for="item in result.assets.images.urls" :key="item" class="rounded-2xl border border-slate-800 bg-slate-950/70 px-4 py-3 text-sm text-slate-300">
              {{ item }} <span class="text-xs text-slate-500">({{ shortHost(item) }})</span>
            </div>
            <div v-if="!result.assets.images.urls.length" class="text-sm text-slate-500">No images found.</div>
          </div>
        </div>

        <div class="rounded-3xl border border-slate-800 bg-slate-900 p-5">
          <div class="flex flex-wrap items-center justify-between gap-3">
            <h3 class="text-lg font-semibold text-white">Inline code snippets</h3>
            <button type="button" class="rounded-2xl border border-slate-700 px-4 py-2 text-sm text-slate-200 transition hover:border-slate-600" @click="copyText(joinLines([...result.assets.scripts.inline_snippets.map((item) => 'Inline script:\\n' + item), ...result.assets.stylesheets.inline_snippets.map((item) => 'Inline style:\\n' + item)]))">
              Copy snippets
            </button>
          </div>
          <div class="mt-4 max-h-80 space-y-3 overflow-auto pr-1">
            <div v-for="item in result.assets.scripts.inline_snippets" :key="item" class="rounded-2xl border border-slate-800 bg-slate-950/80 p-4">
              <div class="mb-2 text-xs uppercase tracking-[0.18em] text-slate-500">Inline script</div>
              <pre class="overflow-auto whitespace-pre-wrap text-xs text-slate-300">{{ item }}</pre>
            </div>
            <div v-for="item in result.assets.stylesheets.inline_snippets" :key="item" class="rounded-2xl border border-slate-800 bg-slate-950/80 p-4">
              <div class="mb-2 text-xs uppercase tracking-[0.18em] text-slate-500">Inline style</div>
              <pre class="overflow-auto whitespace-pre-wrap text-xs text-slate-300">{{ item }}</pre>
            </div>
            <div v-if="!result.assets.scripts.inline_snippets.length && !result.assets.stylesheets.inline_snippets.length" class="text-sm text-slate-500">No inline JS/CSS snippets found.</div>
          </div>
        </div>
      </div>
    </section>
  `,
};
