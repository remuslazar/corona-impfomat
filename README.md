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

## Run unattended (e.g. in screen)

Exit code is 0 when there are vaccine appointments available. So doing
a simple while loop the operation can be re-tried automatically:

```sh
while ! docker-compose run --rm app --postal-code xxx --code xxx ; do sleep 300 ; done
```


Author
----

Remus Lazar