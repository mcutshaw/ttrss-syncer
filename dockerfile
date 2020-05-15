FROM python:3.7.6-buster

ENV docker_path=/data
ADD requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

