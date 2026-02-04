# Stage 1: Build the Flutter Web App
FROM ubuntu:20.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive

# Install dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    unzip \
    xz-utils \
    zip \
    libglu1-mesa \
    && rm -rf /var/lib/apt/lists/*

# Install Flutter
ARG FLUTTER_CHANNEL=stable
ARG FLUTTER_VERSION=3.10.6 
# Using specific version to match pubspec.yaml environment (sdk: ^3.10.7) minimally or just use stable
# pubspec says "sdk: ^3.10.7", let's use a recent stable version or the exact one if possible. 
# 3.10.x is a bit old, but let's try to clone stable and then checkout if needed, or just use stable channel.
# Let's simple clone stable.
RUN git clone https://github.com/flutter/flutter.git /usr/local/flutter
ENV PATH="/usr/local/flutter/bin:/usr/local/flutter/bin/cache/dart-sdk/bin:${PATH}"

# Run flutter doctor
RUN flutter channel stable
RUN flutter upgrade
RUN flutter doctor -v

# Copy source code
WORKDIR /app
COPY . .

# Build Web
RUN flutter config --enable-web
RUN flutter create . --platforms web
RUN flutter pub get
RUN flutter build web --release

# Stage 2: Serve with Nginx
FROM nginx:alpine

# Copy built assets
COPY --from=builder /app/build/web /usr/share/nginx/html

# Copy nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
