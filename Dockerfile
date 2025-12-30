# stage 1: build the extension
FROM python:alpine AS builder

WORKDIR /extension

RUN apk add git

RUN git clone https://github.com/collinsmarra/Quart-HTTPAuth.git .

RUN pip install --root-user-action=ignore build

RUN python -m build

# stage 2: runtime
FROM python:alpine AS runtime

WORKDIR /app

COPY --from=builder /extension/dist/*.whl /extension/

RUN pip install --root-user-action=ignore /extension/*.whl

RUN rm -rf /extension

COPY . .

RUN pip install --root-user-action=ignore -r requirements.txt

EXPOSE 80

ENV PYTHONUNBUFFERED=1

RUN mv /app/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]