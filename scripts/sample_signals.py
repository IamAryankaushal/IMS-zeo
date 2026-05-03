[
  {
    "component_id": "RDBMS_PRIMARY_01",
    "component_type": "RDBMS",
    "error_type": "CONNECTION_REFUSED",
    "message": "PostgreSQL primary instance not accepting connections. TCP timeout after 30s.",
    "latency_ms": 30000,
    "metadata": { "host": "db-primary-01.internal", "port": 5432 }
  },
  {
    "component_id": "CACHE_CLUSTER_01",
    "component_type": "CACHE",
    "error_type": "CACHE_MISS_STORM",
    "message": "Redis cluster miss rate exceeded 90%. Thundering herd from DB fallback.",
    "latency_ms": 850,
    "metadata": { "hit_rate": 0.08, "cluster": "prod-redis-01" }
  },
  {
    "component_id": "KAFKA_BROKER_01",
    "component_type": "QUEUE",
    "error_type": "PARTITION_OFFLINE",
    "message": "Kafka partition 3 on broker 01 is offline. Leader election in progress.",
    "latency_ms": null,
    "metadata": { "topic": "user-events", "partition": 3 }
  },
  {
    "component_id": "MCP_HOST_PROD",
    "component_type": "MCP",
    "error_type": "HEALTH_CHECK_FAILED",
    "message": "MCP host failed 3 consecutive /health checks. Removed from load balancer pool.",
    "latency_ms": 5000,
    "metadata": { "consecutive_failures": 3 }
  },
  {
    "component_id": "API_GATEWAY_PROD",
    "component_type": "API",
    "error_type": "ERROR_RATE_HIGH",
    "message": "API gateway 5xx error rate: 34%. Upstream services unreachable.",
    "latency_ms": 4200,
    "metadata": { "error_rate_pct": 34, "upstream": "order-service" }
  },
  {
    "component_id": "RDBMS_PRIMARY_01",
    "component_type": "RDBMS",
    "error_type": "REPLICATION_LAG",
    "message": "Replication lag on replica-01: 45 seconds. Data divergence risk.",
    "latency_ms": null,
    "metadata": { "lag_seconds": 45, "replica": "db-replica-01.internal" }
  }
]
