FROM node:20-bookworm-slim

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json* /app/frontend/
RUN npm install

COPY frontend /app/frontend

EXPOSE 5173
