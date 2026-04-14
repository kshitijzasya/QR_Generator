export async function analyzeAssets(payload) {
  return fetch("/api/assets/analyze", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}

export async function parseAssetsError(response) {
  try {
    const payload = await response.json();
    return payload.error || "Request failed";
  } catch (error) {
    return "Request failed";
  }
}
