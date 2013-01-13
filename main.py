from bs4 import BeautifulSoup
from google.appengine.api import urlfetch
import base64, datetime, json, lxml, re, urllib, webapp2

class Timetable(object):
	TIMETABLE_URL = "https://weeklytimetable.uclan.ac.uk/"

	def __init__(self, username, password):
		self.username = username
		self.password = password
		self.timetable_html_str = None

	def store_result(self, result):
		self.timetable_html_str = result.content
		self.timetable_html = BeautifulSoup(self.timetable_html_str, "lxml")

	def do_request(self, method = "GET", payload = None):
		headers = {
			"Authorization": "Basic "+base64.encodestring(self.username+":"+self.password)
		}

		if method == "POST":
			headers = {
				"Authorization": "Basic "+base64.encodestring(self.username+":"+self.password),
				"Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
				"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_8_2) AppleWebKit/537.17 (KHTML, like Gecko) Chrome/24.0.1312.52 Safari/537.17"
			}

		methods = {
			"GET": urlfetch.GET,
			"POST": urlfetch.POST
		}

		result = urlfetch.fetch(self.TIMETABLE_URL, payload=payload, method=methods[method], headers=headers)
		if result.status_code == 200:
			self.store_result(result)
			return True
		else:
			return False

	def get(self):
		if self.timetable_html_str == None:
			if not self.do_request():
				return False

		return self._build_timetable()

	def get_week(self, wb_str):
		try:
			wb = datetime.date.today()
			if wb_str == "next_week":
				wb += datetime.timedelta(days=7-wb.weekday())
			elif wb_str == "last_week":
				wb -= datetime.timedelta(days=7+wb.weekday())
			else:
				day = int(wb_str.split("-")[0])
				month = int(wb_str.split("-")[1])
				year = int(wb_str.split("-")[2])
				wb = datetime.date(year, month, day)
				wb -= datetime.timedelta(days=wb.weekday())

			wb = wb.strftime("%A %d %B %Y")
		except:
			return False

		if not self.get():
			return False

		viewstate = self.timetable_html.find("input", id="__VIEWSTATE")["value"]
		eventvalidation = self.timetable_html.find("input", id="__EVENTVALIDATION")["value"]
		
		payload = urllib.urlencode({
			"ctl00$ScriptManager1": "ctl00$MainContent$UpdatePanel1|ctl00$MainContent$dateChangeSubmit",
			"__EVENTTARGET": "",
			"__LASTFOCUS": "",
			"__VIEWSTATE": viewstate,
			"__EVENTVALIDATION": eventvalidation,
			"__ASYNCPOST": "true",
			"ctl00$MainContent$tbCurrentDate": wb,
			"ctl00$MainContent$dateChangeSubmit":"",
		})

		if not self.do_request("POST", payload):
			return False

		return self._build_timetable()

	def _build_timetable(self):
		timetable = {
			"status": "ok",
			"week_beginning": self.timetable_html.find("input", id="tbCurrentDate")["value"],
			"timetable": self._get_timetable()
		}

		return timetable

	def _get_event(self, event_elem):
		event = {}

		try:
			event_namecode = re.findall("(.*) - ([^()]+) \(", event_elem.contents[1])[0]
			event["code"] = event_namecode[0]
			event["name"] = event_namecode[1]
		except:
			pass

		try:
			event_time = re.findall("(.*) - (.*)", event_elem.contents[0].find(text=True))[0]
			event["start_time"] = event_time[0]
			event["finish_time"] = event_time[1]
		except:
			pass

		try:
			event_location = re.findall("(.*) - (.*)", event_elem.contents[3].find(text=True))[0]

			building = event_location[0]
			room = event_location[1]
			if re.match("\w\w LECTURE THEATRE", room) != None:
				room = room.split()[0]+"LT"
			elif re.match("\w+\d+", room) != None:
				room = room.split()[0]
			elif re.match("".join(re.findall("([A-Z])", building))+" ", room) != None:
				room = " ".join(room.split()[1:]).title()
			elif re.match("^"+building+", (.*)", room) != None:
				room = re.findall("^"+building+", (.*)", room)[0]
			elif re.match("\w+\d+", room) == None:
				room = room.title()

			event["room"] = room
			event["building"] = building
		except:
			pass

		try:
			event["type"] = event_elem.contents[7].find(text=True)
		except:
			pass

		try:
			event["tutor"] = event_elem.contents[5].split(", ")[1]+" "+event_elem.contents[5].split(", ")[0]
		except:
			pass

		return event

	def _get_day(self, day):
		day_events = []
		for event in day.select(".TimeTableEvent"):
			day_events.append(self._get_event(event))

		if len(day_events) == 0:
			return None

		day = {
			"day": day.select(".TimeTableRowHeader")[0].contents[0],
			"events": day_events
		}

		return day

	def _get_timetable(self):
		days = [self._get_day(day) for day in self.timetable_html.select(".TimeTableTable tr")]
		return [day for day in days if day != None and len(day["events"]) > 0]


class MainHandler(webapp2.RequestHandler):
	# Specify permitted usernames in the list below
	ACL = []

	def is_permitted_by_acl(self, username):
		return username in self.ACL

	def error(self, code, message):
		result = {
			"status": "error",
			"code": code,
			"message": message
		}

		self.write_json(result)

	def write_json(self, result):
		json_str = json.dumps(result, sort_keys=False, indent=4)
		self.response.content_type = "application/json"
		self.response.write(json_str)

	def get(self, date):
		username = self.request.get("username", None)
		password = self.request.get("password", None)

		if username == None or password == None:
			self.error("missing_parameter", "Username or password missing")
			return

		if not self.is_permitted_by_acl(username):
			self.error("permission_denied", "Your username is not allowed by the ACL")
			return

		timetable = Timetable(username, password)
		result = timetable.get()

		if date != "" and date != "this_week":
			result = timetable.get_week(date)

		if result:
			self.write_json(result)
		else:
			self.error("request_failed", "Request failed, check your username and password are correct")


app = webapp2.WSGIApplication([
    ('/timetable/?(.*)', MainHandler)
], debug=False)
