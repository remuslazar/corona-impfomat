#!/usr/bin/env python3

import argparse
from dataclasses import dataclass, is_dataclass
from typing import List

from selenium import webdriver
import time
import sys
import datetime
import os
import glob
import boto3
# noinspection PyPackageRequirements
import dateutil.tz
import yaml

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

from selenium.webdriver.chrome.webdriver import WebDriver
import json
from pyvirtualdisplay import Display
import re
from enum import Enum

screenshot_index = 1
display: Display

# SES and mail configuration
SENDER = os.environ.get('SENDER')
AWS_REGION = os.environ.get('SES_AWS_REGION')
CHARSET = "UTF-8"
OUT_PATH = "../out"


# see https://stackoverflow.com/questions/51564841/creating-nested-dataclass-objects-in-python
def nested_dataclass(*args, **kwargs):
    def wrapper(cls):
        cls = dataclass(cls, **kwargs)
        original_init = cls.__init__

        def __init__(self, *_args, **_kwargs):
            for name, value in _kwargs.items():
                field_type = cls.__annotations__.get(name, None)
                if is_dataclass(field_type) and isinstance(value, dict):
                    new_obj = field_type(**value)
                    _kwargs[name] = new_obj
            original_init(self, *_args, **_kwargs)

        cls.__init__ = __init__
        return cls

    return wrapper(args[0]) if args else wrapper


class ScheduleStatus(Enum):
    # initial status
    init = 'init'

    # an appointment has been scheduled
    scheduled = 'scheduled'

    # "appointments available" being detected, an email was sent to the user
    pending = 'pending'

    # no appointment case (default, initial one)
    no_appointment = 'no appointment'

    # error, e.g. 429 response and other errors not detected
    error = 'error'


@dataclass
class Address:
    postal_code: str = None
    salutation: str = None
    street: str = None
    street_no: str = None
    surname: str = None
    name: str = None
    city: str = None
    phone: str = None
    email: str = None


@nested_dataclass
class Party:
    name: str
    recipient: str
    address: Address
    url: str
    code: str = None
    postal_code: str = None
    age: int = None
    vaccine_code: str = None
    last_check_timestamp: datetime.datetime = None
    last_check_success: bool = None
    status: ScheduleStatus = ScheduleStatus.init
    last_error: Exception = None
    error_notification_sent: bool = False

    def update_status(self, new_status: ScheduleStatus, error: Exception = None):
        self.status = new_status
        if error:
            self.last_error = error

    def update_check_result(self, success: bool):
        self.last_check_success = success
        self.status = ScheduleStatus.pending if success else ScheduleStatus.no_appointment
        self.last_check_timestamp = get_timestamp()

    def last_check_duration(self):
        if self.last_check_timestamp is None:
            return None
        return get_timestamp() - self.last_check_timestamp

    @property
    def identifier(self):
        return re.sub('[^a-z]', '_', self.name.lower())


class Error(Exception):
    """Base class for exceptions in this module."""
    pass


class ErrorAlreadyScheduled(Exception):
    pass


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


def send_mail(recipient: str, title: str, text: str = None, html: str = None, attachments: list = None) -> dict:
    """
    Send email to recipients. Sends one mail to all recipients.
    The sender needs to be a verified email in SES.
    """

    text += """

-- 
Corona Impf-o-mat
"""
    msg = create_multipart_message(SENDER, [recipient], title, text, html, attachments)
    ses_client = boto3.client('ses')  # Use your settings here
    print(f'will send an email to {recipient} from {SENDER}')
    return ses_client.send_raw_email(
        Source=SENDER,
        Destinations=[recipient],
        RawMessage={'Data': msg.as_string()}
    )


def start_display():
    global display
    display = Display(visible=True, size=(800, 600), backend="xvfb")
    display.start()


def stop_display():
    display.stop()


def set_chrome_options():
    """Sets chrome options for Selenium.
    Chrome options for headless browser is enabled.
    """
    chrome_options = webdriver.ChromeOptions()
    # chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("window-size=923,1011")
    user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.72 " \
                 "Safari/537.36 "
    chrome_options.add_argument(f'user-agent={user_agent}')

    chrome_prefs = dict()
    chrome_options.experimental_options["prefs"] = chrome_prefs
    chrome_options.experimental_options["excludeSwitches"] = ["enable-automation"]
    chrome_options.experimental_options["useAutomationExtension"] = False
    chrome_prefs["profile.default_content_settings"] = {"images": 2}
    return chrome_options


