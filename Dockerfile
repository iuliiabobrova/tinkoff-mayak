FROM python:3.8

ENV PYTHONUNBUFFERED=1

RUN mkdir /code
WORKDIR /code

COPY requirements.txt /code/
RUN pip install --upgrade pip --default-timeout=100
RUN pip install -r --default-timeout=100 requirements.txt

COPY . /code/
