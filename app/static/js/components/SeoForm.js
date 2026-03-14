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

      <label for="seo-content-format">Video Format</label>
      <select id="seo-content-format" class="select" v-model="seoForm.contentFormat">
        <option value="long">Long video</option>
        <option value="short">Short video / Shorts</option>
      </select>

      <label for="seo-topic">Topic</label>
      <textarea
        id="seo-topic"
        class="field textarea"
        placeholder="Example: How to grow a faceless YouTube channel in 2026"
        v-model="seoForm.topic"
        required
      ></textarea>

      <label for="seo-use-own-key" class="mode-option">
        <input id="seo-use-own-key" type="checkbox" v-model="seoForm.useOwnKey" />
        Use my YouTube API key (otherwise app backup env key is used)
      </label>

      <template v-if="seoForm.useOwnKey">
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
