FROM python:3.7.6-buster

ENV docker_path=/data
ADD ./ ./ 
RUN pip3 install -r requirements.txt
CMD ["python3", "main.py"]

