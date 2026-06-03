# --- build stage: produce static assets with Vite ---
FROM node:20-alpine AS build

# Optional build-args. Leave empty for portable bundle (same-origin via window.location).
ARG VITE_API_URL=""
ARG VITE_WS_URL=""
ENV VITE_API_URL=$VITE_API_URL \
    VITE_WS_URL=$VITE_WS_URL

WORKDIR /app

# Copy lockfile separately to cache deps when only source changes.
COPY package.json package-lock.json* ./
RUN npm ci

COPY . .
RUN npm run build

# --- serve stage: nginx with SPA + reverse-proxy to backend ---
FROM nginx:1.27-alpine AS runtime

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
