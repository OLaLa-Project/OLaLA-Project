# Stage 1: Build
FROM ghcr.io/cirruslabs/flutter:3.24.0 AS build

WORKDIR /app

# Copy pubspec files first to cache dependencies
COPY pubspec.yaml pubspec.lock ./
RUN flutter pub get

# Copy source code
COPY . .

# Build for web
# API_URL can be overridden at build time.
ARG API_URL=http://localhost:8080
RUN flutter build web --release --dart-define=API_URL=${API_URL}

# Stage 2: Serve
FROM nginx:alpine

# Copy built assets
COPY --from=build /app/build/web /usr/share/nginx/html
COPY nginx/default.conf /etc/nginx/conf.d/default.conf

# Expose port 80
EXPOSE 80

# Start Nginx
CMD ["nginx", "-g", "daemon off;"]
