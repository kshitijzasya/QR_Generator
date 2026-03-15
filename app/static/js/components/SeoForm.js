export default {
  name: "SeoForm",
  props: {
    seoForm: {
      type: Object,
      required: true,
    },
  },
  emits: ["generate", "reset"],
  computed: {
    formatOptions() {
      const platform = this.seoForm.platform || "youtube";
      if (platform === "instagram") {
        return [
          { value: "reel", label: "Reel", copy: "Short-form discovery content" },
          { value: "post", label: "Post", copy: "Static post or single asset" },
          { value: "carousel", label: "Carousel", copy: "Swipeable educational post" },
        ];
      }
      if (platform === "linkedin") {
        return [
          { value: "post", label: "Post", copy: "Standard professional post" },
          { value: "carousel", label: "Carousel", copy: "Document or slide format" },
          { value: "article", label: "Article", copy: "Long-form editorial content" },
        ];
      }
      return [
        { value: "long", label: "Long video", copy: "Standard YouTube upload" },
        { value: "short", label: "Shorts", copy: "Short-form vertical video" },
      ];
    },
    isYouTube() {
      return (this.seoForm.platform || "youtube") === "youtube";
    },
  },
  methods: {
    onPlatformChange() {
      this.seoForm.contentFormat = this.formatOptions[0]?.value || "long";
      if (!this.isYouTube) {
        this.seoForm.keyMode = "backup";
        this.seoForm.youtubeApiKey = "";
      }
    },
  },
  template: `
    <form @submit.prevent="$emit('generate')">
      <label for="seo-platform">Platform</label>
      <select id="seo-platform" class="select" v-model="seoForm.platform" @change="onPlatformChange">
        <option value="youtube">YouTube</option>
        <option value="instagram">Instagram</option>
        <option value="linkedin">LinkedIn</option>
      </select>

      <label>Format</label>
      <div class="mode-group">
        <label class="mode-card" v-for="option in formatOptions" :key="option.value">
          <input type="radio" name="seo-content-format" :value="option.value" v-model="seoForm.contentFormat" />
          <span class="mode-title">{{ option.label }}</span>
          <span class="mode-copy">{{ option.copy }}</span>
        </label>
      </div>

      <template v-if="isYouTube">
      <label>YouTube Key</label>
      <div class="mode-group">
        <label class="mode-card">
          <input type="radio" name="seo-key-mode" value="backup" v-model="seoForm.keyMode" />
          <span class="mode-title">Use app backup key</span>
          <span class="mode-copy">General live YouTube research</span>
        </label>
        <label class="mode-card">
          <input type="radio" name="seo-key-mode" value="own" v-model="seoForm.keyMode" />
          <span class="mode-title">Use my YouTube key</span>
          <span class="mode-copy">Better for niche-specific intent</span>
        </label>
      </div>
      </template>

      <label for="seo-topic">Topic</label>
      <textarea
        id="seo-topic"
        class="field textarea"
        placeholder="Example: How to grow a faceless YouTube channel in 2026"
        v-model="seoForm.topic"
        required
      ></textarea>

      <template v-if="isYouTube && seoForm.keyMode === 'own'">
        <label for="seo-youtube-key">YouTube API key</label>
        <input
          id="seo-youtube-key"
          class="field"
          type="password"
          placeholder="Your api key here..."
          v-model="seoForm.youtubeApiKey"
        />
      </template>

      <div class="actions">
        <button type="button" class="btn secondary" @click="$emit('reset')">Clear</button>
        <button type="submit" class="btn primary">Generate SEO Pack</button>
      </div>
    </form>
  `,
};
