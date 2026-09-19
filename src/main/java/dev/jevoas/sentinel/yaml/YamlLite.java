package dev.jevoas.sentinel.yaml;

import dev.jevoas.sentinel.json.Json;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * A deliberately small YAML reader for conventional OpenAPI documents.
 * Unsupported YAML features fail loudly instead of being guessed.
 */
public final class YamlLite {
    private YamlLite() {
    }

    public static Object parse(String input) {
        Parser parser = new Parser(input);
        return parser.parse();
    }

    private record Line(int number, int indent, String content, String raw) {
    }

    private static final class Parser {
        private final List<Line> lines;
        private int index;

        private Parser(String input) {
            this.lines = tokenize(input);
        }

        private Object parse() {
            if (lines.isEmpty()) {
                return new LinkedHashMap<String, Object>();
            }
            Object result = parseNode(lines.get(0).indent());
            if (index != lines.size()) {
                throw error(lines.get(index), "Unexpected indentation");
            }
            return result;
        }

        private Object parseNode(int indent) {
            Line line = current();
            if (line.indent() != indent) {
                throw error(line, "Expected indentation " + indent + " but found " + line.indent());
            }
            if (line.content().startsWith("-")) {
                return parseSequence(indent);
            }
            return parseMapping(indent);
        }

        private Map<String, Object> parseMapping(int indent) {
            LinkedHashMap<String, Object> result = new LinkedHashMap<>();
            while (index < lines.size()) {
                Line line = current();
                if (line.indent() < indent) {
                    break;
                }
                if (line.indent() > indent) {
                    throw error(line, "Unexpected nested value");
                }
                if (line.content().startsWith("-")) {
                    break;
                }
                KeyValue pair = splitKeyValue(line.content(), line);
                rejectUnsupported(pair.key(), pair.value(), line);
                index++;
                Object value = readValue(pair.value(), indent, line);
                if (result.put(pair.key(), value) != null) {
                    throw error(line, "Duplicate key: " + pair.key());
                }
            }
            return result;
        }

        private List<Object> parseSequence(int indent) {
            List<Object> result = new ArrayList<>();
            while (index < lines.size()) {
                Line line = current();
                if (line.indent() != indent || !line.content().startsWith("-")) {
                    break;
                }
                String item = line.content().substring(1).stripLeading();
                index++;
                if (item.isEmpty()) {
                    result.add(hasNested(indent) ? parseNode(current().indent()) : null);
                    continue;
                }

                int colon = findMappingColon(item);
                if (colon < 0) {
                    result.add(parseScalar(item, line));
                    if (hasNested(indent)) {
                        throw error(current(), "A scalar sequence item cannot have nested fields");
                    }
                    continue;
                }

                LinkedHashMap<String, Object> mapItem = new LinkedHashMap<>();
                String key = parseKey(item.substring(0, colon).strip(), line);
                String rawValue = item.substring(colon + 1).strip();
                rejectUnsupported(key, rawValue, line);
                Object firstValue = readValue(rawValue, indent, line);
                mapItem.put(key, firstValue);

                if (hasNested(indent)) {
                    int continuationIndent = current().indent();
                    Object continuation = parseNode(continuationIndent);
                    if (!(continuation instanceof Map<?, ?> continuationMap)) {
                        throw error(line, "A mapping sequence item must continue with mapping fields");
                    }
                    for (Map.Entry<?, ?> entry : continuationMap.entrySet()) {
                        String continuationKey = (String) entry.getKey();
                        if (mapItem.put(continuationKey, entry.getValue()) != null) {
                            throw error(line, "Duplicate key: " + continuationKey);
                        }
                    }
                }
                result.add(mapItem);
            }
            return result;
        }

        private Object readValue(String rawValue, int parentIndent, Line source) {
            if (rawValue.isEmpty()) {
                return hasNested(parentIndent) ? parseNode(current().indent()) : new LinkedHashMap<String, Object>();
            }
            if (isBlockMarker(rawValue)) {
                return parseBlockScalar(parentIndent, rawValue.charAt(0));
            }
            return parseScalar(rawValue, source);
        }

        private String parseBlockScalar(int parentIndent, char style) {
            if (!hasNested(parentIndent)) {
                return "";
            }
            int contentIndent = current().indent();
            StringBuilder result = new StringBuilder();
            while (index < lines.size() && current().indent() > parentIndent) {
                Line line = current();
                if (line.indent() < contentIndent) {
                    break;
                }
                if (result.length() > 0) {
                    result.append(style == '>' ? ' ' : '\n');
                }
                int offset = Math.min(line.raw().length(), contentIndent);
                result.append(line.raw().substring(offset));
                index++;
            }
            return result.toString();
        }

        private Object parseScalar(String raw, Line line) {
            String value = stripInlineComment(raw).strip();
            if (value.isEmpty()) {
                return "";
            }
            if ((value.startsWith("{") && value.endsWith("}"))
                    || (value.startsWith("[") && value.endsWith("]"))) {
                return Json.parse(normalizeInlineYaml(value, line));
            }
            if (value.startsWith("\"") || value.startsWith("'")) {
                return parseQuoted(value, line);
            }
            return switch (value.toLowerCase()) {
                case "null", "~" -> null;
                case "true" -> Boolean.TRUE;
                case "false" -> Boolean.FALSE;
                default -> parsePlainScalar(value);
            };
        }

