import boto3
import botocore

s3_client = boto3.client('s3')
s3_resource = boto3.resource('s3')

bucket_name = 'cmctrader'

def download(key, file):
	bucket = s3_resource.Bucket(name=bucket_name)

	try:
		bucket.download_file(key, file)
	except botocore.exceptions.ClientError as e:
		if e.response['Error']['Code'] == "404":
			print("The object does not exist")
		else:
			raise

def uploadPath(path, s3_path):
	s3.meta.client.upload_file(path, bucket_name, s3_path)

def uploadObj(file, s3_path):
	s3.meta.client.upload_fileobj(file, bucket_name, s3_path)
	