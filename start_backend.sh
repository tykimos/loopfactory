#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
uvicorn api.main:app --port 8000
