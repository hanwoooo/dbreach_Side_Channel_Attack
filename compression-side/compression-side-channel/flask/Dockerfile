FROM python:3.9-slim

WORKDIR /app

# 필요한 라이브러리 설치
COPY requirements.txt /app
RUN pip install --no-cache-dir -r requirements.txt

# Flask 앱 복사
COPY . /app

# Flask 실행(혹은 Gunicorn 사용 가능)
CMD ["python", "app.py"]
