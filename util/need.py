import socket
import time
import json
import hmac
import base64
import requests
import subprocess
import os
import signal

# 当前急救车编号
CAR_NUMBER = 'car-0001'
# srs服务器的web端
REMOTE_IP = 'ambulance.thearay.net'
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#存放拉流医院麦克风脚本的进程id文件
AUDIO_PID_PATH=os.path.join(BASE_DIR,'pid-file','audio_pid.txt')
AUDIO_CODE_PATH = os.path.join(BASE_DIR,'test','audio.py') #测试的接口audio位置
#时间格式
TIME_FORMAT = time.strftime('%Y-%m-%d')
TIME_STAMP = time.time()

#获取当前急救车的局域网IP地址【check_ambulance_status使用】
def getip():
    '''获取急救车的局域网IP地址，传递给后端保存起来，平板拉流就直接从局域网拉流'''
    while True:
        try:
             s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
             s.connect(("8.8.8.8", 80))
             ip = s.getsockname()[0]
        except:
            ip = None
        finally:
            s.close()
        if ip:
            return ip
        time.sleep(2)

#急救车端生成的token信息【所有脚本都使用】
def encode_token(key, expire=2*24*60*60):
    r'''
    @Args:
     key: str (用户给定的key，需要用户保存以便之后验证token,每次产生token时的key 都可以是同一个key)
     expire: int(最大有效时间，单位为s)
    @Return:
     state: str
    '''

    live_time = time.time() + expire
    # ts_byte = ts_str.encode("utf-8")
    #把急救车编号放到里面
    dic = {'car_number':key,'time':live_time}
    dic = json.dumps(dic)
    # print(dic,type(dic))
    #急救车编号当盐
    sha1_tshexstr = hmac.new(key.encode("utf-8"), dic.encode('utf-8'), 'sha1').hexdigest()
    token = dic + '#' + sha1_tshexstr
    # print(token)
    b64_token = base64.urlsafe_b64encode(token.encode("utf-8"))
    return b64_token.decode("utf-8")

#查看当前急救车是否有急救任务【所有脚本都使用】
def check_ambulance_status(url,car_number):
    '''
    检测当前急救车是否有急救任务的，如果没有就把访问频率降低
    '''
    co = 0
    #获取急救车IP地址
    ip = getip()
    while True:
        #当前急救车的编号
        token = encode_token(key=car_number)#生成token
        headers = {
            'content-type': 'application/json',
            'token': token,
            'User-Agent':"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:105.0) Gecko/20100101 Firefox/105.0",
        }
        try:
            r = requests.post(url,data=json.dumps({'car_number':car_number,'ip':ip}),headers=headers)
            # print(r.content)
            if r.status_code == 200:
                print('当前急救车有急救任务，可以推送数据',url,time.strftime('%Y-%m-%d %H:%M:%S'))
                data = r.json().get('data') #拿到当前急救车的急救任务编号
                return data
            else:
                #清空队列

                if co<5:
                    #前5次请求，如果急救车没有急救任务，则休眠5秒
                    print('当前急救车没有急救任务,5次请求内，睡眠5秒...')
                    time.sleep(5)

                else:
                    #超过5次，急救车都是没有急救任务的，就休眠1分钟
                    print('当前急救车没有急救任务,超过5次请求，睡眠60秒...')
                    time.sleep(60)
                co+=1

        except Exception as e :
            print('服务器请求超时，睡眠5秒...')
            print('服务器报错=',str(e))
            co+=1
            time.sleep(5)

#测试当前网络是否可用 【给play_audio.py使用，旧的脚本】
def netstatus(queue):
    '''测试当前机器的网络是否可用'''
    while True:
        child = subprocess.run('ping www.baidu.com -n 2', stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        # print(child.returncode, '返回状态码')
        if child.returncode:
            #连不上网时，队列中放0，代表网络不通
            if queue.empty():
                queue.put(0)
            else:
                queue.get()
                queue.put(0)
        else:
            #能连接上网络时，队列中放1，代表有网络
            if queue.empty():
                queue.put(1)
            else:
                queue.get()
                queue.put(1)

#记录camaro.py 调用的cmd，记录cmd的运行日志
def cmd_write_log(log_file,format='%(message)s',result=None):
    '''
    功能： subprocess 开启一个终端执行程序，需要将终端的输出和报错都写到日志中
    log_fle : camaro.log
    format: '%(message)s'
    '''
    from util.log_ import BaseLog
    log = BaseLog(log_file,format)
    log.start_log()
    contents = []
    try:
        while True:
            r = result.stdout.readline().decode('GBK')
            if r.strip() :
                t =r.strip()
                #将cmd的输出打印到控制上
                print(t)
                contents.append(t)
                if len(contents)==2:
                    #每2行写一次日志
                    str_contents = '\n'.join(contents) if contents else ''
                    log.set_log(str_contents)
                    contents = []
                # log.set_log(f'{r.strip()}')
            if subprocess.Popen.poll(result) != None and not r:
                str_contents = '\n'.join(contents) if contents else ''
                log.set_log(str_contents)
                log.end_log()
                return
    except Exception as e:
        pass

#记录audio.py 调用的cmd，记录cmd的运行日志
def audio_cmd_write_log(log_file,format='%(message)s',result=None):
    '''
    功能： subprocess 开启一个终端执行程序，需要将终端的输出和报错都写到日志中
    log_fle : camaro.log
    format: '%(message)s'
    '''
    from util.log_ import BaseLog
    log = BaseLog(log_file,format)
    log.start_log()
    try:
        while True:
            r = result.stdout.readline().decode('GBK')
            if r.strip() :
                t =r.strip()
                #将cmd的输出打印到控制上
                print(t)
                log.set_log(t)
            if subprocess.Popen.poll(result) != None and not r:
                log.set_log(r.strip())
                log.end_log()
                return
    except Exception as e:
        pass

#普通进行直接打日志到文件中
def public_write_log(log_file,content,format = '%(asctime)s: %(message)s'):
    from util.log_ import BaseLog
    log = BaseLog(log_file,format=format)
    log.start_log()
    log.set_log(content)
    log.end_log()

def show_usb_index():
    '''
    查看usb摄像头对应的索引值，在使用时，索引值不能有问题。
    '''
    import cv2
    # 尝试打开不同索引的摄像头并显示图像
    for i in range(10):  # 假设最多支持 10 个摄像头
        cap = cv2.VideoCapture(i)
        if not cap.isOpened():
            break

        # 读取并显示图像
        ret, frame = cap.read() #读取一帧
        cv2.imshow(f"Camera {i}", frame)  #在窗口展示出来
        cv2.waitKey(5000)  # 展示图像 5 秒后关闭窗口
        cap.release() #释放
        cv2.destroyAllWindows() #销毁所有的窗口

if __name__ == '__main__':
    show_usb_index()