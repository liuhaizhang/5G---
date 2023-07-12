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
from util.need import TIME_FORMAT,audio_cmd_write_log

def play_web_audio(url):
    '''
    url:这个是
    '''
    command = [
        'ffplay',
        '-i' ,f'{url}',
        '-fflags','nobuffer',
        '-flags','low_delay',
        # '-pes_payload_size', '0',
        # "-probesize" , '32', #默认是
        # '-sync', 'ext',
        '-vn',
        '-nodisp'
    ]

    #测试的command
    command =[
        'ffplay',
        '-i', f'{url}',
        '-async','1', #解决偶然发生的拉流太慢
        '-f','live_flv', #表明流是直播，会影响搜索行为，迫使它往前走
        '-fflags', 'nobuffer', #不使用缓存
        '-flags','low_delay', #使用低时延
        '-strict','experimental', #允许ffplay偏离解码器性能标准
        '-vf','setpts=N/60/TB',#这个很关键，强制输入流以60fps，由于流实际上以59.25fps速度运行，我们将慢慢赶上
        '-noframedrop',#避免丢帧，保持流畅度
        '-vn', #不要视频
        '-nodisp', #不要展示画面
    ]
    # os.system(f"ffplay -fflags nobuffer -flags low_delay -i {url} -vn")
    main_pid = os.getpid() #主进程的id
    while True:
        try:
            child = subprocess.Popen(command,stderr=subprocess.STDOUT)
            audio_cmd_write_log(f'audio/{TIME_FORMAT}.log',result=child)
            play_pid = child.pid #播放音频的进程id
            '2、将这两个进程的pid写到txt文件中，到时候先杀掉play进程再杀掉main进程'
            dic = {'main':main_pid,'play':play_pid}
            with open(AUDIO_PID_PATH, 'w') as fp:
                fp.write(str(json.dumps(dic)))
                fp.close()
            child.wait()
            print('退出时，等待3秒...')
            time.sleep(3)
        except Exception as e:
            print('播放视频报错了，等待3秒...')
            time.sleep(3)

#先推流视频给srs
def push_video(url):
    '''
    在拉流播放音频前，必须先推流到srs服务器中
    '''
    mp4 =os.path.join(os.path.dirname(os.path.abspath(__file__)),'util','before-play-audio.mp4')
    print(mp4)

    comman = ['ffmpeg',
              # 0、全局参数
              '-re',
              '-i', f'''{mp4}''',
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
    '''播放医院端的语音，新的，需要util/restart_audio.py 文件 来监听网络中断时，重新启动audio.py程序'''
    STREAM = f'{CAR_NUMBER}-audio'  # web端推流的麦克风
    print(os.getpid(),'main的pid',type(os.getpid()))
    token = encode_token(key=CAR_NUMBER)
    '''0、等等系统开机稳定后再启动'''
    print('开机等待3秒...')
    time.sleep(3)

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


