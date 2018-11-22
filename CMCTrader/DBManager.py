import boto3
import decimal
from botocore.exceptions import ClientError
import json

dynamodb = boto3.resource('dynamodb', region_name='ap-southeast-2')
dynamodbClient = boto3.client('dynamodb', region_name='ap-southeast-2')

table_users = dynamodb.Table('users')

class DecimalEncoder(json.JSONEncoder):
	def default(self, o):
		if isinstance(o, decimal.Decimal):
			if abs(o) % 1 > 0:
				return float(o)
			else:
				return int(o)
		return super(DecimalEncoder, self).default(o)

def getItems(user_id, items):
	try:
		response = table_users.get_item(
						Key = {
							'user_id' : int(user_id)
						}
					)
	except ClientError as e:
		print(e.response['Error']['Message'])
		return None

	row = response['Item']
	user_info = json.dumps(row, indent=4, cls=DecimalEncoder)

	result = {}

	if (type(items) == list):
		for item in items:
			try:
				value = json.loads(user_info)[str(item)]
				result[str(item)] = value
			except:
				print("Could not find item", str(item))
				result[str(item)] = None
	else:
		try:
			value = json.loads(user_info)[str(items)]
			result[str(items)] = value
		except:
			print("Could not find item", str(items))
			result[str(items)] = None

	return result

def updateItems(user_id, items):
	try:
		for key in items:
			response = table_users.update_item(
							Key = {
								'user_id' : int(user_id)
							},
							UpdateExpression = "set "+key+"=:i",
							ExpressionAttributeValues = {
								':i' : items[key]
							}
						)
	except ClientError as e:
		print(e.response['Error']['Message'])
		return