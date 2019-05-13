FROM python:3.6-alpine
RUN mkdir -p /app
WORKDIR /app
COPY requirements.txt /app/
RUN pip install -r requirements.txt
COPY . /app/
CMD ash
