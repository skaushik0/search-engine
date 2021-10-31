#! /bin/bash

LB_IP=${SERVER:-"localhost:8080"}

sed -i "s/__LOAD_BALANCER_IP__/${LB_IP}/g" /usr/share/nginx/html/index.html

nginx -g "daemon off;"
