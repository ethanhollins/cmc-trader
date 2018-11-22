from os import path
import json
import boto3

from CMCTrader.Start import Start

class DecimalEncoder(json.JSONEncoder):
	def default(self, o):
		if isinstance(o, decimal.Decimal):
			if abs(o) % 1 > 0:
				return float(o)
			else:
				return int(o)
		return super(DecimalEncoder, self).default(o)

def getPlanPath(name):
	return '\\'.join(path.realpath(__file__).split('\\')[0:-1]) + "\\" + name + ".py"

if __name__ == '__main__':
	with open('app.json') as f:
		data = json.load(f)


	dynamodb = boto3.resource('dynamodb', region_name='ap-southeast-2')
	table = dynamodb.Table('users')

	for user_id in data['traders']:
		try:
			response = self.table.get_item(
					Key = {
						'user_id' : int(user_id)
					}
				)
		except ClientError as e:
			print("Could not find trader:", str(user_id))
			print(e.response['Error']['Message'])
			continue

		item = response['Item']
		json_str = json_dumps(item, indent=4, cls=DecimalEncoder)
		isrunning = json.loads(json_str)['user_isrunning']
		plan_name = json.loads(json_str)['user_program']
		print(isrunning)
		print(plan_name)


	name = input("Enter plan name: ")
	path = getPlanPath(name)
	Start(path, name)

def threaded_client()