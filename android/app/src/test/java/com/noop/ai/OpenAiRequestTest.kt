package com.noop.ai

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class OpenAiRequestTest {
    @Test
    fun requestBodiesMatchStandaloneSwiftOracle() {
        // Verbatim stdout from the Swift production helper compiled with swiftc -O.
        val expected = listOf(
            """{"max_completion_tokens":4096,"messages":[{"content":"Hallo","role":"user"}],"model":"gpt-5.4"}""",
            """{"max_completion_tokens":4096,"messages":[{"content":"Hallo","role":"user"}],"model":"gpt-5.4","stream":true}""",
        )
        val messages = JSONArray().put(JSONObject().put("role", "user").put("content", "Hallo"))
        for ((index, stream) in listOf(false, true).withIndex()) {
            assertTrue(JSONObject(expected[index]).similar(AiCoach.openAiCompatibleBody(AiProvider.OPENAI, "gpt-5.4", messages, stream = stream)))
        }
        val modelOracle = """
            gpt-5.4|true
            gpt-4o|true
            o3-mini|true
            gpt-5.4-pro|false
            gpt-5.4-pro-2026-03-05|false
            omni-moderation-latest|false
            o|false
            o４|false
            text-embedding-3-large|false
            gpt-image-1|false
            gpt-5.3-codex|false
            o3-deep-research|false
            gpt-4o-realtime-preview|false
            gpt-4o-mini-transcribe|false
            gpt-3.5-turbo-instruct|false
            gpt-4o-mini-search-preview|true
            gpt-4o-mini-tts|false
            gpt-4o-audio-preview|true
            gpt-audio|true
        """.trimIndent()
        assertEquals(modelOracle, modelOracle.lines().joinToString("\n") {
            val model = it.substringBefore('|')
            "$model|${AiCoach.isOpenAiChatModel(model)}"
        })
    }

    @Test
    fun regularAndStreamingBodiesUseReasoningCompatibleParameters() {
        val messages = JSONArray().put(JSONObject().put("role", "user").put("content", "Hallo"))
        for (model in listOf("gpt-5.4", "gpt-5-mini", "gpt-4.1", "o3")) {
            for (stream in listOf(false, true)) {
                val body = AiCoach.openAiCompatibleBody(AiProvider.OPENAI, model, messages, stream = stream)
                assertEquals(model, body.getString("model"))
                assertEquals(4096, body.getInt("max_completion_tokens"))
                assertFalse(body.has("max_tokens"))
                if (model == "gpt-4.1") assertEquals(0.6, body.getDouble("temperature"), 0.0)
                else assertFalse(body.has("temperature"))
                assertEquals(stream, body.has("stream"))
                if (stream) assertTrue(body.getBoolean("stream"))
                assertEquals("Hallo", body.getJSONArray("messages").getJSONObject(0).getString("content"))
            }
        }
    }

    @Test
    fun customServersRetainLegacyParametersAndModernRetry() {
        for (stream in listOf(false, true)) {
            val legacy = AiCoach.openAiCompatibleBody(AiProvider.CUSTOM, "local", JSONArray(), stream = stream)
            assertEquals(4096, legacy.getInt("max_tokens"))
            assertEquals(0.6, legacy.getDouble("temperature"), 0.0)
            assertFalse(legacy.has("max_completion_tokens"))
            val retry = AiCoach.openAiCompatibleBody(AiProvider.CUSTOM, "local", JSONArray(), modernParams = true, stream = stream)
            assertEquals(4096, retry.getInt("max_completion_tokens"))
            assertFalse(retry.has("max_tokens"))
            assertFalse(retry.has("temperature"))
        }
    }

    @Test
    fun gpt54IsAvailableWithoutRefreshingModels() {
        assertTrue(AiProvider.OPENAI.models.contains("gpt-5.4"))
        assertTrue(AiProvider.OPENAI.models.contains("gpt-5.4-mini"))
        assertEquals("gpt-5-mini", AiProvider.OPENAI.defaultModel)
        val original = listOf("gpt-5", "gpt-5-mini", "gpt-5-nano", "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano", "gpt-4o", "gpt-4o-mini", "o3", "o4-mini")
        assertTrue(AiProvider.OPENAI.models.containsAll(original))
    }

    @Test
    fun modelRefreshExcludesProAndModerationModels() {
        val body = """{"data":[{"id":"gpt-4o"},{"id":"o3-mini"},{"id":"gpt-5.4"},{"id":"gpt-5.4-pro"},{"id":"gpt-5.4-pro-2026-03-05"},{"id":"omni-moderation-latest"},{"id":"text-embedding-3-large"}]}"""
        assertEquals(listOf("gpt-4o", "o3-mini", "gpt-5.4"), AiCoach.parseOpenAiCompatibleModels(AiProvider.OPENAI, body))
        assertTrue(AiCoach.parseOpenAiCompatibleModels(AiProvider.CUSTOM, body).contains("gpt-5.4-pro"))
    }

    @Test
    fun replyLanguageFollowsAppLanguageWhilePreservingEditedPrompt() {
        for (tag in listOf("de", "en", "es", "fr", "it", "pt-PT", "pl", "zh", "de-DE")) {
            assertEquals(
                "Coach in two sentences.\n\nReply in the app's language (BCP-47: $tag). " +
                    "Use this language even if the context or earlier messages are in another language, " +
                    "unless the user explicitly requests a different language.",
                AiCoach.localizedSystemPrompt("Coach in two sentences.", tag),
            )
        }
        assertEquals(AiCoach.localizedSystemPrompt("Coach", "en"), AiCoach.localizedSystemPrompt("Coach", " \n "))
    }
}
