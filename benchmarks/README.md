# Semantic routing benchmark

This benchmark contains consumer-visible API promises that can change without changing paths, parameters, response codes, or schemas. It demonstrates the gap that JEV OAS Sentinel is designed to cover: deterministic rules remain responsible for definite structural breaks, while contract-prose changes are routed to TypeSafe Jev for bounded semantic judgment.

Run it offline:

```bash
uv run python benchmarks/run.py --check --output benchmarks/results.md
```

The benchmark does not call Jev, measure model accuracy, or claim that another OpenAPI tool cannot display documentation changes. It verifies one narrower and reproducible property: every case contains zero deterministic structural findings and one planned semantic evaluation.

See [`results.md`](results.md) for the generated table and [`cases.json`](cases.json) for the source scenarios.
