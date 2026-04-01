# --- Stage 1: Build React frontend ---
FROM node:22-slim AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Stage 2: Python runtime ---
FROM python:3.11-slim

# System deps for pdfplumber/pdftotext (monopoly-core)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpoppler-cpp-dev \
    pkg-config \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY expense_elt/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY expense_elt/ ./expense_elt/

# Copy built frontend
COPY --from=frontend-build /app/frontend/dist/ ./frontend/dist/

# Create directories for runtime data (volumes will mount here)
RUN mkdir -p /app/expense_elt/state \
             /app/expense_elt/logs \
             /app/expense_elt/output \
             /app/expense_elt/data/RBC_Visa \
             /app/expense_elt/data/BMO_Mastercard \
             /app/expense_elt/data/Amex

EXPOSE 9743

WORKDIR /app/expense_elt

CMD ["python", "main.py", "serve", "--host", "0.0.0.0", "--port", "9743"]
