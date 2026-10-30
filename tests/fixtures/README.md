Static, deterministic synthetic data only. Phase 1's explicit
`python -m sentinelforge.seed_demo` command imports these fixtures through the
domain services. The legacy display ID/timestamp describe the original static
fixture; persistence allocates its own immutable display ID and creation time.
No seed runs on startup, and no case HTTP routes exist yet. No secrets or real targets.
