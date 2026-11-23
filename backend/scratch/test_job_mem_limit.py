import ctypes
import subprocess
import sys
from ctypes import wintypes

kernel32 = ctypes.windll.kernel32

class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ('PerProcessUserTimeLimit', wintypes.LARGE_INTEGER),
        ('PerJobUserTimeLimit', wintypes.LARGE_INTEGER),
        ('LimitFlags', wintypes.DWORD),
        ('MinimumWorkingSetSize', ctypes.c_size_t),
        ('MaximumWorkingSetSize', ctypes.c_size_t),
        ('ActiveProcessLimit', wintypes.DWORD),
        ('Affinity', ctypes.c_size_t),
        ('PriorityClass', wintypes.DWORD),
        ('SchedulingClass', wintypes.DWORD),
    ]

class IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ('ReadOperationCount', ctypes.c_uint64),
        ('WriteOperationCount', ctypes.c_uint64),
        ('OtherOperationCount', ctypes.c_uint64),
        ('ReadTransferCount', ctypes.c_uint64),
        ('WriteTransferCount', ctypes.c_uint64),
        ('OtherTransferCount', ctypes.c_uint64),
    ]

class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ('BasicLimitInformation', JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ('IoCounters', IO_COUNTERS),
        ('ProcessMemoryLimit', ctypes.c_size_t),
        ('JobMemoryLimit', ctypes.c_size_t),
        ('PeakProcessMemoryUsed', ctypes.c_size_t),
        ('PeakJobMemoryUsed', ctypes.c_size_t),
    ]

job = kernel32.CreateJobObjectW(None, None)
limits = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
# Limit process commit memory to 40 MB
limits.BasicLimitInformation.LimitFlags = 0x100 | 0x2000
limits.ProcessMemoryLimit = 40 * 1024 * 1024

res = kernel32.SetInformationJobObject(
    job,
    9,
    ctypes.byref(limits),
    ctypes.sizeof(limits)
)

# Allocate 100 MB which exceeds 40 MB limit
cmd = 'try:\n    b = bytearray(100 * 1024 * 1024)\n    print("Success")\nexcept MemoryError:\n    print("Caught MemoryError")'
p = subprocess.Popen([sys.executable, '-c', cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
assign_res = kernel32.AssignProcessToJobObject(job, int(p._handle))
out, err = p.communicate()
print('Return code:', p.returncode)
print('Output:', repr(out.decode().strip()))
print('Stderr:', repr(err.decode().strip()))
kernel32.CloseHandle(job)