def screenshot(_browser, filename=None):
    global screenshot_index
    if filename is None:
        filename = f'screenshot_{screenshot_index}'

    _browser.save_screenshot(f'{OUT_PATH}/{filename}.png')
    screenshot_index += 1


def get_timestamp():
    tz = dateutil.tz.gettz('Europe/Berlin')
    return datetime.datetime.now(tz)


def get_url(code, postal_code, url):
    if code:
        return f'{url}impftermine/suche/{code}/{postal_code}/'
    else:
        return f'{url}impftermine/service?plz={postal_code}'


def write_file(filename, text):
    file = open(f'{OUT_PATH}/{filename}', 'w')
    file.write(text)
    file.close()


def get_process_script():
    file = open(f'process.js')
    content = file.read()
    file.close()
    return content


def fetch_json_data(_browser: WebDriver):
    output = _browser.execute_async_script(get_process_script(), 'get_ersttermin_json')
    write_file('ersttermin.json', output)

    output = _browser.execute_async_script(get_process_script(), 'get_vaccination_list_json')
    write_file('vaccination-list.json', output)

    output = _browser.execute_async_script(get_process_script(), 'get_version')
    write_file('version.txt', output)


def check_429():
    console = json.dumps(browser.get_log('browser'))
    if "429" in console:
        # driver.execute_script("return localStorage.setItem('nfa-show-cinfo-20201110-VP1246', true)")
        write_file('console.log', console)
        raise Error(f'got 429 error')


def get_last_browser_error():
    logs = [log for log in browser.get_log('browser') if log['level'] == "SEVERE"]
    if len(logs) == 0:
        return None
    return logs.pop()['message']


def dismiss_cookie_banner():
    global browser
    if "Cookie Hinweis" in browser.page_source:
        browser.find_element_by_class_name("cookies-info-close").click()
        print('(accept cookies) ', end='')
        time.sleep(2)
        screenshot(browser)


