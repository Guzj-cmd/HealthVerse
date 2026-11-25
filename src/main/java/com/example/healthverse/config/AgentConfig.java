package com.example.healthverse.config;

import com.google.gson.Gson;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;

import java.io.File;
import java.io.FileInputStream;
import java.io.InputStreamReader;
import java.io.Reader;
import java.nio.charset.StandardCharsets;

/**
 * Resolves Agent configuration without persisting credentials in the project.
 * Environment variables take precedence over the optional local Claude settings.
 */
public final class AgentConfig {
    private static final Gson GSON = new Gson();

    private final String provider;
    private final String apiUrl;
    private final String apiKey;
    private final String model;
    private final String proxyUrl;
    private final String satoriBridgeUrl;

    private AgentConfig(String provider, String apiUrl, String apiKey, String model, String proxyUrl, String satoriBridgeUrl) {
        this.provider = provider;
        this.apiUrl = apiUrl;
        this.apiKey = apiKey;
        this.model = normalizeModel(model);
        this.proxyUrl = proxyUrl;
        this.satoriBridgeUrl = satoriBridgeUrl;
    }

    public static AgentConfig load() {
        String provider = value("AI_PROVIDER");
        String apiUrl = value("AI_API_URL");
        String apiKey = value("AI_API_KEY");
        String model = value("AI_MODEL");
        String proxyUrl = value("AI_PROXY_URL");
        String satoriBridgeUrl = value("SATORI_BRIDGE_URL");

        if (isBlank(apiUrl) || isBlank(apiKey) || isBlank(model)) {
            JsonObject localEnv = readClaudeEnvironment();
            if (localEnv != null) {
                String baseUrl = string(localEnv, "ANTHROPIC_BASE_URL");
                if (isBlank(apiUrl) && !isBlank(baseUrl)) {
                    apiUrl = appendMessagesEndpoint(baseUrl);
                }
                if (isBlank(apiKey)) {
                    apiKey = string(localEnv, "ANTHROPIC_AUTH_TOKEN");
                }
                if (isBlank(model)) {
                    model = firstNonBlank(
                            string(localEnv, "ANTHROPIC_DEFAULT_SONNET_MODEL"),
                            string(localEnv, "ANTHROPIC_DEFAULT_SONNET_MODEL_NAME"));
                }
                if (isBlank(provider)) {
                    provider = "anthropic";
                }
                if (isBlank(proxyUrl)) {
                    proxyUrl = firstNonBlank(
                            firstNonBlank(string(localEnv, "HTTPS_PROXY"), string(localEnv, "https_proxy")),
                            firstNonBlank(string(localEnv, "HTTP_PROXY"), string(localEnv, "http_proxy")));
                }
            }
        }

        if (isBlank(provider)) {
            provider = apiUrl != null && apiUrl.contains("/messages") ? "anthropic" : "openai";
        }

        return new AgentConfig(provider, apiUrl, apiKey, model, proxyUrl, satoriBridgeUrl);
    }

    private static JsonObject readClaudeEnvironment() {
        File settings = new File(new File(System.getProperty("user.home"), ".claude"), "settings.json");
        if (!settings.isFile()) {
            return null;
        }
        try (Reader reader = new InputStreamReader(new FileInputStream(settings), StandardCharsets.UTF_8)) {
            JsonObject root = GSON.fromJson(reader, JsonObject.class);
            JsonElement env = root == null ? null : root.get("env");
            return env != null && env.isJsonObject() ? env.getAsJsonObject() : null;
        } catch (Exception ignored) {
            // A malformed or unavailable private config simply disables the remote Agent.
            return null;
        }
    }

    private static String appendMessagesEndpoint(String baseUrl) {
        String normalized = baseUrl.trim();
        while (normalized.endsWith("/")) {
            normalized = normalized.substring(0, normalized.length() - 1);
        }
        if (normalized.endsWith("/v1/messages")) {
            return normalized;
        }
        if (normalized.endsWith("/v1")) {
            return normalized + "/messages";
        }
        return normalized + "/v1/messages";
    }

    private static String normalizeModel(String model) {
        if (model == null) {
            return null;
        }
        return model.trim().replaceFirst("\\[[^]]*]$", "");
    }

    private static String string(JsonObject object, String key) {
        JsonElement value = object.get(key);
        return value == null || value.isJsonNull() ? null : value.getAsString();
    }

    private static String value(String name) {
        String value = System.getenv(name);
        if (isBlank(value)) {
            value = System.getProperty(name);
        }
        return isBlank(value) ? null : value.trim();
    }

    private static String firstNonBlank(String first, String second) {
        return isBlank(first) ? second : first;
    }

    private static boolean isBlank(String value) {
        return value == null || value.trim().isEmpty();
    }

    public boolean isRemoteReady() {
        return !isBlank(apiUrl) && !isBlank(apiKey) && !isBlank(model);
    }

    public boolean isAnthropic() {
        return "anthropic".equalsIgnoreCase(provider) || (apiUrl != null && apiUrl.contains("/messages"));
    }

    public String getProvider() {
        return provider;
    }

    public String getApiUrl() {
        return apiUrl;
    }

    public String getApiKey() {
        return apiKey;
    }

    public String getModel() {
        return model;
    }

    public String getProxyUrl() {
        return proxyUrl;
    }

    public String getSatoriBridgeUrl() {
        return satoriBridgeUrl;
    }
}
