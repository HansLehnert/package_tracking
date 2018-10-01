"""Tracking and alerting about package status."""

import json
import sys
import smtplib
import argparse
from datetime import datetime
from email.message import EmailMessage
from collections import defaultdict

import correoschile


TIMESTAMP_FORMAT = '%Y.%m.%d %H:%M'


def email_updates(
        updates, smtp_server, sender, receiver,
        tls=True, user=None, password=None, **kwargs):
    """Send an email notification of package updates.

    'updates' is a dictionary where keys are the tracking numbers and the
    values is a list of (date, description) tuples.
    """

    # Build message body
    message_body = '<p>Updates since last check:</p>'
    for category in updates:
        # Catergory title
        message_body += '<p>'
        if type(category) is tuple:
            message_body += '<a href={1}>{0}</a>'.format(*category)
        else:
            message_body += category
        message_body += '</p>'

        # Items
        message_body += '<ul>'
        for item in updates[category]:
            message_body += '<li>'
            message_body += '<b>{}</b> {} '.format(
                item['time'].strftime('%c'), item['status'])
            if 'location' in item:
                message_body += '<i>({})</i>'.format(item['location'])
            message_body += '</li>'
        message_body += '</ul>'

    # Send message
    with smtplib.SMTP(smtp_server) as smtp:
        if tls:
            smtp.starttls()

        if user is not None and password is not None:
            smtp.login(user, password)

        msg = EmailMessage()
        msg['From'] = 'Package Tracking <{}>'.format(sender)
        msg['To'] = receiver
        msg['Subject'] = 'New tracking updates'

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

    # Argument parser
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest='command', title='commands')
    track_parser = subparsers.add_parser('track', help='add a tracking number')
    track_parser.add_argument('tracking_number')
    args = parser.parse_args(argv)

    # Add tracking number (if the 'track' command was selected)
    # TODO: Move to separate function
    if args.command == 'track':
        settings['tracking_numbers'].append(args.tracking_number)

    # Check for updates
    tracking_updates = defaultdict(list)

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
        tracking_info = correoschile.track(number)
        updates = tracking_info['updates']

        # Update check time
        entry['last_check'] = datetime.now().strftime(TIMESTAMP_FORMAT)

        # Remove from settings if package has been delivered
        entry['delivered'] = tracking_info['delivered']
        if entry['delivered'] and settings['autoremove']:
            new_update = {
                'time': datetime.now(),
                'status': 'Finished tracking {}'.format(number),
            }

            tracking_updates['System'].append(new_update)
            settings['tracking_numbers'].remove(number)

        # Check if new updates have been made
        if len(updates) == 0:
            continue

        try:
            last_update = datetime.strptime(
                entry['last_update'], TIMESTAMP_FORMAT)
        except TypeError:
            last_update = None

        for time, status in updates.items():
            category = (number, tracking_info['url'])
            if last_update is None or time > last_update:
                new_update = dict(status)
                new_update['time'] = time
                tracking_updates[category].append(new_update)

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
    main(sys.argv[1:])
