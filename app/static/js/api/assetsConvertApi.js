export async function convertAssets(payload) {
  return fetch("/api/assets/convert", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}

export async function parseAssetsConvertError(response) {
  try {
    const payload = await response.json();
    return payload.error || "Request failed";
  } catch (error) {
    return "Request failed";
  }
}
