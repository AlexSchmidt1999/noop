package com.noop.ai

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ProviderCompatibilityTest {
    @Test
    fun geminiBodyPreservesExistingSamplingAndMatchesSwiftOracle() {
        // Verbatim stdout from the Swift production helper compiled with swiftc -O.
        val expected = """{"contents":[{"parts":[{"text":"Hallo"}],"role":"user"}],"generationConfig":{"maxOutputTokens":4096,"temperature":0.59999999999999998},"system_instruction":{"parts":[{"text":"Coach"}]}}"""
        val contents = JSONArray().put(JSONObject().put("role", "user")
            .put("parts", JSONArray().put(JSONObject().put("text", "Hallo"))))
        val body = AiCoach.geminiRequestBody("Coach", contents)
        assertTrue(JSONObject(expected).similar(body))
        assertEquals(0.6, body.getJSONObject("generationConfig").getDouble("temperature"), 0.0)
    }

    @Test
    fun anthropicJoinsVisibleTextAfterThinkingBlocks() {
        val responses = listOf(
            """{"content":[{"type":"thinking","thinking":"Summary"},{"type":"text","text":"Hallo "},{"type":"tool_use","name":"ignored"},{"type":"text","text":"Welt"}]}""",
            """{"content":[{"type":"thinking","thinking":"Summary"}]}""",
            """{"content":[{"type":"text","text":" Grüße 👋 \n"}]}""",
        )
        // Verbatim Swift oracle stdout, including the JSON string encoding.
        val expected = """
            "Hallo Welt"
            ""
            "Grüße 👋"
        """.trimIndent().lines()
        assertEquals(expected, responses.map { JSONObject.quote(AiCoach.anthropicReplyText(JSONObject(it))) })
    }

    @Test
    fun geminiModelsRequireTextGenerationAndMatchSwiftOracle() {
        val fixture = """{"models":[{"name":"models/gemini-3-pro","supportedGenerationMethods":["generateContent","countTokens"]},{"name":"models/gemini-live","supportedGenerationMethods":["bidiGenerateContent"]},{"name":"models/gemini-3-flash-preview-tts","supportedGenerationMethods":["generateContent"]},{"name":"models/gemini-2.5-flash-native-audio","supportedGenerationMethods":["bidiGenerateContent"]},{"name":"models/gemini-no-generation","supportedGenerationMethods":[]},{"name":" models/gemini-3-pro "}]}"""
        // Verbatim Swift oracle stdout.
        assertEquals("""["gemini-3-pro"]""", JSONArray(AiCoach.parseGeminiModels(fixture)).toString())
    }

    @Test
    fun anthropicPickerReplacesRetiredClaude3WithActiveModels() {
        assertTrue(AiProvider.ANTHROPIC.models.contains("claude-sonnet-5-5"))
        assertTrue(AiProvider.ANTHROPIC.models.contains("claude-opus-5-5"))
        assertFalse(AiProvider.ANTHROPIC.models.any { it.startsWith("claude-3") })
    }
}
