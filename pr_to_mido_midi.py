import numpy as np
import mido
from threading import Thread
from queue import Queue
import time
from struct import Struct
from itertools import cycle

class time_counter(Thread):
    def __init__(self,resolution):
        """ resolution is how often to increment the time counter and by how
        much """
        Thread.__init__(self)
        self.resolution = resolution
        self.count = 0
        self.done = True
    def set_count(self,count):
        """ We might not want to start at 0 """
        self.count = count
    def run(self):
        self.done = False
        while not self.done:
            time.sleep(self.resolution)
            self.count += self.resolution

class frame_midi_scheduler(Thread):
    def __init__(self,
    # where to read frames from
    # expects it to have next_frame() method, which blocks until a frame is available
    frame_stream, 
    # something counting the time
    counter,
    # something that converts frames to a list of MIDI events
    # must return empty list if no events are to be sent
    frame_midi_converter,
    # a queue for midi_events, this will put events onto that queue.
    # must have "put" method (e.g., it could be a subclass of queue.Queue)
    midi_event_queue,
    # if an event comes in late, it is discarded
    discard_late=False
    ): 
        Thread.__init__(self)
        self.frame_stream = frame_stream
        self.counter = counter
        self.done = True
        self.frame_midi_converter = frame_midi_converter
        self.midi_event_queue = midi_event_queue
        self.discard_late = discard_late
    def run(self):
        print("frame_midi_scheduler starting")
        self.done = False
        while not self.done:
            frame = self.frame_stream.next_frame()
            #print(frame)
            time_stamp = self.frame_midi_converter.raw_midi_frame_converter.time_stamp(frame)
            if not self.counter.is_alive():
                # set the intial time to the time of this frame and start the
                # counter
                self.counter.set_count(
                time_stamp)
                self.counter.start()
            if self.discard_late and (time_stamp < self.counter.count):
                # discard, too late
                continue
            # get midi events from frame
            midi_events = self.frame_midi_converter(frame)
            # put midi events into queue (will do nothing if midi_events is
            # empty)
            for event in midi_events:
                self.midi_event_queue.put(event)
            time.sleep(0.1)

class midi_event_player(Thread):
    def __init__(self,
    # queue where to look for MIDI events
    midi_event_queue,
    # something counting the time
    counter,
    # something responding to the send message, which will take midi events
    midi_port):
        Thread.__init__(self)
        self.done = True
        self.midi_event_queue = midi_event_queue
        self.counter = counter
        self.midi_port = midi_port
    def run(self):
        print("midi_event_player starting")
        self.done = False
        while not self.done:
            #if (len(self.midi_event_queue.queue) > 0):
            #    print(self.midi_event_queue.queue[0].timestamp)
            #    print(self.counter.count)
            #while ((self.midi_event_queue.qsize() > 0) and 
            #(self.counter.count > self.midi_event_queue.queue[0].timestamp)):
            ev = self.midi_event_queue.get()
            if ev.timestamp <= self.counter.count:
                self.midi_port.send(ev)
                #print("timestamp: %f" % (ev.timestamp,))
                #print("counter: %f" % (self.counter.count,))
            else:
                # put back
                self.midi_event_queue.put(ev)
                time.sleep(0.1)

class raw_midi_frame:
    """ Routines for converting packed bytes into a midi event """
    def __init__(self,
    # the number of notes in piano roll frame
    n_notes=88,
    # the MIDI note of the lowest frame
    transposition=21):
        self.n_notes = n_notes
        self.transposition = transposition
        self._unpacker = Struct("d%df" % (self.n_notes,))
    def packed_size(self):
        return self._unpacker.size
    def time_stamp(self,frame):
        # parse the time stamp, returns a double
        dat=self._unpacker.unpack(frame)
        ts = dat[0]
        return ts
    def unpack(self,b):
        """ Returns 2 numpy arrays, one containing just the time stamp, the other the frame activations """
        dat=self._unpacker.unpack(b)
        ts = np.array(dat[0],dtype='float64')
        act = np.array(dat[1:],dtype='float32')
        return (ts,act)

class midi_msg:
    def __init__(self,timestamp):
        self.timestamp = timestamp
    def __lt__(self, other):
        return (self.timestamp < other.timestamp)

class note_on_midi_msg(midi_msg):
    def __init__(self,
    timestamp,
    pitch,
    velocity,
    channel=0,
    ):
        midi_msg.__init__(self,timestamp)
        self.channel = channel
        self.pitch = pitch
        self.velocity = velocity
    def as_mido_midi_msg(self):
        return mido.Message(
        'note_on',
        channel=self.channel,
        note=self.pitch,
        velocity=self.velocity)
    def __str__(self):
        return "note_on %d %d %d" % (self.channel,self.pitch,self.velocity)

class note_off_midi_msg(midi_msg):
    def __init__(self,
    timestamp,
    pitch,
    velocity,
    channel=0,
    ):
        midi_msg.__init__(self,timestamp)
        self.channel = channel
        self.pitch = pitch
        self.velocity = velocity
    def as_mido_midi_msg(self):
        return mido.Message(
        'note_off',
        channel=self.channel,
        note=self.pitch,
        velocity=self.velocity)
    def __str__(self):
        return "note_off %d %d %d" % (self.channel,self.pitch,self.velocity)

