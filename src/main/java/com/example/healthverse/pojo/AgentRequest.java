package com.example.healthverse.pojo;

import java.util.Collections;
import java.util.Map;

public class AgentRequest {
    private String message;
    private Map<String, Object> context;

    public String getMessage() {
        return message;
    }

    public void setMessage(String message) {
        this.message = message;
    }

    public Map<String, Object> getContext() {
        return context == null ? Collections.<String, Object>emptyMap() : context;
    }

    public void setContext(Map<String, Object> context) {
        this.context = context;
    }
}
