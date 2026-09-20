# Launch kit

Use the benchmark and demo links when sharing the project. Avoid claiming that Jev replaces deterministic OpenAPI diffing or that the benchmark measures model accuracy.

## One sentence

JEV OAS Sentinel catches consumer-facing API promises hidden in OpenAPI prose by combining deterministic structural checks with typed System One judgments from TypeSafe Jev.

## Show HN

**Title**

> Show HN: JEV OAS Sentinel – catch breaking API changes hidden in OpenAPI prose

**Post**

> Structural OpenAPI diff tools are good at finding removed fields, required parameters, and incompatible schemas. They cannot safely decide whether changing “safe to retry for 24 hours” to “best effort” breaks consumers.
>
> I built JEV OAS Sentinel, a Python CLI and GitHub Action that keeps structural checks deterministic and sends only changed operation fragments to TypeSafe Jev for typed, bounded semantic judgments. Policy code—not generated prose—decides whether to pass, request review, or block.
>
> It includes offline dry-run planning, SARIF output, call limits, sanitized tracing, expiring suppressions, and a reproducible 10-case semantic routing benchmark. Advisory mode is the default.
>
> Repository: https://github.com/ShuhanSun/jev-oas-sentinel
> Marketplace: https://github.com/marketplace/actions/jev-oas-sentinel

## Short social post

> Your OpenAPI schema can remain compatible while the API contract still breaks clients.
>
> JEV OAS Sentinel catches changed promises about pagination, ordering, retries, authorization, timestamps, and error meaning. Deterministic Python handles structural breaks; TypeSafe Jev handles bounded semantic judgments.
>
> Try the offline demo—no API key required:
> https://github.com/ShuhanSun/jev-oas-sentinel

## 中文发布文案

> OpenAPI Schema 没变，不代表 API 没有破坏兼容性。
>
> 默认分页数量、返回顺序、重试幂等性、错误含义、授权行为等承诺，通常藏在 description 和 example 里。JEV OAS Sentinel 使用确定性 Python 规则检查结构变化，再用 TypeSafe Jev 的 System One typed judgment 评估语义风险。
>
> 项目提供 Python CLI、GitHub Action、SARIF、离线 dry-run、调用次数限制和可审计的过期 suppression。默认使用 advisory 模式，不会因为一次概率判断直接阻断发布。
>
> GitHub：https://github.com/ShuhanSun/jev-oas-sentinel
> Marketplace：https://github.com/marketplace/actions/jev-oas-sentinel

## TypeSafe community message

> I built an independent community project on Jev: JEV OAS Sentinel. It uses Jev's typed questions and probability distributions to evaluate behavioral compatibility changes in OpenAPI operation prose, while deterministic code retains control of structural rules and CI policy. The repository includes a no-key dry run and a reproducible semantic-routing benchmark. Feedback on the question boundaries and confidence policy would be especially useful.

## Accuracy language

Use:

- “routes semantic-only changes to bounded JEV review”;
- “complements structural OpenAPI diffing”;
- “returns typed probabilities consumed by deterministic policy code.”

Avoid:

- “detects every breaking change”;
- “proves other diff tools are wrong”;
- “guarantees compatibility.”
