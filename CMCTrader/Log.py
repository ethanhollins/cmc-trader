import boto3
from botocore.exceptions import ClientError

def set_utils(utilities):
	global utils
	utils = utilities

def debug(tag, log):
	time = time_str(utils.getAustralianTime())
	print("("+time+")"+str(tag)+":", str(log))

def db(tag, log):
	time = time_str(utils.getAustralianTime())

def all(tag, log):
	debug(tag, log)
	db(tag, log)

def save(tag, log):
	return

def chart_data(values):
	return

def time_str(dt):
	return str(time.day)+"-"+str(time.month)+"-"+str(time.year), str(time.hours)+":"+str(time.minutes)+":"+str(time.seconds)