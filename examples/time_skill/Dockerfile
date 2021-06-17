FROM python:3.8.10-alpine

COPY requirements.txt /

RUN pip install -r /requirements.txt

COPY time_app.py time_app.py 

CMD [ "python3","time_app.py" ]
