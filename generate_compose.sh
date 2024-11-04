CONTAINER_COUNT=5
COMPOSE_FILE="docker-compose.yml"

echo "version: '3.5'" > $COMPOSE_FILE

cat <<EOL >> $COMPOSE_FILE
x-defaults:
  &defaults
  image: \${CI_REGISTRY_IMAGE}:\${CI_COMMIT_REF_NAME}
  environment:
    - TZ=Europe/Moscow
    - CI_COMMIT_REF_NAME
    - CI_COMMIT_SHORT_SHA
    - CONTAINER_NAME=${HOSTNAME}
services:
EOL

for i in $(seq 1 $CONTAINER_COUNT); do

  cat <<EOL >> $COMPOSE_FILE
  unireger$i:
    <<: *defaults
    environment:
      - CONTAINER_NAME="unireger$i"
    secrets:
      - secret1
      - secret2
      - secret3
    deploy:
      resources:
        limits:
          memory: 1024M
      restart_policy:
        condition: none
      labels:
        - traefik.enable=true
        - traefik.docker.network=traefik-net
        - traefik.http.services.unireger1.loadbalancer.server.scheme=http
        - traefik.http.services.unireger1.loadbalancer.server.port=5000
        - traefik.http.services.unireger2.loadbalancer.server.scheme=http
        - traefik.http.services.unireger2.loadbalancer.server.port=5000
        - traefik.http.services.unireger3.loadbalancer.server.scheme=http
        - traefik.http.services.unireger3.loadbalancer.server.port=5000
        - traefik.http.services.unireger4.loadbalancer.server.scheme=http
        - traefik.http.services.unireger4.loadbalancer.server.port=5000
        - traefik.http.services.unireger5.loadbalancer.server.scheme=http
        - traefik.http.services.unireger5.loadbalancer.server.port=5000
        - traefik.http.routers.unireger$i.rule=Host(\`unireger\${DOMAIN}\`)
        - traefik.http.routers.unireger$i.service=unireger$i
        - traefik.http.routers.unireger$i.entrypoints=websecure
        - traefik.http.routers.unireger$i.tls=true
    networks:
      - default
      - traefik
EOL
done

cat <<EOL >> $COMPOSE_FILE
secrets:
  secret1:
    file: /APIKey.json
  secret2:
    file: /DBConfig.json
  secret3:
    file: /ProxyUserOfKind3.json

networks:
  default:
    name: unireger
    attachable: true
  traefik:
    name: traefik-net
    external: true
EOL


