from socketIO_client import SocketIO, LoggingNamespace
import ast
import threading

DOMAIN = 'localhost'
PORT = 3000

class SocketManager(object):

	def __init__(self, utils):
		self.utils = utils
		self.sio = SocketIO(DOMAIN, PORT, LoggingNamespace)

		task = self.recv
		t = threading.Thread(target = task)
		t.start()

	def convertRawList(self, raw):
		raw_str = raw.decode('utf-8')
		return ast.literal_eval(raw_str[raw_str.find('['):])

	def cmd(self, *args):
		cmd = args[0]

		if cmd == 'stop':
			self.utils.setStopped()
	
	def variables(self, *args):
		# data = self.convertRawData(args[0])
		print(args[0])
		print(type(args[0]))

	def recv(self):
		print("Starting socket receiving service...")
		while True:
			self.sio.on('cmd', self.cmd)
			self.sio.on('variables', self.variables)
			self.sio.wait(seconds=1)

	def send(self, room, msg):
		print("Sending message")
		self.sio.emit(room, msg)
