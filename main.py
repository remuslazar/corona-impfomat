#!/usr/bin/env python3

import argparse
from pprint import pprint
import requests

def process(code, postal_code, url, vaccine_code):
    session = requests.Session()

    web_url=f'{url}terminservice/suche/{code}/{postal_code}/{vaccine_code}'

    print(f'Fetching data from {web_url} ..')
    response = session.get(web_url)

    print(response.text)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Corona Impf-o-mat')
    parser.add_argument('--code', help="Corona Vermittlungscode", required=True)
    parser.add_argument('--postal-code', help="German Postal Code", required=True)
    parser.add_argument('--url', help="Service-URL", default="https://005-iz.impfterminservice.de/")
    parser.add_argument('--vaccine-code', help="Corona Vaccine Code (L920 for BioNTech, L921 for Moderna)", default="L920")
    args = parser.parse_args()

    process(args.code, args.postal_code, args.url, args.vaccine_code)
