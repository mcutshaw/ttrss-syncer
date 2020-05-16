FROM python:3.7.6-buster
RUN mkdir /app
COPY . /app
WORKDIR /app
RUN pip3 install bs4
RUN pip3 install ttrss-python
RUN pip3 install webdavclient3
RUN pip3 install timeout_decorator
CMD python main.py
