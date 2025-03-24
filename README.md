# URL Shortener Service

A high-performance URL shortening service with robust security, analytics, and API management features.

![Version](https://img.shields.io/badge/version-1.1.0-blue)
![Python](https://img.shields.io/badge/python-3.8+-green)
![FastAPI](https://img.shields.io/badge/FastAPI-0.95+-green)
![Redis](https://img.shields.io/badge/Redis-6.0+-red)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-12.0+-blue)

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Installation](#installation)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Security](#security)
- [Frontend Interface](#frontend-interface)
- [Scaling Considerations](#scaling-considerations)
- [Development Guide](#development-guide)

## Overview

This URL Shortener is a full-featured service that allows you to create shortened URLs, track their usage statistics, and manage them through a clean API and user interface. It features advanced capabilities like custom alias support, expiration dates, bulk operations, and comprehensive security controls.

## Features

### Core Functionality

- **URL Shortening**: Convert long URLs to short, easy-to-share links
- **Custom Aliases**: Create personalized short codes for your links
- **Expiration Dates**: Set automatic expiration for temporary links
- **Click Tracking**: Track usage statistics for each shortened URL
- **Bulk Operations**: Create multiple shortened URLs in a single request

### Security & Performance

- **API Key Authentication**: Secure management endpoints with API keys
- **Rate Limiting**: Prevent abuse with configurable request limits
- **Data Privacy**: Anonymized IP address storage for GDPR compliance
- **Redis Caching**: High-performance caching for frequently accessed URLs
- **Vault Integration**: Optional HashiCorp Vault integration for secrets management
- **API Key Rotation**: Built-in API key rotation and management

### User Experience

- **Modern UI**: Clean, responsive user interface for link management
- **Dashboard**: Admin dashboard for viewing all links and statistics
- **QR Code Generation**: Create QR codes for your shortened URLs
- **Recent Links**: Track your recently created links

## Architecture

The application follows a modern, modular architecture:

```
app/
├── auth.py             # Authentication and API key validation
├── cache.py            # Redis caching implementation
├── config.py           # Configuration and environment variables
├── database.py         # Database connection and session management
├── key_rotation.py     # API key rotation and management
├── logger.py           # Structured logging system
├── main.py             # FastAPI application and endpoints
├── middlewares.py      # Request/response middleware
├── models.py           # SQLAlchemy database models
├── rate_limiter.py     # Rate limiting implementation
├── schemas.py          # Pydantic models for request/response validation
├── secrets_manager.py  # Vault integration for secrets management
└── utils.py            # Utility functions

static/
├── dashboard.html      # Admin dashboard interface
└── index.html          # Main user interface

README.md                # Project overview and documentation
requirements.txt         # Python dependencies
```

### Technology Stack

- **Backend**: FastAPI (Python)
- **Database**: PostgreSQL (production) / SQLite (development)
- **Caching**: Redis
- **Secrets Management**: HashiCorp Vault (optional)
- **Frontend**: HTML, CSS, JavaScript (vanilla)

## Installation

### Prerequisites

- Python 3.8+
- PostgreSQL or SQLite
- Redis server
- [Optional] HashiCorp Vault

### Manual Installation

1. Clone the repository:

```bash
git clone https://github.com/yourusername/url-shortener.git
cd url-shortener
```

2. Create a ⚙️ **.env** file with your configuration (see Configuration)

3. Install the dependencies:

```bash
pip install -r requirements.txt
```

4. Run the application:

```bash
uvicorn app.main:app --reload
```

## Configuration

The application is configured through environment variables that can be set in a .env file:

### Required Settings

```
# Database
DATABASE_URL=postgresql://username:password@localhost:5432/url_shortener

# Security
API_KEY=your-secure-api-key
API_KEY_REQUIRED=True

# Application
BASE_URL=http://localhost:8000
```

### Optional Settings

```
# Redis Cache
REDIS_URL=redis://localhost:6379
CACHE_TTL=3600

# Rate Limiting
RATE_LIMIT_ENABLED=True
RATE_LIMIT_MAX_REQUESTS=100
RATE_LIMIT_WINDOW=3600

# Database Connection Pool
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=1800

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# HashiCorp Vault (Optional)
VAULT_URL=http://localhost:8200
VAULT_TOKEN=your-vault-token
VAULT_ENABLED=False

# Sharding (Advanced)
SHARD_COUNT=3
```

## API Reference

| Method | Endpoint              | Description              | Authentication |
| ------ | --------------------- | ------------------------ | -------------- |
| POST   | `/shorten`            | Create a shortened URL   | None           |
| GET    | `/{short_code}`       | Redirect to original URL | None           |
| GET    | `/stats/{short_code}` | Get URL statistics       | API Key        |
| PUT    | `/{short_code}`       | Update a URL             | API Key        |
| DELETE | `/{short_code}`       | Delete a URL             | API Key        |
| POST   | `/bulk-shorten`       | Create multiple URLs     | API Key        |
| GET    | `/admin/urls`         | List all URLs            | API Key        |
| POST   | `/admin/api-keys`     | Create a new API key     | API Key        |
| GET    | `/health`             | Service health check     | None           |

## Examples

### Shorten a URL

```bash
curl -X POST "http://localhost:8000/shorten" \
  -H "Content-Type: application/json" \
  -d '{"original_url": "https://example.com/very/long/path", "alias": "example", "expires_in_days": 30}'
```

### Getting URL Statistics

```bash
curl -X GET "http://localhost:8000/stats/example" \
  -H "x-api-key: your-secure-api-key"
```

### Bulk Url creation

```bash
curl -X POST "http://localhost:8000/bulk-shorten" \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-secure-api-key" \
  -d '{"urls": [{"original_url": "https://example.com/1"}, {"original_url": "https://example.com/2"}]}'
```

## Security

### API Key Authentication

Protected endpoints require an API key, which must be passed in the `X-API-Key` HTTP header.

To create a new API key:

```bash
curl -X POST "http://localhost:8000/admin/api-keys" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-existing-api-key" \
  -d '{"description": "New API key", "expires_in_days": 90}'
```

### Rate Limiting

The service includes a rate limiter to prevent abuse. You can configure the maximum number of requests per window in the .env file.

### Data Privacy

User IP addresses are anonymized before storage:

- IPv4: Only the first three octets are stored (e.g., 192.168.1.\*)
- IPv6: Only the network portion is stored (first 48 bits)

## HashiCorp Vault Integration
For production environments, the application can integrate with HashiCorp Vault for secure API key storage:

1. Start the Vault server:

```bash
vault server -dev
```

2. Set up the KV store

```bash
export VAULT_ADDR='http://127.0.0.1:8200'
export VAULT_TOKEN='your-root-token'
vault secrets enable -path=urlshortener kv-v2
vault kv put urlshortener/api-keys/default api_key="your-api-key"
```

3. Update the .env file:

```
VAULT_URL=http://localhost:8200
VAULT_TOKEN=your-root-token
VAULT_ENABLED=True
```

## Frontend Interface
The application includes two user interfaces:

### Main URL Shortener Interface

Available at `/ui/` or `http://localhost:8000/ui/`

- Create shortened URLs with optional custom aliases and expiration dates
- View recently created URLs
- Check URL statistics
- Generate QR codes for shortened URLs

### Admin Dashboard

Available at [`dashboard.html`](static/dashboard.html) or [`http://localhost:8000/ui/dashboard.html`](http://localhost:8000/ui/dashboard.html)

- Overview of all shortened URLs
- Statistics on active and total URLs
- Search and filter functionality
- Sorting by various criteria
- URL management actions (copy, view stats, delete)

## Scaling Considerations

The application is designed with scalability in mind:

- **Database Connection Pooling**: Efficiently manages database connections
- **Redis Caching**: Reduces database load for frequently accessed URLs
- **Stateless API Design**: Allows horizontal scaling across multiple instances
- **Database Sharding**: Optional sharding support for high-volume deployments

For high-traffic production deployments:

1. Use a load balancer in front of multiple application instances
2. Scale Redis as a cluster
3. Consider database read replicas
4. Implement CDN for static assets
5. Monitor rate limiting configurations

## Development Guide

### Project Structure

- [`app`](app/): Contains the FastAPI application and core logic
- [`static`](static/): Static HTML files for the frontend interfaces
