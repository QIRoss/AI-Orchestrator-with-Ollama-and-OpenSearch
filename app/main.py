from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
import logging
from opensearchpy import OpenSearch
import time
from prometheus_client import Counter, Histogram, generate_latest
import asyncio

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Métricas Prometheus
REQUEST_COUNT = Counter('requests_total', 'Total requests', ['endpoint', 'method'])
REQUEST_DURATION = Histogram('request_duration_seconds', 'Request duration')
OLLAMA_ERRORS = Counter('ollama_errors_total', 'Ollama API errors', ['type'])

app = FastAPI(title="AI Orchestrator")

# Try possible endpoints
OLLAMA_URLS = [
    "http://localhost:11434",
    "http://host.docker.internal:11434",
    "http://ollama:11434",
]

class TextRequest(BaseModel):
    text: str
    model: str = "llama3.1:8b"

async def find_working_ollama_url():
    for url in OLLAMA_URLS:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{url}/api/tags", timeout=5.0)
                if response.status_code == 200:
                    logger.info(f"✅ Ollama found at: {url}")
                    return url
        except Exception as e:
            logger.debug(f"Ollama not found at {url}: {e}")
    
    logger.error("❌ No Ollama endpoint working")
    return None

OLLAMA_URL = None

async def call_ollama(model: str, prompt: str) -> str:
    global OLLAMA_URL
    
    if not OLLAMA_URL:
        OLLAMA_URL = await find_working_ollama_url()
        if not OLLAMA_URL:
            raise HTTPException(status_code=503, detail="Ollama not available")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 500
                    }
                },
                timeout=120.0
            )
            
        if response.status_code != 200:
            OLLAMA_ERRORS.labels(type='http_error').inc()
            raise HTTPException(status_code=response.status_code, detail=f"Ollama API error: {response.text}")
            
        result = response.json()
        return result.get("response", "")
    
    except httpx.TimeoutException:
        OLLAMA_ERRORS.labels(type='timeout').inc()
        raise HTTPException(status_code=504, detail="Ollama request timeout")
    except httpx.ConnectError:
        # Try to reset the URL on connection error
        OLLAMA_URL = None
        OLLAMA_ERRORS.labels(type='connection').inc()
        raise HTTPException(status_code=503, detail="Cannot connect to Ollama")
    except Exception as e:
        OLLAMA_ERRORS.labels(type='other').inc()
        logger.error(f"Ollama API error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ollama API error: {str(e)}")

# Aux function to save in OpenSearch
def save_to_opensearch(endpoint: str, input_text: str, output_text: str, model: str):
    try:
        doc = {
            "endpoint": endpoint,
            "input_text": input_text[:1000],
            "output_text": output_text,
            "model": model,
            "timestamp": time.time()
        }
        OPENSEARCH_CLIENT = OpenSearch(["http://localhost:9200"])
        OPENSEARCH_CLIENT.index(index="ai-requests", body=doc)
        logger.info(f"Saved to OpenSearch: {endpoint}")
    except Exception as e:
        logger.error(f"OpenSearch error: {str(e)}")

@app.on_event("startup")
async def startup_event():
    logger.info("Starting AI Orchestrator...")
    
    # Try find Ollama
    url = await find_working_ollama_url()
    if url:
        global OLLAMA_URL
        OLLAMA_URL = url
        logger.info("✅ Ollama is ready")
    else:
        logger.warning("⚠️ Ollama is not available - endpoints will fail")

@app.post("/summarize")
async def summarize_text(request: TextRequest):
    start_time = time.time()
    REQUEST_COUNT.labels(endpoint='/summarize', method='POST').inc()
    
    prompt = f"""Resuma o seguinte texto de forma concisa e clara em português:

{request.text}

Resumo:"""
    
    try:
        result = await call_ollama(request.model, prompt)
        
        # Save to OpenSearch
        save_to_opensearch("summarize", request.text, result, request.model)
        
        # Register duration
        REQUEST_DURATION.observe(time.time() - start_time)
        
        return {"summary": result}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in summarize: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    ollama_healthy = bool(OLLAMA_URL)
    return {
        "status": "healthy" if ollama_healthy else "degraded",
        "ollama": "healthy" if ollama_healthy else "unavailable",
        "ollama_url": OLLAMA_URL if ollama_healthy else None,
        "opensearch": "connected"
    }

@app.get("/")
async def root():
    ollama_healthy = bool(OLLAMA_URL)
    return {
        "message": "AI Orchestrator API",
        "status": "ready" if ollama_healthy else "waiting for Ollama",
        "ollama_url": OLLAMA_URL,
        "endpoints": {
            "/summarize": "POST - Summarize text",
            "/translate": "POST - Translate text", 
            "/analyze_sentiment": "POST - Analyze sentiment",
            "/health": "GET - Health check",
            "/docs": "API documentation"
        }
    }

# Add endpoints (translate, analyze_sentiment) here following the same pattern as summarize_text

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")