import subprocess
import os
import hashlib
import time
import base64
import hmac
import json
import requests

comman1 = '''ffmpeg -f dshow -i video="RMONCAM A2 1080P" -q 4 -s 640*480 -aspect 4:3 -r 10 -vcodec flv -ar 22050 -ab 64k -ac 1 -acodec libmp3lame -threads 4  -pix_fmt yuv420p  -preset ultrafast -tune zerolatency -f flv rtmp://112.94.31.117/RTMP/RtmpVideo'''


#推流的脚本：同时退摄像头和麦克风；同时推到远端的srs和本地的srs
def push(remote_url,local_url,fmt='flv'):
    print('push', os.getpid())
    comman = ['ffmpeg',
              # 0、全局参数
              '-f', 'dshow',
              # '-thread_queue_size','50',
              '-thread_queue_size', '1048',  #2048
              '-rtbufsize', '10M',  #8M
              '-threads:v', '5',  # ffmpegs支持开启多线程
              '-threads:a', '3',
              '-i', '''video=RMONCAM A2 1080P:audio=Microphone (High Definition Audio Device)''',
              #1、视频的配置参数
              '-framerate', '25',
              '-vcodec', 'libx264', #libx264
              # '-force_key_frames', 'expr:gte(t,n_forced*0.5)',  #降低关键帧间隔，缩短播放拉流时间
              # '-x264-params','keyint=120:scenecut=0',  #减低关键字间隔，缩短播放拉流时间
              #pix_fmt 这两个设置会降低画质，提升速度
              # '-pix_fmt', 'bgr24',
              '-pix_fmt', 'yuv420p',
              '-profile:v', 'baseline',#baseline
              '-level', '5.0',
              '-preset:v', 'ultrafast',#ultrafast
              '-tune:v', 'zerolatency',#zerolatency
              '-vf', '''scale=1980:1080''',  #提高分辨率1
              '-b:v','6400k', #提高分辨率2
              '-s', '1980x1080',  #提高分辨率3

              #2、音频的参数
              '-sample_rate', '44100',
              '-channels', '1',
              '-acodec', 'aac',
              '-preset:a', 'ultrafast',  #音频编码速度快，画质低，延迟低
              '-tune:a', 'zerolatency',  #音频低时延配置
              '-pes_payload_size', '0',  #播放降低时延
              # '-crf','26',#有效范围是0到63，数字越大表示质量越低，输出越小
              '-r', '25',
              '-f', fmt,
              remote_url,  #推流到医院的srs视频服务

              #3、新增，推流到本地的srs服务器上
              '-framerate', '25',
              '-vcodec', 'libx264',
              # pix_fmt 这两个设置会降低画质，提升速度
              # '-pix_fmt', 'bgr24',
              '-pix_fmt', 'yuv420p',
              # '-force_key_frames', 'expr:gte(t,n_forced*0.5)',  # 降低关键帧间隔，缩短播放拉流时间
              '-x264-params', 'keyint=120:scenecut=0',  # 降低关键帧间隔，缩短播放拉流时间
              '-profile:v', 'baseline',
              '-level', '3.0',
              '-preset:v', 'ultrafast',
              '-tune:v', 'zerolatency',
              '-vf', '''scale=iw/2:-1''',  # 分辨率降低，提高播放的流畅度
              '-s', '640x480',  #640x480
              # 麦克风
              '-sample_rate', '44100',
              '-channels', '1',
              '-acodec', 'aac',
              # '-vcodec', 'h264',
              '-preset:a', 'ultrafast',  # 音频编码速度快，画质低，延迟低
              '-tune:a', 'zerolatency',  # 音频低时延配置
              '-pes_payload_size', '0',  # 播放降低时延
              # '-crf','26',#有效范围是0到63，数字越大表示质量越低，输出越小
              '-r', '25',
              '-f', fmt,
              local_url  #推流到本地部署的srs视频服务
              ]
    shell = True
    if type(comman) == 'list':
        shell = False
    co = 1
    while True:
        '''在循环中一直执行， 有了wait，需要等待新开的进程执行完成'''
        child = subprocess.Popen(comman, shell=shell)
        print(f'执行ffmpeg的进程id：{child.pid}')
        if child.stderr:
            print(child.stderr.read(), '所有的报错信息')
        child.wait()
        print(f'推流失败：{co} 次，等待5秒...')
        co+=1
        time.sleep(5)


if __name__ == '__main__':
    '''
    功能：同时收集急救车上麦克风和摄像头的数据，推流到srs服务器上，前端从srs服务器上获取到数据，播放给医院看
    推流地址： rtmp://域名:端口/app/stream?token=xxxx
    1、rtmp，走rtmp的协议
    2、端口：是srs中配置rtmp的端口，默认使用的是1935 ，如果srs中配置的rtmp端口变化，这里就需要变化
    3、流地址：app 代表的一种应用的流的前缀，我们设置为急救车的编号，car-0001(当前急救车在数据库中设置的编号) 
    4、stream：是具体流地址, car-0001-camaro 具体流地址的设置：急救车编号-从哪里获取的流，这里的camaro代表摄像头和麦克风
    '''
    from util.need import check_ambulance_status #检查急救车是否有任务
    from util.need import encode_token#token认证
    from util.need import CAR_NUMBER#急救车编号
    from util.need import REMOTE_IP#服务器域名
    # CAR_NUMBER=当前急救车编号
    # REMOTE_IP=srs服务器的web端
    # 流地址
    STREAM = f'{CAR_NUMBER}-camaro'

    '''1、开机后2分钟再启动脚本'''
    print('开机等待40秒...')
    # time.sleep(40)

    '''2、推送数据前先查看当前急救车是否有任务'''
    CHECK_URL = 'https://ambulance.thearay.net/api/srs/ambulance-before-send'
    data = check_ambulance_status(CHECK_URL,CAR_NUMBER)
    # 视频协议使用的端口,从web端获取，这样如果医院某些没人端口无法提供，可以修改个端口，这样就无需修改急救车段的数据了
    PROTOCOL_PORT = data.get('stream_port')
    print(data,'web传递给来的数据')

    '''3、推送数据'''
    token = encode_token(key=CAR_NUMBER)
    print(token)
    remote_url = f"rtmp://{REMOTE_IP}:{PROTOCOL_PORT.get('rtmp')}/{CAR_NUMBER}/{STREAM}?token={token}"
    local_url = f'rtmp://127.0.0.1:1935/{CAR_NUMBER}/{STREAM}'
    fmt1 = 'flv'
    # time.sleep(40) #开机后，等待2分钟再启动推流，要先等待docker系统启动，等待srs 容器启动
    push(remote_url,local_url ,fmt1)