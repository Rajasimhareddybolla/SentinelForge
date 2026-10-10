#!/bin/bash
echo "Starting FastAPI Backend..."
.venv/bin/uvicorn app.main:app --reload &
FASTAPI_PID=$!

echo "Starting Streamlit Dashboard..."
.venv/bin/streamlit run app/dashboard.py &
STREAMLIT_PID=$!

function cleanup {
  echo "Shutting down servers..."
  kill $FASTAPI_PID
  kill $STREAMLIT_PID
  exit
}

trap cleanup EXIT

wait

