from os import path

from CMCTrader.Start import Start
from CMCTrader import Constants

def getPlanPath(name):
	return '\\'.join(path.realpath(__file__).split('\\')[0:-1]) + "\\" + name + ".py"

if __name__ == '__main__':
	name = input("Enter plan name: ")
	path = getPlanPath(name)
	Start(path, name)