package com.example.healthverse.service;

import com.example.healthverse.pojo.AgentRequest;
import com.example.healthverse.pojo.AgentResponse;
import org.junit.jupiter.api.Test;

import java.util.LinkedHashMap;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class AgentServiceEvidenceTest {
    @Test
    void localFallbackDoesNotInventUnobservedObjects() {
        AgentRequest request = new AgentRequest();
        request.setMessage("保留右侧手写区域并减少低头");
        Map<String, Object> context = new LinkedHashMap<String, Object>();
        context.put("objects", new String[]{"screen"});
        context.put("spatialRelations", new String[]{"屏幕在眼部下方，二维相对量"});
        context.put("boundary", "不能提供真实厘米、深度或诊断");
        request.setContext(context);

        AgentResponse response = AgentService.evidenceBoundLocalFallback(request, "test");
        assertTrue(response.isDegraded());
        assertTrue(response.getReply().contains("二维"));
        assertTrue(response.getReply().contains("不能给出真实厘米"));
        assertFalse(response.getReply().contains("水杯"));
        assertFalse(response.getReply().contains("左前方"));
    }

    @Test
    void localFallbackRequestsEvidenceWhenScreenWasNotObserved() {
        AgentRequest request = new AgentRequest();
        request.setMessage("右侧要用来写字");
        request.setContext(new LinkedHashMap<String, Object>());

        AgentResponse response = AgentService.evidenceBoundLocalFallback(request, "test");
        assertTrue(response.getReply().contains("没有可靠的屏幕或物体关系证据"));
        assertTrue(response.getReply().contains("不会自行假设物体位置"));
    }
}
