make start
sleep 5
echo "lease acquire"|netcat localhost 1235
sleep 2
echo "lease list"|netcat localhost 1236
echo "lease list"|netcat localhost 1235
echo "lease list"|netcat localhost 1237
sleep 1
