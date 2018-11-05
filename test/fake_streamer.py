# simulate a stream of note activation frames, which may arrive at different
# times
import numpy as np
import time
import sys
import signal

out_fd = None
if len(sys.argv) < 2:
    out_fd = sys.stdout
else:
    out_fd = open(sys.argv[1],'wb',buffering=0)

done = False

def quit_cmd(sn,frame):
    done = True

signal.signal(signal.SIGINT,quit_cmd)

# times to sleep for
times = [0.25,0.5,1.0]

cur_time=1000
while not done:
    out_frame = (np.random.standard_normal(88) > 0).astype('float32')
    out_time = np.array(cur_time,dtype='float64')
    b = out_time.tobytes() + out_frame.tobytes()
    out_fd.write(b)
    delta_time = times[np.random.randint(len(times))]
    cur_time += delta_time
    time_jitter = np.random.standard_normal(1)
    time.sleep(max(delta_time+time_jitter,0))

if out_fd != sys.stdout:
    out_fd.close()
    

sys.stderr.write("test/fake_streamer.py quitting\n")
