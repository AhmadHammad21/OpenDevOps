from __future__ import annotations

from opendevops_core.agent.turns import _FALLBACK_PRICING, calc_cost

# A model present in the fallback pricing config — used so the test asserts the
# folding math against known per-token rates without depending on LiteLLM's
# (mutable) pricing database.
_MODEL = "openrouter/google/gemma-4-26b-a4b-it"
_RATES = _FALLBACK_PRICING[_MODEL]


def _expected(input_tok: int, output_tok: int) -> float:
    return (input_tok / 1e6) * _RATES["input"] + (output_tok / 1e6) * _RATES["output"]


def test_reasoning_tokens_folded_when_reported_separately():
    # Gemini-style undercount (issue #59): the provider reports reasoning tokens
    # *outside* output_tokens (visible output is ~0), so they must be added to the
    # billable output or the cost is undercounted.
    undercounted = calc_cost(_MODEL, input_tok=10_000, output_tok=6)
    correct = calc_cost(_MODEL, input_tok=10_000, output_tok=6, reasoning_tok=800)

    assert undercounted == _expected(10_000, 6)
    assert correct == _expected(10_000, 6 + 800)
    assert correct > undercounted


def test_reasoning_not_double_counted_when_already_in_output():
    # gpt-oss style: output_tokens already includes reasoning (53 total, 38 of
    # which are reasoning). reasoning <= output_tokens, so it must NOT be re-added.
    cost = calc_cost(_MODEL, input_tok=1_000, output_tok=53, reasoning_tok=38)
    assert cost == _expected(1_000, 53)


def test_no_reasoning_is_unchanged():
    assert calc_cost(_MODEL, input_tok=1_000, output_tok=200, reasoning_tok=0) == _expected(
        1_000, 200
    )


def test_litellm_priced_model_includes_reasoning():
    # Real reported model from issue #59. Don't assert an absolute price (LiteLLM's
    # table changes); assert that folding reasoning in raises the cost.
    model = "openrouter/google/gemini-2.5-flash"
    without = calc_cost(model, input_tok=14_000, output_tok=6)
    with_reasoning = calc_cost(model, input_tok=14_000, output_tok=6, reasoning_tok=500)
    if without is not None:  # only meaningful when LiteLLM knows this model
        assert with_reasoning > without
