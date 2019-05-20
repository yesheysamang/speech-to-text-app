#!/usr/bin/env python

# Copyright 2017 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Google Cloud Speech API sample application using the streaming API.

NOTE: This module requires the additional dependency `pyaudio`. To install
using pip:

    pip install pyaudio

Example usage:
    python transcribe_streaming_mic.py
"""

# [START import_libraries]
from __future__ import division
from tuning import Tuning

import usb.core
import usb.util
import time
import re
import sys
import os

from google.cloud import speech
from google.cloud.speech import enums
from google.cloud.speech import types
from google.api_core import exceptions

import pyaudio
from six.moves import queue

from Tkinter import *
import random

# [END import_libraries]

# Audio recording parameters
RATE = 16000
CHUNK = int(RATE / 1000)  # 100ms
RESPEAKER_INDEX = 2
PERSON_1_KEY = 1

# GUI parameters 
WIDTH = 600
HEIGHT  = 600

class Application(Frame):
    def __init__(self, master):
        Frame.__init__(self, master)
        self.grid()
        self.create_widgets()

    def __del__(self):
        self.grid().close()
        self.create_widgets().close()

    def create_widgets(self):
        self.person_1 = Label(self, text = "Person 1 is saying: ")
        self.person_1.grid(row=0, column=0,columnspan=2,sticky=W)

        self.content_1 = Text(self, width=50, height=5)
        self.content_1.grid(row=1,column=1,sticky=W)
        
        self.person_1_doa = Label(self, text = "Person 1 Direction of Arrival (Degrees): ")
        self.person_1_doa.grid(row=2, column=0,columnspan=2,sticky=W)

        self.content_1_doa = Text(self, width=10, height=1)
        self.content_1_doa.grid(row=3, column=1,sticky=W)

        self.person_2 = Label(self, text = "Person 2 is saying: ")
        self.person_2.grid(row=0, column=20,columnspan=2,sticky=W)

        self.content_2 = Text(self, width=50, height=5)
        self.content_2.grid(row=1,column=20,sticky=W)

        self.person_2_doa = Label(self, text = "Person 2 Direction of Arrival (Degrees): ")
        self.person_2_doa.grid(row=2, column=20,columnspan=2,sticky=W)

        self.content_2_doa = Text(self, width=10, height=1)
        self.content_2_doa.grid(row=3,column=20,sticky=W)


class Person():
    def __init__(self):
        self.doa = 0
        self.content = ""
    
    def __del__(self):
        print self.doa,'died'
        print self.content, 'died'        

class MicrophoneStream(object):
    """Opens a recording stream as a generator yielding the audio chunks."""
    def __init__(self, rate, chunk):
        self._rate = rate
        self._chunk = chunk

        # Create a thread-safe buffer of audio data
        self._buff = queue.Queue()
        self.closed = True

    def __enter__(self):
        self._audio_interface = pyaudio.PyAudio()
        self._audio_stream = self._audio_interface.open(
            format=pyaudio.paInt16,
            # The API currently only supports 1-channel (mono) audio
            # https://goo.gl/z757pE
            channels=1, rate=self._rate,
            input=True, frames_per_buffer=self._chunk, input_device_index = RESPEAKER_INDEX,
            # Run the audio stream asynchronously to fill the buffer object.
            # This is necessary so that the input device's buffer doesn't
            # overflow while the calling thread makes network requests, etc.
            stream_callback=self._fill_buffer
        )

        self.closed = False

        return self

    def __exit__(self, type, value, traceback):
        self._audio_stream.stop_stream()
        self._audio_stream.close()
        self.closed = True
        # Signal the generator to terminate so that the client's
        # streaming_recognize method will not block the process termination.
        self._buff.put(None)
        self._audio_interface.terminate()

    def _fill_buffer(self, in_data, frame_count, time_info, status_flags):
        """Continuously collect data from the audio stream, into the buffer."""
        self._buff.put(in_data)
        return None, pyaudio.paContinue

    def generator(self):
        while not self.closed:
            # Use a blocking get() to ensure there's at least one chunk of
            # data, and stop iteration if the chunk is None, indicating the
            # end of the audio stream.
            chunk = self._buff.get()
            if chunk is None:
                return
            data = [chunk]

            # Now consume whatever other data's still buffered.
            while True:
                try:
                    chunk = self._buff.get(block=False)
                    if chunk is None:
                        return
                    data.append(chunk)
                except queue.Empty:
                    break

            yield b''.join(data)

# [END audio_stream]
#def get_direction_of_arrival()

def listen_print_loop(responses, Mic_tuning, person1, person2):
    """Iterates through server responses and prints them.

    The responses passed is a generator that will block until a response
    is provided by the server.

    Each response may contain multiple results, and each result may contain
    multiple alternatives; for details, see https://goo.gl/tjCPAU.  Here we
    print only the transcription for the top alternative of the top result.

    In this case, responses are provided for interim results as well. If the
    response is an interim one, print a line feed at the end of it, to allow
    the next result to overwrite it, until the response is a final one. For the
    final one, print a newline to preserve the finalized transcription.
    """
    print "Say something I'm giving up on you"
    num_chars_printed = 0
    global PERSON_1_KEY
    
    # GUI Initialization
    root = Tk()
    display = Canvas(root, width=WIDTH, height=HEIGHT)
    root.title("Speech-to-Text")
    root.geometry('800x800')
    app = Application(root)
    app.create_widgets()
    
    for response in responses:   
        o = display.create_oval(275, 275,325, 325, fill="red")
        # display.create_text(175,225, text="User")
        
        display.create_text(300,300, text="User")
        display.grid(row=8, column=0)
        print "ITERATE!!!!"
        try:
            currentDirection = Mic_tuning.direction
            #time.sleep(0.1)
        except:
            break
        
        if PERSON_1_KEY:
            PERSON_1_KEY = 0
            person1.doa = currentDirection   

        if not response.results:
            #app.content_1.delete(1, END)
            continue

        # The `results` list is consecutive. For streaming, we only c are about
        # the first result being considered, since once it's `is_final`, it
        # moves on to considering the next utterance.
        result = response.results[0]
        if not result.alternatives:
            continue

        # Display the transcription of the top alternative.
        transcript = result.alternatives[0].transcript
        # print(transcript + ' ')
        # Display interim results, but with a carriage return at the end of the
        # line, so subsequent lines will overwrite them.
        #
        # If the previous result was longer than this one, we need to print
        # some extra spaces to overwrite the previous result
        overwrite_chars = ' ' * (num_chars_printed - len(transcript))

        if not result.is_final:
            # Outputs different iterations of transcribed text before final version
            #sys.stdout.write(transcript + overwrite_chars + '\r')
            #sys.stdout.flush()

            num_chars_printed = len(transcript)
            
        else:
            # Clear text fields, for next iteration of transcribed text
            app.content_1.delete(0.0,END)
            app.content_1_doa.delete(0.0,END)
            app.content_2.delete(1.0,END)
            app.content_2_doa.delete(1.0,END)
        
            if ((currentDirection <= 90) or (currentDirection >= 270)):
                person1.content = transcript + overwrite_chars
                person1.doa = currentDirection
               
                # Clear Boxes and labels from canvas associated with person1
                display.delete('P1-box')
                display.delete('P1-text')
                # Display Green Box for person 1 when between specified intervals
                if ((person1.doa <= 22.5) or (person1.doa >= 337.5)):
                    display.create_rectangle(550,275,600,325, fill="green",tags="P1-box")
                    display.create_text(575, 300, text="P1", tags="P1-text")

                elif ((person1.doa > 22.5) and (person1.doa <= 45)):
                    display.create_rectangle(500,150,550, 200, fill="green",tags="P1-box")
                    display.create_text(525, 175, text="P1", tags="P1-text")

                elif ((person1.doa > 45) and (person1.doa <= 67.5)):
                    display.create_rectangle(425,50,475,100, fill="green",tags="P1-box")
                    display.create_text(450, 75, text="P1", tags="P1-text")

                elif ((person1.doa > 67.5) and (person1.doa <= 90)):
                    display.create_rectangle(275,0,325,50, fill="green",tags="P1-box")
                    display.create_text(300, 25, text="P1", tags="P1-text")

                elif ((person1.doa > 315) and (person1.doa < 337.5)):
                    display.create_rectangle(500,400,550,450, fill="green",tags="P1-box")
                    display.create_text(525, 425, text="P1", tags="P1-text")   

                elif ((person1.doa > 292.5) and (person1.doa <= 315)):
                    display.create_rectangle(425,500,475,550, fill="green",tags="P1-box")
                    display.create_text(450, 525, text="P1", tags="P1-text")  
                
                elif ((person1.doa > 270) and (person1.doa <= 292.5)):
                    display.create_rectangle(275,550,325,600, fill="green",tags="P1-box")
                    display.create_text(300, 575, text="P1", tags="P1-text")             
            else:
                person2.doa = currentDirection
                person2.content = transcript + overwrite_chars
                
                # Clear Boxes and labels from canvas associated with person2
                display.delete('P2-box')
                display.delete('P2-text')

                if ((person2.doa > 90) and (person2.doa <= 112.5)):
                    display.create_rectangle(275,0,325,50, fill="orange",tags="P2-box")
                    display.create_text(300, 25, text="P2", tags="P2-text")

                elif ((person2.doa > 112.5) and (person2.doa <= 135)):
                    display.create_rectangle(275,50,225,100, fill="orange",tags="P2-box")
                    display.create_text(250, 75, text="P2", tags="P2-text")

                elif ((person2.doa > 135) and (person2.doa <= 157.5)):
                    display.create_rectangle(100,150,50, 200, fill="orange",tags="P2-box")
                    display.create_text(75, 175, text="P2", tags="P2-text")

                elif ((person2.doa > 157.5) and (person2.doa <= 202.5)):
                    display.create_rectangle(50,275,0,325, fill="orange",tags="P2-box")
                    display.create_text(25, 300, text="P2", tags="P2-text")

                elif ((person2.doa > 202.5) and (person2.doa <= 225)):
                    display.create_rectangle(100,400,50,450, fill="orange",tags="P2-box")
                    display.create_text(75, 425, text="P2", tags="P2-text")   

                elif ((person2.doa > 225) and (person2.doa <= 247.5)):
                    display.create_rectangle(75,500,125,550, fill="orange",tags="P2-box")
                    display.create_text(150, 525, text="P2", tags="P2-text")                  
                
                elif ((person2.doa > 247.5) and (person2.doa <= 270)):
                    display.create_rectangle(275,550,325,600, fill="orange",tags="P2-box")
                    display.create_text(300, 575, text="P2", tags="P2-text")             
            
            # Update text fields with transcribed text
            app.content_1.insert(0.0,person1.content)
            app.content_1_doa.insert(1.0, person1.doa)
            app.content_2.insert(2.0,person2.content)
            app.content_2_doa.insert(3.0, person2.doa)

            root.update_idletasks()
            root.update()

            #print"Current DOA: %d \n" % currentDirection
            # print"Person 1 Content: %s \n" % person1.content
            # #print(transcript + overwrite_chars)
            # print"Person 1 DOA: %d \n" % person1.doa
            # print"\nPerson 2 Content: %s \n" % person2.content
            # print"Person 2 DOA: %d \n" % person2.doa
            # Exit recognition if any of the transcribed phrases could be
            # one of our keywords.
            if re.search(r'\b(exit|quit)\b', transcript, re.I):
                print('Exiting..')
                break

            num_chars_printed = 0
        #Mic_tuning.reset()






def main():
    # See http://g.co/cloud/speech/docs/languages
    # for a list of supported languages.
    language_code = 'en-US'  # a BCP-47 language tag
    person1 = Person()
    person2 = Person()

    client = speech.SpeechClient()
    config = types.RecognitionConfig(
        encoding=enums.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=RATE,
        language_code=language_code)
    streaming_config = types.StreamingRecognitionConfig(
        config=config,
        interim_results=True)

    with MicrophoneStream(RATE, CHUNK) as stream:
        dev = usb.core.find(idVendor=0x2886, idProduct=0x0018)
        if dev:
            Mic_tuning = Tuning(dev)
            audio_generator = stream.generator()
            requests = (types.StreamingRecognizeRequest(audio_content=content)
                        for content in audio_generator)

            responses = client.streaming_recognize(streaming_config, requests)
            # Now, put the transcription responses to use.
            listen_print_loop(responses, Mic_tuning, person1, person2)

if __name__ == '__main__':
    main()
