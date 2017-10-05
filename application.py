from flask import flash, redirect, request, render_template, Response, session
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
from sqlalchemy.sql.expression import func
from sqlalchemy.exc import StatementError
import twilio.twiml
from twilio.rest import TwilioRestClient

import importlib
import random

from telchoir_app import create_app
from telchoir_app import config
from telchoir_app.models import Recording
from telchoir_app.database import db

application = create_app()
APP_URL = config.CONFIG_VARS['APP_URL']
#TODO: Move this to config later, update server-specific config file
FILE_URL = 'http://ottomata.org/tel-choir-static/'


@application.route("/")
def index():

    return render_template('index.html')

# this is where the twilio number should be configured to hit first
@application.route("/incoming-call", methods=['GET', 'POST'])
def incoming_call():

    resp = twilio.twiml.Response()
    gather = twilio.twiml.Gather(input='dtmf', timeout=3, numDigits=1, action="/listen-or-record")

    gather.play(FILE_URL+'/intro2.mp3')
    gather.play(FILE_URL+'/listen-or-record.mp3')
    resp.append(gather)
    resp.gather(numDigits=1, action="/listen-or-record", method="POST", timeout=60)

    return str(resp)

@application.route("/listen-or-record", methods=['GET', 'POST'])
def listen_or_record():

    pressed = request.values.get('Digits', None)
    resp = twilio.twiml.Response()

    if pressed == '1':
        gather = twilio.twiml.Gather(input='dtmf', timeout=3, numDigits=1, action="/listen-or-record")

        resp.pause(length=2)
        resp.say('Welcome to your music mailbox. You have one message. First message.')
        resp.play(FILE_URL+'/pat-dennis_2.mp3')
        resp.pause(length=1)
        gather.say('End of message. To hear this message again, press one. To record a new note, press two. Otherwise, call back soon to hear new music.')
        resp.append(gather)
        resp.gather(numDigits=1, action="/listen-or-record", method="POST", timeout=30)

        return str(resp)

    elif pressed == '2':
        gather = twilio.twiml.Gather(input='dtmf', timeout=3, numDigits=1, action="/instructions")

        resp.pause(length=1)
        gather.play(FILE_URL+'/decision_1a.mp3')
        resp.append(gather)
        resp.gather(numDigits=1, action="/instructions", method="POST", timeout=60)

        return str(resp)

    else:
        gather = twilio.twiml.Gather(input='dtmf', timeout=3, numDigits=1, action="/listen-or-record")

        gather.play(FILE_URL+'/listen-or-record.mp3')
        resp.append(gather)
        resp.gather(numDigits=1, action="/listen-or-record", method="POST", timeout=60)

        return str(resp)

# this is where the random note is selected and assigned, depending on which octave people want to sing in
#TODO: Check if this is the right way to say this:
# and where a new db session is initialized

@application.route("/instructions", methods=['GET', 'POST'])
def instructions():

    pressed = request.values.get('Digits', None)
    call_sid = request.values.get('CallSid', None)
    from_number = request.values.get('From', None)
    resp = twilio.twiml.Response()
    gather = twilio.twiml.Gather(input='dtmf', timeout=3, numDigits=1, action="/record")

    if pressed == '1': # high register
        high_notes = ['high_nasal_Ab4', 'high_nasal_Bb4', 'high_nasal_C#5',
        'high_nasal_F4', 'high_nasal_F#4', 'high_round_AbEb', 'high_round_Ab4',
        'high_round_Bb4', 'high_round_C4', 'high_round_CG', 'high_round_D4',
        'high_round_Eb4']
        #TODO: Find out if this works...
        # list_of_prob = [0.2, 0.2, 0.6]
        # note = random.choices(high_notes, weights=list_of_prob)
        note = random.choice(high_notes)
        gather.play(FILE_URL+'/'+note+'_instructions.mp3')
        resp.append(gather)
        resp.gather(numDigits=1, action="/record", method="POST", timeout=30)

    elif pressed == '2': # low register
        low_notes = ['low_round_G3', 'low_round_FCslide', 'low_round_F3',
        'low_round_Eb3', 'low_round_C3', 'low_round_Bb3', 'low_round_Bb2',
        'low_round_Ab2', 'low_nasal_Eb', 'low_nasal_Ab2']
        #TODO: Find out of this works...
        # list_of_prob = [0.2, 0.2, 0.6]
        # note = random.choices(low_notes, weights=list_of_prob)
        note = random.choice(low_notes)
        gather.play(FILE_URL+'/'+note+'_instructions.mp3')
        resp.append(gather)
        resp.gather(numDigits=1, action="/record", method="POST", timeout=30)

    else: # deviant
        note = 'wild_card'
        gather.play(FILE_URL+'/'+note+'_instructions.mp3')
        resp.append(gather)
        resp.gather(numDigits=1, action="/record", method="POST", timeout=30)

    new_recording = Recording(call_sid, from_number, note)
    db.session.add(new_recording)
    db.session.commit()

    return str(resp)

