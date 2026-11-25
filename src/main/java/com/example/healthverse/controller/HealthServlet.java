package com.example.healthverse.controller;

import com.example.healthverse.config.AgentConfig;
import com.google.gson.Gson;

import javax.servlet.annotation.WebServlet;
import javax.servlet.http.HttpServlet;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.LinkedHashMap;
import java.util.Map;

@WebServlet(name = "HealthServlet", urlPatterns = "/api/health")
public class HealthServlet extends HttpServlet {
    private static final Gson GSON = new Gson();

    @Override
    protected void doGet(HttpServletRequest request, HttpServletResponse response) throws IOException {
        AgentConfig config = AgentConfig.load();
        Map<String, Object> status = new LinkedHashMap<String, Object>();
        status.put("ok", true);
        status.put("agentConfigured", config.isRemoteReady());
        status.put("provider", config.isRemoteReady() ? config.getProvider() : "local-rule");
        status.put("safetyMode", "non-diagnostic-human-confirmation");

        response.setCharacterEncoding("UTF-8");
        response.setContentType("application/json;charset=UTF-8");
        response.setHeader("Cache-Control", "no-store");
        response.getWriter().write(GSON.toJson(status));
    }
}
