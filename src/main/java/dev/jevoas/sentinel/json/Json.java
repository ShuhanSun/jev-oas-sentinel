package dev.jevoas.sentinel.json;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Minimal JSON reader/writer used to keep the runtime dependency-free. */
public final class Json {
    private Json() {
    }

    public static Object parse(String input) {
        Parser parser = new Parser(input);
        Object value = parser.parseValue();
        parser.skipWhitespace();
        if (!parser.atEnd()) {
            throw parser.error("Unexpected trailing content");
        }
        return value;
    }

    public static String write(Object value) {
        StringBuilder output = new StringBuilder();
        writeValue(value, output, 0, false);
        return output.toString();
    }

    public static String writePretty(Object value) {
        StringBuilder output = new StringBuilder();
        writeValue(value, output, 0, true);
        output.append('\n');
        return output.toString();
    }

    private static void writeValue(Object value, StringBuilder output, int depth, boolean pretty) {
        if (value == null) {
            output.append("null");
        } else if (value instanceof String string) {
            writeString(string, output);
        } else if (value instanceof Boolean || value instanceof Number) {
            output.append(value);
        } else if (value instanceof Map<?, ?> map) {
            writeObject(map, output, depth, pretty);
        } else if (value instanceof Collection<?> collection) {
            writeArray(collection, output, depth, pretty);
        } else if (value.getClass().isArray()) {
            List<Object> values = new ArrayList<>();
            int length = java.lang.reflect.Array.getLength(value);
            for (int index = 0; index < length; index++) {
                values.add(java.lang.reflect.Array.get(value, index));
            }
            writeArray(values, output, depth, pretty);
        } else {
            throw new IllegalArgumentException("Unsupported JSON value type: " + value.getClass().getName());
        }
    }

    private static void writeObject(Map<?, ?> map, StringBuilder output, int depth, boolean pretty) {
        output.append('{');
        if (!map.isEmpty()) {
            int index = 0;
            for (Map.Entry<?, ?> entry : map.entrySet()) {
                if (!(entry.getKey() instanceof String key)) {
                    throw new IllegalArgumentException("JSON object keys must be strings");
                }
                if (index++ > 0) {
                    output.append(',');
                }
                newlineAndIndent(output, depth + 1, pretty);
                writeString(key, output);
                output.append(pretty ? ": " : ":");
                writeValue(entry.getValue(), output, depth + 1, pretty);
            }
            newlineAndIndent(output, depth, pretty);
        }
        output.append('}');
    }

    private static void writeArray(Collection<?> collection, StringBuilder output, int depth, boolean pretty) {
        output.append('[');
        if (!collection.isEmpty()) {
            int index = 0;
            for (Object item : collection) {
                if (index++ > 0) {
                    output.append(',');
                }
                newlineAndIndent(output, depth + 1, pretty);
                writeValue(item, output, depth + 1, pretty);
            }
            newlineAndIndent(output, depth, pretty);
        }
        output.append(']');
    }

    private static void newlineAndIndent(StringBuilder output, int depth, boolean pretty) {
        if (!pretty) {
            return;
        }
        output.append('\n');
        output.append("  ".repeat(depth));
    }

    private static void writeString(String value, StringBuilder output) {
        output.append('"');
        for (int index = 0; index < value.length(); index++) {
            char character = value.charAt(index);
            switch (character) {
                case '"' -> output.append("\\\"");
                case '\\' -> output.append("\\\\");
                case '\b' -> output.append("\\b");
                case '\f' -> output.append("\\f");
                case '\n' -> output.append("\\n");
                case '\r' -> output.append("\\r");
                case '\t' -> output.append("\\t");
                default -> {
                    if (character < 0x20) {
                        output.append(String.format("\\u%04x", (int) character));
                    } else {
                        output.append(character);
                    }
                }
            }
        }
        output.append('"');
    }

    private static final class Parser {
        private final String input;
        private int position;

        private Parser(String input) {
            this.input = input;
        }

        private Object parseValue() {
            skipWhitespace();
            if (atEnd()) {
                throw error("Expected a JSON value");
            }
            return switch (input.charAt(position)) {
                case '{' -> parseObject();
                case '[' -> parseArray();
                case '"' -> parseString();
                case 't' -> parseLiteral("true", Boolean.TRUE);
                case 'f' -> parseLiteral("false", Boolean.FALSE);
                case 'n' -> parseLiteral("null", null);
                default -> parseNumber();
            };
        }

