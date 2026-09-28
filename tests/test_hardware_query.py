import unittest
from unittest.mock import Mock,patch
from runtime import hardware


class HardwareQueryTests(unittest.TestCase):
    def test_driver_query_does_not_load_transcription_engine(self):
        import builtins
        real_import=builtins.__import__
        def guarded(name,*args,**kwargs):
            if name in ('ctranslate2','faster_whisper'):
                raise AssertionError('Hardware panel must not import transcription engine')
            return real_import(name,*args,**kwargs)
        driver=Mock()
        driver.cuInit.return_value=0
        def count(pointer):
            pointer._obj.value=1
            return 0
        driver.cuDeviceGetCount.side_effect=count
        with patch('builtins.__import__',side_effect=guarded),patch('ctypes.CDLL',return_value=driver),patch('runtime.enable_cuda_libraries'),patch('runtime.subprocess.run',return_value=Mock(returncode=0,stdout='NVIDIA test')):
            result=hardware()
        self.assertTrue(result['cuda'])
        self.assertTrue(result['nvenc'])

    def test_missing_cuda_driver_keeps_cpu_available(self):
        with patch('ctypes.CDLL',side_effect=OSError('No CUDA driver')),patch('runtime.enable_cuda_libraries'),patch('runtime.subprocess.run',return_value=Mock(returncode=1,stdout='')):
            result=hardware()
        self.assertFalse(result['cuda'])
        self.assertFalse(result['nvenc'])
        self.assertEqual(result['name'],'CPU')
