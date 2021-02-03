# corona-impfomat

## Operational Logic

The app uses web-scrapping tools to interact with the `impfterminservice.de` page and check if there are corona vaccine appointments available. If so, it will send an email and also attach all relevant screenshots. 

## Configuration

```bash
cp .env.example .env
vi .env
```

.. configure valid AWS Credentials here and configure valid email addresses.

## Run App in Docker

Because this app uses Selenium and Chrome, a docker based environment is required.

```bash
docker-compose run --rm app
```

To rebuild the docker image, do:

```bash
docker-compose build app
```

## Run as a service

When doing a `docker-compose up` this app will run in a service mode.
You need to supply valid parameter in your .env file, the docker-compose will
use that to configure the app accordingly.

When running as a service, the app will do a retry every 60 seconds and will just exit after the first successful attempt.

```sh
docker-compose up -d 
```

You can monitor the progress using

```shell
docker-compose logs -f
```


Author
----

Remus Lazar