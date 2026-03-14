export default {
  name: "QrPreview",
  props: {
    previewUrl: {
      type: String,
      default: null,
    },
    svgBlocked: {
      type: Boolean,
      required: true,
    },
    svgHelpText: {
      type: String,
      required: true,
    },
  },
  emits: ["download"],
  template: `
    <section class="preview" :class="{ show: previewUrl }">
      <div class="preview-head">Preview</div>
      <img v-if="previewUrl" :src="previewUrl" alt="Generated QR preview" />
      <div class="download-row">
        <button type="button" class="btn download" @click="$emit('download', 'png')">Download PNG</button>
        <button type="button" class="btn download" @click="$emit('download', 'jpeg')">Download JPEG</button>
        <button type="button" class="btn download" :disabled="svgBlocked" @click="$emit('download', 'svg')">
          Download SVG
        </button>
      </div>
      <p class="help">{{ svgHelpText }}</p>
    </section>
  `,
};