        private Map<String, Object> parseObject() {
            expect('{');
            LinkedHashMap<String, Object> result = new LinkedHashMap<>();
            skipWhitespace();
            if (consume('}')) {
                return result;
            }
            while (true) {
                skipWhitespace();
                if (atEnd() || input.charAt(position) != '"') {
                    throw error("Expected a quoted object key");
                }
                String key = parseString();
                skipWhitespace();
                expect(':');
                result.put(key, parseValue());
                skipWhitespace();
                if (consume('}')) {
                    return result;
                }
                expect(',');
            }
        }

        private List<Object> parseArray() {
            expect('[');
            List<Object> result = new ArrayList<>();
            skipWhitespace();
            if (consume(']')) {
                return result;
            }
            while (true) {
                result.add(parseValue());
                skipWhitespace();
                if (consume(']')) {
                    return result;
                }
                expect(',');
            }
        }

        private String parseString() {
            expect('"');
            StringBuilder result = new StringBuilder();
            while (!atEnd()) {
                char character = input.charAt(position++);
                if (character == '"') {
                    return result.toString();
                }
                if (character != '\\') {
                    result.append(character);
                    continue;
                }
                if (atEnd()) {
                    throw error("Unterminated escape sequence");
                }
                char escaped = input.charAt(position++);
                switch (escaped) {
                    case '"', '\\', '/' -> result.append(escaped);
                    case 'b' -> result.append('\b');
                    case 'f' -> result.append('\f');
                    case 'n' -> result.append('\n');
                    case 'r' -> result.append('\r');
                    case 't' -> result.append('\t');
                    case 'u' -> result.append(parseUnicode());
                    default -> throw error("Unknown escape sequence: \\" + escaped);
                }
            }
            throw error("Unterminated string");
        }

        private char parseUnicode() {
            if (position + 4 > input.length()) {
                throw error("Incomplete unicode escape");
            }
            String hex = input.substring(position, position + 4);
            position += 4;
            try {
                return (char) Integer.parseInt(hex, 16);
            } catch (NumberFormatException exception) {
                throw error("Invalid unicode escape: " + hex);
            }
        }

        private Object parseNumber() {
            int start = position;
            if (consume('-')) {
                // optional sign
            }
            consumeDigits();
            if (consume('.')) {
                consumeDigits();
            }
            if (consume('e') || consume('E')) {
                if (!consume('+')) {
                    consume('-');
                }
                consumeDigits();
            }
            if (start == position) {
                throw error("Expected a JSON value");
            }
            String number = input.substring(start, position);
            try {
                BigDecimal decimal = new BigDecimal(number);
                if (number.indexOf('.') < 0 && number.indexOf('e') < 0 && number.indexOf('E') < 0) {
                    try {
                        return decimal.longValueExact();
                    } catch (ArithmeticException ignored) {
                        return decimal;
                    }
                }
                return decimal;
            } catch (NumberFormatException exception) {
                throw error("Invalid number: " + number);
            }
        }

        private void consumeDigits() {
            int start = position;
            while (!atEnd() && Character.isDigit(input.charAt(position))) {
                position++;
            }
            if (start == position) {
                throw error("Expected a digit");
            }
        }

        private Object parseLiteral(String literal, Object value) {
            if (!input.startsWith(literal, position)) {
                throw error("Expected " + literal);
            }
            position += literal.length();
            return value;
        }

        private boolean consume(char expected) {
            if (!atEnd() && input.charAt(position) == expected) {
                position++;
                return true;
            }
            return false;
        }

        private void expect(char expected) {
            if (!consume(expected)) {
                throw error("Expected '" + expected + "'");
            }
        }

        private void skipWhitespace() {
            while (!atEnd() && Character.isWhitespace(input.charAt(position))) {
                position++;
            }
        }

        private boolean atEnd() {
            return position >= input.length();
        }

        private IllegalArgumentException error(String message) {
            return new IllegalArgumentException(message + " at character " + position);
        }
    }
}

