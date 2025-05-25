
## 🔐 Настройка HTTPS через Nginx и Let's Encrypt

1. Установите Nginx:
```bash
sudo apt update
sudo apt install nginx
```

2. Скопируйте конфиг в /etc/nginx/sites-available/air-alert:
```bash
sudo nano /etc/nginx/sites-available/air-alert
# вставьте содержимое из nginx.conf
```

3. Активируйте сайт:
```bash
sudo ln -s /etc/nginx/sites-available/air-alert /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

4. Установите certbot и получите сертификат:
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d alerts.example.com
```

5. Готово! Nginx проксирует запросы к FastAPI и обслуживает HTTPS.
