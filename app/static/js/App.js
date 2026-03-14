import { computed, onBeforeUnmount, reactive, ref } from "https://unpkg.com/vue@3/dist/vue.esm-browser.prod.js";
import QrForm from "./components/QrForm.js";
import QrPreview from "./components/QrPreview.js";
import SeoTool from "./components/SeoTool.js";
import { useQrGenerator } from "./composables/useQrGenerator.js";

export default {
  name: "App",
  components: {
    QrForm,
    QrPreview,
    SeoTool,
  },
  setup() {
    const activeModule = ref("");

    const form = reactive({
      data: "",
      qrColor: "#000000",
      borderColor: "#000000",
      logoFile: null,
    });
    const previewUrl = ref(null);
    const error = ref("");
    const resetToken = ref(0);

    const { clearPreview, previewQr, downloadQr, resetForm } = useQrGenerator({ form, previewUrl, error });

    const svgBlocked = computed(() => {
      const hasLogo = Boolean(form.logoFile);
      const customBorder = (form.borderColor || "").toLowerCase() !== "#000000";
      return hasLogo || customBorder;
    });

    const svgHelpText = computed(() => {
      if (!svgBlocked.value) {
        return "";
      }
      return "SVG download is disabled when logo is added or border color is custom.";
    });

    function onLogoChange(file) {
      form.logoFile = file;
    }

    function onReset() {
      resetForm();
      resetToken.value += 1;
    }

    function openModule(moduleName) {
      if (moduleName === "seo") {
        window.location.href = "/seo";
        return;
      }
      activeModule.value = moduleName;
    }

    function backToHub() {
      activeModule.value = "";
      error.value = "";
    }

    onBeforeUnmount(() => {
      clearPreview();
    });

    return {
      activeModule,
      backToHub,
      error,
      form,
      openModule,
      onLogoChange,
      onReset,
      previewQr,
      downloadQr,
      previewUrl,
      resetToken,
      svgBlocked,
      svgHelpText,
    };
  },
  template: `
    <div>
      <template v-if="!activeModule">
        <div class="brand"><span class="brand-badge"></span>ToolBox</div>
        <h1>Tools Hub</h1>
        <p class="sub">Choose a tool to start.</p>

        <section class="tool-grid">
          <button type="button" class="tool-card" @click="openModule('qr')">
            <span class="tool-kicker">Create</span>
            <span class="tool-title">QR Generator</span>
            <span class="tool-copy">Generate branded QR previews and downloads.</span>
          </button>
          <button type="button" class="tool-card" @click="openModule('seo')">
            <span class="tool-kicker">Optimize</span>
            <span class="tool-title">SEO Assistant</span>
            <span class="tool-copy">Generate titles, tags, hashtags, and thumbnail ideas.</span>
          </button>
        </section>
      </template>

      <template v-else-if="activeModule === 'qr'">
        <div class="tool-head">
          <button type="button" class="btn secondary back-btn" @click="backToHub">Back to Tools</button>
        </div>
        <div class="brand"><span class="brand-badge"></span>ToolsBox</div>
        <h1>What's your QR about?</h1>
        <p class="sub">Enter your details and generate a preview.</p>

        <QrForm
          :form="form"
          :reset-token="resetToken"
          @preview="previewQr"
          @reset="onReset"
          @logo-change="onLogoChange"
        />

        <QrPreview
          :preview-url="previewUrl"
          :svg-blocked="svgBlocked"
          :svg-help-text="svgHelpText"
          @download="downloadQr"
        />

        <p class="error">{{ error }}</p>
      </template>

      <template v-else>
        <div class="tool-head">
          <button type="button" class="btn secondary back-btn" @click="backToHub">Back to Tools</button>
        </div>
        <SeoTool />
      </template>
    </div>
  `,
};
