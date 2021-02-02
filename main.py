#!/usr/bin/env python3

import argparse

from selenium.webdriver.chrome.options import Options
from selenium import webdriver

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


def process(code, postal_code, url, vaccine_code):
    chrome_options = set_chrome_options()
    driver = webdriver.Chrome(options=chrome_options)


    web_url=f'{url}terminservice/suche/{code}/{postal_code}/{vaccine_code}'
    print(f'Fetching data from {web_url} ..')

    # Do stuff with your driver
    driver.get(web_url)
    screenshot = driver.save_screenshot('out/test.png')

    driver.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Corona Impf-o-mat')
    parser.add_argument('--code', help="Corona Vermittlungscode", required=True)
    parser.add_argument('--postal-code', help="German Postal Code", required=True)
    parser.add_argument('--url', help="Service-URL", default="https://005-iz.impfterminservice.de/")
    parser.add_argument('--vaccine-code', help="Corona Vaccine Code (L920 for BioNTech, L921 for Moderna)", default="L920")
    args = parser.parse_args()

    process(args.code, args.postal_code, args.url, args.vaccine_code)
