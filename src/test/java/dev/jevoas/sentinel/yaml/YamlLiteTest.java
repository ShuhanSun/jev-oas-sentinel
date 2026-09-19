package dev.jevoas.sentinel.yaml;

import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class YamlLiteTest {
    @Test
    void parsesOpenApiShapedYaml() {
        Object parsed = YamlLite.parse("""
                openapi: 3.0.3
                paths:
                  /orders:
                    get:
                      description: |
                        First line.
                        Second line.
                      parameters:
                        - name: status
                          in: query
                          required: false
                """);

        Map<?, ?> root = (Map<?, ?>) parsed;
        Map<?, ?> paths = (Map<?, ?>) root.get("paths");
        Map<?, ?> path = (Map<?, ?>) paths.get("/orders");
        Map<?, ?> get = (Map<?, ?>) path.get("get");
        List<?> parameters = (List<?>) get.get("parameters");
        Map<?, ?> parameter = (Map<?, ?>) parameters.get(0);

        assertEquals("First line.\nSecond line.", get.get("description"));
        assertEquals(Boolean.FALSE, parameter.get("required"));
    }

    @Test
    void rejectsAnchors() {
        IllegalArgumentException exception = assertThrows(
                IllegalArgumentException.class,
                () -> YamlLite.parse("value: &shared thing\n"));
        assertTrue(exception.getMessage().contains("anchors"));
    }
}

