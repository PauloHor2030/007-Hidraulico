#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/home/paulohor2030/ThermoSafeHidraulico"
SERVICE_NAME="thermosafehidraulico"
NGINX_SITE="/etc/nginx/sites-available/thermosafe"

echo "[1/7] Preparing directories..."
sudo mkdir -p "$APP_DIR"
sudo chown -R "$USER":"$USER" "$APP_DIR"

echo "[2/7] Installing packages..."
sudo apt update
sudo apt install -y python3-venv python3-pip nginx

echo "[3/7] Creating venv and installing Python deps..."
cd "$APP_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install flask waitress firebase-admin python-dotenv google-cloud-firestore

echo "[4/7] Placing example .env if not present..."
if [ ! -f "$APP_DIR/.env" ]; then
  cat > "$APP_DIR/.env" <<'EOF'
GOOGLE_APPLICATION_CREDENTIALS=./service-account.json
FIREBASE_PROJECT_ID=thermosafehidraulico
FLASK_RUN_HOST=127.0.0.1
FLASK_RUN_PORT=5000
EOF
  echo "Created $APP_DIR/.env (edit the service-account file name if needed)."
fi

echo "[5/7] Creating systemd service..."
sudo bash -c "cat > /etc/systemd/system/${SERVICE_NAME}.service" <<'EOF'
[Unit]
Description=ThermoSafe Hidraulico Listener (FAST)
After=network.target

[Service]
User=paulohor2030
WorkingDirectory=/home/paulohor2030/ThermoSafeHidraulico
ExecStart=/home/paulohor2030/ThermoSafeHidraulico/venv/bin/python /home/paulohor2030/ThermoSafeHidraulico/main.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

echo "[6/7] Installing Nginx site..."
sudo bash -c "cat > ${NGINX_SITE}" <<'EOF'
limit_req_zone $binary_remote_addr zone=per_ip:10m rate=30r/s;

server {
    listen 80 default_server;
    server_name _;

    access_log /var/log/nginx/thermosafe_access.log;
    error_log  /var/log/nginx/thermosafe_error.log warn;

    gzip on;
    gzip_types application/json text/plain;
    gzip_min_length 256;

    client_max_body_size 128k;
    client_body_timeout 10s;

    location = /healthz {
        return 200 "ok\n";
        add_header Content-Type text/plain;
    }

    location ^~ /api/ {
        limit_req zone=per_ip burst=60 nodelay;
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_connect_timeout 2s;
        proxy_send_timeout    10s;
        proxy_read_timeout    10s;
        proxy_buffering on;
        proxy_buffers 8 8k;
        proxy_busy_buffers_size 16k;
    }

    location ^~ /i/ {
        limit_req zone=per_ip burst=60 nodelay;
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_connect_timeout 2s;
        proxy_send_timeout    10s;
        proxy_read_timeout    10s;
        proxy_buffering on;
        proxy_buffers 8 8k;
        proxy_busy_buffers_size 16k;
    }

    location / { return 404; }
}
EOF

sudo ln -sf "${NGINX_SITE}" /etc/nginx/sites-enabled/thermosafe
sudo nginx -t
sudo systemctl reload nginx

echo "[7/7] Enabling and starting service..."
sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}"
sudo systemctl start "${SERVICE_NAME}"
sudo systemctl status "${SERVICE_NAME}" --no-pager

echo "Done. Test locally:"
echo "  curl -i http://127.0.0.1:5000/healthz"
echo "  curl -i http://127.0.0.1:5000/api/caminho -X POST -H 'Content-Type: application/json' -d '{"id":"TESTE","consumo":1.23}'"
echo "Test via public IP (ensure GCP firewall allows tcp:80):"
echo "  curl -i http://<IP_PUBLICO>/healthz"
echo "  curl -i http://<IP_PUBLICO>/api/caminho -X POST -H 'Content-Type: application/json' -d '{"id":"TESTE","consumo":1.23}'"
