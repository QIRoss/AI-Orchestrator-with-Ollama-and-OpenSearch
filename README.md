# AI Orchestrator with Ollama and OpenSearch

A local AI orchestration service that provides multiple NLP endpoints using Ollama models and OpenSearch for data persistence. Built with FastAPI, Docker, and monitoring stack

## Tech Stack

Backend: Python + FastAPI

AI Models: Ollama (local LLMs)

Search & Storage: OpenSearch

Monitoring: Prometheus + Grafana (To be updated)

Containerization: Docker + Docker Compose.

## Prerequisites

Docker

Docker Compose

8GB+ RAM recommended for model operations

## Quick Start

```
docker-compose up -d
```

This will start:

1) AI Orchestrator API (port 8000)

2) Ollama model server (port 11434)

3) OpenSearch (port 9200)

4) Prometheus (port 9090)

5) Grafana (port 3000)

## Download AI Models

Important: You need to download the AI models before using the API:
```
curl -X POST http://localhost:11434/api/pull -d '{"name": "llama3.1:8b"}'
```

The download may take several minutes depending on your internet connection. You can monitor progress with:
```
curl http://localhost:11434/api/tags
```

Verify Installation
```
curl http://localhost:8000/health
```

## API Usage

Summarize Text
```
curl -X POST "http://localhost:8000/summarize" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Artificial intelligence is transforming how we interact with technology. From virtual assistants to automated content creation, AI systems are becoming increasingly sophisticated. Machine learning algorithms can now understand natural language, recognize patterns in data, and make predictions with remarkable accuracy. This technology has applications across various industries including healthcare, finance, education, and entertainment. While AI offers tremendous benefits, it also raises important ethical considerations about privacy, bias, and the future of work that society must address responsibly.",
    "model": "llama3.1:8b"
  }'
```

## Build Custom Image
```
docker-compose build --no-cache
```

## Opensearch Queries

```
# Search all documents in index
curl -X GET "http://localhost:9200/ai-requests/_search?pretty" -H 'Content-Type: application/json' -d'
{
  "query": {
    "match_all": {}
  },
  "size": 10
}'

# Search by endpoint summarize
curl -X GET "http://localhost:9200/ai-requests/_search?pretty" -H 'Content-Type: application/json' -d'
{
  "query": {
    "term": {
      "endpoint": "summarize"
    }
  }
}'

# Search specific model
curl -X GET "http://localhost:9200/ai-requests/_search?pretty" -H 'Content-Type: application/json' -d'
{
  "query": {
    "term": {
      "model": "llama3.1:8b"
    }
  }
}'

# Group by endpoint
curl -X GET "http://localhost:9200/ai-requests/_search?pretty" -H 'Content-Type: application/json' -d'
{
  "size": 0,
  "aggs": {
    "endpoints": {
      "terms": {
        "field": "endpoint"
      }
    }
  }
}'

# Search by timestamp
curl -X GET "http://localhost:9200/ai-requests/_search?pretty" -H 'Content-Type: application/json' -d'
{
  "query": {
    "range": {
      "timestamp": {
        "gte": "now-1h"
      }
    }
  }
}'
```