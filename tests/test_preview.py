import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import time
import unittest
from unittest.mock import patch
import numpy as np
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from preview import PreviewWorker


class SlowCapture:
    def __init__(self,*args):
        self.index = 0
        time.sleep(.15)

    def isOpened(self): return True
    def get(self,prop): return 30.
    def set(self,prop,value):
        time.sleep(.12)
        self.index = value
        return True
    def read(self):
        time.sleep(.06)
        return True,np.full((360,640,3),100,np.uint8)
    def release(self): pass


class PreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def pump_until(self,predicate,timeout=4):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline and not predicate():
            self.app.processEvents()
            time.sleep(.002)
        self.assertTrue(predicate(),'Background preview did not complete')

    def test_slow_decoder_keeps_ui_alive_and_only_latest_seek_wins(self):
        beats=[];results=[]
        timer=QTimer();timer.setInterval(10)
        timer.timeout.connect(lambda:beats.append(time.monotonic()))
        worker=PreviewWorker('fixture')
        worker.ready.connect(results.append)
        clip=dict(start=0,end=10,crop_keyframes=[dict(time=0,x=.5,y=.5,zoom=1)])
        with patch('preview.cv2.VideoCapture',SlowCapture):
            timer.start();worker.start()
            try:
                for token in range(100):
                    worker.request(token,token/30,clip,{})
                self.pump_until(lambda:bool(results))
                self.assertEqual(results[-1]['token'],99)
                self.assertGreater(len(beats),10)
                self.assertLess(max(b-a for a,b in zip(beats,beats[1:])),.15)
                self.assertLessEqual(len(results),2)
            finally:
                timer.stop();worker.stop()
                self.pump_until(lambda:not worker.isRunning())

    def test_stop_during_decode_does_not_block_caller(self):
        worker=PreviewWorker('fixture')
        with patch('preview.cv2.VideoCapture',SlowCapture):
            worker.start()
            start=time.monotonic();worker.stop()
            self.assertLess(time.monotonic()-start,.05)
            self.pump_until(lambda:not worker.isRunning())
