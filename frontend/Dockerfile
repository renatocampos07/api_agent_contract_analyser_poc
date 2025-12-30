# frontend/Dockerfile - production build
# Multi-stage: build with Node (Vite) then serve static files with nginx

FROM node:18 AS builder
WORKDIR /app

# Copy package files first to leverage layer caching
COPY package.json package-lock.json* ./
RUN npm ci --legacy-peer-deps

# Copy rest of the sources and build
COPY . .

# Allow providing the API url at build time (default to internal compose name)
ARG VITE_API_URL=http://backend:8000/api
ENV VITE_API_URL=${VITE_API_URL}

RUN npm run build

FROM nginx:stable-alpine

# Remove default nginx static files
RUN rm -rf /usr/share/nginx/html/*

# Copy built files from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy custom nginx config if present
COPY nginx.conf /etc/nginx/nginx.conf

# Optional: expose 80 for production
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
