package dev.jevoas.sentinel.jev;

import java.io.IOException;
import java.util.Map;

public interface DecisionClient {
    SemanticDecision evaluate(Map<String, Object> state) throws IOException, InterruptedException;
}

