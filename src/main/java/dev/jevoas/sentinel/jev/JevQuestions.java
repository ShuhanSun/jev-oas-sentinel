package dev.jevoas.sentinel.jev;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class JevQuestions {
    private JevQuestions() {
    }

    public static Map<String, Object> questions() {
        LinkedHashMap<String, Object> questions = new LinkedHashMap<>();
        questions.put("change_kind", choice(
                "Classify the consumer-visible compatibility impact of changing `old_contract` to `new_contract` for the named API operation. Treat descriptions, examples, defaults, ordering, pagination, retry behavior, authorization, and error meanings as contractual when they make a behavioral promise.",
                criteria(
                        "docs_only", "Wording or presentation changed, but every consumer-visible behavioral promise is preserved.",
                        "additive", "The new contract adds optional behavior or clarification without invalidating old client assumptions.",
                        "behavioral_nonbreaking", "Runtime behavior or meaning changed, but conforming existing clients should continue to work.",
                        "breaking", "A client that correctly followed the old contract could fail, receive materially different results, lose access, or require a coordinated change.",
                        "unclear", "The supplied old and new fragments are insufficient or genuinely ambiguous.")));
        questions.put("affected_dimension", choice(
                "Which single semantic dimension is most materially affected by the contract change?",
                criteria(
                        "none", "No consumer-visible semantic dimension changed.",
                        "request_precondition", "Accepted inputs, required context, or preconditions changed.",
                        "default_behavior", "Behavior when an input is omitted or left at its default changed.",
                        "response_meaning", "The meaning, interpretation, or guarantees of returned data changed.",
                        "ordering_pagination", "Ordering, cursors, pages, limits, or result-set semantics changed.",
                        "retry_idempotency", "Retry safety, duplication, idempotency, or timeout behavior changed.",
                        "authentication_authorization", "Authentication, authorization, identity, or scope expectations changed.",
                        "deprecation_migration", "Deprecation timing or migration expectations changed.",
                        "error_semantics", "Error codes, retryability, partial success, or failure meanings changed.",
                        "other", "Another consumer-visible semantic dimension changed.")));
        questions.put("old_promise_preserved", Map.of(
                "type", "noul",
                "instructions", "Does `new_contract` preserve every consumer-visible behavioral promise made by `old_contract` for this operation?",
                "criteria", Map.of(
                        "true", "Every old promise still holds; additions do not invalidate correct old-client assumptions.",
                        "false", "At least one old promise is narrowed, removed, contradicted, or made conditional.")));
        questions.put("migration_burden", Map.of(
                "type", "score",
                "instructions", "Rate the client migration burden caused by changing `old_contract` to `new_contract`.",
                "criteria", List.of(
                        "No client action; behavior and guarantees are preserved.",
                        "Optional client update or documentation awareness; existing clients remain correct.",
                        "Required client code or configuration update that can be rolled out independently.",
                        "Coordinated rollout, version negotiation, or substantial client redesign is required.")));
        return questions;
    }

    private static Map<String, Object> choice(String instructions, Map<String, String> criteria) {
        LinkedHashMap<String, Object> question = new LinkedHashMap<>();
        question.put("type", "choice");
        question.put("instructions", instructions);
        question.put("criteria", criteria);
        return question;
    }

    private static Map<String, String> criteria(String... values) {
        if (values.length % 2 != 0) {
            throw new IllegalArgumentException("Criteria require key/value pairs");
        }
        LinkedHashMap<String, String> criteria = new LinkedHashMap<>();
        for (int index = 0; index < values.length; index += 2) {
            criteria.put(values[index], values[index + 1]);
        }
        return criteria;
    }
}
