FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy semua file
COPY . .

# Koyeb pakai PORT dari environment variable
ENV PORT=8000

EXPOSE 8000

CMD ["python", "bot.py"]
