package com.noop.ai

/**
 * AI Coach providers. The user brings their own API key for one of these and the app
 * sends a compact text summary of their metrics + their question to the chosen provider.
 *
 * Provider names are the only branding shown — there is no app-author / model-vendor
 * branding beyond the provider name the user picks.
 *
 * Wire formats are encoded in [AiCoach]; this enum only carries the display name, the
 * default model, the curated list of selectable models, the chat HTTPS endpoint, and the
 * models-list endpoint used to fetch the provider's live catalogue.
 *
 * The [models] list is a sensible, curated starting point — the user can also fetch the
 * provider's live list (merged in at runtime) or type any model id via "Custom…", so the
 * app never has to ship an exhaustive or up-to-date catalogue.
 */
enum class AiProvider(
    val displayName: String,
    val defaultModel: String,
    val models: List<String>,
    val endpoint: String,
    val modelsEndpoint: String,
) {
    OPENAI(
        displayName = "OpenAI",
        defaultModel = "gpt-5-mini",
        // Versioned model families; fetchModels merges newer releases from the live catalogue.
        //
        // Both request paths use max_completion_tokens; classic GPT sampling stays unchanged.
        // Twin of the Swift `AIProvider.modelOptions`.
        models = listOf(
            "gpt-5.4",
            "gpt-5.4-mini",
            "gpt-5",
            "gpt-5-mini",
            "gpt-5-nano",
            "gpt-4.1",
            "gpt-4.1-mini",
            "gpt-4.1-nano",
            "gpt-4o",
            "gpt-4o-mini",
            "o3",
            "o4-mini",
        ),
        endpoint = "https://api.openai.com/v1/chat/completions",
        modelsEndpoint = "https://api.openai.com/v1/models",
    ),
    ANTHROPIC(
        displayName = "Anthropic",
        defaultModel = "claude-sonnet-4-6",
        models = listOf(
            "claude-opus-5-5",
            "claude-sonnet-5-5",
            "claude-opus-4-8",
            "claude-sonnet-4-6",
            "claude-haiku-4-5-20251001",
        ),
        endpoint = "https://api.anthropic.com/v1/messages",
        modelsEndpoint = "https://api.anthropic.com/v1/models",
    ),

    /**
     * Google Gemini (BYO key). NATIVE Google format — the byte-for-byte twin of the Swift
     * `GeminiClient` (`Strand/AI/Providers/Gemini.swift`): `x-goog-api-key` auth, a `system_instruction`
     * + `contents`/`parts` body, and `candidates[].content.parts[].text` replies. [endpoint] is the base
     * models URL; the per-call `/<model>:generateContent` suffix is appended in [AiCoach.callGemini]
     * (kept literal so the `:` is never percent-encoded).
     *
     * The default and curated list use provider-managed `-latest` aliases, which may point to stable
     * or preview releases. [AiCoach.fetchModels] lists compatible text-generation models so the user
     * can pin a concrete version. Same list and default as the Swift enum.
     */
    GEMINI(
        displayName = "Google Gemini",
        defaultModel = "gemini-flash-latest",
        models = listOf(
            "gemini-pro-latest",
            "gemini-flash-latest",
            "gemini-flash-lite-latest",
        ),
        endpoint = "https://generativelanguage.googleapis.com/v1beta/models",
        modelsEndpoint = "https://generativelanguage.googleapis.com/v1beta/models",
    ),

    /**
     * A generic OpenAI-compatible server the user points at — typically a LOCAL LLM such as
     * Ollama, LM Studio or llama.cpp (`http://localhost:11434/v1`), or any self-hosted gateway.
     * The endpoints here are placeholders: the real chat/models URLs are built at call time from
     * the user-set base URL (see [AiCoach] / [AiKeyStore.readCustomBaseUrl]). The API key is
     * optional — local servers usually need none.
     */
    CUSTOM(
        displayName = "Custom (OpenAI-compatible)",
        defaultModel = "",
        models = emptyList(),
        endpoint = "",
        modelsEndpoint = "",
    );

    companion object {
        /** Resolve a provider by its persisted [name], falling back to [OPENAI]. */
        fun fromName(name: String?): AiProvider =
            entries.firstOrNull { it.name == name } ?: OPENAI
    }
}

enum class CustomAiAuthHeader(val displayName: String) {
    BEARER("Bearer"),
    X_API_KEY("x-api-key");

    companion object {
        fun fromName(name: String?): CustomAiAuthHeader =
            entries.firstOrNull { it.name == name } ?: BEARER
    }
}
