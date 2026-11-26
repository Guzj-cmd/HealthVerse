package com.example.healthverse.service;

import com.google.gson.Gson;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.Map;

/** Reads the configured coordinator's public, non-sensitive status endpoint. */
public final class FederatedStatusService {
    private static final Gson GSON = new Gson();
    private static final int CONNECT_TIMEOUT_MS = 1500;
    private static final int READ_TIMEOUT_MS = 2500;
    private static final int MAX_RESPONSE_CHARS = 64 * 1024;

    private final String statusUrl;

    public FederatedStatusService(String statusUrl) {
        this.statusUrl = normalize(statusUrl);
    }

    public static FederatedStatusService fromEnvironment() {
        String value = System.getenv("HV_FED_STATUS_URL");
        if (isBlank(value)) value = System.getProperty("HV_FED_STATUS_URL");
        return new FederatedStatusService(value);
    }

    public Map<String, Object> readStatus() {
        Map<String, Object> result = new LinkedHashMap<String, Object>();
        result.put("configured", !isBlank(statusUrl));
        result.put("reachable", false);
        result.put("state", isBlank(statusUrl) ? "not_configured" : "unreachable");
        result.put("optInRequired", true);
        result.put("browserUploadsRawData", false);
        if (isBlank(statusUrl)) return result;

        HttpURLConnection connection = null;
        try {
            URL url = new URL(statusUrl);
            if (!"http".equalsIgnoreCase(url.getProtocol()) && !"https".equalsIgnoreCase(url.getProtocol())) {
                result.put("state", "invalid_protocol");
                return result;
            }
            connection = (HttpURLConnection) url.openConnection();
            connection.setRequestMethod("GET");
            connection.setConnectTimeout(CONNECT_TIMEOUT_MS);
            connection.setReadTimeout(READ_TIMEOUT_MS);
            connection.setRequestProperty("Accept", "application/json");
            int code = connection.getResponseCode();
            if (code != HttpURLConnection.HTTP_OK) {
                result.put("state", "http_" + code);
                return result;
            }
            String body = readBounded(connection);
            JsonObject source = GSON.fromJson(body, JsonObject.class);
            if (source == null) {
                result.put("state", "invalid_response");
                return result;
            }
            result.put("reachable", true);
            result.put("state", "online");
            copyString(source, result, "run_type", "runType");
            copyNumber(source, result, "round", "round");
            copyNumber(source, result, "registered_clients", "registeredClients");
            copyNumber(source, result, "distinct_device_fingerprints", "distinctDevices");
            copyNumber(source, result, "pending_updates", "pendingUpdates");
            copyBoolean(source, result, "raw_samples_accepted", "rawSamplesAccepted");
            copyBoolean(source, result, "secure_aggregation", "secureAggregation");
            JsonElement completed = source.get("completed_rounds");
            result.put("completedRounds", completed != null && completed.isJsonArray() ? completed.getAsJsonArray().size() : 0);
            return result;
        } catch (Exception ignored) {
            return result;
        } finally {
            if (connection != null) connection.disconnect();
        }
    }

    private static String readBounded(HttpURLConnection connection) throws Exception {
        StringBuilder value = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(connection.getInputStream(), StandardCharsets.UTF_8))) {
            char[] buffer = new char[2048];
            int read;
            while ((read = reader.read(buffer)) != -1) {
                if (value.length() + read > MAX_RESPONSE_CHARS) throw new IllegalStateException("response_too_large");
                value.append(buffer, 0, read);
            }
        }
        return value.toString();
    }

    private static void copyString(JsonObject source, Map<String, Object> target, String sourceName, String targetName) {
        JsonElement value = source.get(sourceName);
        if (value != null && value.isJsonPrimitive()) target.put(targetName, value.getAsString());
    }

    private static void copyNumber(JsonObject source, Map<String, Object> target, String sourceName, String targetName) {
        JsonElement value = source.get(sourceName);
        if (value != null && value.isJsonPrimitive() && value.getAsJsonPrimitive().isNumber()) target.put(targetName, value.getAsInt());
    }

    private static void copyBoolean(JsonObject source, Map<String, Object> target, String sourceName, String targetName) {
        JsonElement value = source.get(sourceName);
        if (value != null && value.isJsonPrimitive() && value.getAsJsonPrimitive().isBoolean()) target.put(targetName, value.getAsBoolean());
    }

    private static String normalize(String value) {
        if (isBlank(value)) return null;
        String normalized = value.trim();
        return normalized.endsWith("/status") ? normalized : normalized.replaceAll("/+$", "") + "/status";
    }

    private static boolean isBlank(String value) {
        return value == null || value.trim().isEmpty();
    }
}
