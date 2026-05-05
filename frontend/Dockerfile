# Production build — React app served by nginx
FROM node:20-bookworm-slim AS build

WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
RUN mkdir -p /var/cache/nginx /var/run /var/log/nginx /tmp/nginx \
	&& chown -R nginx:nginx /usr/share/nginx/html /etc/nginx/conf.d /var/cache/nginx /var/run /var/log/nginx /tmp/nginx \
	&& sed -ri 's@^\s*pid\s+[^;]+;@pid /tmp/nginx.pid;@' /etc/nginx/nginx.conf

USER nginx
EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
