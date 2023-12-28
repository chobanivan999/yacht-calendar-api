import datetime
import os.path
import json
from flask import Flask, request
import json
from flask_cors import CORS

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

app = Flask(__name__)
CORS(app)

creds = None
# The file token.json stores the user's access and refresh tokens, and is
# created automatically when the authorization flow completes for the first
# time.
if os.path.exists("token.json"):
  creds = Credentials.from_authorized_user_file("token.json", SCOPES)
# If there are no (valid) credentials available, let the user log in.
if not creds or not creds.valid:
  if creds and creds.expired and creds.refresh_token:
    creds.refresh(Request())
  else:
    flow = InstalledAppFlow.from_client_secrets_file(
        "credentials.json", SCOPES
    )
    creds = flow.run_local_server(port=0)
  # Save the credentials for the next run
  with open("token.json", "w") as token:
    token.write(creds.to_json())

  # Get Yacht Calendar list
  service = build("calendar", "v3", credentials=creds)
  page_token = None
  calendar_list = service.calendarList().list(pageToken=page_token).execute()
  if not os.path.exists("yachts.json"):
    yachtsdata = []
    omitids = ["calendar@theyachtclub.sg", "yachtclub-calendar@yachtcalendar.iam.gserviceaccount.com", "en.singapore#holiday@group.v.calendar.google.com"]
    while True:
          calendar_list = service.calendarList().list(pageToken=page_token).execute()
          for calendar_list_entry in calendar_list['items']:
              print (calendar_list_entry["id"], calendar_list_entry['summary'])
              yachtsdata.append(
                  {
                    "id": calendar_list_entry["id"],
                    "name": calendar_list_entry["summary"]
                  }
              )
          page_token = calendar_list.get('nextPageToken')
          if not page_token:
              break
    with open("yachts.json", "w") as yachts:
      yachts.write(json.dumps(yachtsdata, indent=4))

# Get yacht list
f = open('yachts.json')
yachtdata = json.load(f)
yacht_ids = [{"id" : x["id"]} for x in yachtdata]

def last_day_of_month(date):
    try:
      if date.month == 12:
          return {"type": "success", "data": date.replace(day=31)}
      lastdate = date.replace(month=date.month+1, day=1) - datetime.timedelta(days=1)
      return {"type": "success", "data": lastdate}
    except Exception as ex:
       print("hello : ", str(ex))
       return {"type": "fail", "data": str(ex)}

@app.route("/")
def index():
    return "<!doctype html><html><head><title>Yacht Calendar API</title></head><body><h1>Yacht Calendar API</h1></body></html>"

@app.route("/v1/yachts")
def getYachts():
  # Response data
  resdata = {
        "code": 200,
        "msg": "success",
        "data": None
    }
  try:
    # Get Yacht Calendar list
    service = build("calendar", "v3", credentials=creds)
    page_token = None
    calendar_list = service.calendarList().list(pageToken=page_token).execute()
    yachtsdata = []
    omitids = ["calendar@theyachtclub.sg", "yachtclub-calendar@yachtcalendar.iam.gserviceaccount.com", "en.singapore#holiday@group.v.calendar.google.com"]
    while True:
          calendar_list = service.calendarList().list(pageToken=page_token).execute()
          for calendar_list_entry in calendar_list['items']:
              if not calendar_list_entry["id"] in omitids:
                yachtsdata.append(
                    {
                      "id": calendar_list_entry["id"],
                      "name": calendar_list_entry["summary"]
                    }
                )
          page_token = calendar_list.get('nextPageToken')
          if not page_token:
              break
    yachtsdata = sorted(yachtsdata, key=lambda k: k.get('name', 0))
    resdata["data"] = yachtsdata
    return resdata
  
  except Exception as error:
      resdata["code"] = 500
      resdata["msg"] = str(error)
      return resdata
          
