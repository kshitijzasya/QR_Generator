import { generateSeo, parseSeoError } from "../api/seoApi.js";

export function useSeoTool({ seoForm, seoResult, seoError }) {
  async function generate() {
    seoError.value = "";

    const useOwnLive = seoForm.platform === "youtube" && seoForm.keyMode === "own";
    if (useOwnLive && !(seoForm.youtubeApiKey || "").trim()) {
      seoError.value = "Enter your YouTube API key for personal-key mode.";
      return;
    }

    const response = await generateSeo({
      platform: seoForm.platform,
      topic: seoForm.topic,
      content_format: seoForm.contentFormat,
      live: true,
      use_own_key: useOwnLive,
      youtube_api_key: useOwnLive ? (seoForm.youtubeApiKey || "").trim() : "",
      allow_fallback: true,
    });

    if (!response.ok) {
      seoError.value = await parseSeoError(response);
      return;
    }

    seoResult.value = await response.json();
  }

  function reset() {
    seoForm.platform = "youtube";
    seoForm.contentFormat = "long";
    seoForm.topic = "";
    seoForm.keyMode = "backup";
    seoForm.youtubeApiKey = "";
    seoError.value = "";
    seoResult.value = null;
  }

  return {
    generate,
    reset,
  };
}
