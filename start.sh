#!/usr/bin/env bash
set -euo pipefail

echo "=== Officero EAR V0 — Starting ==="

# Install espeak-ng (needed by Kokoro for phonemization)
echo "Installing espeak-ng..."
apt-get update -qq && apt-get install -y -qq espeak-ng > /dev/null 2>&1
echo "espeak-ng installed"

# Install Python deps
echo "Installing Python dependencies..."
pip install -q -r requirements.txt
echo "Dependencies installed"

# Start vLLM in background
echo "Starting vLLM..."
vllm serve Qwen/Qwen3-8B \
    --gpu-memory-utilization 0.3 \
    --port 8000 \
    &
VLLM_PID=$!

# Wait for vLLM to be ready
echo "Waiting for vLLM to be ready..."
until curl -s http://localhost:8000/health > /dev/null 2>&1; do
    sleep 2
done
echo "vLLM is ready (PID=$VLLM_PID)"

# Start FastAPI
echo "Starting FastAPI on port 8080..."
uvicorn app.main:app --host 0.0.0.0 --port 8080