def process(party):
    global browser

    # chrome_options = set_chrome_options()
    # driver = webdriver.Chrome(options=chrome_options)

    web_url = get_url(code=party.code, postal_code=party.postal_code, url=party.url)

    print(f'[{party.name}] #{party.status.value}', end=' ', flush=True)

    browser.get(web_url)

    time.sleep(1)

    # we will take screenshots from time to time, this being the initial one
    screenshot(browser)

    dismiss_cookie_banner()

    # check if the page is currently in maintenance mode
    if "Wartungsarbeiten" in browser.page_source:
        print('site is currently in maintenance mode')
        return False

    dismiss_cookie_banner()

    if "Virtueller Warteraum" in browser.page_source:
        timeout_sec = 600
        timeout_after = datetime.datetime.now() + datetime.timedelta(seconds=timeout_sec)
        print('[virtual delay] ', end='')
        while "Virtueller Warteraum" in browser.page_source:
            print('.', end='')
            time.sleep(3)
            if datetime.datetime.now() > timeout_after:
                raise Error(f'Timeout in the "Virtueller Warteraum" step has occurred (timeout={timeout_sec}s)')

        screenshot(browser)
        print(' ', end='')

    dismiss_cookie_banner()

    if party.code:
        # check if the challenge validation page is the current one (this should be the case, anyway)
        if "Challenge Validation" in browser.title:
            timeout_sec = 60
            timeout_after = datetime.datetime.now() + datetime.timedelta(seconds=timeout_sec)
            # wait for the "processing" page to disappear (we will be redirected to somewhere else after 30s
            while "Challenge Validation" in browser.title:
                print('.', end='')
                time.sleep(3)
                if datetime.datetime.now() > timeout_after:
                    raise Error(f'Timeout in the "Challenge Validation" step has occurred (timeout={timeout_sec}s)')

            screenshot(browser)
            print(' ', end='')

        dismiss_cookie_banner()

        if browser.current_url == f"{party.url}impftermine":
            print(f'(reload) ', end='')
            browser.get(web_url)
            time.sleep(1)
            screenshot(browser)

        if browser.current_url == f"{party.url}impftermine":
            raise Error(f'Unable to access the page {web_url}, being redirected to {browser.current_url}')

        # check if there is already an appointment scheduled for this code
        if "Ihr Termin am" in browser.page_source:
            for h2 in browser.find_elements_by_css_selector('h2.ets-booking-headline'):
                print(f'({h2.text}) ', end='')
            raise ErrorAlreadyScheduled(f'appointment already scheduled')

        dismiss_cookie_banner()

        # now we should see a page with a "wählen Sie bitte ein Terminpaar für Ihre Corona-Schutzimpfung" text
        if "Termine suchen" not in browser.page_source:
            raise Error(f'was expecting to see "Termine suchen" but this string was not found')

        # noinspection PyBroadException
        try:
            browser.find_element_by_css_selector("button.search-filter-button").click()

        except Exception:
            print(f'parsing error (button.search-filter-button not found)')
            return False

        time.sleep(5)
        screenshot(browser)

        # dismiss the cookie banner, else we will not be able to click on stuff behind it
        if "Cookie Hinweis" in browser.page_source:
            browser.find_element_by_class_name("cookies-info-close").click()
            time.sleep(1)
            screenshot(browser)

        print('=> ', end='')

        screenshot(browser)

        if "leider keine Termine" in browser.page_source:
            print(f'no appointments available')
            return False

        elif "Termine werden gesucht" in browser.page_source:
            print(f'timeout')
            return False

        else:
            print(f'success: at least one appointment found.')
            write_file('form.html', browser.page_source)

            return True

    else:
        # dismiss the cookie banner, else we will not be able to click on stuff behind it
        if "Cookie Hinweis" in browser.page_source:
            browser.find_element_by_class_name("cookies-info-close").click()
            time.sleep(3)
        screenshot(browser)

        if browser.current_url == f"{party.url}impftermine":
            print(f'(reload) ', end='')
            browser.get(web_url)
            time.sleep(1)
            screenshot(browser)

        if browser.current_url == f"{party.url}impftermine":
            raise Error(f'Unable to access the page {web_url}, being redirected to {browser.current_url}')

        # now we should see a page with a "Wurde Ihr Anspruch auf .." text
        if "Wurde Ihr Anspruch" not in browser.page_source:
            raise Error(f'was expecting to see "Wurde Ihr Anspruch" but this string was not found')

        # click on "Nein"
        browser.find_element_by_css_selector('app-corona-vaccination > div:nth-child(2) > div > div > '
                                             'label:nth-child(2) > span').click()
        # wait some time
        time.sleep(5)
        screenshot(browser)

        print('=> ', end='')

        if "Es wurden keine freien" in browser.page_source:
            print(f'no appointments available (1)')
            return False

        if "Folgende Personen" not in browser.page_source:
            raise Error(f'was expecting to see "Folgende Personen" but this string was not found')

        if "Gehören Sie" not in browser.page_source:
            raise Error(f'was expecting to see "Gehören Sie..." but this string was not found')

        browser.find_element_by_css_selector('app-corona-vaccination > div:nth-child(3) > div > div > div > '
                                             'div.ets-login-form-section.in > div > app-corona-vaccination-no > '
                                             'form > div.form-group.d-flex.justify-content-center > div > div > '
                                             'label:nth-child(1) > span').click()

        age_str = f'{party.age}'
        browser.find_element_by_xpath(f"//input[@name='age']").send_keys(age_str)
        time.sleep(2)
        screenshot(browser)

        browser.find_element_by_css_selector('app-corona-vaccination-no > form > div:nth-child(4) > button').click()
        time.sleep(1)
        screenshot(browser)

        if "Es wurden keine freien Termine" in browser.page_source:
            print(f'no appointments available (2)')
            return False

        write_file('page.html', browser.page_source)
        print(f'Success: saved page source to page.html..')
        return True


def remove_screenshot_files():
    global screenshot_index

    files = glob.glob(f'f{OUT_PATH}/screenshot_*.*')
    for f in files:
        os.remove(f)
    screenshot_index = 1


def get_config(config_file):
    with open(config_file) as file:
        data = yaml.full_load(file)
        return data


browser: WebDriver


def setup_browser():
    global browser

    chrome_options = set_chrome_options()
    browser = webdriver.Chrome(options=chrome_options)


