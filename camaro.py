import subprocess
import os
import hashlib
import time
import base64
import hmac
import json
import requests
import signal
from util.need import cmd_write_log
from util.need import TIME_FORMAT


comman1 = '''ffmpeg -f dshow -i video="RMONCAM A2 1080P" -q 4 -s 640*480 -aspect 4:3 -r 10 -vcodec flv -ar 22050 -ab 64k -ac 1 -acodec libmp3lame -threads 4  -pix_fmt yuv420p  -preset ultrafast -tune zerolatency -f flv rtmp://112.94.31.117/RTMP/RtmpVideo'''

#推流的脚本：同时退摄像头和麦克风；同时推到远端的srs和本地的srs
def push(remote_url,local_url,fmt='flv'):
    print('push', os.getpid())
    comman = ['ffmpeg',
              # 0、全局参数
              '-f', 'dshow',
              # '-thread_queue_size','50',
              '-thread_queue_size', '1024',  #1024
              '-rtbufsize', '13M',  #10M
              '-threads:v', '8',  # ffmpegs支持开启多线程
              '-threads:a', '8',
              '-vsync', '1',  #解决音频滞后问题，-async 1 解决音频超前问题
              '-itsscale', '1',  # 2023-03-27设置输入数据速度，坑点，此参数不当会引起视频流的延迟
              # '-itsoffset','-0.1', #2023-03-27，设置时间戳向左偏移，如果不是储存视频文件，或者视频文件推流貌似不起效果
              '-i', '''video=RMONCAM A2 1080P:audio=Microphone (High Definition Audio Device)''',
              #1、视频的配置参数
              # '-tcp_nodelay','1', #2023-03-27 新增
              '-framerate', '25',
              '-vcodec', 'libx264',

              #pix_fmt 这两个设置会降低画质，提升速度
              # '-pix_fmt', 'bgr24',
              '-pix_fmt', 'yuv420p',  #yuv420p
              # '-g', '10', #10帧一个关键帧
              '-force_key_frames', 'expr:gte(t,n_forced*0.5)',  # 强行指定GOP size，缩短关键帧时间，0.5秒插入一个关键帧，缩短拉流等待时间
              # '-x264-params', 'keyint=120:scenecut=0',  #数值/帧数=关键帧间隔  缩短视频播放的等待时间

              '-profile:v', 'baseline',
              '-level', '3.0',
              '-preset:v', 'ultrafast',
              '-tune:v', 'zerolatency',
              # '-vf', '''scale=iw/2:-1''',  #分辨率降低，提高播放的流畅度
              # '-s', '640x480',
              '-vf', '''scale=1920:1080''',  # 提高分辨率1080p = 1920:1080, 720p=1280:720
              '-b:v', '1500k',  # 提高分辨率2   3400
              # '-maxrate','1500k',# 2023-03-27 为了视频流畅播放，设置的大小与b:v  3400
              '-s', '1920x1080',  # 提高分辨率1080p=1920x1080 ,720p=1280x720
              #2、音频的参数
              '-af', '''highpass=f=200,afftdn=nr=10:nf=-30:tn=1,lowpass=f=3000''',  #过滤背景杂音
              '-af', 'arnndn=m=lq.rnnn',  # 使用模型来过略背景杂音
              '-af', 'arnndn=m=sr.rnnn',  # 使用模型来过略背景杂音
              '-af', 'arnndn=m=bd.rnnn',  # 使用模型来过略背景杂音
              '-af', 'arnndn=m=cb.rnnn',  # 使用模型来过略背景杂音

              '-sample_rate', '44100',  #当前麦克风最大支持44100，通道2，bits=16
              '-channels', '1',
              '-acodec', 'aac',
              # '-vcodec', 'h264',
              '-preset:a', 'ultrafast',  #音频编码速度快，画质低，延迟低
              '-tune:a', 'zerolatency',  #音频低时延配置
              '-pes_payload_size', '0',  #播放降低时延
              # '-crf','26',#有效范围是0到63，数字越大表示质量越低，输出越小
              '-r', '25',
              '-f', fmt,
              # ' -flvflags','no_duration_filesize',
              remote_url,  #推流到医院的srs视频服务

              #3、新增，推流到本地的srs服务器上
              '-framerate', '25',
              '-vcodec', 'libx264',
              # pix_fmt 这两个设置会降低画质，提升速度
              # '-pix_fmt', 'bgr24',
              '-pix_fmt', 'yuv420p',
              '-force_key_frames', 'expr:gte(t,n_forced*0.5)',  # 加上这个参数，缩短关键帧时间，减少拉流时间
              '-profile:v', 'baseline',
              '-level', '3.0',
              '-preset:v', 'ultrafast',
              '-tune:v', 'zerolatency',
              '-vf', '''scale=iw/2:-1''',  # 分辨率降低，提高播放的流畅度
              '-s', '640x480',  #640x480
              # # 麦克风[平板拉取本地视频时，不需要麦克风]
              # '-sample_rate', '44100',
              # '-channels', '1',
              # '-acodec', 'aac',
              # # '-vcodec', 'h264',
              # '-preset:a', 'ultrafast',  # 音频编码速度快，画质低，延迟低
              # '-tune:a', 'zerolatency',  # 音频低时延配置
              '-an',
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
        try:
            child = subprocess.Popen(comman, shell=shell,stderr=subprocess.STDOUT,stdout=subprocess.PIPE)
            print(f'执行ffmpeg的进程id：{child.pid}')
            # if child.stderr:
                # print(child.communicate()[0])
                # print('报错了报错了')
                # print(child.stderr.read(), '所有的报错信息')
            '2023-03-28 将终端的输出和报错写到日志中'
            cmd_write_log(f'camaro/{TIME_FORMAT}.log', result=child)
            #等待推流进程结束
            child.wait()
            print(f'推流失败：{co} 次，等待1秒...')
            child.kill()
            co += 1
            time.sleep(1)
        except Exception as e:
            print(e,'这个是报错信息')
            #推流打上日志
            child.kill()
        #报错后，ffmpeg推流进程




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
    print('开机等待20秒，先等待docker启动...')
    time.sleep(20)

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