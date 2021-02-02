#!/usr/bin/env python3

import argparse

from selenium.webdriver.chrome.options import Options
from selenium import webdriver
import time
import sys
import datetime
import os

import boto3
from botocore.exceptions import ClientError

screenshot_index=1

# SES and mail configuration
SENDER = os.environ.get('SENDER')
RECIPIENT = os.environ.get('RECIPIENT')
AWS_REGION = os.environ.get('SES_AWS_REGION')
CHARSET = "UTF-8"

def send_mail(subject, body):
    client = boto3.client('ses', region_name=AWS_REGION)
    try:
        client.send_email(
            Destination={
                'ToAddresses': [
                    RECIPIENT,
                ],
            },
            Message={
                'Body': {
                    'Text': {
                        'Charset': CHARSET,
                        'Data': body,
                    },
                },
                'Subject': {
                    'Charset': CHARSET,
                    'Data': subject,
                },
            },
            Source=SENDER,
        )
    except ClientError as e:
        print(e.response['Error']['Message'])


def set_chrome_options():
    """Sets chrome options for Selenium.
    Chrome options for headless browser is enabled.
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_prefs = {}
    chrome_options.experimental_options["prefs"] = chrome_prefs
    chrome_prefs["profile.default_content_settings"] = {"images": 2}
    return chrome_options

def screenshot(driver):
    global screenshot_index

    driver.save_screenshot(f'out/test{screenshot_index}.png')
    screenshot_index += 1

def print_timestamp():
    print(datetime.datetime.utcnow())

def process(code, postal_code, url, vaccine_code):
    chrome_options = set_chrome_options()
    driver = webdriver.Chrome(options=chrome_options)

    web_url=f'{url}terminservice/suche/{code}/{postal_code}/{vaccine_code}'

    print()
    print_timestamp()

    print(f'Fetching data from {web_url} ..')

    # Do stuff with your driver
    driver.get(web_url)
    screenshot(driver)
    # print("Waiting for the 30 second banner to disappear..")

    time.sleep(35)
    screenshot(driver)

    # now we should see a page with a "termin suchen" button
    # print("Click on the big button")
    button = driver.find_element_by_class_name("kv-btn")
    button.click()
    time.sleep(1)

    # dismiss the cookie banner
    driver.find_element_by_class_name("cookies-info-close").click()

    success = False

    if "leider keine Termine" in driver.page_source:
        text = driver.find_element_by_class_name("ets-search-no-results").text
        print(text)
    else:
        print(driver.page_source)
        success=True

    screenshot(driver)

    driver.close()
    return success

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Corona Impf-o-mat')
    parser.add_argument('--code', help="Corona Vermittlungscode", required=True)
    parser.add_argument('--postal-code', help="German Postal Code", required=True)
    parser.add_argument('--url', help="Service-URL", default="https://005-iz.impfterminservice.de/")
    parser.add_argument('--vaccine-code', help="Corona Vaccine Code (L920 for BioNTech, L921 for Moderna)", default="L920")
    parser.add_argument('--test-mail', help="Just send a mail for testing", action='store_true')

    args = parser.parse_args()

    if (args.test_mail):
        print(f'Sending a mail to {SENDER} ..')
        send_mail('Test Mail', 'This is just a test. If you can read this text, everything is just fine!')
        sys.exit()

    success=process(args.code, args.postal_code, args.url, args.vaccine_code)
    sys.exit(0 if success else 10)
