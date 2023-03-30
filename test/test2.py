from util.need import BASE_DIR
from util.need import AUDIO_PID_PATH
from util.need import encode_token
import subprocess
import time
from util.log_ import BaseLog
token = encode_token('car-0001')
print(token)



# 运行cmd过程中获取标准输出与标准错误
def run_cmd(cmd):
    result = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log = BaseLog('screen.log')
    log.start_log()
    contents = []
    while True:
        r = result.stdout.readline().decode('GBK')
        time.sleep(1)
        if r.strip() :
            t =r.strip()
            print(t)
            contents.append(t)
            # log.set_log(f'{r.strip()}')
        if subprocess.Popen.poll(result) != None and not r:
            str_contents = '\n'.join(contents) if contents else ''
            log.set_log(str_contents)
            log.end_log()
            break
    return result
def cmd_write_log(log_file,format,result):
    '''
    log_fle : camaro.log
    format: '%(message)s'
    '''
    log = BaseLog(log_file,format)
    log.start_log()
    contents = []
    while True:
        r = result.stdout.readline().decode('GBK')
        if r.strip() :
            t =r.strip()
            print(t)
            contents.append(t)
            if len(contents)==20:
                str_contents = '\n'.join(contents) if contents else ''
                log.set_log(str_contents)
                contents = []
            # log.set_log(f'{r.strip()}')
        if subprocess.Popen.poll(result) != None and not r:
            str_contents = '\n'.join(contents) if contents else ''
            log.set_log(str_contents)
            log.end_log()
            return

def hanshu():
    import sys
    print(sys._getframe().f_code.co_name)
if __name__ == '__main__':
    hanshu()