        private Object parsePlainScalar(String value) {
            if (value.matches("[-+]?[0-9]+")) {
                try {
                    return Long.parseLong(value);
                } catch (NumberFormatException ignored) {
                    return new BigDecimal(value);
                }
            }
            if (value.matches("[-+]?(?:[0-9]+\\.[0-9]*|[0-9]*\\.[0-9]+)(?:[eE][-+]?[0-9]+)?")) {
                return new BigDecimal(value);
            }
            return value;
        }

        private String parseQuoted(String value, Line line) {
            char quote = value.charAt(0);
            if (value.length() < 2 || value.charAt(value.length() - 1) != quote) {
                throw error(line, "Unterminated quoted scalar");
            }
            String body = value.substring(1, value.length() - 1);
            if (quote == '\'') {
                return body.replace("''", "'");
            }
            Object parsed = Json.parse(value);
            return (String) parsed;
        }

        private String normalizeInlineYaml(String value, Line line) {
            // JSON syntax is a valid YAML subset. Keep the implementation honest by requiring it here.
            if (value.indexOf('\'') >= 0) {
                throw error(line, "Inline collections must use JSON double quotes");
            }
            return value;
        }

        private boolean hasNested(int parentIndent) {
            return index < lines.size() && current().indent() > parentIndent;
        }

        private Line current() {
            return lines.get(index);
        }

        private static List<Line> tokenize(String input) {
            List<Line> result = new ArrayList<>();
            String[] rawLines = input.replace("\r\n", "\n").replace('\r', '\n').split("\n", -1);
            for (int lineIndex = 0; lineIndex < rawLines.length; lineIndex++) {
                String raw = rawLines[lineIndex];
                if (raw.indexOf('\t') >= 0) {
                    throw new IllegalArgumentException("YAML tabs are not supported at line " + (lineIndex + 1));
                }
                int indent = 0;
                while (indent < raw.length() && raw.charAt(indent) == ' ') {
                    indent++;
                }
                String content = raw.substring(indent);
                if (content.isBlank() || content.stripLeading().startsWith("#")) {
                    continue;
                }
                result.add(new Line(lineIndex + 1, indent, content, raw));
            }
            return result;
        }

        private static KeyValue splitKeyValue(String content, Line line) {
            int colon = findMappingColon(content);
            if (colon < 0) {
                throw error(line, "Expected a mapping entry");
            }
            String key = parseKey(content.substring(0, colon).strip(), line);
            String value = content.substring(colon + 1).strip();
            return new KeyValue(key, value);
        }

        private static String parseKey(String raw, Line line) {
            if (raw.isEmpty()) {
                throw error(line, "Mapping key cannot be empty");
            }
            if ((raw.startsWith("\"") && raw.endsWith("\""))
                    || (raw.startsWith("'") && raw.endsWith("'"))) {
                return new Parser("").parseQuoted(raw, line);
            }
            return raw;
        }

        private static int findMappingColon(String text) {
            boolean singleQuoted = false;
            boolean doubleQuoted = false;
            int squareDepth = 0;
            int braceDepth = 0;
            for (int position = 0; position < text.length(); position++) {
                char character = text.charAt(position);
                if (character == '\'' && !doubleQuoted) {
                    singleQuoted = !singleQuoted;
                } else if (character == '"' && !singleQuoted
                        && (position == 0 || text.charAt(position - 1) != '\\')) {
                    doubleQuoted = !doubleQuoted;
                } else if (!singleQuoted && !doubleQuoted) {
                    if (character == '[') {
                        squareDepth++;
                    } else if (character == ']') {
                        squareDepth--;
                    } else if (character == '{') {
                        braceDepth++;
                    } else if (character == '}') {
                        braceDepth--;
                    } else if (character == ':' && squareDepth == 0 && braceDepth == 0
                            && (position + 1 == text.length() || Character.isWhitespace(text.charAt(position + 1)))) {
                        return position;
                    }
                }
            }
            return -1;
        }

        private static String stripInlineComment(String text) {
            boolean singleQuoted = false;
            boolean doubleQuoted = false;
            for (int position = 0; position < text.length(); position++) {
                char character = text.charAt(position);
                if (character == '\'' && !doubleQuoted) {
                    singleQuoted = !singleQuoted;
                } else if (character == '"' && !singleQuoted
                        && (position == 0 || text.charAt(position - 1) != '\\')) {
                    doubleQuoted = !doubleQuoted;
                } else if (character == '#' && !singleQuoted && !doubleQuoted
                        && (position == 0 || Character.isWhitespace(text.charAt(position - 1)))) {
                    return text.substring(0, position);
                }
            }
            return text;
        }

        private static boolean isBlockMarker(String value) {
            return value.matches("[|>][-+]?([1-9])?");
        }

        private static void rejectUnsupported(String key, String value, Line line) {
            if (key.equals("<<") || value.startsWith("&") || value.startsWith("*") || value.startsWith("!")) {
                throw error(line, "YAML anchors, aliases, merge keys, and custom tags are not supported");
            }
        }

        private static IllegalArgumentException error(Line line, String message) {
            return new IllegalArgumentException(message + " at YAML line " + line.number());
        }
    }

    private record KeyValue(String key, String value) {
    }
}

