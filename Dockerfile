# see https://nander.cc/using-selenium-within-a-docker-container
FROM python:3.8

# Adding trusting keys to apt for repositories
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -

# Adding Google Chrome to the repositories
RUN sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list'

# Install chrome and unzip
RUN apt-get -y update \
  && apt-get install -y google-chrome-stable \
  && apt-get install -yqq unzip \
  && rm -rf /var/lib/apt/lists/*

# Install xvfb and xserver
RUN apt-get -y update \
  && apt-get install -y xvfb xserver-xephyr tigervnc-standalone-server xfonts-base \
  && rm -rf /var/lib/apt/lists/*

# Download and install the Chrome Driver
RUN wget -O /tmp/chromedriver.zip http://chromedriver.storage.googleapis.com/$(curl -sS chromedriver.storage.googleapis.com/LATEST_RELEASE)/chromedriver_linux64.zip \
  && unzip /tmp/chromedriver.zip chromedriver -d /usr/local/bin/ \
  && rm -f /tmp/chromedriver.zip

# Set display port as an environment variable
ENV DISPLAY=:99

WORKDIR /app
COPY ./requirements.txt ./

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# We do not need that because of the volume mapping in docker-compose.yml
#COPY ./src ./

WORKDIR /app/src
ENTRYPOINT ["python", "./main.py"]