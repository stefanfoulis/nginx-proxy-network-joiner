FROM python:3.7-alpine
RUN mkdir -p /app
WORKDIR /app
COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt
COPY . /app/
ENTRYPOINT ["python", "dpnj.py"]
CMD ["sync", "--watch", "--proxy-name", "proxy", "--proxy-network-name", "proxy_overlay"]
