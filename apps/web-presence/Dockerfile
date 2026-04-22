FROM python:3.11-alpine AS builder
WORKDIR /build
COPY src/ src/

COPY build/ .
RUN pip install --no-cache-dir -r requirements.txt
RUN python build.py

FROM nginx:alpine

COPY nginx.conf /etc/nginx/nginx.conf
COPY --from=builder --chown=nginx:nginx /build/public/ /usr/share/nginx/html/