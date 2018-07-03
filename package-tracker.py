"""Script for tracking and alerting about package status."""

import requests
import bs4
import json
import sys
import smtplib
from datetime import datetime
from email.message import EmailMessage
from collections import defaultdict


TIMESTAMP_FORMAT = '%Y.%m.%d %H:%M'


def track_correoschile(tracking_number):
    """Get tracking information from CorreosChile website."""

    request_url = 'http://seguimientoweb.correos.cl/ConEnvCorreos.aspx'

    tracking_page = requests.post(
        request_url,
        params={
            'obj_key': 'Cor398-cc',  # key was hardcoded in the website
            'obj_env': tracking_number
        })

    tracking_info = {
        'updates': {},
        'delivered': False,
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


def email_updates(
        updates, smtp_server, sender, receiver,
        tls=True, user=None, password=None, **kwargs):
    """Send an email notification of package updates.

    'updates' is a dictionary where keys are the tracking numbers and the
    values is a list of (date, description) tuples.
    """

    with smtplib.SMTP(smtp_server) as smtp:
        if tls:
            smtp.starttls()

        if user is not None and password is not None:
            smtp.login(user, password)

        msg = EmailMessage()
        msg['From'] = 'Package Tracking <{}>'.format(sender)
        msg['To'] = receiver
        msg['Subject'] = 'New tracking updates'

        # Build message body
        message_body = '<p>Updates since last check:</p>'
        for number in updates:
            message_body += '<p>{}</p>'.format(number)
            message_body += '<ul>'
            for item in updates[number]:
                message_body += '<li><b>{}</b> {}</li>'.format(
                    item[0].strftime('%c'), item[1])
            message_body += '</ul>'
        msg.set_content(message_body, subtype='html')

        smtp.send_message(msg, sender, receiver)


def main(argv):
    # Load settings and log files
    try:
        with open('settings.json', 'r') as settings_file:
            settings = json.load(settings_file)
    except IOError:
        print('Missing configuration file "settings.json"')
        return

    try:
        with open('log.json', 'r') as log_file:
            tracking_log = json.load(log_file)
    except IOError:
        tracking_log = {}

    tracking_updates = defaultdict(list)

    # Check for updates
    for number in settings['tracking_numbers'][:]:
        # Create entry for new tracking number
        if number not in tracking_log:
            tracking_log[number] = {
                'last_check': None,
                'last_update': None,
                'delivered': False,
                'updates': {}
            }
        entry = tracking_log[number]

        # Get info from tracking website
        tracking_info = track_correoschile(number)
        updates = tracking_info['updates']

        # Update check time
        entry['last_check'] = datetime.now().strftime(TIMESTAMP_FORMAT)

        # Update package delivery
        entry['delivered'] = tracking_info['delivered']
        if entry['delivered'] and settings['autoremove']:
            tracking_updates['System'].append(
                (datetime.now(), 'Finished tracking {}'.format(number)))
            settings['tracking_numbers'].remove(number)

        # Check if new updates have been made
        if len(updates) == 0:
            continue

        try:
            last_update = datetime.strptime(
                entry['last_update'], TIMESTAMP_FORMAT)
        except TypeError:
            last_update = None

        for x in updates:
            if last_update is None or x > last_update:
                tracking_updates[number].append((x, updates[x]['status']))

        # Update entry in the log
        entry['updates'].update(
            {x.strftime(TIMESTAMP_FORMAT): updates[x] for x in updates})
        entry['last_update'] = max(updates.keys()).strftime(TIMESTAMP_FORMAT)

    # Write updated log and settings file
    with open('log.json', 'w') as log_file:
        json.dump(tracking_log, log_file, indent=4, sort_keys=True)

    with open('settings.json', 'w') as settings_file:
        json.dump(settings, settings_file, indent=4, sort_keys=True)

    # Send updates
    if len(tracking_updates) > 0 and settings['alert']:
        email_updates(tracking_updates, **settings['email'])


if __name__ == '__main__':
    main(sys.argv)
