package dev.jevoas.sentinel.json;

import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class JsonTest {
    @Test
    void roundTripsNestedValues() {
        Map<String, Object> input = Map.of(
                "text", "line one\nline two",
                "number", new BigDecimal("0.91"),
                "items", List.of(true, 4L, "value"));

        Object parsed = Json.parse(Json.write(input));

        assertEquals(input, parsed);
    }

    @Test
    void rejectsTrailingContent() {
        assertThrows(IllegalArgumentException.class, () -> Json.parse("{} trailing"));
    }
}

