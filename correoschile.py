"""Utilities for tracking correoschile packages."""

import requests
import bs4
from datetime import datetime


def track(tracking_number):
    """Get tracking updates from CorreosChile website."""

    request_url = 'http://seguimientoweb.correos.cl/ConEnvCorreos.aspx'

    tracking_page = requests.post(
        request_url,
        params={
            'obj_key': 'Cor398-cc',  # key was hardcoded in the website
            'obj_env': tracking_number
        }
    )

    tracking_info = {
        'updates': {},
        'delivered': False,
        'url': (
            'https://www.correos.cl/SitePages/seguimiento/seguimiento.aspx'
            '?envio={}'.format(tracking_number)
        ),
    }

    soup = bs4.BeautifulSoup(tracking_page.content, 'html.parser')
    table = soup.find(class_='tracking')

    if table is not None:
        for row in table.find_all('tr'):
            values = [cell.string.strip() for cell in row.find_all('td')]

            if len(values) != 3:
                continue

            date = datetime.strptime(values[1], '%d/%m/%Y %H:%M')
            status = values[0].capitalize()
            location = values[2].capitalize()

            tracking_info['updates'][date] = {
                'status': status,
                'location': location
            }

            if status == 'Envio entregado':
                tracking_info['delivered'] = True

    return tracking_info
