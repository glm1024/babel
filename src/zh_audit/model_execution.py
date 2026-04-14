from __future__ import absolute_import

from zh_audit.candidate_validation import MAX_GENERATION_ATTEMPTS_PER_ITEM


STANDARD_EXECUTION_STRATEGY = "standard"
THINK_FAST_EXECUTION_STRATEGY = "think_fast"
MODEL_EXECUTION_STRATEGIES = (
    STANDARD_EXECUTION_STRATEGY,
    THINK_FAST_EXECUTION_STRATEGY,
)
DEFAULT_EXECUTION_STRATEGY = THINK_FAST_EXECUTION_STRATEGY


def normalize_model_execution_strategy(value):
    candidate = str(value or "").strip().lower()
    if not candidate:
        return DEFAULT_EXECUTION_STRATEGY
    if candidate not in MODEL_EXECUTION_STRATEGIES:
        raise ValueError('model_config.execution_strategy must be "standard" or "think_fast".')
    return candidate


def resolve_model_execution_strategy(model_config):
    strategy = normalize_model_execution_strategy((model_config or {}).get("execution_strategy"))
    if strategy == STANDARD_EXECUTION_STRATEGY:
        return {
            "strategy": strategy,
            "enable_reviewer": True,
            "max_generation_attempts": MAX_GENERATION_ATTEMPTS_PER_ITEM,
        }
    return {
        "strategy": strategy,
        "enable_reviewer": False,
        "max_generation_attempts": 1,
    }