# get for a month
@app.route('/v1/month/<int:year>/<int:month>', methods=['GET'])
def getMonthSlot(year, month):
    # Response data
    resdata = {
         "code": 200,
         "msg": "success",
         "data": None
      }
    
    try:
      lastdate_res = last_day_of_month(datetime.datetime(year, month, 1))
      if lastdate_res["type"] == "success":
        lastdate = lastdate_res["data"].day

        service = build("calendar", "v3", credentials=creds)

        start_date = datetime.datetime(year, month, 1).isoformat() + 'Z'
        end_date = datetime.datetime(year, month, lastdate).isoformat() + 'Z'
        req_body = {
          "timeMin": start_date,
          "timeMax": end_date,
          "items": yacht_ids
        }

        response = service.freebusy().query(body=req_body).execute()
        for i in range(len(yacht_ids)):
          busy_periods = response['calendars'][yacht_ids[i]["id"]]["busy"]
          # Calculate the free periods
          free_periods = []
          start_time = req_body['timeMin']
          for period in busy_periods:
              end_time = period['start']
              if start_time < end_time:
                  free_periods.append({'start': start_time, 'end': end_time})
              start_time = period['end']
          end_time = req_body['timeMax']
          if start_time < end_time:
              free_periods.append({'start': start_time, 'end': end_time})

          yachtdata[i]["free"] = free_periods
        
        resdata["data"] = yachtdata
        return resdata
      
      else:
        resdata["code"] = 500
        resdata["msg"] = lastdate_res["data"]
        return resdata
    
    except Exception as error:
      resdata["code"] = 500
      resdata["msg"] = str(error)
      return resdata

# get for a month
@app.route('/v1/date/<int:dt>/<int:month>/<int:year>/<string:id>', methods=['GET'])
def getDateIdSlot(dt, month, year, id):
    # Response data
    resdata = {
         "code": 200,
         "msg": "success",
         "data": None
      }
    
    try:
      service = build("calendar", "v3", credentials=creds)

      data = [x for x in yachtdata if x['id'] == id]
      name = ""
      if len(data):
        name = data[0]["name"]
        start_date = datetime.datetime(year, month, dt, 0, 0, 0).isoformat() + 'Z'
        end_date = datetime.datetime(year, month, dt, 23, 59, 59).isoformat() + 'Z'
        req_body = {
          "timeMin": start_date,
          "timeMax": end_date,
          "items": [{"id": id}]
        }

        response = service.freebusy().query(body=req_body).execute()
        busy_periods = response['calendars'][id]["busy"]
        # Calculate the free periods
        free_periods = []
        start_time = req_body['timeMin']
        for period in busy_periods:
            end_time = period['start']
            if start_time < end_time:
                free_periods.append({'start': start_time, 'end': end_time})
            start_time = period['end']
        end_time = req_body['timeMax']
        if start_time < end_time:
            free_periods.append({'start': start_time, 'end': end_time})
        
        resdata["data"] = {"name": name, "free": free_periods}
      else:
        resdata["code"] = 404
        resdata["msg"] = "No such yacht"
      
      return resdata
    
    except Exception as error:
      resdata["code"] = 500
      resdata["msg"] = str(error)
      return resdata

# get for a date range
@app.route('/v1/days/<int:month>/<int:year>/<int:start_day>/<int:end_day>', methods=['GET'])
def getDateRangeSlot(month, year, start_day, end_day):
    # Response data
    resdata = {
         "code": 200,
         "msg": "success",
         "data": None
      }
    
    try:
      service = build("calendar", "v3", credentials=creds)

      start_date = datetime.datetime(year, month, start_day, 0, 0, 0).isoformat() + 'Z'
      end_date = datetime.datetime(year, month, end_day, 23, 59, 59).isoformat() + 'Z'
      req_body = {
        "timeMin": start_date,
        "timeMax": end_date,
        "items": yacht_ids
      }

      response = service.freebusy().query(body=req_body).execute()
      for i in range(len(yacht_ids)):
        busy_periods = response['calendars'][yacht_ids[i]["id"]]["busy"]
        # Calculate the free periods
        free_periods = []
        start_time = req_body['timeMin']
        for period in busy_periods:
            end_time = period['start']
            if start_time < end_time:
                free_periods.append({'start': start_time, 'end': end_time})
            start_time = period['end']
        end_time = req_body['timeMax']
        if start_time < end_time:
            free_periods.append({'start': start_time, 'end': end_time})

        yachtdata[i]["free"] = free_periods
        
      resdata["data"] = yachtdata
      return resdata
    
    except Exception as error:
      resdata["code"] = 500
      resdata["msg"] = str(error)
      return resdata
    
if __name__ == "__main__":
  app.run()