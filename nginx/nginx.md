## HTTPS via Nginx + Let's Encrypt

1. Install Nginx:

```bash
sudo apt update
sudo apt install nginx
```

2. Copy the config:

```bash
sudo cp nginx/nginx.conf /etc/nginx/sites-available/air-alert
# set your real server_name first
sudo ln -s /etc/nginx/sites-available/air-alert /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

3. Issue a certificate:

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.example.com
```

Nginx proxies requests to FastAPI on `127.0.0.1:8000`.
