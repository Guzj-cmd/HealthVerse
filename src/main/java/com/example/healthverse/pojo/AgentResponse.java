package com.example.healthverse.pojo;

public class AgentResponse {
    private final String title;
    private final String reply;
    private final String source;
    private final boolean degraded;

    public AgentResponse(String title, String reply, String source, boolean degraded) {
        this.title = title;
        this.reply = reply;
        this.source = source;
        this.degraded = degraded;
    }

    public String getTitle() {
        return title;
    }

    public String getReply() {
        return reply;
    }

    public String getSource() {
        return source;
    }

    public boolean isDegraded() {
        return degraded;
    }
}
