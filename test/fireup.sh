start() {
rm -rf ../*.log
python ../run.py 1 -t& 
python ../run.py 2 -t&
python ../run.py 3 -t&
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