# this is where people either record their message
# or practice signing their note again
@application.route("/record", methods=['GET', 'POST'])
def record():

    pressed = request.values.get('Digits', None)
    resp = twilio.twiml.Response()
    gather = twilio.twiml.Gather(input='dtmf', timeout=3, numDigits=1, action="/record")
    call_sid = request.values.get('CallSid', None)
    note_lookup = Recording.query.filter_by(call_sid=call_sid).first()
    note = note_lookup.note

    if pressed == '3': # ready to record
        resp.play(FILE_URL+'/'+note+'_record.mp3')
        resp.pause(length=1)
        resp.record(maxLength="60", action="/handle-recording", finishOnKey='#', timeout=30)

    if pressed == '*': # listen to note again
        gather.play(FILE_URL+'/'+note+'_retry.mp3')
        resp.append(gather)
        resp.gather(numDigits=1, action="/record", method="POST", timeout=30)

    return str(resp)

# this is where the recording gets committed to the database
# and where you ask permission to follow up when the recording is ready
@application.route("/handle-recording", methods=['GET', 'POST'])
def handle_recording():

    recording_url = request.values.get('RecordingUrl', None)
    call_sid = request.values.get('CallSid', None)
    resp = twilio.twiml.Response()
    # gather = twilio.twiml.Gather(input='dtmf', timeout=3, numDigits=1, action="/consent-contact")

    if recording_url:
        new_recording = Recording.query.filter_by(call_sid=call_sid).first()
        new_recording.recording_url = recording_url
        db.session.commit()

        resp.play(FILE_URL+'/thatsall.mp3')
        resp.play(FILE_URL+'/thank-you-final.mp3')
        resp.pause(length=2)

    return str(resp)

# this is where permission gets committed to the database
# and where you play the final "thank you" message
# @application.route("/consent-contact", methods=['GET', 'POST'])
# def consent_contact():
#
#     pressed = request.values.get('Digits', None)
#     call_sid = request.values.get('CallSid', None)
#     resp = twilio.twiml.Response()
#
#     if pressed == '1': # permission to contact
#
#         new_recording = Recording.query.filter_by(call_sid=call_sid).first()
#         new_recording.contact_ok = True
#         db.session.commit()
#
#         resp.play(FILE_URL+'/thankyou_yes.mp3')
#
#     else: # doesn't want to be contacted
#         resp.play(FILE_URL+'/thankyou_no.mp3')
#
#     return str(resp)
#
# #TODO: Find @requires_auth definitions in Cathy's story hotline

@application.route('/settings', methods=['GET', 'POST'])
# @requires_auth
def settings():

    if request.method == 'POST':
        new_config = {
            "TWILIO_ACCOUNT_SID": request.form['twilio-account-sid'],
            "TWILIO_AUTH_TOKEN": request.form['twilio-auth-token'],
            "TWILIO_PHONE_NO": request.form['twilio-phone-no'],
        }
        config.update_config(new_config)
        importlib.reload(config)
        flash("settings updated!")

    return render_template('settings.html', CONFIG_VARS=config.CONFIG_VARS)

@application.route('/initialize')
# @requires_auth
def initialize():
    db.create_all()
    flash("db initialized!")

    return redirect('/')


if __name__ == "__main__":

    application.secret_key = config.CONFIG_VARS['SECRET_KEY']
    debug = True if config.CONFIG_VARS['DEBUG'] == 'True' else False
    application.run(debug=debug, host='0.0.0.0')
