FROM node:24-alpine AS build

WORKDIR /app

ARG VITE_OMNI_API_BASE_URL=http://127.0.0.1:8000/api/v1
ENV VITE_OMNI_API_BASE_URL=$VITE_OMNI_API_BASE_URL

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:1.27-alpine AS runtime

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1
