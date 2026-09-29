# AI4CPI Runbook

This document describes operational procedures.

## Restart Services

Agent

systemctl restart ai4biz-agent

Embedding Service

systemctl restart ai4biz-embedding

## Qdrant

Check health:

curl `http://localhost:6333/healthz`

## Logs

Agent logs:

/var/log/ai4cpi/agent.log

Embedding logs:

/var/log/ai4cpi/embedding.log
