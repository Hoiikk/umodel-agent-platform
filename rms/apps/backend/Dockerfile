FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
COPY apps/backend/package.json apps/backend/package.json
COPY packages/shared/package.json packages/shared/package.json
RUN npm ci
COPY apps/backend apps/backend
COPY packages/shared packages/shared
RUN npm run build -w @rms/shared
WORKDIR /app/apps/backend
RUN npx tsc --outDir dist
RUN npm prune --omit=dev

FROM node:22-alpine
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app/node_modules /app/node_modules
COPY --from=build /app/packages/shared /app/packages/shared
COPY --from=build /app/apps/backend/dist /app/apps/backend/dist
CMD ["node", "apps/backend/dist/src/index.js"]
