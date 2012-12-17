make start
sleep 5
echo "lease acquire"|netcat localhost 1235
sleep 3
echo "lease list"|netcat localhost 1236
echo "lease list"|netcat localhost 1235
echo "lease list"|netcat localhost 1237
sleep 2
echo "kill run.py 1"
pid=$(pgrep -f "run.py 1")
kill $pid

sleep 3

python run.py 1 &
sleep 3

echo "lease slowlist"|netcat localhost 1235
echo "lease list"|netcat localhost 1235
