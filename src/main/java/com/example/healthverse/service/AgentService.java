package com.example.healthverse.service;

import com.example.healthverse.config.AgentConfig;
import com.example.healthverse.pojo.AgentRequest;
import com.example.healthverse.pojo.AgentResponse;
import com.google.gson.Gson;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.InetSocketAddress;
import java.net.Proxy;
import java.net.URI;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class AgentService {
    private static final Gson GSON = new Gson();
    private static final int CONNECT_TIMEOUT_MS = 8000;
    private static final int READ_TIMEOUT_MS = 25000;
    private static final String SYSTEM_PROMPT =
            "你是 HealthVerse 的空间健康协同 Agent。请结合用户任务、空间观察和明确限制给出克制、可执行、可撤销的建议。" +
            "你不是医生，不诊断疾病，不把短期姿态推断为长期健康结果。先说明依据，再给最多两个轻量建议；" +
            "信息不足时只提出一个求证问题。尊重用户纠正、拒绝和恢复原始布局的权利。" +
            "仅输出 JSON：{\"title\":\"不超过18字\",\"reply\":\"80到160字\"}。";

    private final AgentConfig config;

    public AgentService(AgentConfig config) {
        this.config = config;
    }

    public AgentResponse reply(AgentRequest request) {
        if (request == null || request.getMessage() == null || request.getMessage().trim().isEmpty()) {
            return new AgentResponse("请描述你的目标", "可以告诉我你希望保留的桌面区域、当前任务或不希望被打断的时机。", "local-rule", true);
        }

        if (!config.isRemoteReady()) {
            return localFallback(request, "remote_not_configured");
        }

        try {
            return config.isAnthropic() ? callAnthropic(request) : callOpenAiCompatible(request);
        } catch (Exception ignored) {
            // Never expose gateway messages, private URLs, or credentials to the browser.
            return localFallback(request, "remote_unavailable");
        }
    }

    private AgentResponse callAnthropic(AgentRequest request) throws Exception {
        Map<String, Object> body = new HashMap<String, Object>();
        body.put("model", config.getModel());
        body.put("max_tokens", 420);
        body.put("temperature", 0.2);
        body.put("system", SYSTEM_PROMPT);

        List<Map<String, Object>> messages = new ArrayList<Map<String, Object>>();
        Map<String, Object> user = new HashMap<String, Object>();
        user.put("role", "user");
        user.put("content", buildUserContent(request));
        messages.add(user);
        body.put("messages", messages);

        Map<String, String> headers = new HashMap<String, String>();
        headers.put("anthropic-version", "2023-06-01");
        headers.put("x-api-key", config.getApiKey());
        headers.put("Authorization", "Bearer " + config.getApiKey());

        JsonObject response = postJson(config.getApiUrl(), headers, body);
        JsonArray content = response.getAsJsonArray("content");
        if (content == null) {
            throw new IllegalStateException("Missing Agent content");
        }
        StringBuilder text = new StringBuilder();
        for (JsonElement item : content) {
            if (item.isJsonObject() && "text".equals(string(item.getAsJsonObject(), "type"))) {
                text.append(string(item.getAsJsonObject(), "text"));
            }
        }
        return parseModelResponse(text.toString());
    }

    private AgentResponse callOpenAiCompatible(AgentRequest request) throws Exception {
        Map<String, Object> body = new HashMap<String, Object>();
        body.put("model", config.getModel());
        body.put("max_tokens", 420);
        body.put("temperature", 0.2);

        List<Map<String, String>> messages = new ArrayList<Map<String, String>>();
        messages.add(message("system", SYSTEM_PROMPT));
        messages.add(message("user", buildUserContent(request)));
        body.put("messages", messages);

        Map<String, String> headers = new HashMap<String, String>();
        headers.put("Authorization", "Bearer " + config.getApiKey());

        JsonObject response = postJson(config.getApiUrl(), headers, body);
        JsonArray choices = response.getAsJsonArray("choices");
        if (choices == null || choices.size() == 0) {
            throw new IllegalStateException("Missing Agent choices");
        }
        JsonObject message = choices.get(0).getAsJsonObject().getAsJsonObject("message");
        return parseModelResponse(string(message, "content"));
    }

    private JsonObject postJson(String endpoint, Map<String, String> headers, Object body) throws Exception {
        URL target = new URL(endpoint);
        HttpURLConnection connection;
        // The local Satori sidecar must never be sent through the model gateway proxy.
        // This also keeps the bridge usable when ~/.claude/settings.json defines HTTPS_PROXY.
        if (config.getProxyUrl() != null && !config.getProxyUrl().trim().isEmpty() && !isLoopback(target.getHost())) {
            URI proxyUri = URI.create(config.getProxyUrl().trim());
            int proxyPort = proxyUri.getPort();
            if (proxyPort < 0) {
                proxyPort = "https".equalsIgnoreCase(proxyUri.getScheme()) ? 443 : 80;
            }
            Proxy proxy = new Proxy(Proxy.Type.HTTP, new InetSocketAddress(proxyUri.getHost(), proxyPort));
            connection = (HttpURLConnection) target.openConnection(proxy);
        } else {
            connection = (HttpURLConnection) target.openConnection();
        }
        try {
            connection.setRequestMethod("POST");
            connection.setConnectTimeout(CONNECT_TIMEOUT_MS);
            connection.setReadTimeout(READ_TIMEOUT_MS);
            connection.setDoOutput(true);
            connection.setRequestProperty("Content-Type", "application/json; charset=UTF-8");
            connection.setRequestProperty("Accept", "application/json");
            for (Map.Entry<String, String> header : headers.entrySet()) {
                connection.setRequestProperty(header.getKey(), header.getValue());
            }

            byte[] payload = GSON.toJson(body).getBytes(StandardCharsets.UTF_8);
            try (OutputStream output = connection.getOutputStream()) {
                output.write(payload);
            }

            int status = connection.getResponseCode();
            InputStream stream = status >= 200 && status < 300 ? connection.getInputStream() : connection.getErrorStream();
            String text = readLimited(stream, 256 * 1024);
            if (status < 200 || status >= 300) {
                throw new IllegalStateException("Agent gateway returned HTTP " + status);
            }
            JsonElement parsed = JsonParser.parseString(text);
            if (!parsed.isJsonObject()) {
                throw new IllegalStateException("Unexpected Agent response");
            }
            return parsed.getAsJsonObject();
        } finally {
            connection.disconnect();
        }
    }

    private static boolean isLoopback(String host) {
        if (host == null) {
            return false;
        }
        String normalized = host.trim().toLowerCase();
        return "localhost".equals(normalized)
                || "127.0.0.1".equals(normalized)
                || "::1".equals(normalized)
                || "0:0:0:0:0:0:0:1".equals(normalized);
    }

    private AgentResponse parseModelResponse(String text) {
        if (text == null) {
            throw new IllegalStateException("Empty Agent response");
        }
        String cleaned = text.trim();
        if (cleaned.startsWith("```")) {
            cleaned = cleaned.replaceFirst("^```(?:json)?\\s*", "").replaceFirst("\\s*```$", "");
        }
        try {
            JsonObject object = JsonParser.parseString(cleaned).getAsJsonObject();
            String title = shorten(string(object, "title"), 40);
            String reply = shorten(string(object, "reply"), 800);
            if (title == null || reply == null) {
                throw new IllegalStateException("Incomplete Agent JSON");
            }
            return new AgentResponse(title, reply, "remote-agent", false);
        } catch (RuntimeException exception) {
            return new AgentResponse("Agent 已更新推理", shorten(cleaned, 800), "remote-agent", false);
        }
    }

    private AgentResponse localFallback(AgentRequest request, String reason) {
        String message = request.getMessage().trim();
        String title = "已把你的限制加入方案";
        String reply;
        if (containsAny(message, "右侧", "手写", "写字")) {
            reply = "依据：你明确要求保留右侧手写区域。可以先只抬高显示器，并保持键盘与书写区不变；若需要移动水杯，优先放到左前方的舒适可达区。两种调整都应先预览，再由你决定是否执行。";
        } else if (containsAny(message, "不提醒", "打断", "专注")) {
            reply = "已记录你当前更重视任务连续性。Agent 会在自然停顿时再提示，并保留“立即静默”和“本次不再提醒”。这只是会话级偏好，不会在未确认时写入长期记忆。";
        } else {
            reply = "已将“" + shorten(message, 80) + "”作为本次任务约束。建议先比较一个轻量调整和一个保持原布局的对照方案；完成短时体验后，再由你确认是否保存为个人偏好。";
        }
        return new AgentResponse(title, reply, "local-rule:" + reason, true);
    }

    private String buildUserContent(AgentRequest request) {
        StringBuilder content = new StringBuilder();
        content.append("用户输入：").append(shorten(request.getMessage().trim(), 2000));
        content.append("\n当前界面上下文：").append(GSON.toJson(request.getContext()));
        JsonObject bdiPlan = callSatoriBridge(request);
        if (bdiPlan != null) {
            content.append("\nSatori 风格 BDI 规划结果：").append(GSON.toJson(bdiPlan));
        }
        return content.toString();
    }

    private JsonObject callSatoriBridge(AgentRequest request) {
        String bridgeUrl = config.getSatoriBridgeUrl();
        if (bridgeUrl == null || bridgeUrl.trim().isEmpty()) {
            return null;
        }
        try {
            Map<String, Object> body = new HashMap<String, Object>();
            body.put("message", shorten(request.getMessage().trim(), 2000));
            body.put("context", request.getContext());
            return postJson(bridgeUrl.trim(), new HashMap<String, String>(), body);
        } catch (Exception ignored) {
            // The paper-code bridge is optional; the primary Agent remains available.
            return null;
        }
    }

    private static Map<String, String> message(String role, String content) {
        Map<String, String> message = new HashMap<String, String>();
        message.put("role", role);
        message.put("content", content);
        return message;
    }

    private static String readLimited(InputStream stream, int maxBytes) throws Exception {
        if (stream == null) {
            return "";
        }
        StringBuilder result = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(stream, StandardCharsets.UTF_8))) {
            char[] buffer = new char[4096];
            int read;
            while ((read = reader.read(buffer)) != -1 && result.length() < maxBytes) {
                result.append(buffer, 0, Math.min(read, maxBytes - result.length()));
            }
        }
        return result.toString();
    }

    private static String string(JsonObject object, String key) {
        if (object == null) {
            return null;
        }
        JsonElement value = object.get(key);
        return value == null || value.isJsonNull() ? null : value.getAsString();
    }

    private static String shorten(String value, int max) {
        if (value == null) {
            return null;
        }
        String trimmed = value.trim();
        return trimmed.length() <= max ? trimmed : trimmed.substring(0, max) + "…";
    }

    private static boolean containsAny(String value, String... candidates) {
        for (String candidate : candidates) {
            if (value.contains(candidate)) {
                return true;
            }
        }
        return false;
    }

    public AgentConfig getConfig() {
        return config;
    }
}
