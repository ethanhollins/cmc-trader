import socketio
import eventlet

DOMAIN = 'localhost'
PORT = 3000

sio = socketio.Server()
@sio.event
def connect(sid, eviron):
	print('connected')

@sio.event
def disconnect(sid):
	print('disconnected')

@sio.on('ping')
def ping(sid, data):
	print('Receieved ping.')
	sio.emit('ping', {})

@sio.event
def stop(sid, data):
	if not utils.isStopped:
		utils.setStopped()

	sio.emit('stop', {})

@sio.event
def start(sid, data):
	sio.emit('start', {})
	if utils.isStopped:
		utils.restart()

@sio.event
def status(sid, data):
	if utils.isStopped:
		sio.emit('status', 'stopped')
	else:
		sio.emit('status', 'started')

@sio.event
def bank(sid, data):
	res = {}
	for k in data:
		if k == 'get':
			res['get'] = {
				'external': utils.external_bank,
				'maximum': utils.maximum_bank
			}
		elif k == 'external':
			try:
				res['external'] = float(data['external'])
				utils.updateBank(external_bank=float(data['external']))
			except:
				print('Server Error: Illegal external bank parameter.')
				res['external'] = None
		elif k == 'maximum':
			try:
				res['maximum'] = float(data['maximum'])
				utils.updateBank(maximum_bank=float(data['maximum']))
			except:
				print('Server Error: Illegal external bank parameter.')
				res['maximum'] = None

	sio.emit('bank', res)

def init(utilities):
	global utils
	utils = utilities

	app = socketio.WSGIApp(sio, static_files={
		'/': {'content_type': 'text/html', 'filename': 'index.html'}
	})

	eventlet.wsgi.server(eventlet.listen(('', 3000)), app)
