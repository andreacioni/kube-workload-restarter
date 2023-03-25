FROM golang:1.20.2

WORKDIR /usr/src/app

COPY src/main.go go.mod go.sum ./

RUN go mod download && go mod verify

RUN go build -v -o /usr/local/bin/app 

CMD ["app"]