#!/usr/bin/env python3

import argparse

from selenium.webdriver.chrome.options import Options
from selenium import webdriver
import time
import sys
import datetime
import os
import glob
import boto3
import dateutil.tz

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

screenshot_index = 1

# SES and mail configuration
SENDER = os.environ.get('SENDER')
RECIPIENT = os.environ.get('RECIPIENT')
AWS_REGION = os.environ.get('SES_AWS_REGION')
CHARSET = "UTF-8"


def create_multipart_message(
        sender: str, recipients: list, title: str, text: str = None, html: str = None, attachments: list = None) \
        -> MIMEMultipart:
    """
    Creates a MIME multipart message object.
    Uses only the Python `email` standard library.
    Emails, both sender and recipients, can be just the email string or have the format 'The Name <the_email@host.com>'.

    :param sender: The sender.
    :param recipients: List of recipients. Needs to be a list, even if only one recipient.
    :param title: The title of the email.
    :param text: The text version of the email body (optional).
    :param html: The html version of the email body (optional).
    :param attachments: List of files to attach in the email.
    :return: A `MIMEMultipart` to be used to send the email.
    """
    multipart_content_subtype = 'alternative' if text and html else 'mixed'
    msg = MIMEMultipart(multipart_content_subtype)
    msg['Subject'] = title
    msg['From'] = sender
    msg['To'] = ', '.join(recipients)

    # Record the MIME types of both parts - text/plain and text/html.
    # According to RFC 2046, the last part of a multipart message, in this case the HTML message, is best and preferred.
    if text:
        part = MIMEText(text, 'plain')
        msg.attach(part)
    if html:
        part = MIMEText(html, 'html')
        msg.attach(part)

    # Add attachments
    for attachment in attachments or []:
        with open(attachment, 'rb') as f:
            part = MIMEApplication(f.read())
            part.add_header('Content-Disposition', 'attachment', filename=os.path.basename(attachment))
            msg.attach(part)

    return msg


def send_mail(
        title: str, text: str = None, html: str = None, attachments: list = None) -> dict:
    """
    Send email to recipients. Sends one mail to all recipients.
    The sender needs to be a verified email in SES.
    """
    msg = create_multipart_message(SENDER, [RECIPIENT], title, text, html, attachments)
    ses_client = boto3.client('ses')  # Use your settings here
    return ses_client.send_raw_email(
        Source=SENDER,
        Destinations=[RECIPIENT],
        RawMessage={'Data': msg.as_string()}
    )


def set_chrome_options():
    """Sets chrome options for Selenium.
    Chrome options for headless browser is enabled.
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_prefs = dict()
    chrome_options.experimental_options["prefs"] = chrome_prefs
    chrome_prefs["profile.default_content_settings"] = {"images": 2}
    return chrome_options


def screenshot(driver):
    global screenshot_index

    driver.save_screenshot(f'out/test{screenshot_index}.png')
    screenshot_index += 1


def get_timestamp():
    tz = dateutil.tz.gettz('Europe/Berlin')
    return datetime.datetime.now(tz)


def get_url(code, postal_code, url, vaccine_code):
    return f'{url}terminservice/suche/{code}/{postal_code}/{vaccine_code}'


def write_file(filename, text):
    file = open(filename, 'w')
    file.write(text)
    file.close()


def process(code, postal_code, url, vaccine_code):
    chrome_options = set_chrome_options()
    driver = webdriver.Chrome(options=chrome_options)

    web_url = get_url(code=code, postal_code=postal_code, url=url, vaccine_code=vaccine_code)

    print(get_timestamp(), end=' ', flush=True)

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
    filename = 'corona.html'

    if "leider keine Termine" in driver.page_source:
        text = driver.find_element_by_class_name("ets-search-no-results").text
        write_file('no-appointments-text.txt', text)
        print(f'no appointments available')
    else:
        if "Gefundene Termine" in driver.page_source:
            screenshot(driver)
            driver.find_element_by_class_name('ets-slot-button').click()
            print(f'Success: at least one appointment found')
            success = True

        else:
            print(f'Unexpected state, will save the page source as {filename}')

        write_file(filename, driver.page_source)

    screenshot(driver)

    driver.close()
    return success


def remove_screenshot_files():
    files = glob.glob('/out/*.*')
    for f in files:
        os.remove(f)


def main():
    parser = argparse.ArgumentParser(description='Corona Impf-o-mat')
    parser.add_argument('--code', help="Corona Vermittlungscode", required=True)
    parser.add_argument('--postal-code', help="German Postal Code", required=True)
    parser.add_argument('--url', help="Service-URL", default="https://005-iz.impfterminservice.de/")
    parser.add_argument('--vaccine-code', help="Corona Vaccine Code (L920 for BioNTech, L921 for Moderna)",
                        default="L920")
    parser.add_argument('--retry', help="Retry time in seconds, 0 to disable", type=int, default=0)
    parser.add_argument('--test-mail', help="Just send a mail for testing", action='store_true')

    args = parser.parse_args()

    if args.test_mail:
        print(f'Will send an email to {SENDER}.')
        send_mail('Test Mail',
                  'This is just a test. If you can read this text, everything is just fine!',
                  None,
                  None)
        sys.exit()

    web_url = get_url(code=args.code,
                      postal_code=args.postal_code,
                      url=args.url,
                      vaccine_code=args.vaccine_code)

    print(f'Using URL: {web_url}')

    while True:
        remove_screenshot_files()
        success = process(args.code, args.postal_code, args.url, args.vaccine_code)

        if success:
            send_mail('Corona Impf-o-mat :: Notification',
                      f'Corona vaccines are currently available, see the attached screenshots.'
                      f''
                      f'To book an appointment, use this URL:'
                      f''
                      f'<{web_url}>'
                      f''
                      f'-- '
                      f'Corona Impf-o-mat',
                      None,
                      glob.glob('out/*.*'))
            break

        if args.retry == 0: break
        time.sleep(args.retry)

    sys.exit(0 if success else 10)


if __name__ == '__main__':
    main()
