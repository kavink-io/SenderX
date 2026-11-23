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
limits.BasicLimitInformation.LimitFlags = 0x100 | 0x2000
limits.ProcessMemoryLimit = 256 * 1024 * 1024

res = kernel32.SetInformationJobObject(
    job,
    9,
    ctypes.byref(limits),
    ctypes.sizeof(limits)
)
print('SetInformationJobObject result:', res)

p = subprocess.Popen([sys.executable, '-c', 'print("hello from job object")'], stdout=subprocess.PIPE)
assign_res = kernel32.AssignProcessToJobObject(job, int(p._handle))
print('AssignProcessToJobObject result:', assign_res)
out, _ = p.communicate()
print('Child output:', repr(out.decode().strip()))
kernel32.CloseHandle(job)
