export default {
  name: "SeoResults",
  props: {
    result: {
      type: Object,
      default: null,
    },
  },
  template: `
    <section v-if="result" class="seo-results">
      <h3 class="seo-head">Title Ideas</h3>
      <ul class="seo-list">
        <li v-for="item in result.titles" :key="item">{{ item }}</li>
      </ul>

      <h3 class="seo-head">Description</h3>
      <p class="seo-text">{{ result.description }}</p>

      <h3 class="seo-head">Hashtags</h3>
      <p class="seo-text">{{ result.hashtags.join(' ') }}</p>

      <h3 class="seo-head">SEO Tags</h3>
      <p class="seo-text">{{ result.seo_tags.join(', ') }}</p>

      <h3 class="seo-head">Thumbnail Ideas</h3>
      <ul class="seo-list">
        <li v-for="item in result.thumbnail_ideas" :key="item">{{ item }}</li>
      </ul>

      <h3 class="seo-head">Thumbnail Text Options</h3>
      <ul class="seo-list">
        <li v-for="item in result.thumbnail_text" :key="item">{{ item }}</li>
      </ul>
    </section>
  `,
};
