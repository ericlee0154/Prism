# Prism event research and confidence lineage

## Boundary

OpenAI performs source discovery, structured extraction, and narrative
summarization. It never supplies prices or market reactions. Prism computes
those values from locally stored Massive bars. Every AI record is discarded
unless at least one URL in the structured result was also returned by that
request's web-search tool.

No `OPENAI_API_KEY` means no AI event or confidence data. There are no default
events, institutions, scores, or brand signals.

## Event lifecycle

```text
world/company research
        |
        v
scheduled / ongoing event ---------> forecast horizon annotation
        |
        v
sourced post-event outcome
        |
        v
1 / 5 / 20 stored-session reaction + SPY excess return
```

`event_research_runs` records the provider, model, prompt version, requested
window, response identifier, usage, status, and error. `research_events` is the
latest materialized state. `event_observations` is the append-only history of
scheduled, current, post-event, and market-reaction observations.

An after-market event anchors its reaction to the next stored session. Other
release timings anchor on the event date or the next stored session. A horizon
remains pending until that future bar exists. SPY-relative values remain null
when matching SPY dates are unavailable.

## Weekly institutional confidence

The research provider extracts public evidence for each named institution and
labels its stance on a fixed ordinal scale:

```text
-2 strongly negative
-1 negative
 0 mixed or neutral
 1 positive
 2 strongly positive
```

For an institution with evidence items `i`:

```text
weighted_stance = sum(stance_i * extraction_confidence_i)
                  / sum(extraction_confidence_i)

weekly_index = clamp(50 + 25 * weighted_stance, 0, 100)
```

The index is a Prism research construct, not a vendor consensus rating or a
claim about the institution's internal portfolio. The source links, statement,
rationale, publication date, evidence count, model, prompt version, and
calculation period are stored with each snapshot.

## Monthly company long-term confidence

The market-price component requires at least 127 stored sessions:

```text
6m momentum score  = 50 + 50 * tanh(return_126 / 0.30)
12m momentum score = 50 + 50 * tanh(return_252 / 0.45)
drawdown resilience = 100 * max(0, 1 + trailing_drawdown)

market score = available weighted mean(45%, 35%, 20%)
```

The monthly composite uses:

```text
market-price component       50%
institutional weekly mean    30%
sourced brand evidence       20%
```

Weights are renormalized over available components, but the coverage status is
`partial` unless all three exist. Component values remain null in storage and
the UI. The snapshot always includes the Massive data cutoff used for its
market component.

## Frequency and scheduling

Refresh is manual in the current version. Repeated refreshes within the same
week or month replace the materialized snapshot for that period while retaining
append-only evidence and run records. A future local scheduler can call the same
endpoints without changing the point-in-time schema.
