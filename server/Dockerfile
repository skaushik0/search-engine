FROM python:latest

ADD requirements.txt /tmp
RUN pip3 install -r /tmp/requirements.txt
RUN python3 -m nltk.downloader stopwords

WORKDIR /usr/search-engine
COPY server.py .
COPY conf.json .

EXPOSE 80

CMD ["python3", "server.py"]
