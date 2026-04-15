#!/bin/sh
set -eu

: "${SERVER_NAME:=_}"
: "${LISTEN_PORT:=4433}"
: "${TIMELAPSE_UPSTREAM:=http://timelapse:8080}"
: "${GO2RTC_UPSTREAM:=http://go2rtc:1984}"
: "${SSL_CERT:=}"
: "${SSL_CERT_KEY:=}"

NGINX_CONF="/etc/nginx/conf.d/default.conf"

if [ -n "$SSL_CERT" ] && [ -n "$SSL_CERT_KEY" ]; then
  LISTEN_DIRECTIVE="listen ${LISTEN_PORT} ssl http2;"
  SSL_DIRECTIVES="ssl_certificate ${SSL_CERT};
    ssl_certificate_key ${SSL_CERT_KEY};"
else
  LISTEN_DIRECTIVE="listen ${LISTEN_PORT};"
  SSL_DIRECTIVES=""
fi

cat > "$NGINX_CONF" <<EOF
server {
    ${LISTEN_DIRECTIVE}
    server_name ${SERVER_NAME};

    ${SSL_DIRECTIVES}

    client_max_body_size 100m;
    proxy_buffering off;

    location = /go2rtc {
        return 301 /go2rtc/;
    }

    location /go2rtc/ {
        proxy_pass ${GO2RTC_UPSTREAM}/;
        proxy_http_version 1.1;

        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-Host \$host;
        proxy_set_header X-Forwarded-Prefix /go2rtc;

        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    location / {
        proxy_pass ${TIMELAPSE_UPSTREAM};
        proxy_http_version 1.1;

        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-Host \$host;

        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
EOF

nginx -t
