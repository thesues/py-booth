start() {
rm -rf ../*.log
python ../run.py -c conf/1.conf & 
python ../run.py -c conf/2.conf &
python ../run.py -c conf/3.conf &
sleep 2
}

stop() {
  pkill -f run.py
}
action=$1
case $action in
  'start') start ;;
  'stop') stop ;;
  'restart') stop;start;;
esac
