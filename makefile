test:run.py test.py
	python test.py
1:run.py
	telnet localhost 1235
2:run.py
	telnet localhost 1236
3:run.py
	telnet localhost 1237
stop:
	sh test.sh stop
	sh test.sh stop
start:run.py
	sh test.sh stop
	rm -rf *.log
	python run.py 1 &
	python run.py 2 &
	python run.py 3 &
clean:
	rm -rf *.log
	rm -rf *.pyc
send:
	python -m unittest test_network_send test.py
