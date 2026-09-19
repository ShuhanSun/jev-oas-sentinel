package dev.jevoas.sentinel.openapi;

import dev.jevoas.sentinel.json.Json;
import dev.jevoas.sentinel.yaml.YamlLite;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.Map;

public final class OpenApiSpecLoader {
    public Map<String, Object> load(Path path) throws IOException {
        String content = Files.readString(path);
        String stripped = content.stripLeading();
        Object parsed = stripped.startsWith("{") || stripped.startsWith("[")
                ? Json.parse(content)
                : YamlLite.parse(content);
        if (!(parsed instanceof Map<?, ?> root)) {
            throw new IllegalArgumentException("OpenAPI document must be a top-level object: " + path);
        }
        Map<String, Object> document = stringMap(root, "OpenAPI document");
        Object version = document.get("openapi");
        if (!(version instanceof String) || !document.containsKey("paths")) {
            throw new IllegalArgumentException("Missing required OpenAPI fields 'openapi' or 'paths': " + path);
        }
        return document;
    }

    public static Map<String, Object> stringMap(Object value, String context) {
        if (!(value instanceof Map<?, ?> source)) {
            throw new IllegalArgumentException(context + " must be an object");
        }
        LinkedHashMap<String, Object> result = new LinkedHashMap<>();
        for (Map.Entry<?, ?> entry : source.entrySet()) {
            if (!(entry.getKey() instanceof String key)) {
                throw new IllegalArgumentException(context + " contains a non-string key");
            }
            result.put(key, entry.getValue());
        }
        return result;
    }
}

