#ffplay -fflags nobuffer -flags low_delay -i 'srt://srs.thearay.com:10080?streamid=#!::h=live/livestream,m=request&latency=20'
import subprocess
import os
import threading
import time
import json
import hmac
import base64
import queue
import requests
import signal
import multiprocessing

#token 是生成的token，需要携带上token才能进行操作
from util.need import encode_token #token认证
from util.need import check_ambulance_status #验证急救车是否有急救任务
from util.need import netstatus #检查网络是否中断
from util.need import CAR_NUMBER #急救车编号
from util.need import REMOTE_IP #服务器域名
from util.need import AUDIO_PID_PATH #audio的进程id文件存放路径

def play_web_audio(url):
    '''
    url:这个是
    '''
    command = [
        'ffplay',
        '-i' ,{url},
        '-fflags','nobuffer',
        '-flags','low_delay',
        # '-pes_payload_size', '0',
        # "-probesize" , '32', #默认是
        # '-sync', 'ext',
        '-vn',
        '-nodisp'
    ]
    # os.system(f"ffplay -fflags nobuffer -flags low_delay -i {url} -vn")
    main_pid = os.getpid() #主进程的id
    while True:
        try:
            child = subprocess.Popen(command)
            play_pid = child.pid #播放音频的进程id
            '2、将这两个进程的pid写到txt文件中，到时候先杀掉play进程再杀掉main进程'
            dic = {'main':main_pid,'play':play_pid}
            with open(AUDIO_PID_PATH, 'w') as fp:
                fp.write(str(json.dumps(dic)))
                fp.close()
            child.wait()
        except Exception as e:
            print('播放视频报错了，等待3秒...')
            time.sleep(3)

#先推流视频给srs
def push_video(url):
    '''
    在拉流播放音频前，必须先推流到srs服务器中
    '''
    comman = ['ffmpeg',
              # 0、全局参数
              '-re',
              '-i', '''../util/before-play-audio.mp4''',
              '-ss','2',
              '-c','copy',
              '-r', '25',
              '-f', 'flv',
              url,  # 推流到医院的srs视频服务

              ]
    shell = True
    if type(comman) == 'list':
        shell = False
    while True:
        '''在循环中一直执行， 有了wait，需要等待新开的进程执行完成'''
        child = subprocess.Popen(comman, shell=shell,)

        child.wait()
        print(f'每次拉流前得先推送一个流')
        break

if __name__ == '__main__':
    STREAM = f'{CAR_NUMBER}-audio'  # web端推流的麦克风
    print(os.getpid(),'main的pid',type(os.getpid()))
    token = encode_token(key=CAR_NUMBER)
    '''0、等等系统开机稳定后再启动'''
    print('开机等待85秒...')
    # time.sleep(85)

    '''1、检测当前急救车是否有急救事件'''
    CHECK_URL = f'https://{REMOTE_IP}/api/srs/ambulance-before-send'
    data = check_ambulance_status(CHECK_URL,CAR_NUMBER)
    # 视频协议使用的端口
    PROTOCOL_PORT = data.get('stream_port')
    print(data)

    '3、先推送音频上去'
    url = f'rtmp://{REMOTE_IP}:{PROTOCOL_PORT.get("rtmp")}/{CAR_NUMBER}/{STREAM}?token={token}'
    push_video(url)

    '''4、执行播放医院端音频'''
    url = f'rtmp://{REMOTE_IP}:{PROTOCOL_PORT.get("rtmp")}/{CAR_NUMBER}/{STREAM}?token={token}'
    play_web_audio(url)


