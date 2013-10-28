#!/usr/bin/env python

from datetime import datetime, date, timedelta
import icalendar
import json
import pytz
import requests
import sys

class TimetableException(Exception):
    pass

def get_monday_date():
    today = date.today()
    days_offset = today.weekday()
    return today - timedelta(days_offset)

def get_event_datetime(date, time):
    time_parts = time.split(':')
    hour = int(time_parts[0])
    minute = int(time_parts[1])

    date_parts = date.split('-')
    day = int(date_parts[0])
    month = int(date_parts[1])
    year = int(date_parts[2])

    return datetime(year, month, day, hour, minute)

def main(argv):
    if len(argv) < 4:
        print 'Usage: %s <username> <password> <num_weeks> <ical_filename>' % sys.argv[0]
        return

    auth_data = {
        'username': argv[0],
        'password': argv[1]
    }
    num_weeks = int(argv[2])
    ical_filename = argv[3]

    cal = icalendar.Calendar()
    cal.add('prodid', '-//UCLan Timetable Importer//hexxeh.net//')
    cal.add('version', '2.0')

    import_date = datetime.now()
    current_week = get_monday_date()
    week_increment = timedelta(days=7)

    for week_number in xrange(0, num_weeks):
        date_str = '%d-%d-%d' % (current_week.day, current_week.month, current_week.year)
        print 'Importing week beginning %s' % date_str
        r = requests.get('https://uclan-apis.appspot.com/timetable/%s' % date_str, params=auth_data)
        timetable_json = r.json()

        if not 'status' in timetable_json:
            raise TimetableException('Malformed response from server')

        if timetable_json['status'] != 'ok':
            raise TimetableException('Bad status code: %s' % timetable_json['status'])

        for day in timetable_json['timetable']:
            for event in day['events']:
                description = event['tutor']
                if 'type' in event:
                    description = event['type'] + ' - ' + description

                cal_event = icalendar.Event()
                cal_event.add('summary', event['name'])
                cal_event.add('dtstart', get_event_datetime(day['date'], event['start_time']))
                cal_event.add('dtend', get_event_datetime(day['date'], event['finish_time']))
                cal_event.add('dtstamp', import_date)
                cal_event.add('location', event['room'])
                cal_event.add('description', description)

                cal.add_component(cal_event)

        current_week += week_increment

    with open(ical_filename, 'wb') as f:
        f.write(cal.to_ical())

if __name__ == '__main__':
    main(sys.argv[1:])