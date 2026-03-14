import { reactive, ref } from "https://unpkg.com/vue@3/dist/vue.esm-browser.prod.js";
import SeoForm from "./SeoForm.js";
import SeoResults from "./SeoResults.js";
import { useSeoTool } from "../composables/useSeoTool.js";

export default {
  name: "SeoTool",
  components: {
    SeoForm,
    SeoResults,
  },
  setup() {
    const seoForm = reactive({
      platform: "youtube",
      topic: "",
      contentFormat: "long",
      useOwnKey: false,
      youtubeApiKey: "",
    });
    const seoResult = ref(null);
    const seoError = ref("");

    const { generate, reset } = useSeoTool({ seoForm, seoResult, seoError });

    return {
      generate,
      reset,
      seoError,
      seoForm,
      seoResult,
    };
  },
  template: `
    <div>
      <div class="brand"><span class="brand-badge"></span>ToolsBox</div>
      <h1>Social SEO Assistant</h1>
      <p class="sub">Generate title, description, hashtags, tags, and thumbnail ideas from one topic.</p>

      <SeoForm :seo-form="seoForm" @generate="generate" @reset="reset" />
      <p class="error">{{ seoError }}</p>
      <SeoResults :result="seoResult" />
    </div>
  `,
};
