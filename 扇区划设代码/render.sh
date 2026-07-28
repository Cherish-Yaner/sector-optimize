set -e

LOG=log_$(date +%Y%m%d_%H%M%S).txt

python render.py 2>&1 >$LOG
python illu.py $LOG
