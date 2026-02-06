# Flutter Stage Streaming Proxy Checklist

This checklist is for environments where `/api/truth/check/stream-v2` passes through
Nginx/Ingress and stream lines appear to arrive in a burst at the end.

## Nginx

Apply these settings only to the streaming route:

```nginx
location /api/truth/check/stream-v2 {
    proxy_pass http://backend_upstream;
    proxy_http_version 1.1;
    proxy_set_header Connection "";

    proxy_buffering off;
    gzip off;

    chunked_transfer_encoding on;
    proxy_read_timeout 300s;
}
```

## Kubernetes Ingress (Nginx Ingress Controller)

Use route-level annotations where possible:

```yaml
nginx.ingress.kubernetes.io/proxy-buffering: "off"
nginx.ingress.kubernetes.io/proxy-read-timeout: "300"
nginx.ingress.kubernetes.io/enable-modsecurity: "false"
```

If gzip is enabled globally, exclude the stream path.

## Validation

1. From a client host, run:

```bash
curl -N -X POST 'http://<host>/api/truth/check/stream-v2' \
  -H 'Content-Type: application/json' \
  --data '{"input_type":"text","input_payload":"테스트"}'
```

2. Confirm NDJSON lines appear progressively (not all at once at the end).
3. Compare line timestamps with Flutter logs to identify proxy-induced delay.
