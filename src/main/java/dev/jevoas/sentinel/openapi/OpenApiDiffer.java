package dev.jevoas.sentinel.openapi;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.Set;

public final class OpenApiDiffer {
    private static final Set<String> HTTP_METHODS = Set.of(
            "get", "put", "post", "delete", "options", "head", "patch", "trace", "query");
    private static final Set<String> DOCUMENTATION_KEYS = Set.of(
            "summary", "description", "example", "examples", "externalDocs", "title");

    public List<OperationChange> compare(Map<String, Object> base, Map<String, Object> head) {
        Map<String, Map<String, Object>> oldOperations = operations(base);
        Map<String, Map<String, Object>> newOperations = operations(head);
        LinkedHashSet<String> operationNames = new LinkedHashSet<>();
        operationNames.addAll(oldOperations.keySet());
        operationNames.addAll(newOperations.keySet());

        List<OperationChange> changes = new ArrayList<>();
        for (String operationName : operationNames) {
            Map<String, Object> oldOperation = oldOperations.get(operationName);
            Map<String, Object> newOperation = newOperations.get(operationName);
            if (oldOperation == null) {
                changes.add(new OperationChange(
                        operationName,
                        Map.of(),
                        newOperation,
                        List.of(new StructuralIssue(
                                "operation-added", Severity.NOTICE, operationName, "Operation was added")),
                        false,
                        true,
                        false));
                continue;
            }
            if (newOperation == null) {
                changes.add(new OperationChange(
                        operationName,
                        oldOperation,
                        Map.of(),
                        List.of(new StructuralIssue(
                                "operation-removed", Severity.BLOCK, operationName, "Operation was removed")),
                        false,
                        false,
                        true));
                continue;
            }
            if (Objects.equals(oldOperation, newOperation)) {
                continue;
            }

            List<StructuralIssue> issues = compareStructure(operationName, oldOperation, newOperation);
            boolean semanticChanged = !Objects.equals(documentationView(oldOperation), documentationView(newOperation));
            if (!semanticChanged && issues.isEmpty()) {
                continue;
            }
            changes.add(new OperationChange(
                    operationName, oldOperation, newOperation, List.copyOf(issues), semanticChanged, false, false));
        }
        return List.copyOf(changes);
    }

    private List<StructuralIssue> compareStructure(
            String operation,
            Map<String, Object> oldOperation,
            Map<String, Object> newOperation) {
        List<StructuralIssue> issues = new ArrayList<>();
        compareParameters(operation, oldOperation, newOperation, issues);
        compareRequestBody(operation, oldOperation, newOperation, issues);
        compareResponses(operation, oldOperation, newOperation, issues);

        if (!Objects.equals(oldOperation.get("security"), newOperation.get("security"))) {
            issues.add(new StructuralIssue(
                    "security-requirements-changed",
                    Severity.REVIEW,
                    operation,
                    "Security requirements changed; verify existing credentials and scopes remain valid"));
        }

        Object oldWithoutDocs = removeDocumentation(oldOperation);
        Object newWithoutDocs = removeDocumentation(newOperation);
        if (!Objects.equals(oldWithoutDocs, newWithoutDocs) && issues.isEmpty()) {
            issues.add(new StructuralIssue(
                    "structural-change-unclassified",
                    Severity.REVIEW,
                    operation,
                    "Non-documentation contract structure changed and requires compatibility review"));
        }
        return issues;
    }