def main():
    parser = argparse.ArgumentParser(description='Corona Impf-o-mat')
    parser.add_argument('--config', help="Path to the configuration file. See documentation for details.",
                        default="config.yml")
    parser.add_argument('--retry', help="Retry time in seconds, 0 to disable", type=int, default=0)
    parser.add_argument('--test-mail', help="Just send a mail for testing")

    args = parser.parse_args()

    if args.test_mail:
        recipient = args.test_mail
        send_mail(recipient,
                  'Test Mail',
                  f"""This is just a test.
                                    
If you can read this text, everything is just fine!
""",
                  None,
                  None)
        sys.exit()

    config_file = os.path.join(os.path.dirname(__file__), '..', args.config)
    config = get_config(config_file)

    admin_email = config['admin_email']
    parties: List[Party] = [Party(**party) for party in config['parties']]

    remove_screenshot_files()

    global browser
    start_display()
    setup_browser()

    print(f"Using Chrome Browser v{browser.capabilities['browserVersion']}")

    while True:
        for party in parties:

            # if the last check was successful, skip processing for 20 minutes
            if party.status == ScheduleStatus.pending and party.last_check_duration().seconds < 20 * 60:
                continue

            # if the party has already a valid schedule, skip the processing for 2 hours
            if party.status == ScheduleStatus.scheduled and party.last_check_duration().seconds < 2 * 60 * 60:
                continue

            # if the party is in the error state for longer than 30 minutes, send an
            # admin notification.
            if (party.status == ScheduleStatus.error
                    and party.last_check_timestamp is not None
                    and party.last_check_duration().seconds > 30 * 60
                    and not party.error_notification_sent):
                if admin_email:
                    files = glob.glob(f'{OUT_PATH}/*.*')
                    send_mail(admin_email,
                              f'Corona Impf-o-mat :: Error ({party.name})',
                              f"""There were persistent errors.                              

Party: {party.name}
Code: {party.code}
Postal Code: {party.postal_code}

Error (last check at {party.last_check_timestamp}):
----

{party.last_error}

""",
                              None,
                              files)

                    party.error_notification_sent = True
                    for file in files:
                        os.remove(file)

            web_url = get_url(code=party.code,
                              postal_code=party.postal_code,
                              url=party.url)

            remove_screenshot_files()
            try:
                success = process(party)
                old_status = party.status

                if old_status == ScheduleStatus.error and party.error_notification_sent:
                    if admin_email:
                        party.error_notification_sent = False
                        send_mail(admin_email,
                                  f'Corona Impf-o-mat :: Recovery ({party.name})',
                                  f"""This is a recovery notification
                                  
Party: {party.name}
Last successful check timestamp: {party.last_check_timestamp}

""")

                party.update_check_result(success)

                if success:
                    send_mail(
                        party.recipient,
                        f'Corona Impf-o-mat :: Notification',
                        f"""Corona vaccines are currently available, see the attached screenshots.

Profile Name: {party.name}
Reservation Code: {party.code}

To book an appointment, use this URL:

<{web_url}>

""",
                        None,
                        glob.glob(f'{OUT_PATH}/screenshot_*.*'))

            except ErrorAlreadyScheduled as e:
                print(e)
                party.update_status(ScheduleStatus.scheduled)

            except Error as error:
                party.update_status(ScheduleStatus.error, error=error)
                print(error)
                last_error = get_last_browser_error()
                if last_error:
                    print(last_error)
                    if "429" in last_error:
                        print(f'Got 429 error: reset browser and wait 2 minutes')
                        browser.close()
                        time.sleep(2 * 60)
                        setup_browser()

            except Exception as e:
                ts_string = get_timestamp().strftime('%Y%m%d%H%M%S')
                write_file(f'error-{ts_string}-console.log', json.dumps(browser.get_log('browser')))
                print(f"Got an error while trying to parse the page, "
                      f"will save the screenshot and page source to error-{ts_string}-*")
                screenshot(browser, f'error-{ts_string}-screenshot')
                write_file(f'error-{ts_string}-pagesource.html', browser.page_source)

                files = glob.glob(f'{OUT_PATH}/error-{ts_string}*')
                if admin_email:
                    send_mail(admin_email,
                              f'Corona Impf-o-mat :: Error ({party.name})',
                              f"""There were errors while interacting with the URL <{web_url}> :
Party: {party.name}
Code: {party.code}
Postal Code: {party.postal_code}

Error
----

{e}

""",
                              None,
                              files)

                    for file in files:
                        os.remove(file)

            finally:
                write_file(f'console_{party.identifier}.json', json.dumps(browser.get_log('browser')))
                write_file(f'cookies_{party.identifier}.json', json.dumps(browser.get_cookies()))

                # wait a short while before processing the next party
                time.sleep(10)

        if args.retry == 0:
            break

        time.sleep(args.retry)


if __name__ == '__main__':
    main()
