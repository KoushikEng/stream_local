FROM python:alpine

WORKDIR /app

COPY . .

RUN pip install --root-user-action=ignore -r requirements.txt

EXPOSE 80

ENV PYTHONUNBUFFERED=1

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]