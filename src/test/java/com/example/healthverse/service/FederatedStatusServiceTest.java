package com.example.healthverse.service;

import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.Test;

import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class FederatedStatusServiceTest {
    @Test
    void reportsUnconfiguredWithoutInventingDeployment() {
        Map<String, Object> result = new FederatedStatusService(null).readStatus();
        assertEquals("not_configured", result.get("state"));
        assertFalse((Boolean) result.get("reachable"));
        assertFalse((Boolean) result.get("browserUploadsRawData"));
    }

    @Test
    void exposesOnlyCoordinatorStatusFields() throws Exception {
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/status", exchange -> {
            String json = "{\"round\":4,\"registered_clients\":2,\"distinct_device_fingerprints\":2," +
                    "\"pending_updates\":0,\"completed_rounds\":[{\"round\":3}]," +
                    "\"run_type\":\"multi_device_federated_run\",\"raw_samples_accepted\":false," +
                    "\"secure_aggregation\":false,\"secret\":\"must-not-leak\"}";
            byte[] body = json.getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().set("Content-Type", "application/json");
            exchange.sendResponseHeaders(200, body.length);
            exchange.getResponseBody().write(body);
            exchange.close();
        });
        server.start();
        try {
            Map<String, Object> result = new FederatedStatusService(
                    "http://127.0.0.1:" + server.getAddress().getPort()).readStatus();
            assertTrue((Boolean) result.get("reachable"));
            assertEquals("multi_device_federated_run", result.get("runType"));
            assertEquals(2, result.get("distinctDevices"));
            assertEquals(1, result.get("completedRounds"));
            assertFalse(result.containsKey("secret"));
        } finally {
            server.stop(0);
        }
    }
}
