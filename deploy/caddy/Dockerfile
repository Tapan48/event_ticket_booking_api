ARG CADDY_VERSION=2.11.4
FROM caddy:${CADDY_VERSION}-builder-alpine AS builder
ARG CADDY_VERSION
RUN xcaddy build v${CADDY_VERSION} \
    --with github.com/caddy-dns/duckdns@86ea11d23d37c85f3900a8c3093405e2bcd68d2e

FROM caddy:${CADDY_VERSION}-alpine
COPY --from=builder /usr/bin/caddy /usr/bin/caddy
COPY Caddyfile /etc/caddy/Caddyfile
# Port 8443 needs no privileged-port capability. Remove the upstream file capability
# so execution also works with cap_drop: ALL and no-new-privileges.
RUN setcap -r /usr/bin/caddy \
    && mkdir -p /data /config && chown -R 10001:10001 /data /config
USER 10001:10001
