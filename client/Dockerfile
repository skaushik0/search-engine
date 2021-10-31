FROM nginx:latest

COPY index.html /usr/share/nginx/html/index.html
COPY entrypoint.sh /usr/local/bin

EXPOSE 80

CMD ["/usr/local/bin/entrypoint.sh"]
