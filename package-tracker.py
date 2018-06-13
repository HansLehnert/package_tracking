"""Script for tracking and alerting about package status."""

import requests
import bs4
import json
import sys
import smtplib
from datetime import datetime
from email.message import EmailMessage


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

    soup = bs4.BeautifulSoup(tracking_page.content, 'html.parser')
    table = soup.find(attrs={'class': 'tracking'})

    updates = {}
    for row in table.find_all('tr'):
        values = [cell.string.strip() for cell in row.find_all('td')]

        if len(values) != 3:
            continue

        date = datetime.strptime(values[1], '%d/%m/%Y %H:%M')
        updates[date] = {
            'status': values[0].capitalize(),
            'location': values[2].capitalize()
        }

    return updates


def main(argv):
    settings = None
    try:
        settings_file = open('settings.json', 'r')
        settings = json.load(settings_file)
        settings_file.close()
    except IOError:
        print('Missing configuration file "settings.json"')
        return

    tracking_log = {}
    try:
        log_file = open('log.json', 'r')
        tracking_log = json.load(log_file)
        log_file.close()
    except IOError:
        pass

    tracking_updates = {}

    # Check for updates
    for number in settings['tracking_numbers']:
        if number not in tracking_log:
            tracking_log[number] = {
                'last_check': None,
                'last_update': None,
                'updates': {}
            }
        entry = tracking_log[number]

        # Get info from tracking website
        updates = track_correoschile(number)

        # Check if new updates have been made
        try:
            last_update = datetime.strptime(
                entry['last_update'], TIMESTAMP_FORMAT)
        except TypeError:
            last_update = None

        for x in updates:
            if last_update is None or x > last_update:
                if number not in tracking_updates:
                    tracking_updates[number] = []

                tracking_updates[number].append((x, updates[x]['status']))

        # Update entry in the log
        entry['last_check'] = datetime.now().strftime(TIMESTAMP_FORMAT)
        entry['updates'].update(
            {x.strftime(TIMESTAMP_FORMAT): updates[x] for x in updates})
        entry['last_update'] = max(updates.keys()).strftime(TIMESTAMP_FORMAT)

    # Write updated log file
    log_file = open('log.json', 'w')
    json.dump(tracking_log, log_file, indent=4)
    log_file.close()

    # Send updates
    if len(tracking_updates) > 0:
        with smtplib.SMTP(settings['email']['smtp_server']) as smtp:
            smtp.login(
                settings['email']['user'],
                settings['email']['password'],
            )

            msg = EmailMessage()
            msg['From'] = 'Package Tracking <{}>'.format(
                settings['email']['sender'])
            msg['To'] = settings['email']['receiver']
            msg['Subject'] = 'New tracking updates'

            message_body = '<p>Updates since last check:</p>'
            for number in tracking_updates:
                message_body += '<p>{}</p>'.format(number)
                message_body += '<ul>'
                for update in tracking_updates[number]:
                    message_body += '<li>'
                    message_body += '<b>{}</b> {}'.format(
                        update[0].strftime('%c'), update[1])
                    message_body += '</li>'
                message_body += '</ul>'

            msg.set_content(message_body, subtype='html')

            smtp.send_message(
                msg,
                settings['email']['sender'],
                settings['email']['receiver']
            )


if __name__ == '__main__':
    main(sys.argv)