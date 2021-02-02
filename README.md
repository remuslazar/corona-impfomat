# corona-impfomat

This app tries to get an corona vaccine appointment scheduled for given params. 

## Configuration

```bash
cp .env.example .env
vi .env
```

.. put valid AWS Credentials here

## Run App in Docker

Because this app uses Selenium and Chrome, a docker based environment is required.

```bash
docker-compose run app
```

To rebuild the docker image, do:

```bash
docker-compose build app
```