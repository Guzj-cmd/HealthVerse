package com.example.healthverse.controller;

import com.example.healthverse.config.AgentConfig;
import com.example.healthverse.pojo.AgentRequest;
import com.example.healthverse.pojo.AgentResponse;
import com.example.healthverse.service.AgentService;
import com.google.gson.Gson;
import com.google.gson.JsonParseException;

import javax.servlet.ServletException;
import javax.servlet.annotation.WebServlet;
import javax.servlet.http.HttpServlet;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import java.io.BufferedReader;
import java.io.IOException;

@WebServlet(name = "AgentServlet", urlPatterns = "/api/agent")
public class AgentServlet extends HttpServlet {
    private static final Gson GSON = new Gson();
    private static final int MAX_BODY_CHARS = 32 * 1024;
    private transient AgentService agentService;

    @Override
    public void init() throws ServletException {
        agentService = new AgentService(AgentConfig.load());
    }

    @Override
    protected void doPost(HttpServletRequest request, HttpServletResponse response) throws IOException {
        prepare(response);
        if (request.getContentLengthLong() > MAX_BODY_CHARS) {
            writeError(response, HttpServletResponse.SC_REQUEST_ENTITY_TOO_LARGE, "request_too_large");
            return;
        }

        String body = readBody(request);
        if (body == null) {
            writeError(response, HttpServletResponse.SC_REQUEST_ENTITY_TOO_LARGE, "request_too_large");
            return;
        }

        try {
            AgentRequest input = GSON.fromJson(body, AgentRequest.class);
            if (input == null || input.getMessage() == null || input.getMessage().trim().isEmpty()) {
                writeError(response, HttpServletResponse.SC_BAD_REQUEST, "message_required");
                return;
            }
            if (input.getMessage().length() > 2000) {
                writeError(response, HttpServletResponse.SC_BAD_REQUEST, "message_too_long");
                return;
            }
            AgentResponse result = agentService.reply(input);
            response.setStatus(HttpServletResponse.SC_OK);
            response.getWriter().write(GSON.toJson(result));
        } catch (JsonParseException exception) {
            writeError(response, HttpServletResponse.SC_BAD_REQUEST, "invalid_json");
        }
    }

    private static String readBody(HttpServletRequest request) throws IOException {
        request.setCharacterEncoding("UTF-8");
        StringBuilder value = new StringBuilder();
        try (BufferedReader reader = request.getReader()) {
            char[] buffer = new char[2048];
            int read;
            while ((read = reader.read(buffer)) != -1) {
                if (value.length() + read > MAX_BODY_CHARS) {
                    return null;
                }
                value.append(buffer, 0, read);
            }
        }
        return value.toString();
    }

    private static void prepare(HttpServletResponse response) {
        response.setCharacterEncoding("UTF-8");
        response.setContentType("application/json;charset=UTF-8");
        response.setHeader("Cache-Control", "no-store");
        response.setHeader("X-Content-Type-Options", "nosniff");
    }

    private static void writeError(HttpServletResponse response, int status, String error) throws IOException {
        response.setStatus(status);
        response.getWriter().write("{\"error\":\"" + error + "\"}");
    }
}
