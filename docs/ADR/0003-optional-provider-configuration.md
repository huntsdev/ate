# ADR 0003: Optional provider configuration before integration

Status: adopted for Phase 0.

## Context

Native Windows Ollama and `qwen3:8b` are installed on the development host.
An Elastic endpoint has not been selected. A default Elastic URL previously
pointed at an optional Compose service even when that service was stopped.

## Decision

- Allow `ATE_ELASTIC_URL` to be omitted or blank. Both mean unconfigured;
  supplied values must still be valid HTTP(S) URLs. Remove the implicit local
  Elastic endpoint from the settings and Compose environment defaults.
- Leave the template blank. Document `http://elasticsearch:9200` as the address
  for the optional synthetic Compose profile when an endpoint is needed later.
  Starting that profile does not configure or implement ingestion.
- Retain `ATE_OLLAMA_URL=http://host.docker.internal:11434` and the configurable
  `ATE_OLLAMA_MODEL=qwen3:8b`. Installation/model inventory can be checked on the
  host without loading a model, downloading weights, or invoking inference.
- Keep both integrations `not_enabled` in the application health contract.
  PostgreSQL and Redis remain the only readiness dependencies. No provider
  adapters, provider network probes, or model orchestration are added here.

## Consequences

A fresh installation and the current developer environment start without an
Elastic endpoint. Invalid nonblank URLs still fail safe configuration validation.
Available Ollama weights do not imply an integrated or benchmarked AI feature.
Container-to-host routing and inference validation remain Phase 4 work.
