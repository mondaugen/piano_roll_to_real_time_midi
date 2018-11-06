# Start a program, save its pid
launch_ () 
{
    $*&
    _pid=$!
    echo "$_pid" >> /tmp/.$$_pids
    echo "$1 $_pid"
}

# Kill programs that were started with launch_
kill_all ()
{
    if [ -a /tmp/.$$_pids ]; then
        for pid in $(< /tmp/.$$_pids); do
            kill -s SIGINT $pid >/dev/null 2>&1
        done
        echo "removing /tmp/.$$_pids"
        rm /tmp/.$$_pids
    fi
}

# Wait for programs started with launch_ to terminate
wait_all ()
{
    _keep_running=1
    while [ $_keep_running == 1 ]; do
        sleep 1
        if [[ ! -a /tmp/.$$_pids ]]; then
            echo "/tmp/.$$_pids no longer exists"
            _keep_running=0
        else
            for pid in $(< /tmp/.$$_pids); do
                # If $pid no longer exists then this will return non-zero
                if [ kill -0 $pid >/dev/null 2>&1 != 0 ]; then
                    echo "$pid quit"
                    _keep_running=0
                fi
            done
        fi
    done
    echo "no more waiting..."
}

export PYTHONPATH=".:$PYTHONPATH"

fifo_name=/tmp/mido_streamer_test.fifo

on_quit ()
{
    kill_all
    rm -f ${fifo_name}
}
trap on_quit SIGINT

mkfifo "$fifo_name"
# launch fluidsynth which will accept midi messages
# launch_ fluidsynth -s -m coremidi -a coreaudio -p my_fluid_synth ~/Documents/sounds/sf2/TimGM6mb.sf2
# launch fluidsynth with test/launch_fluidsynth.sh because it doesn;t seem to survive in the background
ps aux|grep fluidsynth
# launch fake MIDI source
#launch_ python3 test/fake_streamer.py "$fifo_name"
sleep 1
# launch midi parser which should send events to fluidsynth
#python3 test/pr_to_mido_midi_test.py "$fifo_name"
#python3 -m pdb test/pr_to_mido_midi_test.py "$fifo_name"
launch_ python3 test/fake_streamer.py | launch_ python3 test/pr_to_mido_midi_test.py

wait_all
# in case of error
on_quit

exit 0
