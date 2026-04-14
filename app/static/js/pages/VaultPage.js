import { computed, reactive, ref } from "https://unpkg.com/vue@3/dist/vue.esm-browser.prod.js";
import { copyTextValue } from "../utils/copyText.js";
import {
  createVaultEntry,
  createVaultUser,
  deleteVaultEntry,
  importVaultFile,
  listVaultEntries,
  lookupVaultUser,
  parseVaultError,
  revealVaultEntry,
  updateVaultEntry,
} from "../api/vaultApi.js";

function formatTimestamp(value) {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

export default {
  name: "VaultPage",
  setup() {
    const phase = ref("identify");
    const loading = ref(false);
    const status = ref("");
    const identifyError = ref("");
    const createError = ref("");
    const importError = ref("");
    const editError = ref("");
    const deleteError = ref("");
    const showModal = ref(false);
    const modalMode = ref("asset");

    const currentUser = ref(null);
    const entries = ref([]);
    const selectedEntryId = ref(null);
    const search = ref("");
    const unlockInputs = reactive({});
    const revealErrorsById = reactive({});
    const revealedContents = reactive({});
    const shakeCards = reactive({});
    const unlockPromptEntryId = ref(null);
    const detailsEntryId = ref(null);
    const editMode = ref(false);
    const deleteConfirmState = reactive({
      open: false,
      entryId: null,
      secretKey: "",
    });

    const identifyForm = reactive({
      identifier: "",
    });
    const entryForm = reactive({
      title: "",
      category: "note",
      content: "",
      isSecret: false,
      secretKey: "",
      secretHint: "",
    });
    const importForm = reactive({
      category: "imported",
      file: null,
    });
    const revealState = reactive({
      generatedSecretKey: "",
    });
    const editForm = reactive({
      title: "",
      category: "note",
      content: "",
      isSecret: false,
      secretKey: "",
      secretHint: "",
    });

    const visibleEntries = computed(() => {
      const term = search.value.trim().toLowerCase();
      if (!term) {
        return entries.value;
      }
      return entries.value.filter((entry) => `${entry.title} ${entry.category}`.toLowerCase().includes(term));
    });
    const hasPrivacyInput = computed(() => Boolean(identifyForm.identifier.trim()));

    async function loadEntries() {
      if (!currentUser.value) {
        entries.value = [];
        return;
      }
      const response = await listVaultEntries(currentUser.value.id);
      if (!response.ok) {
        throw new Error(await parseVaultError(response));
      }
      entries.value = await response.json();
      if (entries.value.length && !entries.value.some((entry) => entry.id === selectedEntryId.value)) {
        selectedEntryId.value = entries.value[0].id;
      }
      clearCardState();
      await preloadVisibleEntries();
    }

    async function identifyUser() {
      identifyError.value = "";
      status.value = "";
      const identifier = identifyForm.identifier.trim();
      if (!identifier) {
        identifyError.value = "Enter email or username.";
        return;
      }

      loading.value = true;
      try {
        const response = await lookupVaultUser(identifier);
        if (!response.ok) {
          identifyError.value = await parseVaultError(response);
          return;
        }
        const payload = await response.json();
        if (payload.user) {
          currentUser.value = payload.user;
          phase.value = "workspace";
          status.value = "User found.";
          await loadEntries();
          return;
        }

        const createResponse = await createVaultUser({
          username: identifier.includes("@") ? identifier.split("@", 1)[0] : identifier,
          name: "",
          email: identifier.includes("@") ? identifier : `${identifier}@vault.local`,
          password: "vault-user",
        });
        if (!createResponse.ok) {
          identifyError.value = await parseVaultError(createResponse);
          return;
        }
        currentUser.value = await createResponse.json();
        phase.value = "workspace";
        status.value = "User created.";
        await loadEntries();
      } catch (error) {
        identifyError.value = "Could not check this user right now.";
      } finally {
        loading.value = false;
      }
    }

    function clearCardState() {
      Object.keys(unlockInputs).forEach((key) => delete unlockInputs[key]);
      Object.keys(revealErrorsById).forEach((key) => delete revealErrorsById[key]);
      Object.keys(revealedContents).forEach((key) => delete revealedContents[key]);
      Object.keys(shakeCards).forEach((key) => delete shakeCards[key]);
      unlockPromptEntryId.value = null;
      detailsEntryId.value = null;
      editMode.value = false;
      deleteConfirmState.open = false;
      deleteConfirmState.entryId = null;
      deleteConfirmState.secretKey = "";
    }

    async function fetchEntryContent(entryId, secretKey = "", options = {}) {
      const { silent = false } = options;
      const entry = entries.value.find((item) => item.id === entryId);
      if (!entry) {
        return false;
      }
      if (!silent) {
        status.value = "";
      }
      revealErrorsById[entryId] = "";
      try {
        const response = await revealVaultEntry(entryId, {
          secret_key: secretKey || unlockInputs[entryId] || "",
          password: secretKey || unlockInputs[entryId] || "",
        });
        if (!response.ok) {
          revealErrorsById[entryId] = await parseVaultError(response);
          return false;
        }
        const payload = await response.json();
        revealedContents[entryId] = payload.content;
        unlockInputs[entryId] = "";
        revealErrorsById[entryId] = "";
        shakeCards[entryId] = false;
        if (!silent) {
          status.value = entry.is_secret ? "Entry unlocked." : "Entry opened.";
        }
        return true;
      } catch (error) {
        revealErrorsById[entryId] = "Could not open this entry right now.";
        return false;
      }
    }

    async function preloadVisibleEntries() {
      const publicEntries = entries.value.filter((entry) => !entry.is_secret);
      await Promise.all(publicEntries.map((entry) => fetchEntryContent(entry.id, "", { silent: true })));
    }

    async function openEntry(entry) {
      selectedEntryId.value = entry.id;
      if (entry.is_secret) {
        if (isUnlocked(entry)) {
          detailsEntryId.value = entry.id;
          return;
        }
        openUnlockPrompt(entry.id);
        return;
      }
      await fetchEntryContent(entry.id);
      detailsEntryId.value = entry.id;
    }

    function openUnlockPrompt(entryId) {
      unlockPromptEntryId.value = entryId;
      revealErrorsById[entryId] = "";
      shakeCards[entryId] = false;
    }

    function closeUnlockPrompt() {
      if (unlockPromptEntryId.value !== null) {
        unlockInputs[unlockPromptEntryId.value] = "";
      }
      unlockPromptEntryId.value = null;
    }

    async function unlockEntry(entryId) {
      const ok = await fetchEntryContent(entryId);
      if (ok) {
        closeUnlockPrompt();
        detailsEntryId.value = entryId;
        return;
      }
      shakeCards[entryId] = true;
      window.setTimeout(() => {
        shakeCards[entryId] = false;
      }, 420);
    }

    function openAssetModal() {
      showModal.value = true;
      modalMode.value = "asset";
      createError.value = "";
      status.value = "";
    }

    function openImportModal() {
      showModal.value = true;
      modalMode.value = "import";
      importError.value = "";
      status.value = "";
    }

    function closeModal() {
      showModal.value = false;
      if (!revealState.generatedSecretKey) {
        modalMode.value = "asset";
      }
    }

    async function saveEntry() {
      createError.value = "";
      status.value = "";
      if (!currentUser.value) {
        createError.value = "Select a user first.";
        return;
      }

      loading.value = true;
      try {
        const response = await createVaultEntry({
          user_id: currentUser.value.id,
          title: entryForm.title,
          category: entryForm.category,
          content: entryForm.content,
          is_secret: entryForm.isSecret,
          secret_key: entryForm.secretKey,
          password: entryForm.secretKey,
          secret_hint: entryForm.secretHint,
        });
        if (!response.ok) {
          createError.value = await parseVaultError(response);
          return;
        }

        const payload = await response.json();
        revealState.generatedSecretKey = payload.generated_secret_key || "";
        entryForm.title = "";
        entryForm.category = "note";
        entryForm.content = "";
        entryForm.isSecret = false;
        entryForm.secretKey = "";
        entryForm.secretHint = "";
        status.value = "Entry saved.";
        await loadEntries();
        selectedEntryId.value = payload.id;
        if (!revealState.generatedSecretKey) {
          closeModal();
        }
      } catch (error) {
        createError.value = "Could not save entry right now.";
      } finally {
        loading.value = false;
      }
    }

    async function submitImport() {
      importError.value = "";
      status.value = "";
      if (!currentUser.value) {
        importError.value = "Select a user first.";
        return;
      }
      if (!importForm.file) {
        importError.value = "Choose a file to import.";
        return;
      }

      const formData = new FormData();
      formData.append("user_id", currentUser.value.id);
      formData.append("category", importForm.category);
      formData.append("file", importForm.file);

      loading.value = true;
      try {
        const response = await importVaultFile(formData);
        if (!response.ok) {
          importError.value = await parseVaultError(response);
          return;
        }
        const payload = await response.json();
        importForm.file = null;
        status.value = `Imported ${payload.created_count} entr${payload.created_count === 1 ? "y" : "ies"}.`;
        await loadEntries();
        closeModal();
      } catch (error) {
        importError.value = "Could not import this file right now.";
      } finally {
        loading.value = false;
      }
    }

    async function copyValue(value) {
      const copied = await copyTextValue(value);
      status.value = copied ? "Copied to clipboard." : "Copy failed in this browser.";
    }

    function onFileChange(event) {
      const files = event.target.files || [];
      importForm.file = files.length ? files[0] : null;
    }

    function resetToIdentify() {
      phase.value = "identify";
      currentUser.value = null;
      entries.value = [];
      selectedEntryId.value = null;
      revealState.generatedSecretKey = "";
      clearCardState();
      showModal.value = false;
      status.value = "";
      identifyError.value = "";
      createError.value = "";
      importError.value = "";
      identifyForm.identifier = "";
    }

    function closeDetailsModal() {
      detailsEntryId.value = null;
      editMode.value = false;
      editError.value = "";
    }

    function startEditEntry(entry) {
      editForm.title = entry.title || "";
      editForm.category = entry.category || "note";
      editForm.content = entryContent(entry);
      editForm.isSecret = Boolean(entry.is_secret);
      editForm.secretKey = "";
      editForm.secretHint = entry.secret_hint || "";
      editError.value = "";
      revealState.generatedSecretKey = "";
      editMode.value = true;
    }

    function cancelEditEntry() {
      editMode.value = false;
      editError.value = "";
      revealState.generatedSecretKey = "";
    }

    async function saveEditedEntry() {
      if (!detailsEntry.value) {
        return;
      }
      editError.value = "";
      loading.value = true;
      try {
        const response = await updateVaultEntry(detailsEntry.value.id, {
          title: editForm.title,
          category: editForm.category,
          content: editForm.content,
          is_secret: editForm.isSecret,
          secret_key: editForm.secretKey,
          password: editForm.secretKey,
          secret_hint: editForm.secretHint,
        });
        if (!response.ok) {
          editError.value = await parseVaultError(response);
          return;
        }
        const payload = await response.json();
        revealState.generatedSecretKey = payload.generated_secret_key || "";
        await loadEntries();
        selectedEntryId.value = payload.id;
        detailsEntryId.value = payload.id;
        if (editForm.isSecret) {
          if (editForm.secretKey || payload.generated_secret_key) {
            await fetchEntryContent(payload.id, editForm.secretKey || payload.generated_secret_key);
          }
        } else {
          revealedContents[payload.id] = editForm.content;
        }
        editMode.value = false;
        status.value = "Entry updated.";
      } catch (error) {
        editError.value = "Could not update this entry right now.";
      } finally {
        loading.value = false;
      }
    }

    function requestDeleteEntry(entry) {
      deleteConfirmState.open = true;
      deleteConfirmState.entryId = entry.id;
      deleteConfirmState.secretKey = "";
      deleteError.value = "";
    }

    function closeDeleteConfirm() {
      deleteConfirmState.open = false;
      deleteConfirmState.entryId = null;
      deleteConfirmState.secretKey = "";
      deleteError.value = "";
    }

    async function confirmDeleteEntry() {
      if (!deleteConfirmEntry.value) {
        return;
      }
      deleteError.value = "";
      loading.value = true;
      try {
        const response = await deleteVaultEntry(deleteConfirmEntry.value.id, {
          secret_key: deleteConfirmState.secretKey,
          password: deleteConfirmState.secretKey,
        });
        if (!response.ok) {
          deleteError.value = await parseVaultError(response);
          return;
        }
        const deletedId = deleteConfirmEntry.value.id;
        delete revealedContents[deletedId];
        closeDeleteConfirm();
        closeDetailsModal();
        await loadEntries();
        status.value = "Entry deleted.";
      } catch (error) {
        deleteError.value = "Could not delete this entry right now.";
      } finally {
        loading.value = false;
      }
    }

    function entryContent(entry) {
      return revealedContents[entry.id] || "";
    }

    function isUnlocked(entry) {
      return Boolean(revealedContents[entry.id]);
    }

    function isCardShaking(entryId) {
      return Boolean(shakeCards[entryId]);
    }

    const detailsEntry = computed(() => entries.value.find((entry) => entry.id === detailsEntryId.value) || null);
    const unlockEntryTarget = computed(() => entries.value.find((entry) => entry.id === unlockPromptEntryId.value) || null);
    const deleteConfirmEntry = computed(() => entries.value.find((entry) => entry.id === deleteConfirmState.entryId) || null);

    return {
      cancelEditEntry,
      closeDeleteConfirm,
      closeDetailsModal,
      closeModal,
      closeUnlockPrompt,
      confirmDeleteEntry,
      copyValue,
      createError,
      currentUser,
      deleteConfirmEntry,
      deleteConfirmState,
      deleteError,
      detailsEntry,
      editError,
      editForm,
      editMode,
      entryContent,
      entries,
      entryForm,
      formatTimestamp,
      hasPrivacyInput,
      identifyError,
      identifyForm,
      identifyUser,
      importError,
      importForm,
      isCardShaking,
      isUnlocked,
      loading,
      modalMode,
      onFileChange,
      openAssetModal,
      openEntry,
      openImportModal,
      openUnlockPrompt,
      phase,
      revealErrorsById,
      requestDeleteEntry,
      resetToIdentify,
      revealState,
      saveEntry,
      saveEditedEntry,
      search,
      selectedEntryId,
      showModal,
      startEditEntry,
      unlockInputs,
      unlockPromptEntryId,
      status,
      submitImport,
      unlockEntryTarget,
      unlockEntry,
      visibleEntries,
    };
  },
  template: `
    <section class="mb-8 grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px] lg:items-center">
      <div>
        <a href="/" class="mb-4 inline-flex items-center gap-2 rounded-full border border-[#d8c3a5] bg-white/75 px-4 py-2 text-sm font-medium text-[#5f4b3e] transition hover:border-[#c89c6d] hover:text-[#b26114]">
          Back to Tools
        </a>
        <div class="mt-4 inline-flex items-center rounded-full border border-[#f0c48d] bg-[#fff4e6] px-3 py-1 text-xs font-semibold uppercase tracking-[0.22em] text-[#d17216]">Secret Vault</div>
        <h1 class="mt-4 text-3xl font-bold tracking-tight text-[#2f241f] md:text-5xl">Notes, credentials and secrets in one sculpted vault</h1>
        <p v-if="status" class="mt-4 text-sm text-[#0f8b66]">{{ status }}</p>
      </div>

      <div class="vault-scene hidden lg:flex">
        <div class="vault-scene__grid"></div>
        <div class="vault-scene__glow"></div>
        <div class="vault-scene__orb"></div>
        <div class="vault-scene__ring"></div>
        <div class="vault-scene__column">
          <div class="vault-scene__column-face vault-scene__column-face--front"></div>
          <div class="vault-scene__column-face vault-scene__column-face--side"></div>
          <div class="vault-scene__column-face vault-scene__column-face--top"></div>
        </div>
        <div class="vault-scene__card vault-scene__card--one"></div>
        <div class="vault-scene__card vault-scene__card--two"></div>
        <div class="vault-scene__lock">
          <div class="vault-scene__lock-shackle"></div>
          <div class="vault-scene__lock-body"></div>
        </div>
        <div class="vault-scene__leaf vault-scene__leaf--one"></div>
        <div class="vault-scene__leaf vault-scene__leaf--two"></div>
        <div class="vault-pedestal"></div>
      </div>
    </section>

    <section v-if="phase === 'identify'" class="mx-auto max-w-md">
      <div class="vault-panel rounded-[32px] border border-[#ddc7a8] px-8 py-10 shadow-[0_30px_90px_rgba(167,126,82,0.18)]">
        <div class="flex justify-center">
          <div class="vault-login-figure" :class="hasPrivacyInput ? 'vault-login-figure--clear' : ''" aria-hidden="true">
            <div class="vault-login-figure__face">
              <div class="vault-login-figure__eyes"></div>
              <div class="vault-login-figure__cheeks"></div>
              <div class="vault-login-figure__mouth"></div>
            </div>
            <div class="vault-login-figure__hands vault-login-figure__hands--left"></div>
            <div class="vault-login-figure__hands vault-login-figure__hands--right"></div>
          </div>
        </div>
        <h2 class="mt-6 text-center text-3xl font-semibold text-[#2f241f]">Vault Login</h2>
        <form class="mt-8 space-y-5" @submit.prevent="identifyUser">
          <div>
            <label class="mb-2 block text-sm font-semibold text-[#5f4b3e]">Email</label>
            <input v-model="identifyForm.identifier" type="text" placeholder="email@domain.com" class="h-12 w-full rounded-2xl border border-[#90c8e8] bg-white/82 px-4 text-[#3c2f27] shadow-[inset_0_1px_0_rgba(255,255,255,0.82)] focus:border-[#4bb3e4] focus:outline-none" />
          </div>
          <button type="submit" class="w-full rounded-2xl bg-[#4bb3e4] px-5 py-3 font-semibold text-white shadow-[0_16px_30px_rgba(75,179,228,0.22)] transition hover:bg-[#33a4d9]" :disabled="loading">
            {{ loading ? 'Logging in...' : 'Log in' }}
          </button>
          <p v-if="identifyError" class="text-sm text-rose-600">{{ identifyError }}</p>
        </form>
      </div>
    </section>

    <section v-else class="vault-panel grid min-h-[760px] gap-0 overflow-hidden rounded-[30px] border border-[#ddc7a8] shadow-[0_30px_90px_rgba(167,126,82,0.18)] lg:grid-cols-[260px_minmax(0,1fr)]">
      <aside class="border-b border-[#e6d5bf] bg-[rgba(255,250,244,0.78)] p-5 backdrop-blur-xl lg:border-b-0 lg:border-r">
        <div class="text-[11px] font-bold uppercase tracking-[0.24em] text-[#8b735b]">Vault</div>
        <div class="mt-2 text-xl font-semibold text-[#2f241f]">{{ currentUser?.username }}</div>
        <div class="mt-1 text-sm text-[#7a6351]">{{ currentUser?.email }}</div>

        <div class="mt-8 space-y-3">
          <div class="rounded-2xl border border-[#e1ccb0] bg-white/70 px-4 py-3 shadow-[0_16px_32px_rgba(166,130,88,0.08)]">
            <div class="text-[11px] font-semibold uppercase tracking-[0.2em] text-[#8b735b]">Stored</div>
            <div class="mt-2 text-3xl font-semibold text-[#2f241f]">{{ entries.length }}</div>
            <div class="text-xs text-[#7a6351]">vault cards</div>
          </div>
          <button type="button" class="flex w-full items-center justify-between rounded-2xl border border-[#e1ccb0] bg-white/58 px-4 py-3 text-left text-[#5f4b3e] transition hover:border-[#c89c6d] hover:bg-white/88 hover:text-[#b26114]" @click="openAssetModal">
            <span>Add Asset</span>
            <span>+</span>
          </button>
          <button type="button" class="flex w-full items-center justify-between rounded-2xl border border-[#e1ccb0] bg-white/58 px-4 py-3 text-left text-[#5f4b3e] transition hover:border-[#c89c6d] hover:bg-white/88 hover:text-[#b26114]" @click="openImportModal">
            <span>Import File</span>
            <span>+</span>
          </button>
          <button type="button" class="flex w-full items-center justify-between rounded-2xl border border-[#e1ccb0] bg-white/58 px-4 py-3 text-left text-[#5f4b3e] transition hover:border-[#c89c6d] hover:bg-white/88 hover:text-[#b26114]" @click="resetToIdentify">
            <span>Switch User</span>
            <span>+</span>
          </button>
        </div>

        <div class="mt-8 rounded-3xl border border-[#b9ddcc] bg-[#ebfaf4] p-4 text-sm leading-6 text-[#0f8b66]">
          Locked cards stay blurred until the right key or password is entered.
        </div>
      </aside>

      <main class="bg-[rgba(246,239,229,0.52)] p-5 backdrop-blur-xl md:p-7">
        <div class="vault-board rounded-[34px] border border-[#e8d6bf] bg-[rgba(255,251,246,0.72)] p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.62)] md:p-6">
          <div class="flex flex-col gap-4 border-b border-[#eadbca] pb-4 md:flex-row md:items-center md:justify-between">
            <div>
              <div class="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#8b735b]">Vault Cards</div>
              <h2 class="mt-2 text-2xl font-semibold text-[#2f241f]">Saved notes</h2>
            </div>
            <div class="flex w-full max-w-md items-center gap-3 rounded-2xl border border-[#dec8ad] bg-white/76 px-4 py-3 shadow-[0_12px_20px_rgba(177,136,92,0.07)]">
              <input v-model="search" type="text" placeholder="Search vault by title" class="w-full bg-transparent text-sm text-[#3c3128] placeholder:text-[#9d836f] focus:outline-none" />
            </div>
          </div>

          <div v-if="visibleEntries.length" class="vault-notes-grid mt-5 sm:grid-cols-2 xl:grid-cols-3">
          <article
            v-for="entry in visibleEntries"
            :key="entry.id"
            class="vault-card relative overflow-hidden rounded-[24px] border border-transparent p-5 transition duration-200"
            :class="[
              selectedEntryId === entry.id ? 'ring-2 ring-[#0f8b66]/35' : '',
              'min-h-[180px]',
              revealErrorsById[entry.id] ? 'border border-rose-500/70' : '',
              isCardShaking(entry.id) ? 'vault-card-shake' : '',
            ]"
            @click="openEntry(entry)"
          >
            <div class="flex items-start justify-between gap-3 relative z-[1]">
              <div>
                <div class="vault-card-meta">{{ entry.is_secret ? 'Secret note' : 'Open note' }}</div>
                <h3 class="vault-card-title mt-4 pr-3 text-xl font-semibold leading-7">{{ entry.title }}</h3>
              </div>
              <button
                v-if="entry.is_secret && !isUnlocked(entry)"
                type="button"
                class="vault-card-lock flex h-11 w-11 shrink-0 items-center justify-center rounded-full transition"
                @click.stop="openUnlockPrompt(entry.id)"
              >
                <svg viewBox="0 0 24 24" class="h-5 w-5 fill-none stroke-current" stroke-width="1.8">
                  <path d="M7 11V8a5 5 0 0 1 10 0v3" />
                  <rect x="5" y="11" width="14" height="10" rx="2" />
                </svg>
              </button>
              <button
                v-else-if="entryContent(entry)"
                type="button"
                class="rounded-full border border-white/60 bg-white/60 px-4 py-2 text-xs font-medium text-[#0f8b66] shadow-[inset_0_1px_0_rgba(255,255,255,0.8)] transition hover:border-white"
                @click.stop="copyValue(entryContent(entry))"
              >
                Copy
              </button>
            </div>

            <div class="relative mt-8 overflow-hidden rounded-[20px] border border-white/45 bg-white/24 backdrop-blur-sm">
              <div
                class="flex min-h-[96px] items-center px-4 py-4 text-sm leading-7 text-[#977b67] transition duration-200"
                :class="entry.is_secret && !isUnlocked(entry) ? 'pointer-events-none select-none blur-md opacity-30' : ''"
              >
                <div class="w-full">
                  <div class="h-3 w-3/4 rounded-full bg-white/80"></div>
                  <div class="mt-3 h-3 w-1/2 rounded-full bg-white/65"></div>
                  <div class="mt-3 h-3 w-2/3 rounded-full bg-white/55"></div>
                </div>
              </div>

              <div
                v-if="entry.is_secret && !isUnlocked(entry)"
                class="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-white/18 px-5 text-center backdrop-blur-[2px]"
              >
                <div class="vault-card-lock flex h-12 w-12 items-center justify-center rounded-full">
                  <svg viewBox="0 0 24 24" class="h-7 w-7 fill-none stroke-current" stroke-width="1.8">
                    <path d="M7 11V8a5 5 0 0 1 10 0v3" />
                    <rect x="5" y="11" width="14" height="10" rx="2" />
                  </svg>
                </div>
                <div class="text-sm font-medium text-current">Locked</div>
              </div>
              <div
                v-else
                class="absolute inset-x-0 bottom-0 flex items-center justify-between border-t border-white/40 bg-white/34 px-4 py-3 text-xs uppercase tracking-[0.18em] text-[#78614c]"
              >
                <span>{{ entry.is_secret ? 'Unlocked' : 'Public' }}</span>
                <span>Open</span>
              </div>
            </div>

          </article>
          </div>
          <div v-else class="mt-5 flex min-h-[320px] items-center justify-center rounded-[24px] border border-dashed border-[#dbc6ab] bg-white/44 p-10 text-center text-[#8b735b]">
            No assets match the current search.
          </div>
        </div>
      </main>
    </section>

    <div v-if="showModal" class="fixed inset-0 z-50 flex items-center justify-center bg-[rgba(87,60,33,0.18)] px-4 py-6 backdrop-blur-md">
      <div class="vault-modal-shell w-full max-w-3xl rounded-[32px] border border-[#e1cfb8] p-6">
        <div class="flex items-start justify-between gap-4">
          <div>
            <div class="text-xs font-semibold uppercase tracking-[0.22em] text-[#d17216]">{{ modalMode === 'asset' ? 'Add Asset' : 'Import File' }}</div>
            <h2 class="mt-3 text-2xl font-semibold text-[#2f241f]">{{ modalMode === 'asset' ? 'Store a new vault asset' : 'Upload a document' }}</h2>
          </div>
          <button type="button" class="rounded-full border border-[#dbc4a7] bg-white/54 px-4 py-2 text-sm text-[#5f4b3e] transition hover:border-[#c89c6d]" @click="closeModal">
            Close
          </button>
        </div>

        <div class="mt-5 flex gap-2">
          <button type="button" class="rounded-full px-4 py-2 text-sm font-medium transition" :class="modalMode === 'asset' ? 'bg-[#0f8b66] text-white shadow-[0_12px_24px_rgba(15,139,102,0.24)]' : 'border border-[#dbc4a7] bg-white/54 text-[#6f5a48]'" @click="modalMode = 'asset'">
            Manual
          </button>
          <button type="button" class="rounded-full px-4 py-2 text-sm font-medium transition" :class="modalMode === 'import' ? 'bg-[#0f8b66] text-white shadow-[0_12px_24px_rgba(15,139,102,0.24)]' : 'border border-[#dbc4a7] bg-white/54 text-[#6f5a48]'" @click="modalMode = 'import'">
            Upload Document
          </button>
        </div>

        <div v-if="modalMode === 'asset'" class="mt-6">
          <form class="space-y-4" @submit.prevent="saveEntry">
            <div class="grid gap-4 md:grid-cols-2">
              <input v-model="entryForm.title" type="text" placeholder="Title" class="h-12 rounded-2xl border border-[#dbc4a7] bg-white/78 px-4 text-[#3c2f27] focus:border-[#d17216] focus:outline-none" />
              <input v-model="entryForm.category" type="text" placeholder="Category" class="h-12 rounded-2xl border border-[#dbc4a7] bg-white/78 px-4 text-[#3c2f27] focus:border-[#d17216] focus:outline-none" />
            </div>
            <label class="inline-flex items-center gap-2 text-sm text-[#6f5a48]">
              <input v-model="entryForm.isSecret" type="checkbox" class="h-4 w-4 rounded border-[#cba77f] bg-white text-[#0f8b66]" />
              Secret data
            </label>
            <textarea v-model="entryForm.content" rows="10" placeholder="Credentials, links, notes..." class="w-full rounded-3xl border border-[#dbc4a7] bg-white/78 px-4 py-4 text-sm text-[#3c2f27] focus:border-[#d17216] focus:outline-none"></textarea>
            <div v-if="entryForm.isSecret" class="grid gap-4 md:grid-cols-2">
              <input v-model="entryForm.secretKey" type="text" placeholder="Optional key/password (leave blank to auto-generate)" class="h-12 rounded-2xl border border-[#dbc4a7] bg-white/78 px-4 text-[#3c2f27] focus:border-[#d17216] focus:outline-none" />
              <input v-model="entryForm.secretHint" type="text" placeholder="Secret hint" class="h-12 rounded-2xl border border-[#dbc4a7] bg-white/78 px-4 text-[#3c2f27] focus:border-[#d17216] focus:outline-none" />
            </div>
            <div class="flex flex-wrap gap-3">
              <button type="submit" class="rounded-full bg-[#0f8b66] px-5 py-3 font-semibold text-white shadow-[0_16px_30px_rgba(15,139,102,0.2)] transition hover:bg-[#0c7556]" :disabled="loading">
                {{ loading ? 'Saving...' : 'Save asset' }}
              </button>
            </div>
            <p v-if="createError" class="text-sm text-rose-600">{{ createError }}</p>
            <div v-if="revealState.generatedSecretKey" class="rounded-2xl border border-[#f0c48d] bg-[#fff1dd] p-4 text-sm text-[#b26114]">
              Keep this key safe: <span class="font-semibold">{{ revealState.generatedSecretKey }}</span>
              <button type="button" class="ml-3 rounded-full border border-[#e9b67b] bg-white/65 px-3 py-1 text-xs text-[#b26114] transition hover:border-[#d68a33]" @click="copyValue(revealState.generatedSecretKey)">
                Copy key
              </button>
            </div>
          </form>
        </div>

        <div v-else class="mt-6">
          <form class="space-y-4" @submit.prevent="submitImport">
            <input v-model="importForm.category" type="text" placeholder="Category for imported rows" class="h-12 w-full rounded-2xl border border-[#dbc4a7] bg-white/78 px-4 text-[#3c2f27] focus:border-[#d17216] focus:outline-none" />
            <input type="file" accept=".csv,.json,.txt,.md,.xlsx,.docx" class="block h-12 w-full rounded-2xl border border-[#dbc4a7] bg-white/78 px-3 py-3 text-sm text-[#6f5a48]" @change="onFileChange" />
            <button type="submit" class="rounded-full bg-[#f38d1f] px-5 py-3 font-semibold text-white shadow-[0_16px_30px_rgba(243,141,31,0.2)] transition hover:bg-[#df7d15]" :disabled="loading">
              {{ loading ? 'Importing...' : 'Import file' }}
            </button>
            <p v-if="importError" class="text-sm text-rose-600">{{ importError }}</p>
          </form>
        </div>
      </div>
    </div>

    <div v-if="detailsEntry" class="fixed inset-0 z-40 flex items-center justify-center bg-[rgba(87,60,33,0.18)] px-4 py-6 backdrop-blur-md">
      <div class="vault-modal-shell w-full max-w-3xl rounded-[32px] border border-[#e1cfb8] p-6">
        <div class="flex items-start justify-between gap-4">
          <div>
            <div class="text-xs font-semibold uppercase tracking-[0.22em] text-[#d17216]">Vault Asset</div>
            <h2 class="mt-3 text-2xl font-semibold text-[#2f241f]">{{ detailsEntry.title }}</h2>
          </div>
          <div class="flex items-center gap-3">
            <button v-if="!editMode" type="button" class="rounded-full border border-[#b9ddcc] bg-[#ebfaf4] px-4 py-2 text-sm text-[#0f8b66] transition hover:border-[#0f8b66]" @click="copyValue(entryContent(detailsEntry))">
              Copy
            </button>
            <button v-if="!editMode" type="button" class="rounded-full border border-[#dbc4a7] bg-white/54 px-4 py-2 text-sm text-[#5f4b3e] transition hover:border-[#c89c6d]" @click="startEditEntry(detailsEntry)">
              Edit
            </button>
            <button v-if="!editMode" type="button" class="rounded-full border border-[#f0c7c1] bg-[#fff1ee] px-4 py-2 text-sm text-[#b24b3e] transition hover:border-[#d86f61]" @click="requestDeleteEntry(detailsEntry)">
              Delete
            </button>
            <button type="button" class="rounded-full border border-[#dbc4a7] bg-white/54 px-4 py-2 text-sm text-[#5f4b3e] transition hover:border-[#c89c6d]" @click="closeDetailsModal">
              Close
            </button>
          </div>
        </div>

        <form v-if="editMode" class="mt-5 space-y-4" @submit.prevent="saveEditedEntry">
          <div class="grid gap-4 md:grid-cols-2">
            <input v-model="editForm.title" type="text" placeholder="Title" class="h-12 rounded-2xl border border-[#dbc4a7] bg-white/78 px-4 text-[#3c2f27] focus:border-[#d17216] focus:outline-none" />
            <input v-model="editForm.category" type="text" placeholder="Category" class="h-12 rounded-2xl border border-[#dbc4a7] bg-white/78 px-4 text-[#3c2f27] focus:border-[#d17216] focus:outline-none" />
          </div>
          <label class="inline-flex items-center gap-2 text-sm text-[#6f5a48]">
            <input v-model="editForm.isSecret" type="checkbox" class="h-4 w-4 rounded border-[#cba77f] bg-white text-[#0f8b66]" />
            Secret data
          </label>
          <textarea v-model="editForm.content" rows="10" class="w-full rounded-3xl border border-[#dbc4a7] bg-white/78 px-4 py-4 text-sm text-[#3c2f27] focus:border-[#d17216] focus:outline-none"></textarea>
          <div v-if="editForm.isSecret" class="grid gap-4 md:grid-cols-2">
            <input v-model="editForm.secretKey" type="text" placeholder="Current key/password required for secret updates" class="h-12 rounded-2xl border border-[#dbc4a7] bg-white/78 px-4 text-[#3c2f27] focus:border-[#d17216] focus:outline-none" />
            <input v-model="editForm.secretHint" type="text" placeholder="Secret hint" class="h-12 rounded-2xl border border-[#dbc4a7] bg-white/78 px-4 text-[#3c2f27] focus:border-[#d17216] focus:outline-none" />
          </div>
          <div class="flex flex-wrap gap-3">
            <button type="submit" class="rounded-full bg-[#0f8b66] px-5 py-3 font-semibold text-white shadow-[0_16px_30px_rgba(15,139,102,0.2)] transition hover:bg-[#0c7556]" :disabled="loading">
              {{ loading ? 'Saving...' : 'Save changes' }}
            </button>
            <button type="button" class="rounded-full border border-[#dbc4a7] bg-white/54 px-5 py-3 text-sm text-[#5f4b3e] transition hover:border-[#c89c6d]" @click="cancelEditEntry">
              Cancel
            </button>
          </div>
          <p v-if="editError" class="text-sm text-rose-600">{{ editError }}</p>
          <div v-if="revealState.generatedSecretKey" class="rounded-2xl border border-[#f0c48d] bg-[#fff1dd] p-4 text-sm text-[#b26114]">
            Keep this key safe: <span class="font-semibold">{{ revealState.generatedSecretKey }}</span>
            <button type="button" class="ml-3 rounded-full border border-[#e9b67b] bg-white/65 px-3 py-1 text-xs text-[#b26114] transition hover:border-[#d68a33]" @click="copyValue(revealState.generatedSecretKey)">
              Copy key
            </button>
          </div>
        </form>

        <div v-else class="mt-5 overflow-hidden rounded-[24px] border border-[#e6d3bb] bg-white/65">
          <div class="max-h-[520px] overflow-auto whitespace-pre-wrap px-5 py-5 text-sm leading-7 text-[#3c2f27]">{{ entryContent(detailsEntry) }}</div>
        </div>
      </div>
    </div>

    <div v-if="unlockEntryTarget && !isUnlocked(unlockEntryTarget)" class="fixed inset-0 z-40 flex items-center justify-center bg-[rgba(87,60,33,0.18)] px-4 py-6 backdrop-blur-md">
      <div class="vault-modal-shell w-full max-w-md rounded-[32px] border border-[#e1cfb8] p-6">
        <div class="flex items-start justify-between gap-4">
          <div>
            <div class="text-xs font-semibold uppercase tracking-[0.22em] text-[#d17216]">Unlock Asset</div>
            <h2 class="mt-3 text-2xl font-semibold text-[#2f241f]">{{ unlockEntryTarget.title }}</h2>
            <p class="mt-2 text-sm text-[#6f5a48]">Enter the secret key or password to open this vault item.</p>
            <p v-if="unlockEntryTarget.secret_hint" class="mt-3 text-sm text-[#b26114]">Hint: {{ unlockEntryTarget.secret_hint }}</p>
          </div>
          <button type="button" class="rounded-full border border-[#dbc4a7] bg-white/54 px-4 py-2 text-sm text-[#5f4b3e] transition hover:border-[#c89c6d]" @click="closeUnlockPrompt">
            Close
          </button>
        </div>

        <div class="mt-5 space-y-4">
          <input
            v-model="unlockInputs[unlockEntryTarget.id]"
            type="text"
            placeholder="Secret key or password"
            class="h-12 w-full rounded-2xl border border-[#dbc4a7] bg-white/78 px-4 text-[#3c2f27] focus:border-[#d17216] focus:outline-none"
            @keydown.enter.prevent="unlockEntry(unlockEntryTarget.id)"
          />
          <button
            type="button"
            class="w-full rounded-full bg-[#0f8b66] px-5 py-3 font-semibold text-white shadow-[0_16px_30px_rgba(15,139,102,0.2)] transition hover:bg-[#0c7556]"
            @click="unlockEntry(unlockEntryTarget.id)"
          >
            Unlock
          </button>
          <p v-if="revealErrorsById[unlockEntryTarget.id]" class="text-sm text-rose-600">{{ revealErrorsById[unlockEntryTarget.id] }}</p>
        </div>
      </div>
    </div>

    <div v-if="deleteConfirmEntry && deleteConfirmState.open" class="fixed inset-0 z-40 flex items-center justify-center bg-[rgba(87,60,33,0.18)] px-4 py-6 backdrop-blur-md">
      <div class="vault-modal-shell w-full max-w-md rounded-[32px] border border-[#e1cfb8] p-6">
        <div class="flex items-start justify-between gap-4">
          <div>
            <div class="text-xs font-semibold uppercase tracking-[0.22em] text-[#d17216]">Delete Asset</div>
            <h2 class="mt-3 text-2xl font-semibold text-[#2f241f]">{{ deleteConfirmEntry.title }}</h2>
            <p class="mt-2 text-sm text-[#6f5a48]">
              {{ deleteConfirmEntry.is_secret ? 'Enter the key or password to confirm deleting this secret note.' : 'This note will be deleted immediately once confirmed.' }}
            </p>
          </div>
          <button type="button" class="rounded-full border border-[#dbc4a7] bg-white/54 px-4 py-2 text-sm text-[#5f4b3e] transition hover:border-[#c89c6d]" @click="closeDeleteConfirm">
            Close
          </button>
        </div>

        <div class="mt-5 space-y-4">
          <input
            v-if="deleteConfirmEntry.is_secret"
            v-model="deleteConfirmState.secretKey"
            type="text"
            placeholder="Secret key or password"
            class="h-12 w-full rounded-2xl border border-[#dbc4a7] bg-white/78 px-4 text-[#3c2f27] focus:border-[#d17216] focus:outline-none"
            @keydown.enter.prevent="confirmDeleteEntry"
          />
          <button
            type="button"
            class="w-full rounded-full bg-[#c95e49] px-5 py-3 font-semibold text-white shadow-[0_16px_30px_rgba(201,94,73,0.18)] transition hover:bg-[#b9503c]"
            @click="confirmDeleteEntry"
          >
            Delete note
          </button>
          <p v-if="deleteError" class="text-sm text-rose-600">{{ deleteError }}</p>
        </div>
      </div>
    </div>
  `,
};
