import os
import time
import random
import string
import urllib.parse
from ftplib import FTP
from flask import Flask, jsonify, render_template, request, url_for, send_from_directory
from flask_socketio import SocketIO, send, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = "sgsdgJHUIHHAasfasUDN"
socketio = SocketIO(app)

UPLOAD_FOLDER = f'{os.getcwd()}/static/upload'

channels = {"#general": []}

messages = []
users = {"#general": []}
filenames = {}
typing_users = {"#general": []}


def placeFile(filename):
	ftp = FTP('ftp.stackcp.com', timeout=100)
	ftp.login(user='flack-uploads.com', passwd='4daf3b85ff35')
	ftp.cwd('/public_html')
	ftp.storbinary('STOR ' + filenames[filename], open(os.path.join(UPLOAD_FOLDER, filename), 'rb'))
	ftp.quit()


def get_channels():
	res = []
	for channel in channels.keys():
		res.append(channel)
	return res


def append_message(list, msg):
	if len(list) == 100:
		list.pop(0)
		list.append(msg)
	else:
		list.append(msg)


@app.route("/")
def index():
	return render_template("index.html")


@app.route("/check_user", methods=["POST"])
def check_user():
	username = request.form.get("username")
	usernames = {"admin"}

	for channel in users.keys():
		for user in channel:
			usernames.add(user)

	if username in usernames:
		return jsonify({"exists": True})
	else:
		return jsonify({"exists": False})


@socketio.on("type")
def on_type(msg):
	username = msg['username']
	channel = msg['channel']
	if msg['status'] == "end":
		if msg['username'] in typing_users[msg['channel']]:
			typing_users[msg['channel']].remove(msg['username'])

		message = {
			"usernames": typing_users[channel],
			"channel": channel,
			"files": {}
		}

		emit('typing', message, broadcast=True)
	else:
		if channel not in typing_users:
			typing_users[channel] = []
		if username not in typing_users[channel]:
			typing_users[channel].append(username)

		message = {
			"usernames": typing_users[channel],
			"channel": channel,
			"files": {}
		}

		emit('typing', message, broadcast=True)


@app.route("/send_file", methods=['POST'])
def send_file():
	file = request.files['file']
	filename = file.filename
	filename = urllib.parse.unquote(filename)
	filename = ''.join(e for e in filename if e.isalnum() or e == ".")
	name, ext = os.path.splitext(filename)
	filenames[filename] = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(20)) + ext
	file.save(os.path.join(UPLOAD_FOLDER, filename))
	placeFile(filename)
	os.remove(os.path.join(UPLOAD_FOLDER, filename))
	return jsonify({"success": True})


@socketio.on('add channel')
def add_channel(msg):
	if msg['channel'] not in channels:
		channels[msg['channel']] = []
		users[msg['channel']] = []
		emit('channel added', {"channel": msg['channel']}, broadcast=True)


@socketio.on('get channel story')
def get_channel(msg):
	if msg['channel'] in channels:
		emit('announce message', {'messages': channels[msg['channel']]})
	else:
		emit('announce message', {'messages': "#general"})


@socketio.on('get all channels')
def get_all_channels(msg):
	emit('channels', {'channels': get_channels()})


@socketio.on('send message')
def handle_message(msg):
	if "connection" in msg and msg['username'] not in users[msg['channel']] and not msg['username'] == None:
		message = {
			"connection": True,
			"text": "has connected",
			"username": msg['username'],
			"date": msg['date'],
			"channel": msg['channel'],
			"files": {}
		}
		users[msg['channel']].append(msg['username'])
		append_message(channels[msg['channel']], message)

		emit('announce message', {'messages': channels[msg['channel']]}, broadcast=True)
	elif "connection" in msg and msg['username'] in users[msg['channel']]:
		emit('announce message', {'messages': channels[msg['channel']]})
	elif "connection" not in msg:
		files = {}
		for file in msg['files']:
			file = ''.join(e for e in file if e.isalnum() or e == ".")
			# files[file] = os.path.join('/static/upload', file)
			files[file] = "http://flack-uploads-com.stackstaging.com/" + filenames[file]
		message = {
			"connection": False,
			"text": msg['text'],
			"username": msg['username'],
			"date": msg['date'],
			"channel": msg['channel'],
			"files": files
		}
		append_message(channels[msg['channel']], message)

		emit('announce message', message, broadcast=True)


@socketio.on('change username')
def change_username(msg):
	old_username = msg['old_username']
	new_username = msg['new_username']

	for channel in channels.keys():
		for n, msg in enumerate(channels[channel]):
			if msg["username"] == old_username:
				channels[channel][n]["username"] = new_username

	for channel in users.keys():
		for n, username in enumerate(users[channel]):
			if username == old_username:
				message = {
					"connection": True,
					"text": f"is now {new_username}",
					"username": old_username,
					"date": msg['date'],
					'channel': channel
				}
				append_message(channels[channel], message)
				users[channel][n] = new_username

		emit('announce message', {'messages': channels[channel]})


if __name__ == '__main__':
	socketio.run(app)