    private void compareParameters(
            String operation,
            Map<String, Object> oldOperation,
            Map<String, Object> newOperation,
            List<StructuralIssue> issues) {
        Map<String, Map<String, Object>> oldParameters = parameters(oldOperation.get("parameters"));
        Map<String, Map<String, Object>> newParameters = parameters(newOperation.get("parameters"));
        for (Map.Entry<String, Map<String, Object>> entry : oldParameters.entrySet()) {
            Map<String, Object> updated = newParameters.get(entry.getKey());
            if (updated == null) {
                issues.add(new StructuralIssue(
                        "parameter-removed", Severity.BLOCK, operation, "Parameter removed: " + entry.getKey()));
                continue;
            }
            boolean wasRequired = Boolean.TRUE.equals(entry.getValue().get("required"));
            boolean nowRequired = Boolean.TRUE.equals(updated.get("required"));
            if (!wasRequired && nowRequired) {
                issues.add(new StructuralIssue(
                        "parameter-became-required",
                        Severity.BLOCK,
                        operation,
                        "Optional parameter became required: " + entry.getKey()));
            }
            if (!Objects.equals(removeDocumentation(entry.getValue()), removeDocumentation(updated))) {
                issues.add(new StructuralIssue(
                        "parameter-structure-changed",
                        Severity.REVIEW,
                        operation,
                        "Parameter schema or constraints changed: " + entry.getKey()));
            }
        }
        for (Map.Entry<String, Map<String, Object>> entry : newParameters.entrySet()) {
            if (!oldParameters.containsKey(entry.getKey()) && Boolean.TRUE.equals(entry.getValue().get("required"))) {
                issues.add(new StructuralIssue(
                        "required-parameter-added",
                        Severity.BLOCK,
                        operation,
                        "New required parameter added: " + entry.getKey()));
            }
        }
    }

    private void compareRequestBody(
            String operation,
            Map<String, Object> oldOperation,
            Map<String, Object> newOperation,
            List<StructuralIssue> issues) {
        Map<String, Object> oldBody = optionalMap(oldOperation.get("requestBody"));
        Map<String, Object> newBody = optionalMap(newOperation.get("requestBody"));
        boolean oldRequired = Boolean.TRUE.equals(oldBody.get("required"));
        boolean newRequired = Boolean.TRUE.equals(newBody.get("required"));
        if (!oldRequired && newRequired) {
            issues.add(new StructuralIssue(
                    "request-body-became-required",
                    Severity.BLOCK,
                    operation,
                    "Request body became required"));
        }
        if (!Objects.equals(removeDocumentation(oldBody), removeDocumentation(newBody))
                && !(oldBody.isEmpty() && newBody.isEmpty())) {
            issues.add(new StructuralIssue(
                    "request-body-structure-changed",
                    Severity.REVIEW,
                    operation,
                    "Request body schema or constraints changed"));
        }
    }

    private void compareResponses(
            String operation,
            Map<String, Object> oldOperation,
            Map<String, Object> newOperation,
            List<StructuralIssue> issues) {
        Map<String, Object> oldResponses = optionalMap(oldOperation.get("responses"));
        Map<String, Object> newResponses = optionalMap(newOperation.get("responses"));
        for (String status : oldResponses.keySet()) {
            if (!newResponses.containsKey(status)) {
                issues.add(new StructuralIssue(
                        "response-removed",
                        Severity.BLOCK,
                        operation,
                        "Response status removed: " + status));
            }
        }
        if (!Objects.equals(removeDocumentation(oldResponses), removeDocumentation(newResponses))) {
            issues.add(new StructuralIssue(
                    "response-structure-changed",
                    Severity.REVIEW,
                    operation,
                    "Response schemas or constraints changed"));
        }
    }

    private Map<String, Map<String, Object>> operations(Map<String, Object> document) {
        Map<String, Object> paths = optionalMap(document.get("paths"));
        Object globalSecurity = document.get("security");
        LinkedHashMap<String, Map<String, Object>> result = new LinkedHashMap<>();
        for (Map.Entry<String, Object> pathEntry : paths.entrySet()) {
            Map<String, Object> pathItem = optionalMap(pathEntry.getValue());
            Object pathParameters = pathItem.get("parameters");
            for (Map.Entry<String, Object> methodEntry : pathItem.entrySet()) {
                String method = methodEntry.getKey().toLowerCase(Locale.ROOT);
                if (!HTTP_METHODS.contains(method)) {
                    continue;
                }
                LinkedHashMap<String, Object> operation = new LinkedHashMap<>(optionalMap(methodEntry.getValue()));
                operation.put("parameters", mergeParameters(pathParameters, operation.get("parameters")));
                if (!operation.containsKey("security") && globalSecurity != null) {
                    operation.put("security", globalSecurity);
                }
                result.put(method.toUpperCase(Locale.ROOT) + " " + pathEntry.getKey(), operation);
            }
        }
        return result;
    }

    private List<Object> mergeParameters(Object inherited, Object declared) {
        LinkedHashMap<String, Object> merged = new LinkedHashMap<>();
        addParameters(merged, inherited);
        addParameters(merged, declared);
        return List.copyOf(merged.values());
    }

