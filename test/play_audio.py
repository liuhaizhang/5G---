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


def play_web_audio(url,queue):
    '''
    url:这个是
    '''
    command = [
        'ffplay',
        '-i' ,{url},
        '-fflags','nobuffer',
        '-flags','low_delay',
        '-vn',
        '-nodisp'
    ]
    # os.system(f"ffplay -fflags nobuffer -flags low_delay -i {url} -vn")

    child = subprocess.Popen(command)
    # 把播放音频的进程id放到队列中，当队列有数据时，就说明还在拉流
    if queue.empty():
        queue.put(child.pid) #
    else:
        queue.get()
        queue.put(child.pid)


    # child.wait()
    #将subprocess的对象返回，当网络不通时，将播放的进程杀掉

    return child

#先推流视频给srs
def push_video(url):
    '''
    在拉流播放音频前，必须先推流到srs服务器中
    '''
    comman = ['ffmpeg',
              # 0、全局参数
              '-re',
              '-i', '''./util/before-play-audio.mp4''',
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
        child = subprocess.Popen(comman, shell=shell)
        # # print(f'执行ffmpeg的进程id：{child.pid}')
        # if child.stderr:
        #     print(child.stderr.read(), '所有的报错信息')
        child.wait()
        print(f'每次拉流前得先推送一个流')
        break



if __name__ == '__main__':
    '''急救车播放医院端的语音：'''
    #token 是生成的token，需要携带上token才能进行操作
    from util.need import encode_token #token认证
    from util.need import check_ambulance_status #验证急救车是否有急救任务
    from util.need import netstatus #检查网络是否中断
    from util.need import CAR_NUMBER #急救车编号
    from util.need import REMOTE_IP #服务器域名

    STREAM = f'{CAR_NUMBER}-audio'  # web端推流的麦克风

    print(os.getpid(),'main')
    token = encode_token(key=CAR_NUMBER)

    network_url = 'https://'
    play_que = queue.Queue(maxsize=1)
    net_que = queue.Queue(maxsize=1)
    '''0、等等系统开机稳定后再启动'''
    print('开机等待85秒...')
    # time.sleep(85)

    '''1、检测当前急救车是否有急救事件'''
    CHECK_URL = 'https://ambulance.thearay.net/api/srs/ambulance-before-send'
    data = check_ambulance_status(CHECK_URL,CAR_NUMBER)
    # 视频协议使用的端口
    PROTOCOL_PORT = data.get('stream_port')
    print(data)

    url = f'rtmp://{REMOTE_IP}:{PROTOCOL_PORT.get("rtmp")}/{CAR_NUMBER}/{STREAM}?token={token}'
    '''2、在拉流播放前，先推送MP4视频到srs中(推流地址跟步骤3一样)，保证后面拉流正常运行'''
    push_video(url)

    '''3、播放web端的麦克风 音频'''
    child = play_web_audio(url,play_que)

    '''4、检测当前网络是否中断了'''
    threading.Thread(target=netstatus,args=(net_que,)).start()
    is_break=0 #网络中断标识
    re_play= 0 #重新播放的次数
    interrupt = 1 #网络中断的次数
    while True:
        can_online = net_que.get()
        # print(can_online,'是否有网络')
        if not can_online:
            #当前网络中断了
            #判断播放的队列中是否有数据：有就要杀掉播放进程，从队列中取出数据（播放队列没有数据了，就说明播放进程以死，等待有网络时，就重新拉流）
            if not play_que.empty():
                ''' 
                此时网络中断了，且播放队列中还有数据时，说明此时ffplay还在拉流。
                1、在网络中断时，需要将ffplay拉流的进程杀掉，
                2、从播放队列中，将播放进程id取出，这个数据代表播放进程是否在进行中
                '''
                ffplay_pid = play_que.get()
                # print('杀掉的进程id：',ffplay_pid)
                # os.kill(ffplay_pid,signal.SIGINT) #
                child.kill() #把ffplay 进程结束掉
                print('网络中断次数：',interrupt)
                interrupt+=1
                is_break = 1 #网络已经中断了
                time.sleep(10)
            else:
                '''网络中断，但是播放队列中无数据，说明ffplay进程已经被杀死，就无需操作了'''
                #从play_que队列中，取不到播放的进程id时，就不操作
                pass
        else:
            '''
            当急救车可以上网时
            查看播放队列中是否有进程id，
            1、有，就说明播放进程已经被启动了，就无需再启动播放进程
            2、无，说明网络中断以来，播放进程还没有被启动，需要启动播放进程
            '''
            if play_que.empty():
                #必须拿到播放进程的返回值，当网络中断时，需要返回值来杀掉播放进程
                child = play_web_audio(url,queue=play_que)
                re_play+=1
                print("重新拉流，",re_play,'次')
                if is_break==1:
                    is_break = 0
                    print('网络回复了')
            else:
                #播放进程队列有数据，已经启动播放进程了。无需再启动
                pass




