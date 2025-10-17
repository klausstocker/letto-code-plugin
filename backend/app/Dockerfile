FROM python:3.13-slim

WORKDIR /usr/src/app

# set environment variables - has advantages for python in docker container
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# install python dependencies
RUN pip install --upgrade pip
COPY ./requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt

COPY ./src /usr/src/app/src

