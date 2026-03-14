export default {
  name: "SeoForm",
  props: {
    seoForm: {
      type: Object,
      required: true,
    },
  },
  emits: ["generate", "reset"],
  template: `
    <form @submit.prevent="$emit('generate')">
      <label for="seo-platform">Platform</label>
      <select id="seo-platform" class="select" v-model="seoForm.platform">
        <option value="youtube">YouTube</option>
      </select>

      <label>Video Format</label>
      <div class="mode-group">
        <label class="mode-card">
          <input type="radio" name="seo-content-format" value="long" v-model="seoForm.contentFormat" />
          <span class="mode-title">Long video</span>
          <span class="mode-copy">Standard YouTube upload</span>
        </label>
        <label class="mode-card">
          <input type="radio" name="seo-content-format" value="short" v-model="seoForm.contentFormat" />
          <span class="mode-title">Shorts</span>
          <span class="mode-copy">Short-form vertical video</span>
        </label>
      </div>

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

      <label for="seo-topic">Topic</label>
      <textarea
        id="seo-topic"
        class="field textarea"
        placeholder="Example: How to grow a faceless YouTube channel in 2026"
        v-model="seoForm.topic"
        required
      ></textarea>

      <template v-if="seoForm.keyMode === 'own'">
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
