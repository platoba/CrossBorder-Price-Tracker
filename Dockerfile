FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p data

ENV DB_PATH=/app/data/prices.db
VOLUME /app/data

ENTRYPOINT ["python", "-m", "app.cli"]
CMD ["monitor"]
