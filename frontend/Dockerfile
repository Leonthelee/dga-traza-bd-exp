# Dockerfile — DGA Módulo de Oposiciones Frontend
# Servidor web Nginx Alpine ultraligero y seguro (Kit Digital Gob.cl 2026)
FROM nginx:alpine

# Copiar configuración Nginx con reverse proxy y cabeceras OWASP
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

# Copiar archivos estáticos desacoplados (HTML, CSS, JS)
COPY frontend/index.html /usr/share/nginx/html/index.html
COPY frontend/css /usr/share/nginx/html/css
COPY frontend/js /usr/share/nginx/html/js

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
