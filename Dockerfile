FROM python:3.12-slim
RUN pip install --no-cache-dir \
    mysql-connector-python \
    sqlite-utils \
    pandas \
    requests
WORKDIR /app
