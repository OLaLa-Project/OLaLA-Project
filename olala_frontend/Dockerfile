# Stage 1: Build
FROM ghcr.io/cirruslabs/flutter:3.24.0 AS build

WORKDIR /app

# Copy pubspec files first to cache dependencies
COPY pubspec.yaml pubspec.lock ./
RUN flutter pub get

# Copy source code
COPY . .

# Build for web
# Pass API_URL as build argument (can be overridden by --build-arg, but here we hardcode or use default for Docker defaults)
# When running via docker-compose on user machine, backend is at localhost:8080 usually.
RUN flutter build web --release --dart-define=API_URL=http://localhost:8080

# Stage 2: Serve
FROM nginx:alpine

# Copy built assets
COPY --from=build /app/build/web /usr/share/nginx/html

# Expose port 80
EXPOSE 80

# Start Nginx
CMD ["nginx", "-g", "daemon off;"]
