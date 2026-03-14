import { computed, reactive, ref } from "https://unpkg.com/vue@3/dist/vue.esm-browser.prod.js";
import { generateSeo, parseSeoError } from "../api/seoApi.js";

function cleanTag(tag) {
  return String(tag || "").replace(/^#/, "").trim();
}

function uniqueList(items) {
  const out = [];
  const seen = new Set();
  for (const item of items) {
    const value = String(item || "").trim();
    if (!value) {
      continue;
    }
    const key = value.toLowerCase();
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    out.push(value);
  }
  return out;
}

export default {
  name: "SeoPage",
  setup() {
    const form = reactive({
      topic: "",
      platform: "youtube",
      contentFormat: "long",
      useOwnKey: false,
      youtubeApiKey: "",
    });
    const result = ref(null);
    const error = ref("");
    const loading = ref(false);
    const copyNotice = ref("");
    let copyNoticeTimer = null;

    const topTitle = computed(() => result.value?.titles?.[0] || "");
    const qualityScores = computed(() => result.value?.quality_scores || {});
    const validationChecks = computed(() => result.value?.validation?.checks || {});
    const overallScore = computed(() => qualityScores.value?.overall_score || 0);
    const titleScore = computed(() => qualityScores.value?.best_title_score || 0);
    const descriptionScore = computed(() => qualityScores.value?.description_score || 0);
    const hashtagScore = computed(() => qualityScores.value?.hashtags_score || 0);
    const seoTagsScore = computed(() => qualityScores.value?.seo_tags_score || 0);
    const thumbnailTextScore = computed(() => qualityScores.value?.thumbnail_text_score || 0);
    const titleReadability = computed(() => qualityScores.value?.title_readability || {});
    const descriptionReadability = computed(() => qualityScores.value?.description_readability || {});

    const relatedKeywords = computed(() => {
      if (!result.value) {
        return [];
      }
      const tags = uniqueList([
        ...(result.value.seo_tags || []).map(cleanTag),
        ...(result.value.hashtags || []).map(cleanTag),
      ]).slice(0, 8);

      return tags.map((label, idx) => ({
        label,
        score: Math.max(60, 74 - idx),
      }));
    });
    const relatedKeywordsText = computed(() =>
      relatedKeywords.value.map((item) => `${item.score} ${item.label}`).join(", ")
    );

    const hashtagItems = computed(() => {
      if (!result.value) {
        return [];
      }
      const tags = uniqueList((result.value.hashtags || []).map(cleanTag)).slice(0, 15);

      return tags.map((label, idx) => ({
        label,
        score: Math.max(55, 74 - idx),
      }));
    });
    const hashtagText = computed(() => hashtagItems.value.map((tag) => tag.label).join(", "));

    const seoTagItems = computed(() => {
      if (!result.value) {
        return [];
      }
      const tags = uniqueList((result.value.seo_tags || []).map(cleanTag)).slice(0, 20);

      return tags.map((label, idx) => ({
        label,
        score: Math.max(60, 78 - idx),
      }));
    });
    const seoTagsText = computed(() => seoTagItems.value.map((tag) => tag.label).join(", "));

    const thumbnailCards = computed(() => {
      if (!result.value) {
        return [];
      }

      const labels = uniqueList([
        ...(result.value.thumbnail_text || []),
        ...(result.value.titles || []).slice(0, 3),
      ]).slice(0, 3);

      return labels.map((label, idx) => ({
        label,
        variant: idx % 3,
      }));
    });
    const thumbnailText = computed(() => thumbnailCards.value.map((item) => item.label).join("\n"));

    const hookLine = computed(() => {
      if (!result.value) {
        return "";
      }
      const seed = result.value.thumbnail_text?.[0] || topTitle.value;
      return seed
        ? `Can ${seed.toLowerCase()}? Watch this before you publish.`
        : "Open with a high-curiosity claim in your first 5 seconds.";
    });

    const outlinePoints = computed(() => {
      if (!result.value) {
        return [];
      }
      return uniqueList([
        "Hook and context in first 15 seconds",
        ...(result.value.thumbnail_ideas || []).slice(0, 2),
        "Key explanation with proof/examples",
        "Strong CTA and keyword recap at the end",
      ]).slice(0, 5);
    });
    const outlineText = computed(() => outlinePoints.value.join("\n"));

    async function onSubmit() {
      if (loading.value) {
        return;
      }

      error.value = "";
      result.value = null;

      if (!form.topic.trim()) {
        error.value = "Please enter your video idea.";
        return;
      }

      const useOwnLive = form.useOwnKey;
      // if (useOwnLive && !form.youtubeApiKey.trim()) {
      //   error.value = "Enter your YouTube API key for personal-key mode.";
      //   return;
      // }

      loading.value = true;
      try {
        const response = await generateSeo({
          topic: form.topic,
          platform: form.platform,
          content_format: form.contentFormat,
          live: true,
          use_own_key: useOwnLive,
          youtube_api_key: useOwnLive ? form.youtubeApiKey.trim() : "",
          allow_fallback: true,
        });

        if (!response.ok) {
          error.value = await parseSeoError(response);
          return;
        }

        result.value = await response.json();
      } catch (requestError) {
        error.value = "Could not generate results right now. Try again.";
      } finally {
        loading.value = false;
      }
    }

    async function copyText(value) {
      const text = String(value || "").trim();
      if (!text || !navigator.clipboard) {
        return;
      }
      try {
        await navigator.clipboard.writeText(text);
        copyNotice.value = "Copied to clipboard";
        if (copyNoticeTimer) {
          clearTimeout(copyNoticeTimer);
        }
        copyNoticeTimer = setTimeout(() => {
          copyNotice.value = "";
          copyNoticeTimer = null;
        }, 1500);
      } catch (copyError) {
        // Clipboard API may be blocked in some browsers.
      }
    }

    function onRegenerate() {
      onSubmit();
    }

    function scoreBadgeClass(score) {
      if (score >= 85) {
        return "border-emerald-500/40 bg-emerald-500/10 text-emerald-300";
      }
      if (score >= 70) {
        return "border-amber-500/40 bg-amber-500/10 text-amber-300";
      }
      return "border-rose-500/40 bg-rose-500/10 text-rose-300";
    }

    return {
      copyText,
      copyNotice,
      descriptionReadability,
      descriptionScore,
      error,
      form,
      hookLine,
      loading,
      onRegenerate,
      onSubmit,
      outlinePoints,
      outlineText,
      overallScore,
      relatedKeywords,
      relatedKeywordsText,
      result,
      scoreBadgeClass,
      hashtagItems,
      hashtagText,
      seoTagItems,
      seoTagsText,
      seoTagsScore,
      thumbnailCards,
      thumbnailText,
      thumbnailTextScore,
      topTitle,
      titleReadability,
      titleScore,
      validationChecks,
      hashtagScore,
    };
  },
  template: `
    <section class="mb-6">
      <span class="mb-3 inline-flex items-center rounded-full border border-slate-700/80 bg-slate-900 px-3 py-1 text-xs font-medium text-slate-200">AI YouTube Content Studio</span>
      <h1 class="text-3xl font-bold tracking-tight text-slate-50 md:text-4xl">Get better SEO results in one workspace</h1>
      <p class="mt-2 text-sm text-slate-400 md:text-base">Generate title, description, tags, hook, and outline for your video idea.</p>

      <form class="mt-4 grid gap-3 rounded-2xl border border-slate-700 bg-gradient-to-br from-slate-900 to-slate-800 p-4 md:grid-cols-[1fr_220px]" @submit.prevent="onSubmit">
        <label class="md:col-span-2 text-sm text-slate-300">
          Video format
        </label>
        <select
          class="md:col-span-2 h-12 w-full rounded-xl border border-slate-700 bg-slate-800 px-3 text-slate-100 focus:border-blue-500 focus:outline-none"
          v-model="form.contentFormat"
        >
          <option value="long">Long video</option>
          <option value="short">Short video / Shorts</option>
        </select>

        <label class="md:col-span-2 inline-flex items-center gap-2 text-sm text-slate-300">
          <input class="h-4 w-4 accent-blue-500" id="use-own-key" type="checkbox" v-model="form.useOwnKey" />
          Use my YouTube API key (for niche-specific results). If disabled, backup env key is used.
        </label>

        <input
          v-if="form.useOwnKey"
          class="md:col-span-2 h-12 w-full rounded-xl border border-slate-700 bg-slate-800 px-3 text-slate-100 placeholder:text-slate-500 focus:border-blue-500 focus:outline-none"
          v-model="form.youtubeApiKey"
          type="password"
          placeholder="Paste your YouTube Data API key"
          autocomplete="off"
        />

        <input
          class="h-12 w-full rounded-xl border border-slate-700 bg-slate-800 px-3 text-slate-100 placeholder:text-slate-500 focus:border-blue-500 focus:outline-none"
          v-model="form.topic"
          type="text"
          placeholder="What's your video about?"
          autocomplete="off"
        />

        <button class="h-12 rounded-xl bg-gradient-to-r from-blue-500 to-blue-600 font-semibold text-white transition hover:from-blue-400 hover:to-blue-500 disabled:cursor-not-allowed disabled:opacity-70" type="submit" :disabled="loading">
          {{ loading ? 'Generating...' : 'Generate for free' }}
        </button>
      </form>

      <p class="mt-2 text-sm text-rose-400" v-if="error">{{ error }}</p>
    </section>

    <section v-if="result" class="grid gap-4">
      <div class="grid gap-4 md:grid-cols-[220px_1fr]">
        <div class="rounded-2xl border border-slate-700 bg-slate-900 p-4">
          <div class="text-xs uppercase tracking-[0.2em] text-slate-400">Overall SEO Score</div>
          <div class="mt-2 text-5xl font-bold text-white">{{ overallScore }}</div>
          <div class="mt-3 text-sm" :class="result.validation?.passed ? 'text-emerald-300' : 'text-rose-300'">
            {{ result.validation?.passed ? 'Passed validation' : 'Needs improvement' }}
          </div>
        </div>

        <div class="grid gap-3 rounded-2xl border border-slate-700 bg-slate-900 p-4 md:grid-cols-2 xl:grid-cols-3">
          <div class="rounded-xl border border-slate-700 bg-slate-800 p-3">
            <div class="flex items-center justify-between gap-3">
              <span class="text-sm text-slate-300">Title</span>
              <span class="rounded-full border px-2 py-1 text-xs font-semibold" :class="scoreBadgeClass(titleScore)">{{ titleScore }}</span>
            </div>
            <div class="mt-2 text-xs text-slate-400">Readable: {{ validationChecks.title_readability ? 'yes' : 'no' }}</div>
          </div>
          <div class="rounded-xl border border-slate-700 bg-slate-800 p-3">
            <div class="flex items-center justify-between gap-3">
              <span class="text-sm text-slate-300">Description</span>
              <span class="rounded-full border px-2 py-1 text-xs font-semibold" :class="scoreBadgeClass(descriptionScore)">{{ descriptionScore }}</span>
            </div>
            <div class="mt-2 text-xs text-slate-400">Readable: {{ validationChecks.description_readability ? 'yes' : 'no' }}</div>
          </div>
          <div class="rounded-xl border border-slate-700 bg-slate-800 p-3">
            <div class="flex items-center justify-between gap-3">
              <span class="text-sm text-slate-300">Hashtags</span>
              <span class="rounded-full border px-2 py-1 text-xs font-semibold" :class="scoreBadgeClass(hashtagScore)">{{ hashtagScore }}</span>
            </div>
            <div class="mt-2 text-xs text-slate-400">Valid: {{ validationChecks.hashtags ? 'yes' : 'no' }}</div>
          </div>
          <div class="rounded-xl border border-slate-700 bg-slate-800 p-3">
            <div class="flex items-center justify-between gap-3">
              <span class="text-sm text-slate-300">SEO Tags</span>
              <span class="rounded-full border px-2 py-1 text-xs font-semibold" :class="scoreBadgeClass(seoTagsScore)">{{ seoTagsScore }}</span>
            </div>
            <div class="mt-2 text-xs text-slate-400">Valid: {{ validationChecks.seo_tags ? 'yes' : 'no' }}</div>
          </div>
          <div class="rounded-xl border border-slate-700 bg-slate-800 p-3">
            <div class="flex items-center justify-between gap-3">
              <span class="text-sm text-slate-300">Thumbnail Text</span>
              <span class="rounded-full border px-2 py-1 text-xs font-semibold" :class="scoreBadgeClass(thumbnailTextScore)">{{ thumbnailTextScore }}</span>
            </div>
            <div class="mt-2 text-xs text-slate-400">Valid: {{ validationChecks.thumbnail_text ? 'yes' : 'no' }}</div>
          </div>
        </div>
      </div>

      <div class="rounded-2xl border border-slate-700 bg-slate-900 p-4">
        <div class="mb-2 flex items-center justify-between gap-3">
          <div class="text-sm text-slate-400">Use top related keyword</div>
          <button type="button" class="grid h-9 w-9 place-items-center rounded-full border border-slate-600 bg-slate-800 text-slate-200 transition hover:border-slate-500 hover:text-white" title="Copy related keywords" aria-label="Copy related keywords" @click="copyText(relatedKeywordsText)">
            <svg class="h-4 w-4 fill-current" viewBox="0 0 24 24" aria-hidden="true"><path d="M16 1H6a2 2 0 0 0-2 2v12h2V3h10V1zm3 4H10a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h9a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2zm0 16H10V7h9v14z"/></svg>
          </button>
        </div>
        <div class="mb-3 flex flex-wrap gap-2">
          <span class="inline-flex items-center gap-2 rounded-lg bg-slate-800 px-3 py-2 text-sm text-slate-100" v-for="item in relatedKeywords" :key="item.label">
            <strong class="text-emerald-400">{{ item.score }}</strong> {{ item.label }}
          </span>
        </div>
        <button type="button" class="rounded-full bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-500" @click="onRegenerate">Regenerate</button>
      </div>

      <div class="grid gap-4 rounded-2xl border border-slate-700 bg-slate-900 p-4">
        <div class="flex items-center justify-between gap-3">
          <div class="flex items-center gap-3">
            <h3 class="text-xl font-semibold text-white md:text-2xl">Title</h3>
            <span class="rounded-full border px-2 py-1 text-xs font-semibold" :class="scoreBadgeClass(titleScore)">{{ titleScore }}</span>
          </div>
          <button type="button" class="grid h-9 w-9 place-items-center rounded-full border border-slate-600 bg-slate-800 text-slate-200 transition hover:border-slate-500 hover:text-white" title="Copy title" aria-label="Copy title" @click="copyText(topTitle)">
            <svg class="h-4 w-4 fill-current" viewBox="0 0 24 24" aria-hidden="true"><path d="M16 1H6a2 2 0 0 0-2 2v12h2V3h10V1zm3 4H10a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h9a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2zm0 16H10V7h9v14z"/></svg>
          </button>
        </div>
        <div class="rounded-xl border border-slate-700 bg-slate-800 p-4 text-xl font-semibold text-slate-100 md:text-2xl">{{ topTitle }}</div>
        <div class="grid gap-2 text-xs text-slate-400 md:grid-cols-3">
          <div>Flesch: {{ titleReadability.flesch_reading_ease || 0 }}</div>
          <div>Grade: {{ titleReadability.flesch_kincaid_grade || 0 }}</div>
          <div>Readability: {{ titleReadability.readability_score || 0 }}</div>
        </div>
      </div>

      <div class="grid gap-4 rounded-2xl border border-slate-700 bg-slate-900 p-4">
        <div class="flex items-center justify-between gap-3">
          <div class="flex items-center gap-3">
            <h3 class="text-xl font-semibold text-white md:text-2xl">Description</h3>
            <span class="rounded-full border px-2 py-1 text-xs font-semibold" :class="scoreBadgeClass(descriptionScore)">{{ descriptionScore }}</span>
          </div>
          <button type="button" class="grid h-9 w-9 place-items-center rounded-full border border-slate-600 bg-slate-800 text-slate-200 transition hover:border-slate-500 hover:text-white" title="Copy description" aria-label="Copy description" @click="copyText(result.description)">
            <svg class="h-4 w-4 fill-current" viewBox="0 0 24 24" aria-hidden="true"><path d="M16 1H6a2 2 0 0 0-2 2v12h2V3h10V1zm3 4H10a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h9a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2zm0 16H10V7h9v14z"/></svg>
          </button>
        </div>
        <div class="rounded-xl border border-slate-700 bg-slate-800 p-4 leading-relaxed text-slate-100">{{ result.description }}</div>
        <div class="grid gap-2 text-xs text-slate-400 md:grid-cols-3">
          <div>Flesch: {{ descriptionReadability.flesch_reading_ease || 0 }}</div>
          <div>Grade: {{ descriptionReadability.flesch_kincaid_grade || 0 }}</div>
          <div>Readability: {{ descriptionReadability.readability_score || 0 }}</div>
        </div>
      </div>

      <div class="grid gap-4 rounded-2xl border border-slate-700 bg-slate-900 p-4">
        <div class="flex items-center justify-between gap-3">
          <div class="flex items-center gap-3">
            <h3 class="text-xl font-semibold text-white md:text-2xl">Hashtags</h3>
            <span class="rounded-full border px-2 py-1 text-xs font-semibold" :class="scoreBadgeClass(hashtagScore)">{{ hashtagScore }}</span>
          </div>
          <button type="button" class="grid h-9 w-9 place-items-center rounded-full border border-slate-600 bg-slate-800 text-slate-200 transition hover:border-slate-500 hover:text-white" title="Copy hashtags" aria-label="Copy hashtags" @click="copyText(hashtagText)">
            <svg class="h-4 w-4 fill-current" viewBox="0 0 24 24" aria-hidden="true"><path d="M16 1H6a2 2 0 0 0-2 2v12h2V3h10V1zm3 4H10a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h9a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2zm0 16H10V7h9v14z"/></svg>
          </button>
        </div>
        <div class="flex flex-wrap gap-2 rounded-xl border border-slate-700 bg-slate-800 p-4">
          <span class="inline-flex items-center gap-2 rounded-lg bg-slate-700 px-3 py-2 text-sm text-slate-100" v-for="item in hashtagItems" :key="item.label">
            <strong class="text-emerald-400">{{ item.score }}</strong> {{ item.label }}
          </span>
        </div>
      </div>

      <div class="grid gap-4 rounded-2xl border border-slate-700 bg-slate-900 p-4">
        <div class="flex items-center justify-between gap-3">
          <div class="flex items-center gap-3">
            <h3 class="text-xl font-semibold text-white md:text-2xl">SEO Tags</h3>
            <span class="rounded-full border px-2 py-1 text-xs font-semibold" :class="scoreBadgeClass(seoTagsScore)">{{ seoTagsScore }}</span>
          </div>
          <button type="button" class="grid h-9 w-9 place-items-center rounded-full border border-slate-600 bg-slate-800 text-slate-200 transition hover:border-slate-500 hover:text-white" title="Copy SEO tags" aria-label="Copy SEO tags" @click="copyText(seoTagsText)">
            <svg class="h-4 w-4 fill-current" viewBox="0 0 24 24" aria-hidden="true"><path d="M16 1H6a2 2 0 0 0-2 2v12h2V3h10V1zm3 4H10a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h9a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2zm0 16H10V7h9v14z"/></svg>
          </button>
        </div>
        <div class="flex flex-wrap gap-2 rounded-xl border border-slate-700 bg-slate-800 p-4">
          <span class="inline-flex items-center gap-2 rounded-lg bg-slate-700 px-3 py-2 text-sm text-slate-100" v-for="item in seoTagItems" :key="item.label">
            <strong class="text-emerald-400">{{ item.score }}</strong> {{ item.label }}
          </span>
        </div>
      </div>

      <div class="grid gap-4 rounded-2xl border border-slate-700 bg-slate-900 p-4">
        <div class="flex items-center justify-between gap-3">
          <div class="flex items-center gap-3">
            <h3 class="text-xl font-semibold text-white md:text-2xl">Thumbnail</h3>
            <span class="rounded-full border px-2 py-1 text-xs font-semibold" :class="scoreBadgeClass(thumbnailTextScore)">{{ thumbnailTextScore }}</span>
          </div>
          <button type="button" class="grid h-9 w-9 place-items-center rounded-full border border-slate-600 bg-slate-800 text-slate-200 transition hover:border-slate-500 hover:text-white" title="Copy thumbnail text" aria-label="Copy thumbnail text" @click="copyText(thumbnailText)">
            <svg class="h-4 w-4 fill-current" viewBox="0 0 24 24" aria-hidden="true"><path d="M16 1H6a2 2 0 0 0-2 2v12h2V3h10V1zm3 4H10a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h9a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2zm0 16H10V7h9v14z"/></svg>
          </button>
        </div>
        <div class="grid gap-3 rounded-xl border border-slate-700 bg-slate-800 p-3 md:grid-cols-3">
          <article class="flex min-h-28 items-end rounded-lg border border-slate-600 bg-gradient-to-br p-3 text-sm font-semibold text-white shadow-sm"
            v-for="item in thumbnailCards"
            :key="item.label"
            :class="item.variant === 0 ? 'from-sky-900 via-slate-800 to-orange-600' : item.variant === 1 ? 'from-slate-700 via-slate-800 to-orange-500' : 'from-cyan-900 via-slate-800 to-rose-600'"
          >
            {{ item.label }}
          </article>
        </div>
      </div>

      <div class="grid gap-4 rounded-2xl border border-slate-700 bg-slate-900 p-4">
        <div class="flex items-center justify-between gap-3">
          <h3 class="text-xl font-semibold text-white md:text-2xl">Hook</h3>
          <button type="button" class="grid h-9 w-9 place-items-center rounded-full border border-slate-600 bg-slate-800 text-slate-200 transition hover:border-slate-500 hover:text-white" title="Copy hook" aria-label="Copy hook" @click="copyText(hookLine)">
            <svg class="h-4 w-4 fill-current" viewBox="0 0 24 24" aria-hidden="true"><path d="M16 1H6a2 2 0 0 0-2 2v12h2V3h10V1zm3 4H10a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h9a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2zm0 16H10V7h9v14z"/></svg>
          </button>
        </div>
        <div class="rounded-xl border border-slate-700 bg-slate-800 p-4 text-slate-100">{{ hookLine }}</div>
      </div>

      <div class="grid gap-4 rounded-2xl border border-slate-700 bg-slate-900 p-4">
        <div class="flex items-center justify-between gap-3">
          <h3 class="text-xl font-semibold text-white md:text-2xl">Outline</h3>
          <button type="button" class="grid h-9 w-9 place-items-center rounded-full border border-slate-600 bg-slate-800 text-slate-200 transition hover:border-slate-500 hover:text-white" title="Copy outline" aria-label="Copy outline" @click="copyText(outlineText)">
            <svg class="h-4 w-4 fill-current" viewBox="0 0 24 24" aria-hidden="true"><path d="M16 1H6a2 2 0 0 0-2 2v12h2V3h10V1zm3 4H10a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h9a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2zm0 16H10V7h9v14z"/></svg>
          </button>
        </div>
        <div class="rounded-xl border border-slate-700 bg-slate-800 p-4 text-slate-100">
          <ol class="list-decimal space-y-2 pl-5">
            <li v-for="point in outlinePoints" :key="point">{{ point }}</li>
          </ol>
        </div>
      </div>
    </section>

    <div class="fixed bottom-5 right-5 rounded-lg border border-sky-700 bg-slate-800 px-4 py-2 text-sm text-slate-100 shadow-lg" v-if="copyNotice">{{ copyNotice }}</div>
  `,
};
