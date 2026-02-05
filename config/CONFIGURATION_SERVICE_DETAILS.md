# Configuration Service (Redis-backed)

## Overview

This directory contains the implementation of the **Configuration Management** subsystem for the
LE Beta Particle Visualization project.

The goal of this subsystem is to establish a **single source of truth** for all system configuration
values shared across the Desktop GUI, Unattended Processing Pipeline, and supporting services, as
described in the Design Document (Section 6).

Redis is used as the centralized runtime configuration store, with defaults seeded from an
authoritative registry.

---

## Motivation

Prior to this implementation, the project relied on a hardcoded `MockConfigurationService` to
unblock early development. While useful for prototyping, the mock implementation does not support
shared state between components or runtime configurability.

This Redis-backed Configuration Service enables:
- Consistent configuration values across GUI and pipeline
- Centralized updates without code duplication
- A clean path toward runtime configurability and Pub/Sub signaling in later sprints

---

## Files in This Directory

### `ConfigurationService.py`

Provides a minimal Python client for interacting with Redis.

Responsibilities:
- Connects to a password-protected Redis instance
- Reads credentials from environment variables
- Exposes basic `ping`, `get`, and `set` operations
- Fails fast if required credentials are missing

Environment variables used:
- `REDIS_HOST` (default: `127.0.0.1`)
- `REDIS_PORT` (default: `6379`)
- `REDIS_PASSWORD` (required)

> Note: Redis stores all values as strings. Type enforcement is handled by the consumer of the
> configuration values (e.g., via typed accessors), which will be added during integration.

---

### `scripts/seed_config_initialization.py`

A one-time (or on-demand) initialization script that populates Redis with **all default configuration
values** defined in `ConfigurationKeys.md`.

Responsibilities:
- Connects to the Redis Configuration Service
- Seeds all configuration keys using strict colon-separated namespaces
- Serializes values into consistent string representations
- Serves as the authoritative source of default configuration values

This script should be run after starting Redis locally.

---

## Configuration Registry

The defaults seeded by this script correspond exactly to the entries in
`ConfigurationKeys.md`, including:

- `global:*` — shared infrastructure and physics parameters
- `gui:*` — GUI rendering, layout, and interaction defaults
- `pipeline:*` — unattended pipeline ingestion parameters

Each key follows the convention:
```bash
<namespace>:<category>:<key>
```

Example:
global:db:connection_string
gui:raw_analysis:vis_range_max
pipeline:ingress:polling_location

---

## Local Usage (Single-Computer MVP)

### 1. Start Redis
Ensure Redis is running via Docker:

```bash
docker compose up -d
```

### 2. Set environment variables
Create a .env file in the project root containing:

```bash
REDIS_PASSWORD=your_password_here
REDIS_PORT=6379
```
### 3. Seed default configuration values
From the project root:
```bash
python -m config.scripts.seed_config_initialization
```