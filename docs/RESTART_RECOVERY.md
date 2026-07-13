# Restart Recovery

Render can restart during deploys and infrastructure events.

## On Startup

The service:

- validates settings;
- connects to the database;
- starts the scheduler if enabled;
- logs product, universe mode and safety state;
- exposes readiness only when required capabilities are available.

## Persistent State

Stored in database:

- universe snapshots;
- candles;
- setup evaluations;
- trade signals;
- paper accounts;
- paper positions;
- paper fills;
- provider health;
- job locks;
- job executions.

## Duplicate Prevention

Signals use unique fingerprints. Job executions use job/window uniqueness. Job locks prevent duplicate scheduler execution.

## Recovery Rule

If the database is unavailable, the system must not create signals or paper positions in memory-only mode.
