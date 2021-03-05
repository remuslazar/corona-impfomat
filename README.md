# corona-impfomat

## Operational Logic

The app uses the Web-Scraping technology to interact with the `impfterminservice.de` page and check if there are corona vaccine appointments available. If so, it will send an email and also attach all relevant screenshots.

Because https://impfterminservice.de/ needs JavaScript and to ensure maximum compatibility, the app uses a recent
Chrome browser to perform the tasks.

## Configuration

```bash
cp .env.example .env
cp config-example.yml config.yml
vi .env
```

Edit `config.yml` and `.env`.


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

This will show something like:

```
Attaching to corona-impfomat_app_1
app_1  | Using URL: https://005-iz.impfterminservice.de/terminservice/suche/XXXX-XXXX-XXXX/XXXXX/L920
app_1  | 2021-02-03 19:45:21.845840+01:00 no appointments available
app_1  | 2021-02-03 19:47:00.159274+01:00 no appointments available
app_1  | 2021-02-03 19:48:38.365646+01:00 no appointments available
app_1  | 2021-02-03 19:50:16.293274+01:00 no appointments available
app_1  | 2021-02-03 19:51:54.236332+01:00 no appointments available
```

The service will exit after the first successful attempt.


Resources
----

* https://towardsdatascience.com/advanced-web-scraping-concepts-to-help-you-get-unstuck-17c0203de7ab
* https://grantwinney.com/websites-requesting-access-to-motion-sensors/
* https://gist.github.com/grantwinney/7e72df102373e721971edf09cde458ba
* https://github.com/infosimples/detect-headless
* https://intoli.com/blog/making-chrome-headless-undetectable/

Author
----

Remus Lazar