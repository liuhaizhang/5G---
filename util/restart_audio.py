import subprocess
import os
import json
import time
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#存放拉流医院麦克风脚本的进程id文件
AUDIO_PID_PATH=os.path.join(BASE_DIR,'pid-file','audio_pid.txt') #audio.py执行时进程的保存的文件位置
AUDIO_CODE_PATH = os.path.join(BASE_DIR,'audio.py') #audio.py文件所在位置

#测试网络，网络中断时，杀掉播放音频的进程，网络恢复时，启动播放音频的脚本
def restart_network_break():
    print('网络中断检测恢复功能.....')
    while True:
        print('-----外层循环------')
        child = subprocess.run('ping www.baidu.com -n 3', stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        # print(child.returncode, '返回状态码')
        if child.returncode:#1代表网络不通
            # 网络中断了
            with open(AUDIO_PID_PATH,'r') as fp:
                dic = fp.readline()
            with open(AUDIO_PID_PATH,'w') as fp:
                fp.write('0')
            if dic.strip().isdigit():
                #如果从audio_pid.txt文件中获取的内容是数值0，说明当前audio.py进程已经被杀掉了
                pass
            else:
                try:
                    dic =json.loads(dic)
                    main_pid = dic.get('main')
                    play_pid = dic.get('play')
                    play = subprocess.Popen(['taskkill', '-f', '-pid', f'{play_pid}'], shell=False)
                    main = subprocess.Popen(['taskkill', '-f', '-pid', f'{main_pid}'], shell=False)
                    print(f'main返回值 = {main.returncode}')
                    print(f'play返回值 = {play}')
                except Exception as e:
                    pass

            while True:
                print('-----网络中断后，等待网络恢复层循环-----')
                child = subprocess.run('ping www.baidu.com -n 3', stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       shell=True)
                if not child.returncode:#child.returncode=0,网络通
                    #此时网络通了
                    #启动播放音频的函数

                    try:
                        play_chile = subprocess.Popen(['python',f'{AUDIO_CODE_PATH}'], shell=False)
                        play_chile.wait(3)
                        print('----内层启动播放进程成功....')
                    except Exception as e:
                        pass
                    #网络恢复后，跳出到外层循环继续
                    break
                time.sleep(1)
        else:
            # 能连接上网络时，队列中放1，代表有网络
            pass
        time.sleep(1)

if __name__ == '__main__':
    '''
    1、这个脚本需要一开机就启动，用来监听网络是否中断了
    2、播放音频的脚本，在网络中断后，再恢复后，无法正常使用，需要这个程序来重启播放音频的脚本
    '''
    restart_network_break()