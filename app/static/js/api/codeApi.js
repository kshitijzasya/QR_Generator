export async function generateCode(payload) {
  return fetch("/api/code/generate", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}

export async function parseCodeError(response) {
  try {
    const payload = await response.json();
    return payload.error || "Request failed";
  } catch (error) {
    return "Request failed";
  }
}
