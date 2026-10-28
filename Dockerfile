# Standalone UI playground only. No n8n execution, database, secrets or business API.
FROM node:22-alpine AS build
WORKDIR /app
COPY playground/package.json ./playground/package.json
RUN npm install --prefix playground --no-audit --no-fund
COPY playground ./playground
RUN npm --prefix playground run build
FROM node:22-alpine
WORKDIR /app
COPY --from=build /app/playground/dist ./dist
COPY playground/server.mjs ./server.mjs
ENV PORT=3000
EXPOSE 3000
CMD ["node","server.mjs"]
