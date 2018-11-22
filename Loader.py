from os import path
import json
import threading

import boto3
import decimal
from botocore.exceptions import ClientError

from CMCTrader.Start import Start

class DecimalEncoder(json.JSONEncoder):
	def default(self, o):
		if isinstance(o, decimal.Decimal):
			if abs(o) % 1 > 0:
				return float(o)
			else:
				return int(o)
		return super(DecimalEncoder, self).default(o)

def threaded_client(path, user_info):
	username = json.loads(user_info)['user_username']
	print("Starting", str(username) + "...")
	task = Start
	t = threading.Thread(target=task, args=[path, user_info])
	t.start()

def getPlanPath(name):
	return '\\'.join(path.realpath(__file__).split('\\')[0:-1]) + "\\" + name + ".py"

if __name__ == '__main__':
	with open('app.json') as f:
		data = json.load(f)

	dynamodb = boto3.resource('dynamodb', region_name='ap-southeast-2')
	table = dynamodb.Table('users')

	for user_id in data['traders']:
		try:
			response = table.get_item(
					Key = {
						'user_id' : int(user_id)
					}
				)
		except ClientError as e:
			print("Could not find user:", str(user_id))
			print(e.response['Error']['Message'])
			continue

		item = response['Item']
		user_info = json.dumps(item, indent=4, cls=DecimalEncoder)
		isrunning = json.loads(user_info)['user_isrunning']
		plan_name = json.loads(user_info)['user_program']

		if (isrunning):
			path = getPlanPath(plan_name)

			threaded_client(path, user_info)
		else:
			continue