    private void addParameters(Map<String, Object> destination, Object value) {
        if (!(value instanceof List<?> list)) {
            return;
        }
        int anonymousIndex = destination.size();
        for (Object item : list) {
            Map<String, Object> parameter = optionalMap(item);
            String key;
            if (parameter.containsKey("$ref")) {
                key = "$ref:" + parameter.get("$ref");
            } else if (parameter.containsKey("name") && parameter.containsKey("in")) {
                key = parameter.get("in") + ":" + parameter.get("name");
            } else {
                key = "anonymous:" + anonymousIndex++;
            }
            destination.put(key, item);
        }
    }

    private Map<String, Map<String, Object>> parameters(Object value) {
        LinkedHashMap<String, Map<String, Object>> result = new LinkedHashMap<>();
        if (!(value instanceof List<?> list)) {
            return result;
        }
        for (Object item : list) {
            Map<String, Object> parameter = optionalMap(item);
            String name = Objects.toString(parameter.get("name"), "<unnamed>");
            String location = Objects.toString(parameter.get("in"), "<unknown>");
            result.put(location + ":" + name, parameter);
        }
        return result;
    }

    private Object documentationView(Object value) {
        if (value instanceof Map<?, ?> map) {
            LinkedHashMap<String, Object> result = new LinkedHashMap<>();
            for (Map.Entry<?, ?> entry : map.entrySet()) {
                String key = String.valueOf(entry.getKey());
                if (DOCUMENTATION_KEYS.contains(key)) {
                    result.put(key, entry.getValue());
                } else {
                    Object nested = documentationView(entry.getValue());
                    if (!isEmpty(nested)) {
                        result.put(key, nested);
                    }
                }
            }
            return result;
        }
        if (value instanceof List<?> list) {
            List<Object> result = new ArrayList<>();
            for (Object item : list) {
                Object nested = documentationView(item);
                if (!isEmpty(nested)) {
                    result.add(nested);
                }
            }
            return result;
        }
        return null;
    }

    private boolean isEmpty(Object value) {
        return value == null
                || value instanceof Map<?, ?> map && map.isEmpty()
                || value instanceof List<?> list && list.isEmpty();
    }

    private Object removeDocumentation(Object value) {
        if (value instanceof Map<?, ?> map) {
            LinkedHashMap<String, Object> result = new LinkedHashMap<>();
            for (Map.Entry<?, ?> entry : map.entrySet()) {
                String key = String.valueOf(entry.getKey());
                if (!DOCUMENTATION_KEYS.contains(key)) {
                    result.put(key, removeDocumentation(entry.getValue()));
                }
            }
            return result;
        }
        if (value instanceof List<?> list) {
            return list.stream().map(this::removeDocumentation).toList();
        }
        return value;
    }

    public Map<String, Object> semanticState(OperationChange change) {
        LinkedHashMap<String, Object> state = new LinkedHashMap<>();
        state.put("operation", change.operation());
        state.put("old_contract", compact(change.oldOperation()));
        state.put("new_contract", compact(change.newOperation()));
        state.put("deterministic_changes", change.structuralIssues().stream()
                .map(issue -> Map.of(
                        "rule", issue.ruleId(),
                        "severity", issue.severity().name().toLowerCase(Locale.ROOT),
                        "message", issue.message()))
                .toList());
        return state;
    }

    private Object compact(Object value) {
        if (value instanceof Map<?, ?> map) {
            LinkedHashMap<String, Object> result = new LinkedHashMap<>();
            for (Map.Entry<?, ?> entry : map.entrySet()) {
                String key = String.valueOf(entry.getKey());
                if (key.startsWith("x-") || key.equals("callbacks") || key.equals("servers")) {
                    continue;
                }
                result.put(key, compact(entry.getValue()));
            }
            return result;
        }
        if (value instanceof List<?> list) {
            return list.stream().limit(100).map(this::compact).toList();
        }
        if (value instanceof String string && string.length() > 4_000) {
            return string.substring(0, 4_000) + "…[truncated]";
        }
        return value;
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> optionalMap(Object value) {
        if (value == null) {
            return Map.of();
        }
        if (!(value instanceof Map<?, ?> map)) {
            return Map.of("value", value);
        }
        return (Map<String, Object>) map;
    }
}
