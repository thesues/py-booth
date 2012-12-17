make start
sleep 5
echo "lease acquire"|netcat localhost 1235
sleep 2
echo "lease list"|netcat localhost 1236
echo "lease list"|netcat localhost 1235
echo "lease list"|netcat localhost 1237
sleep 1

for i in `seq 2 3`
do
    pid=$(pgrep -f "run.py $i")
    kill $pid
done
