export async function listVaultEntries(userId) {
  return fetch(`/api/vault/entries?user_id=${encodeURIComponent(userId)}`);
}

export async function lookupVaultUser(identifier) {
  return fetch(`/api/vault/users/lookup?identifier=${encodeURIComponent(identifier)}`);
}

export async function createVaultUser(payload) {
  return fetch("/api/vault/users", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function startVaultSession(payload) {
  return fetch("/api/vault/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function createVaultEntry(payload) {
  return fetch("/api/vault/entries", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function revealVaultEntry(entryId, payload) {
  return fetch(`/api/vault/entries/${entryId}/reveal`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function updateVaultEntry(entryId, payload) {
  return fetch(`/api/vault/entries/${entryId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function deleteVaultEntry(entryId, payload = {}) {
  return fetch(`/api/vault/entries/${entryId}`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function importVaultFile(formData) {
  return fetch("/api/vault/import", {
    method: "POST",
    body: formData,
  });
}

export async function parseVaultError(response) {
  try {
    const payload = await response.json();
    return payload.error || "Request failed";
  } catch (error) {
    return "Request failed";
  }
}
