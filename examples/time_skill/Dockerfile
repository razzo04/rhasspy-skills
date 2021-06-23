FROM python:3.8.10-alpine

RUN mkdir /app
WORKDIR /app

COPY requirements.txt /
RUN pip install -r /requirements.txt

RUN addgroup rhasspy-app \
    && adduser rhasspy-app --disabled-password --no-create-home --ingroup rhasspy-app \
    && chown -R rhasspy-app /app
USER rhasspy-app

COPY time_app.py /app 

CMD [ "python3","/app/time_app.py" ]
