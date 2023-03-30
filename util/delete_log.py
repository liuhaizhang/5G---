import requests
import os
from need import REMOTE_IP
from need import BASE_DIR
def delete_log_file():
    '1、获取日志文件保留的天数'
    url = f'https://{REMOTE_IP}/api/srs/ambulance-log-day'
    day = 60 #设置日志保存的天数
    for i in range(3):
        ret = requests.get(url)
        dic = ret.json()
        # print(dic)
        if dic.get('code',-1) == 200:
            day = dic.get('day',day)
            # print(day,type(day))
            break
    log_path = os.path.join(BASE_DIR,'logs')
    if not os.path.exists(log_path):
        #没有日志文件时，就无需去过期的日志文件了
        return False

    '2、过滤出要删除的文件路径'
    log_dirs = os.listdir(log_path) #[audio,camaro,gps,network,screen]
    dir_paths = [os.path.join(log_path,dir) for dir in log_dirs] #拼接成日志文件上级文件夹的路径
    for dir_path in dir_paths:
        file_list = os.listdir(dir_path) #拿到各个日志文件夹中所有的日志文件名，如logs/audio文件夹下的所有文件名
        file_list.sort() #进行升序排序，文件名是是以日期命名的
        # print(file_list)
        delete_len =len(file_list)-day #拿到要删除文件数量
        if delete_len >0:
            delete_file = file_list[:delete_len] #把最前的文件进行删除
            delete_paths = [os.path.join(dir_path,file) for file in delete_file] #拼接上日志文件的路径
            for file_path in delete_paths:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print('删除的文件',file_path)
        else:
            print(f'当前日志文件天数：{day+delete_len}, 保留的天数：{day}')

if __name__ == '__main__':
    delete_log_file()
