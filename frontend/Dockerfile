FROM node:24-bookworm-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
COPY scripts ./scripts
RUN npm ci
COPY . .
ARG SOURCEATLAS_API_ORIGIN=http://api:8112
ENV SOURCEATLAS_API_ORIGIN=$SOURCEATLAS_API_ORIGIN NEXT_TELEMETRY_DISABLED=1
RUN npm run build && npm prune --omit=dev

FROM node:24-bookworm-slim
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
COPY --from=build --chown=node:node /app ./
USER node
EXPOSE 3102
CMD ["npx", "next", "start", "--port", "3102", "--hostname", "0.0.0.0"]
