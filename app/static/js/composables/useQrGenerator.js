import { requestDownload, requestPreview, parseError } from "../api/qrApi.js";

export function useQrGenerator({ form, previewUrl, error }) {
  function buildFormData(format) {
    const fd = new FormData();
    fd.set("data", form.data || "");
    fd.set("qr_color", form.qrColor || "#000000");
    fd.set("border_color", form.borderColor || "#000000");
    fd.set("format", format || "png");

    if (form.logoFile) {
      fd.set("logo", form.logoFile);
    }

    return fd;
  }

  function clearPreview() {
    if (previewUrl.value) {
      URL.revokeObjectURL(previewUrl.value);
      previewUrl.value = null;
    }
  }

  async function previewQr() {
    error.value = "";

    const response = await requestPreview(buildFormData("png"));
    if (!response.ok) {
      error.value = await parseError(response);
      return;
    }

    const blob = await response.blob();
    clearPreview();
    previewUrl.value = URL.createObjectURL(blob);
  }

  async function downloadQr(format) {
    error.value = "";

    const response = await requestDownload(buildFormData(format));
    if (!response.ok) {
      error.value = await parseError(response);
      return;
    }

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `qrcode.${format}`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  function resetForm() {
    error.value = "";
    form.data = "";
    form.qrColor = "#000000";
    form.borderColor = "#000000";
    form.logoFile = null;
    clearPreview();
  }

  return {
    clearPreview,
    downloadQr,
    previewQr,
    resetForm,
  };
}
