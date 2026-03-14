import { ref, watch } from "https://unpkg.com/vue@3/dist/vue.esm-browser.prod.js";

export default {
  name: "QrForm",
  props: {
    form: {
      type: Object,
      required: true,
    },
    resetToken: {
      type: Number,
      required: true,
    },
  },
  emits: ["preview", "reset", "logo-change"],
  setup(props, { emit }) {
    const logoInput = ref(null);

    function onLogoChange(event) {
      const files = event.target.files || [];
      emit("logo-change", files.length ? files[0] : null);
    }

    watch(
      () => props.resetToken,
      () => {
        if (logoInput.value) {
          logoInput.value.value = "";
        }
      }
    );

    return {
      logoInput,
      onLogoChange,
      emit,
    };
  },
  template: `
    <form enctype="multipart/form-data" @submit.prevent="emit('preview')">
      <label for="data">Title / Link / Content</label>
      <input
        id="data"
        class="field"
        name="data"
        type="text"
        placeholder="https://forms.gle/..."
        v-model="form.data"
        required
      />

      <div class="grid-2">
        <div>
          <label for="qr_color">QR Content Color</label>
          <div class="color-wrap">
            <input id="qr_color" name="qr_color" type="color" v-model="form.qrColor" />
            <span class="color-code">{{ form.qrColor }}</span>
          </div>
        </div>

        <div>
          <label for="border_color">Border Color</label>
          <div class="color-wrap">
            <input id="border_color" name="border_color" type="color" v-model="form.borderColor" />
            <span class="color-code">{{ form.borderColor }}</span>
          </div>
        </div>
      </div>

      <label for="logo">Center Logo (optional)</label>
      <input
        id="logo"
        ref="logoInput"
        class="file"
        name="logo"
        type="file"
        accept="image/*"
        @change="onLogoChange"
      />

      <div class="actions">
        <button type="button" class="btn secondary" @click="emit('reset')">Cancel</button>
        <button type="submit" class="btn primary">Preview</button>
      </div>
    </form>
  `,
};
