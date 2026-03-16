FROM python:3.11-slim
 
WORKDIR /app/backend
 
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
 
COPY backend/ ./
COPY frontend/ ../frontend/
COPY sql/ ../sql/
 
EXPOSE $PORT
 
CMD ["sh", "-c", "python -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
 
