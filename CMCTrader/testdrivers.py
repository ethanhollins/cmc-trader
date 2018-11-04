from selenium import webdriver
import threading
import time
import sys

def init(driver_id):
	driver = webdriver.Chrome(getChromeDriverPath())
	driver.get("http://www.google.com.au")
	infiniteloop(driver, driver_id)

def infiniteloop(driver, driver_id):
	if (driver_id == '1'):
		print("getting facebook")
		time.sleep(3)
		driver.get("http://www.facebook.com")
	else:
		print("getting yahoo")
		time.sleep(3)
		driver.get("http://www.yahoo.com")
	# try:
	# 	while True:
	# 		print(driver_id)
	# 		time.sleep(3)
	# 		pass
	# except KeyboardInterrupt:
	# 	print("interrupted!")
	# 	sys.exit()

def getChromeDriverPath():
	return "./drivers/chromedriver.exe"

def threadedDriver(driver_id):
	task = init
	t = threading.Thread(target = task, args=[driver_id])
	t.start()

threadedDriver('1')
threadedDriver('2')
