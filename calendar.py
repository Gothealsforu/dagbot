import pytz, icalendar
from urllib2 import urlopen
from datetime import datetime, timedelta
from collections import namedtuple

Event = namedtuple('Event', ['start', 'end', 'summary'])

def get_raw_events(url):
    file = urlopen(url)
    contents = file.read()
    file.close()
    return contents

def sanitize_dt(dt):
    # Assume UTC for non tz aware events
    newdt = dt if hasattr(dt, 'hour') else datetime.combine(dt, datetime.min.time()).replace(tzinfo=pytz.UTC)
    newdt = newdt if newdt.tzinfo != None else newdt.replace(tzinfo=pytz.UTC)
    return newdt

# Conservative delta used. No event should be longer than 1 week.
def prune_event_start(start_time, utc_now):
    delta = utc_now - sanitize_dt(start_time)
    return delta > timedelta(weeks=1)

def prune_event_end(end_time, utc_now):
    return sanitize_dt(end_time) < utc_now

def prune_event(event, utc_now, start, end):
    return not hasattr(start.dt, 'hour') or prune_event_start(start.dt, utc_now) or (end and prune_event_end(end.dt, utc_now))

def prune_past_events(ics_events, now):
    utc_now = now.replace(tzinfo=pytz.UTC)
    events = []
    for component in ics_events.walk():
            if component.name == "VEVENT":
                start = component.get('dtstart')
                end = component.get('dtend')
                if prune_event(component, utc_now, start, end):
                    continue
                events.append(Event(sanitize_dt(start.dt), sanitize_dt(end.dt) if end else None, component.get('summary')))
    return events

def closest_event(events, event_type_end):
    deltas = []
    utc_now = sanitize_dt(datetime.utcnow())
    for event in events:
        delta = event.start - utc_now
        if (event.summary.lower().endswith(event_type_end) and delta > timedelta(microseconds=0)):
            deltas.append((event, delta))
    deltas.sort(key=lambda x: x[1])
    if (len(deltas) == 0):
        return None
    return deltas[0]

def in_event(events, default_event_duration):
    utc_now = sanitize_dt(datetime.utcnow())
    for event in events:
        end = event.end if event.end else event.start + default_event_duration
        if event.start < utc_now and utc_now < end:
            return True
    return False

class Calendar(object):
    update_interval = timedelta(days=1)
    default_event_duration = timedelta(minutes=90)
    def __init__(self, calendar_url):
        self.calendar_url = calendar_url
        self.last_updated = datetime.min
        self.events = []
        self.__update_calendar()

    def __update_calendar(self):
            if datetime.utcnow() - self.last_updated > self.update_interval:
                self.__get_new_calendar()

    def __get_new_calendar(self):
        self.last_updated = datetime.utcnow()
        self.events = prune_past_events(icalendar.Calendar.from_ical(get_raw_events(self.calendar_url)), self.last_updated)

    def __get_events(self):
        self.__update_calendar()
        return self.events

    def closest_event(self, event_end_filter):
        return closest_event(self.__get_events(), event_end_filter)

    def in_event(self):
        return in_event(self.__get_events(), self.default_event_duration)