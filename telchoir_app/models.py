import datetime

from .database import db


class Recording(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    call_sid = db.Column(db.String(255))
    from_number = db.Column(db.String(255))
    note = db.Column(db.String(255))
    recording_url = db.Column(db.String(255))

    contact_ok = db.Column(db.Boolean)

    dt = db.Column(db.DateTime, default=datetime.datetime.now)


    def __init__(self, call_sid, from_number, note, recording_url=False, contact_ok=False):
        self.call_sid = call_sid
        self.from_number = from_number
        self.note = note
        self.recording_url = recording_url
        self.contact_ok = contact_ok

    def __repr__(self):
        return '<Story %r>' % self.recording_url
