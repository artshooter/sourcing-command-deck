FROM python:3.11-slim

WORKDIR /app

COPY apps/ ./

RUN mkdir -p runs secrets uploads

EXPOSE 8765

CMD ["python3", "server.py"]