class midi_event:
    """ A very simple implementation, just a time stamp and midi message. """
    def __init__(self,
    timestamp,
    msg):
        self.timestamp = timestamp
        self.msg = msg

class frame_midi_converter:
    def __init__(self,
    # a class that converts from raw bytes to (timestamp,activations) pair by
    # calling unpack
    raw_midi_frame_converter=raw_midi_frame(),
    program=0,
    transposition=0,
    n_pitches=88,
    velocity_scalar=100,
    channel=0):
        self.raw_midi_frame_converter = raw_midi_frame_converter
        self.transposition = transposition
        self.velocity_scalar = velocity_scalar
        # each row of _notes is (start_time,end_time,velocity,pitch)
        self._notes = np.full((n_pitches,4),0,dtype='float32')
        self._notes[:,-1]=np.arange(n_pitches)
        self._last_active = np.full(n_pitches,0,dtype='int32')
        self.channel = channel
    
    def _note_ons_from_notes(self,notes):
        ret = []
        for note in notes:
            ret.append(
            note_on_midi_msg(
            timestamp=note[1],
            channel=self.channel,
            pitch=int(self.transposition + note[-1]),
            velocity=self.velocity_scalar))
        return ret

    def _note_offs_from_notes(self,notes):
        ret = []
        for note in notes:
            ret.append(
            note_off_midi_msg(
            timestamp=note[1],
            channel=self.channel,
            pitch=int(self.transposition + note[-1]),
            velocity=0))
        return ret
            
    def __call__(self,frame):
        # where to hold result     
        events=[]
        # unpack timestamp and piano roll activations slice
        timestamp,pr_slice = self.raw_midi_frame_converter.unpack(frame)
        # find those that are active currently
        now_active = (pr_slice > 0).astype('int32')
        # new notes are ones that weren't active before
        new_notes = (self._last_active - now_active) < 0
        # off notes are ones that were active before and are now off
        off_notes = (self._last_active - now_active) > 0
        # store the time they went off using the timestamp
        self._notes[off_notes,1] = timestamp
        # make into midi note events
        events += self._note_offs_from_notes(self._notes[off_notes])
        # now turn them off
        self._last_active[off_notes] = 0
        # TODO timestamp not currently used, but available
        # mido doesn't have that precise of scheduling capabilities
        self._notes[new_notes,0] = timestamp
        self._notes[new_notes,2] = pr_slice[new_notes]
        # make the new notes
        events += self._note_ons_from_notes(self._notes[new_notes])
        self._last_active[new_notes] = 1
        return events

class midi_port:
    def send(ev):
        return NotImplemented

class mido_midi_port:
    def __init__(self,
    # TODO for now just leave port_name as None, it seems like picking a
    # specific port is broken
    port_name=None,
    backend='mido.backends.portmidi'):
        mido.set_backend(backend)
        self._port = mido.open_output(port_name)
    def __del__(self):
        self._port.close()
    def send(self,midi_ev):
        ev = midi_ev.as_mido_midi_msg()
        print("sending: " + str(ev))
        self._port.send(ev)

class midi_note_frame_stream_fd:
    def __init__(self,
    fd,
    raw_midi_frame_parser=raw_midi_frame()):
        self._fd = fd 
        self._raw_midi_frame_parser = raw_midi_frame_parser
    def get_frame_parser(self):
        return self._raw_midi_frame_parser
    def next_frame(self):
        dat = b''
        dat_rem = self._raw_midi_frame_parser.packed_size()
        while dat_rem > 0:
            dat += self._fd.buffer.read(dat_rem)
            dat_rem = self._raw_midi_frame_parser.packed_size() - len(dat)
        return dat

class test_midi_note_frame_stream:
    """ A fake midi note stream. """
    def __init__(self,
    # number of notes in frame
    n_notes=88,
    # possible delay times for a note
    times=[1.0],
    raw_midi_frame_parser=raw_midi_frame(),
    prob_on=0.5):
        self.n_notes = n_notes
        self.times = times
        self.cur_time = 0
        self._raw_midi_frame_parser = raw_midi_frame_parser
        self.prob_on = prob_on
        self._note_vects=[
        np.zeros(n_notes,dtype='float32') for _ in range(4)]
        self._note_vects[0][40] = 1
        self._note_vects[1][47] = 1
        self._note_vects[2][44] = 1
        self.note_vects = cycle(self._note_vects)
    def get_frame_parser(self):
        return self._raw_midi_frame_parser
    def next_frame(self):
        """ Get a frame with fake delay """
        delta_time = self.times[np.random.randint(len(self.times))]
        print(delta_time)
        # time jitter really screws stuff up
        time_jitter = 0 #np.random.standard_normal(1)*0.001
        time.sleep(max(delta_time+time_jitter,0))
        self.cur_time += delta_time
        #out_frame = (np.random.uniform(0,1,88) > (1 - self.prob_on)).astype('float32')
        out_frame = next(self.note_vects)
        out_time = np.array(self.cur_time,dtype='float64')
        b = out_time.tobytes() + out_frame.tobytes()
        return b
