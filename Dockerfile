# syntax=docker/dockerfile:1

FROM python:3.8-slim-buster

RUN pip3 install k8s-workload-restarter==0.0.10

CMD [ "python3", "-m", "k8s-workload-restarter"]