export async function parseError(response) {
  try {
    const payload = await response.json();
    return payload.error || "Request failed";
  } catch (error) {
    return "Request failed";
  }
}

export async function requestPreview(formData) {
  return fetch("/api/qr/preview", {
    method: "POST",
    body: formData,
  });
}

export async function requestDownload(formData) {
  return fetch("/api/qr", {
    method: "POST",
    body: formData,
  });
}
