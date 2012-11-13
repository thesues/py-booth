start() {
rm -rf *.log
python run.py 1 -b & 
python run.py 2 -b &
python run.py 3 -b &
sleep 2
}

stop() {
  pids=`ps aux|grep -v grep |grep 'python run.py'|awk '{print $2}'|xargs`
  if [[ $pids != '' ]]
  then
  kill -9 $pids
  fi
}
action=$1
case $action in
  'start') start ;;
  'stop') stop ;;
  'restart') stop;start;;
esac
