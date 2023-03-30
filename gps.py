#!/usr/bin/env python
# -*- coding:utf-8 -*-

import math
import serial.tools.list_ports
import json
import multiprocessing
import serial
import time
import threading
import os
import requests
import base64
import hmac
import queue

#急救车编号：必须与数据库中急救车编号一致

all_comports = serial.tools.list_ports.comports()

for comport in all_comports:
    print(comport.device, comport.name, comport.description, comport.interface)
'''4、换GPS时，设置换报文的开头 '''
GPS_textname = ['GNGGA','GNGLL','GNGSA','GPGSV','BDGGA','BDGLL','BDGSA','BDGSV','GNRMC','GNZDA']
#生成验证信息
from util.need import public_write_log
import sys
from util.need import TIME_FORMAT

#发送gps数据信息给web端
def send(data):
    '''
    data: 要传递给web的定位数据
    '''
    #拿到的队列
    global has_task_queue #只要该队列中有数据，就要将电脑重启
    from util.need import CAR_NUMBER
    global FIRST_TASK_NUMBER #首次请求成功后，拿到的急救车的急救任务编号，与gps请求响应会的数据中，
    from util.need import encode_token
    global URL
    url = URL #web后端接收http请求的地址
    car_number = CAR_NUMBER#当前急救车的编号
    token = encode_token(key=car_number)#生成token
    headers = {
        'content-type': 'application/json',
        'token': token,
        'User-Agent':"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:105.0) Gecko/20100101 Firefox/105.0"
    }
    # 注意这里必须以json字符串构造数据
    if type(data)!=str:
        #把结构数据转成字符串
        data = json.dumps(data)
    try:
        r = requests.post(url, data=data, headers=headers)
    except Exception as e:
        public_write_log(f'gps/{TIME_FORMAT}.log',f'发送gps数据给后端失败，{e}\nfilename={__file__}\nfunction={sys._getframe().f_code.co_name}')
        print(str(e),'网络中断')
        return
    # print(r.content)
    if r.status_code == 200:
        print('请求成功',URL,time.strftime('%Y-%m-%d %H:%M:%S'))
        '''2023-02-10: 当正在运行'''
        data = r.json()
        task_number = data.get('task_number')
        if FIRST_TASK_NUMBER != task_number:
            #第一次拿到的急救车任务编号，与gps请求响应会回来的gps数据不一样时，说明急救车任务已经变化了，需要重新启动
            if not has_task_queue.full():
                # 队列不满才能存入数据，在判断重启电脑时，只要该队列有数据，就执行重启电脑的脚本
                has_task_queue.put(1)
    elif r.status_code == 404:
        #当前急救车的任务已经结束了，应该准备重启电脑，为下一次急救任务准备
        if not has_task_queue.full():
            #队列不满才能存入数据，在判断重启电脑时，只要该队列有数据，就执行重启电脑的脚本
            has_task_queue.put(1)
        print('当前急救车没有急救任务')
    elif r.status_code == 403:
        print('携带的token有问题')


#经纬度的转换。获得WGS84坐标系.从GPS获取的数据需要经过转换
def GpsChangeWgs84(longitude,latitude,gnvtg):
    '''
    longitude : 经度数据
    latitude： 维度数据
    gnvtg：速度和角度数据
    '''
    global loaction_filename
    #默认，正数为东经，北纬。（符合中国使用）
    # wGS84经纬度十进制         latitude- 纬度（-90-90）    longitude-经度（-180-180）
    #gps的数据中，形式：,2310.11802,N,11326.09065,E。纬度：ddmm.mmmm（度分）格式，经度：dddmm.mmmm（度分）格式
    #经纬度查询网址：https://www.earthol.com/
    # 数据为字符串
    try:
        Wgs84_lon = float('%.18f' % (int(longitude[0:3]) + float(float(longitude[3:]) / 60)))
        #print(longitude[0:3],float(longitude[3:]))
        Wgs84_lat = float('%.18f' % (int(latitude[0:2]) + float(float(latitude[2:]) / 60)))
        #print(latitude[0:2],float(latitude[2:]))
        # print('WGS84坐标：',Wgs84_lon,',',Wgs84_lat)
        # wgsmodi_lon,wgsmodi_lat = wgs84modfi(Wgs84_lon, Wgs84_lat)
        # print('WGS84坐标modi(CJ02-1)：', wgsmodi_lon, ',', wgsmodi_lat)
        cj02_lon, cj02_lat = getGCJ02(Wgs84_lon, Wgs84_lat)
        # print('CJ02-2坐标：', cj02_lon, ',', cj02_lat)
        WGS84 = {'longitude': Wgs84_lon, 'dimension': Wgs84_lat}
        GCJ02 = {'longitude': cj02_lon, 'dimension': cj02_lat}
        Location_string = 'WGS84坐标：' + str(Wgs84_lon) + ',' + str(Wgs84_lat) + '\n' + 'CJ02-2坐标：' + str(
            cj02_lon) + ',' + str(cj02_lat) + '\n'

        '''
               1、这里写一个请求，把数据传递给后端
               2、后端的处理
                   拿到gps数据后的处理
                   将数据存到文本文件中，时间戳:gps位置，文件名是急救任务的名字，位置存到视频的位置下
                   还要将gps数据保存redis数据库中，这个要好好想想怎么座
        '''
        #要发送给web后端的定位数据
        global CAR_ID
        global CAR_ID
        dic = {
            'longitude':cj02_lon,
            'dimension':cj02_lat,
            'speed':gnvtg.get('speed',''), #速度
            'read_north_angle':gnvtg.get('read_north_angle',''), #以真北为参照的航向
            'magnetic_north_angle':gnvtg.get('magnetic_north_angle',''), #以磁北为参照的航向
            'time':time.time(),#时间戳
            'str_time':time.strftime('%Y-%m-%d %H:%M:%S'),#字符串时间
            'car_number':CAR_NUMBER ,#急救车编号
            'car_id':CAR_ID #急救车的id
        }
        #45行拿到导航的数据，把这个数据传递给web后端，，后端存起来，前端再从web后端拿
        # print(dic,'要发送给后端的数据')
        print('发送给后端的数据')
        print(dic)
        #开启线程去，将数据请求给web端
        p = threading.Thread(target=send,args=(dic,))
        p.start()
        time.sleep(0.2)
        #将数据传递给web端
        # send(dic)
        # #将经纬度写到文件中
        # loaction_thread = WriteText('GetLocation', Location_string, loaction_filename)
        # loaction_thread.start()
    except ValueError:
        public_write_log(f'gps/{TIME_FORMAT}.log','valueError,无效值')
        print('valueError,无效值')


'''
WGS84：为一种大地坐标系，也是目前广泛使用的GPS全球卫星定位系统使用的坐标系。
GCJ02：又称火星坐标系，是由中国国家测绘局制定的地理坐标系统，是由WGS84加密后得到的坐标系。
BD09：为百度坐标系，在GCJ02坐标系基础上再次加密。其中bd09ll表示百度经纬度坐标，bd09mc表示百度墨卡托米制坐标

WGS84坐标系	113.43439010626824,23.168768226353254
GCJ02坐标系	113.43987815980573,23.166257044966
BD09坐标系	113.44641879537117,23.172089394184233

定位器得到：113.434886333333 , 23.168589333333，是WGS84坐标系的。
仅适用于https://www.earthol.com/

都是WGS84转CJ02
'''
def transformlat(x,y):
    ret = float('%.18f' % (-100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1*x*y+0.2*math.sqrt(abs(x))))
    ret += float('%.18f' % ((20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0))
    ret += float('%.18f' % ((20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0))
    ret += float('%.18f' % ((160.0 * math.sin(y / 12.0 * math.pi) + 320 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0))
    return ret
def transformlon(x,y):
    ret = float('%.18f' % (300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))))
    ret += float('%.18f' % ((20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0))
    ret += float('%.18f' % ((20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0))
    ret += float('%.18f' % ((150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0))
    return ret

def wgs84modfi(longitude,latitude):
    longitude = float(longitude)
    latitude = float(latitude)

    a = 6378245.0
    ee = 0.00669342162296594323
    dLat = transformlat(longitude - 105.0, latitude - 35.0)
    dLon = transformlon(longitude - 105.0, latitude - 35.0)
    radLat = float('%.18f' % (latitude / 180.0 * math.pi))
    magic = float('%.18f' % (math.sin(radLat)))
    magic = float('%.18f' % (1 - ee * magic * magic))
    sqrtMagic = float('%.18f' % (math.sqrt(magic)))
    dLat = float('%.18f' % ((dLat * 180.0) / ((a * (1 - ee)) / (magic * sqrtMagic) * math.pi)))
    dLon = float('%.18f' % ((dLon * 180.0) / (a / sqrtMagic * math.cos(radLat) * math.pi)))
    modi_lat = latitude + dLat
    modi_lon = longitude + dLon

    #得到为谷歌的信号

    return modi_lon,modi_lat

class LngLatTransfer():

    def __init__(self):
        self.x_pi = 3.14159265358979324 * 3000.0 / 180.0
        self.pi = math.pi  # π
        self.a = 6378245.0  # 长半轴
        self.es = 0.00669342162296594323  # 偏心率平方
        pass

    def GCJ02_to_BD09(self, gcj_lng, gcj_lat):
        """
        实现GCJ02向BD09坐标系的转换
        :param lng: GCJ02坐标系下的经度
        :param lat: GCJ02坐标系下的纬度
        :return: 转换后的BD09下经纬度
        """
        z = math.sqrt(gcj_lng * gcj_lng + gcj_lat * gcj_lat) + 0.00002 * math.sin(gcj_lat * self.x_pi)
        theta = math.atan2(gcj_lat, gcj_lng) + 0.000003 * math.cos(gcj_lng * self.x_pi)
        bd_lng = z * math.cos(theta) + 0.0065
        bd_lat = z * math.sin(theta) + 0.006
        return bd_lng, bd_lat


    def BD09_to_GCJ02(self, bd_lng, bd_lat):
        '''
        实现BD09坐标系向GCJ02坐标系的转换
        :param bd_lng: BD09坐标系下的经度
        :param bd_lat: BD09坐标系下的纬度
        :return: 转换后的GCJ02下经纬度
        '''
        x = bd_lng - 0.0065
        y = bd_lat - 0.006
        z = math.sqrt(x * x + y * y) - 0.00002 * math.sin(y * self.x_pi)
        theta = math.atan2(y, x) - 0.000003 * math.cos(x * self.x_pi)
        gcj_lng = z * math.cos(theta)
        gcj_lat = z * math.sin(theta)
        return gcj_lng, gcj_lat


    def WGS84_to_GCJ02(self, lng, lat):
        '''
        实现WGS84坐标系向GCJ02坐标系的转换
        :param lng: WGS84坐标系下的经度
        :param lat: WGS84坐标系下的纬度
        :return: 转换后的GCJ02下经纬度
        '''
        dlat = self._transformlat(lng - 105.0, lat - 35.0)
        dlng = self._transformlng(lng - 105.0, lat - 35.0)
        radlat = lat / 180.0 * self.pi
        magic = math.sin(radlat)
        magic = 1 - self.es * magic * magic
        sqrtmagic = math.sqrt(magic)
        dlat = (dlat * 180.0) / ((self.a * (1 - self.es)) / (magic * sqrtmagic) * self.pi)
        dlng = (dlng * 180.0) / (self.a / sqrtmagic * math.cos(radlat) * self.pi)
        gcj_lng = lat + dlat
        gcj_lat = lng + dlng
        return gcj_lng, gcj_lat


    def GCJ02_to_WGS84(self, gcj_lng, gcj_lat):
        '''
        实现GCJ02坐标系向WGS84坐标系的转换
        :param gcj_lng: GCJ02坐标系下的经度
        :param gcj_lat: GCJ02坐标系下的纬度
        :return: 转换后的WGS84下经纬度
        '''
        dlat = self._transformlat(gcj_lng - 105.0, gcj_lat - 35.0)
        dlng = self._transformlng(gcj_lng - 105.0, gcj_lat - 35.0)
        radlat = gcj_lat / 180.0 * self.pi
        magic = math.sin(radlat)
        magic = 1 - self.es * magic * magic
        sqrtmagic = math.sqrt(magic)
        dlat = (dlat * 180.0) / ((self.a * (1 - self.es)) / (magic * sqrtmagic) * self.pi)
        dlng = (dlng * 180.0) / (self.a / sqrtmagic * math.cos(radlat) * self.pi)
        mglat = gcj_lat + dlat
        mglng = gcj_lng + dlng
        lng = gcj_lng * 2 - mglng
        lat = gcj_lat * 2 - mglat
        return lng, lat


    def BD09_to_WGS84(self, bd_lng, bd_lat):
        '''
        实现BD09坐标系向WGS84坐标系的转换
        :param bd_lng: BD09坐标系下的经度
        :param bd_lat: BD09坐标系下的纬度
        :return: 转换后的WGS84下经纬度
        '''
        lng, lat = self.BD09_to_GCJ02(bd_lng, bd_lat)
        return self.GCJ02_to_WGS84(lng, lat)


    def WGS84_to_BD09(self, lng, lat):
        '''
        实现WGS84坐标系向BD09坐标系的转换
        :param lng: WGS84坐标系下的经度
        :param lat: WGS84坐标系下的纬度
        :return: 转换后的BD09下经纬度
        '''
        lng, lat = self.WGS84_to_GCJ02(lng, lat)
        return self.GCJ02_to_BD09(lng, lat)


    def _transformlat(self, lng, lat):
        ret = -100.0 + 2.0 * lng + 3.0 * lat + 0.2 * lat * lat + \
              0.1 * lng * lat + 0.2 * math.sqrt(math.fabs(lng))
        ret += (20.0 * math.sin(6.0 * lng * self.pi) + 20.0 *
                math.sin(2.0 * lng * self.pi)) * 2.0 / 3.0
        ret += (20.0 * math.sin(lat * self.pi) + 40.0 *
                math.sin(lat / 3.0 * self.pi)) * 2.0 / 3.0
        ret += (160.0 * math.sin(lat / 12.0 * self.pi) + 320 *
                math.sin(lat * self.pi / 30.0)) * 2.0 / 3.0
        return ret


    def _transformlng(self, lng, lat):
        ret = 300.0 + lng + 2.0 * lat + 0.1 * lng * lng + \
              0.1 * lng * lat + 0.1 * math.sqrt(math.fabs(lng))
        ret += (20.0 * math.sin(6.0 * lng * self.pi) + 20.0 *
                math.sin(2.0 * lng * self.pi)) * 2.0 / 3.0
        ret += (20.0 * math.sin(lng * self.pi) + 40.0 *
                math.sin(lng / 3.0 * self.pi)) * 2.0 / 3.0
        ret += (150.0 * math.sin(lng / 12.0 * self.pi) + 300.0 *
                math.sin(lng / 30.0 * self.pi)) * 2.0 / 3.0
        return ret

    def WGS84_to_WebMercator(self, lng, lat):
        '''
        实现WGS84向web墨卡托的转换
        :param lng: WGS84经度
        :param lat: WGS84纬度
        :return: 转换后的web墨卡托坐标
        '''
        x = lng * 20037508.342789 / 180
        y = math.log(math.tan((90 + lat) * self.pi / 360)) / (self.pi / 180)
        y = y * 20037508.34789 / 180
        return x, y

    def WebMercator_to_WGS84(self, x, y):
        '''
        实现web墨卡托向WGS84的转换
        :param x: web墨卡托x坐标
        :param y: web墨卡托y坐标
        :return: 转换后的WGS84经纬度
        '''
        lng = x / 20037508.34 * 180
        lat = y / 20037508.34 * 180
        lat = 180 / self.pi * (2 * math.atan(math.exp(lat * self.pi / 180)) - self.pi / 2)
        return lng, lat
def getBD0009(lng,lat):
    lng = float(lng)
    lat = float(lat)
    Instance = LngLatTransfer()  # python 中先对类方法进行实例，再使用类方法
    result = Instance.WGS84_to_BD09(lng,lat)
    return result[1],result[0]

def getGCJ02(lng,lat):
    lng = float(lng)
    lat = float(lat)
    Instance = LngLatTransfer()  # python 中先对类方法进行实例，再使用类方法
    result = Instance.WGS84_to_GCJ02(lng,lat)
    return result[1],result[0]

def to_ascii(text):
    ascii_values = [ord(character) for character in text]
    return ascii_values

#写入txt文件
class WriteText(threading.Thread):
    def __init__(self,name,textstring,filename):
        super().__init__()
        self.name = name
        self.textstring = textstring
        self.filename = filename

    def run(self):
        file_lock = threading.RLock()
        if self.name == 'comGetText':
            strlist= str.split(self.textstring, "\r")
            x = ''
            for i in strlist:
                x = x + i
            self.textstring = x

        file_lock.acquire()
        catchfile = open(self.filename,'a')
        catchfile.write(self.textstring)
        catchfile.close()
        file_lock.release()


#（线程）校验码验证，及分开输出和处理......涉及计算
class CheckAndDealThread(threading.Thread):
    def __init__(self,textstring):
        super().__init__()
        self.text = textstring
        self.GPdict = {}
        self.GPdict = self.GPdict.fromkeys(GPS_textname)

    #将文本转换为单独的列表
    def splittext(self):
        t_list = str.split(self.text,"\r\n")
        for list_line in t_list:
            #除末尾空字符串
            if list_line == '':
                continue
            for textname in GPS_textname:
                if textname in list_line:
                    #分别为：空值判断，有多个值，转列表
                    if self.GPdict.get(textname) is  None:
                        self.GPdict[textname] = list_line

                    else:
                        if type(self.GPdict[textname]) is list:
                            self.GPdict[textname].append(list_line)

                        else:
                            self.GPdict[textname] = [self.GPdict[textname]]   #int 向 list转换，并不丢失值
    def get_type_data(self,key:str):
        '''
        key是一行报文的 开头字段如：$GNVTG
        通过这个，获取整段报文中，该字段开头的数据，返回值是一个列表[[],]
        '''
        all_list = self.text.split('\r\n')[:-1]
        ret_list = []
        #self.text 接收了整个报文数据
        for line in all_list:
            # print(line)
            if key in line:
                gnvtg_list = line.split(',')
                ret_list.append(gnvtg_list)
        return ret_list


    #校验码验证,接收string完整的信息，并自动验证*后的内容
    def JIAOYANHE(self,textline):
        split_line = (textline.split('$')[1]).split('*')
        check_num = split_line[1]

        ascii_num = to_ascii(split_line[0])
        ascii_sum = ascii_num[0]
        for i in ascii_num[1:]:
            ascii_sum = ascii_sum ^ i

        Bcount_num = hex(ascii_sum).split('x')[-1].upper()
        Bcount_num = Bcount_num.zfill(2)
        #print('十六进制:', hex(ascii_sum).split('x')[-1])
        if Bcount_num != check_num:
            print('校验字符：', textline)
            print('校验结果：',Bcount_num == check_num,Bcount_num,check_num)
        return Bcount_num == check_num
    #全球导航卫星系统（GNSS-global navigation satellite system）
    def getGN(self):
        #先从简单的获取，若校验错误，则获取其他的。直到全部出错为止
        #相关的值有：GNGGA\GNGLL\GNGSA\GNRMC\GNZDA
        #日期值：GNZDA
        #优先级：GNRMC>GNGGA>GNGSA

        if self.JIAOYANHE(self.GPdict['GNRMC']):
            GN_split = self.GPdict['GNRMC'].split(',')
            GN_lati = GN_split[3]  #纬度
            GN_NorS = GN_split[4]
            GN_longi = GN_split[5]   #经度
            GN_EorW = GN_split[6]

        elif self.JIAOYANHE(self.GPdict['GNGGA']):
            GN_split = self.GPdict['GNGGA'].split(',')
            GN_lati = GN_split[2]
            GN_NorS = GN_split[3]
            GN_longi = GN_split[4]
            GN_EorW = GN_split[5]

        # elif self.JIAOYANHE(self.GPdict['GNGLL']):
        #     GN_split = self.GPdict['GNGLL'].split(',')
        #     GN_lati = GN_split[3]
        #     GN_NorS = GN_split[4]
        #     GN_longi = GN_split[5]
        #     GN_EorW = GN_split[6]
        #暂不进行计算GSA
        #elif self.JIAOYANHE(self.GPdict['GNGSA']):
        else:
            GN_longi = None
            GN_NorS = None
            GN_lati = None
            GN_EorW = None

        GN_dict = {'GN_longi':GN_longi,'GN_EorW':GN_EorW,'GN_lati':GN_lati,'GN_NorS':GN_NorS}
        # print(GN_dict)

        '''2022、12、21：新增获取速度和角度'''
        gnvtg_list = self.get_type_data('$GNVTG')[0]
        gnvtg_dic =dict()
        if gnvtg_list:
            gnvtg_dic['speed'] = gnvtg_list[-3]  # 地面速度，0000.0~1851.8 公里/小时
            gnvtg_dic['read_north_angle'] = gnvtg_list[1]  # 以真北为参考基准的地面航向（000~359 度
            gnvtg_dic['magnetic_north_angle'] = gnvtg_list[3]  # 以磁北为参考基准的地面航向（000~359 度

        GpsChangeWgs84(GN_longi,GN_lati,gnvtg_dic) # GPS数据进行转换操作，再把数据传递医院的web端


        return GN_dict

    #GP 全球定位系统（GPS-global positioning system）
    # def getGP(self):

    # BD 北斗二代卫星系统
    def getBD(self):
        #先从简单的获取，若校验错误，则获取其他的。直到全部出错为止
        #相关的值有：BDGGA\BDGLL\BDGSA\BDRMC\BDZDA
        #日期值：BDZDA
        #优先级：BDGLL>BDGGA>BDRMC>BDGSA

        if self.JIAOYANHE(self.GPdict['BDGLL']):
            BD_split = self.GPdict['BDGLL'].split(',')
            BD_lati = BD_split[1]  #纬度
            BD_NorS = BD_split[2]
            BD_longi = BD_split[3]   #经度
            BD_EorW = BD_split[4]

        elif self.JIAOYANHE(self.GPdict['BDGGA']):
            BD_split = self.GPdict['BDGGA'].split(',')
            BD_lati = BD_split[2]
            BD_NorS = BD_split[3]
            BD_longi = BD_split[4]
            BD_EorW = BD_split[5]

        elif self.JIAOYANHE(self.GPdict['BDRMC']):
            BD_split = self.GPdict['BDRMC'].split(',')
            BD_lati = BD_split[3]
            BD_NorS = BD_split[4]
            BD_longi = BD_split[5]
            BD_EorW = BD_split[6]
        #暂不进行计算GSA
        #elif self.JIAOYANHE(self.GPdict['BDGSA']):
        else:
            BD_longi = None
            BD_NorS = None
            BD_lati = None
            BD_EorW = None

        BD_dict = {'BD_longi':BD_longi,'BD_EorW':BD_EorW,'BD_lati':BD_lati,'BD_NorS':BD_NorS}
        # print(BD_dict)

        #2022、12、21新增：速度和航向
        gnvtg_list = self.get_type_data('$GNVTG')[0]
        gnvtg_dic = dict()
        if gnvtg_list:
            gnvtg_dic['speed'] = gnvtg_list[-3]  # 地面速度，0000.0~1851.8 公里/小时
            gnvtg_dic['read_north_angle'] = gnvtg_list[1]  # 以真北为参考基准的地面航向（000~359 度
            gnvtg_dic['magnetic_north_angle'] = gnvtg_list[3]  # 以磁北为参考基准的地面航向（000~359 度


        GpsChangeWgs84(BD_longi,BD_lati,gnvtg_dic)
        return BD_dict

    def run(self):

        #split
        self.splittext()
        #print(self.GPdict)

        #单独每一项进行处理
        #GN
        self.GN_dict = self.getGN()
        #GP
        #BD
        # print('可观测的时间:',time.localtime())
        #self.BD_dict = self.getBD()
        #分别验证信息的完整性
        '''
        #######################################
        未完待续
        #######################################
        '''

#校验码验证，及分开输出和处理......涉及计算，采用并行处理，CPU密集型任务
class CheckAndDealProcess(multiprocessing.Process):
    def __init__(self,textstring):
        super().__init__()
        self.text = textstring
        self.GPdict = {}
        self.GPdict = self.GPdict.fromkeys(GPS_textname)

    #将文本转换为单独的列表
    def splittext(self):
        t_list = str.split(self.text,"\r\n")
        for list_line in t_list:
            #除末尾空字符串
            if list_line == '':
                continue
            for textname in GPS_textname:
                if textname in list_line:
                    #分别为：空值判断，有多个值，转列表
                    if self.GPdict.get(textname) is  None:
                        self.GPdict[textname] = list_line

                    else:
                        if type(self.GPdict[textname]) is list:
                            self.GPdict[textname].append(list_line)

                        else:
                            self.GPdict[textname] = [self.GPdict[textname]]   #int 向 list转换，并不丢失值


    #校验码验证,接收string完整的信息，并自动验证*后的内容
    def JIAOYANHE(self,textline):
        split_line = (textline.split('$')[1]).split('*')
        check_num = split_line[1]

        ascii_num = to_ascii(split_line[0])
        ascii_sum = ascii_num[0]
        for i in ascii_num[1:]:
            ascii_sum = ascii_sum ^ i

        Bcount_num = hex(ascii_sum).split('x')[-1].upper()
        Bcount_num = Bcount_num.zfill(2)
        #print('十六进制:', hex(ascii_sum).split('x')[-1])
        if Bcount_num != check_num:
            print('校验字符：', textline)
            print('校验结果：',Bcount_num == check_num,Bcount_num,check_num)
        return Bcount_num == check_num
    #全球导航卫星系统（GNSS-global navigation satellite system）
    def getGN(self):
        '''3、换GPS时，拿BD数据时，按照优先级拿，什么好拿就拿什么'''
        #先从简单的获取，若校验错误，则获取其他的。直到全部出错为止
        #相关的值有：GNGGA\GNRMC
        #日期值：GNZDA
        #优先级：GNRMC>GNGGA>GNGSA

        if self.JIAOYANHE(self.GPdict['GNRMC']):
            GN_split = self.GPdict['GNRMC'].split(',')
            GN_lati = GN_split[3]  #纬度
            GN_NorS = GN_split[4]
            GN_longi = GN_split[5]   #经度
            GN_EorW = GN_split[6]

        elif self.JIAOYANHE(self.GPdict['GNGGA']):
            GN_split = self.GPdict['GNGGA'].split(',')
            GN_lati = GN_split[2]
            GN_NorS = GN_split[3]
            GN_longi = GN_split[4]
            GN_EorW = GN_split[5]

        # elif self.JIAOYANHE(self.GPdict['GNGLL']):
        #     GN_split = self.GPdict['GNGLL'].split(',')
        #     GN_lati = GN_split[1]
        #     GN_NorS = GN_split[2]
        #     GN_longi = GN_split[3]
        #     GN_EorW = GN_split[4]
        #暂不进行计算GSA
        #elif self.JIAOYANHE(self.GPdict['GNGSA']):
        else:
            GN_longi = None
            GN_NorS = None
            GN_lati = None
            GN_EorW = None

        GN_dict = {'GN_longi':GN_longi,'GN_EorW':GN_EorW,'GN_lati':GN_lati,'GN_NorS':GN_NorS}
        print(GN_dict)

        '''2022、12、21：新增获取速度和角度'''
        gnvtg_list = self.get_type_data('$GNVTG')[0]
        gnvtg_dic = dict()
        if gnvtg_list:
            gnvtg_dic['speed'] = gnvtg_list[-3]  # 地面速度，0000.0~1851.8 公里/小时
            gnvtg_dic['read_north_angle'] = gnvtg_list[1]  # 以真北为参考基准的地面航向（000~359 度
            gnvtg_dic['magnetic_north_angle'] = gnvtg_list[3]  # 以磁北为参考基准的地面航向（000~359 度

        GpsChangeWgs84(GN_longi,GN_lati,gnvtg_dic)
        return GN_dict

    #GP 全球定位系统（GPS-global positioning system）
    # def getGP(self):

    # BD 北斗二代卫星系统
    def getBD(self):
        #先从简单的获取，若校验错误，则获取其他的。直到全部出错为止
        #相关的值有：BDGGA\BDGLL\BDGSA\BDRMC\BDZDA
        #日期值：BDZDA
        #优先级：BDGLL>BDGGA>BDRMC>BDGSA
        '''3、换GPS时，拿BD数据时，按照优先级拿，什么好拿就拿什么'''
        if self.JIAOYANHE(self.GPdict['BDGLL']):
            BD_split = self.GPdict['BDGLL'].split(',')
            BD_lati = BD_split[1]  #纬度
            BD_NorS = BD_split[2]
            BD_longi = BD_split[3]   #经度
            BD_EorW = BD_split[4]

        elif self.JIAOYANHE(self.GPdict['BDGGA']):
            BD_split = self.GPdict['BDGGA'].split(',')
            BD_lati = BD_split[2]
            BD_NorS = BD_split[3]
            BD_longi = BD_split[4]
            BD_EorW = BD_split[5]

        elif self.JIAOYANHE(self.GPdict['BDRMC']):
            BD_split = self.GPdict['BDRMC'].split(',')
            BD_lati = BD_split[3]
            BD_NorS = BD_split[4]
            BD_longi = BD_split[5]
            BD_EorW = BD_split[6]
        #暂不进行计算GSA
        #elif self.JIAOYANHE(self.GPdict['BDGSA']):
        else:
            BD_longi = None
            BD_NorS = None
            BD_lati = None
            BD_EorW = None

        BD_dict = {'BD_longi':BD_longi,'BD_EorW':BD_EorW,'BD_lati':BD_lati,'BD_NorS':BD_NorS}
        print(BD_dict)
        '''2022、12、21：新增获取速度和角度'''
        gnvtg_list = self.get_type_data('$GNVTG')[0]
        gnvtg_dic = dict()
        if gnvtg_list:
            gnvtg_dic['speed'] = gnvtg_list[-3]  # 地面速度，0000.0~1851.8 公里/小时
            gnvtg_dic['read_north_angle'] = gnvtg_list[1]  # 以真北为参考基准的地面航向（000~359 度
            gnvtg_dic['magnetic_north_angle'] = gnvtg_list[3]  # 以磁北为参考基准的地面航向（000~359 度

        GpsChangeWgs84(BD_longi,BD_lati,gnvtg_dic)
        return BD_dict

    def get_type_data(self,key:str):
        '''
        key是一行报文的 开头字段如：$GNVTG
        通过这个，获取整段报文中，该字段开头的数据，返回值是一个列表[[],]
        '''
        all_list = self.text.split('\r\n')[:-1]
        ret_list = []
        #self.text 接收了整个报文数据
        for line in all_list:
            # print(line)
            if key in line:
                gnvtg_list = line.split(',')
                ret_list.append(gnvtg_list)
        return ret_list

    def run(self):

        #split
        self.splittext()
        #print(self.GPdict)

        #单独每一项进行处理
        #GN
        '2、换GPS时，指定拿什么数据，北斗或GN或其他'
        self.GN_dict = self.getGN()
        #GP
        #BD
        #self.BD_dict = self.getBD()
        #分别验证信息的完整性
        '''
        #######################################
        未完待续
        #######################################
        '''



'''
解析RAC-C1的数据内容
$GNRMC,014704.70,A,2310.119832,N,11326.063720,E,0.004,,171122,,,D,V,*39
$GNVTG,,T,,M,0.004,N,0.007,K,A*3E
$GNGGA,014704.70,2310.119832,N,11326.063720,E,2,12,0.89,61.83,M,-5.10,M,,0000*60
$GNGSA,M,3,24,02,23,05,29,15,,,,,,,1.60,0.86,1.35,1*0C
$GNGSA,M,3,16,08,27,23,30,28,25,,,,,,1.60,0.86,1.35,4*03
$GPGSV,3,1,12,02,63,181,18,05,28,090,24,15,42,029,39,18,67,300,25*71
$GPGSV,3,2,12,20,01,113,38,23,34,326,25,24,71,131,39,25,00,182,*73
$GPGSV,3,3,12,29,18,208,,40,21,256,28,41,46,236,45,50,59,149,*7A
$GBGSV,4,1,16,01,46,122,,04,32,111,,05,25,256,,06,69,229,21*6F
$GBGSV,4,2,16,07,08,187,,08,70,038,32,09,54,221,19,10,07,200,*6B
$GBGSV,4,3,16,13,64,354,21,16,79,240,26,20,00,278,,23,41,139,37*65
$GBGSV,4,4,16,25,34,075,38,27,44,232,45,28,19,179,,30,27,294,27*63
一个$GNRMC 是一段报文的开头，结尾是另一个$GNRMC 前一个

$GNRMC,014704.70,A,2310.119832,N,11326.063720,E,0.004,,171122,,,D,V,*39
...
完整报文：
BD	北斗二代卫星系统
GP	全球定位系统（GPS-global positioning system）
GN	全球导航卫星系统（GNSS-global navigation satellite system）

表示方式：
GGA：时间、位置、定位类型
GLL：经度、纬度、UTC时间
GSA：GPS接收机操作模式，定位使用的卫星，DOP值
GSV：可见GPS卫星信息、仰角、方位角、信噪比（SNR）
RMC：时间、日期、位置、速度
VTG：地面速度信息


'''


'''
方案：
静态：
验证数据完整性————处理有效信息————从多个定位综合得出判断
GN直接提取使用
GP和BD通过卫星数获取定位

动态：
方法一：
两点之间的位置矫正，偏移回正
方法二：
若有点的地标信息（如道路，城市，山脉）等，则可进行纠正
'''


text_filename = os.path.join(os.path.join(os.path.expanduser("~"), 'Desktop'), 'comread.txt')
loaction_filename = os.path.join(os.path.join(os.path.expanduser("~"), 'Desktop'), 'getloaction.txt')

#全局队列，当请求给web后端时，如果当前急救车没有急救任务时，就应该休息1分钟再发


def gps_error(url,status=3):
    '''
    status=3, 说明这个是gps的初错误，在存到缓存中需要用到，在缓存中取出也需要用到
    '''
    from util.need import encode_token
    car_number = CAR_NUMBER  # 当前急救车的编号
    token = encode_token(key=car_number)  # 生成token
    headers = {
        'content-type': 'application/json',
        'token': token,
        'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:105.0) Gecko/20100101 Firefox/105.0",
    }
    message = '急救车的gps获取不到数据，可能是插口松动或被拔掉了'
    r = requests.post(url, data=json.dumps({'car_number': car_number,'status':status,'message':message}), headers=headers)

def restart_windows():
    # 3、立即关机
    print('各单位请注意了，5秒后重启电脑...')
    os.system("shutdown -r -t 5")

if __name__ == '__main__':
    # C:\\Users\\Xinrui\\Desktop
    from util.need import check_ambulance_status #检验急救车是否有急救任务
    from util.need import REMOTE_IP #服务器域名
    from util.need import CAR_NUMBER #急救车编号
    from util.need import public_write_log #普通日志
    import sys

    # CAR_NUMBER = 'car-0001'  # 急救车编号
    URL = f'https://{REMOTE_IP}/api/srs/save-gps'  # 急救车定位数据处理的路由
    #创建锁
    file_lock = threading.RLock()
    #创建队列，急救车没有急救车任务时，在队列中存数据
    has_task_queue = queue.Queue(maxsize=10)
    '''0、等待开机稳定后再启动'''
    print('开机等待5秒...')
    time.sleep(5)
    '''1、检测当前急救车是否有急救事件，没有的话就不会进入到获取gps数据的代码和发送gps数据给web端了
        下面这个函数是个循环，直到请求到该急救车有急救任务，才会跳出，往下走
    '''
    CHECK_URL='https://ambulance.thearay.net/api/srs/ambulance-before-send'
    data = check_ambulance_status(CHECK_URL,CAR_NUMBER)
    CAR_ID = data.get('car_id')  # 拿到急救车的id
    FIRST_TASK_NUMBER = data.get('task') #拿到任务编号
    '''
    判断状态拿到的任务编号，用来判断急救车的任务是否被覆盖且新建了
    1、FIRST_TASK_NUMBER任务编号与gps请求返回的任务编号一致，说明当前任务没有进行过覆盖新建的操作
    2、FIRST_TASK_NUMBER任务编号与gps请求返回的任务编号不一致时，说明当前任务已经变化，（急救车开车在路上，中心系统给该急救车新增一个任务，一开始的任务结束，）
        当是这种情况时，急救车应该立即重启电脑，进入一个新的循环中，（可能旧的事件的视频会被判断属于刚刚新建的事件，最少要保证新建的事件的视频还是属于新的事件）
        【此时要重启电脑】
    '''
    print(data,'请求拿到的数据')


    out = []
    start = time.time()
    x = 0
    strBW = ''
    CanRead = 0
    count = 0
    event = threading.Event()

    co = 1
    while True:
        '''2.扫描端口，获取字段： 先使用串口软件，定位出当前电脑是哪个串口读取gps数据'''
        co =6
        # while True:
        try:
            ser = serial.Serial(f'COM{co}', 115200)
            if ser.isOpen():
                print('gps可用',f' COM{co}')
                # break
            else:
                co+=1
        except Exception as e:
            co+=1
            # print(str(e), '当前电脑读取gps数据的串口有问题！！')
            # time.sleep(3)
            pass

        '''3、获取gps数据，将处理后的gps数据发送给web端'''
        try:
            while ser.inWaiting() > 0:
                '''  
                #读取方法一：读取固定长度的字符串的方式

                start_time = time.time()
                data = ser.read(1750).decode('utf8')    # 是读1000*（1+3/4）个字符
                end_time = time.time()
                print('\n', data)
                print('\n', end_time - start_time)    #约1.8s时间
            '''
                '''  
                #读取方法二：读取缓存的方式

                newS = ser.read(ser.in_waiting).decode('utf8')  #读取所有缓存
                print(newS)
                strBW = strBW + newS
                print('有东西',len(strBW))
                if len(strBW) > 1300 :
                    print(strBW)
                    print('\n',data)
                    x = 10
                    break

            if x == 10 :
                break
            '''
                '''  
                    #读取方法三：触发式读取的方式，读取到重复的，就释放掉，再读
                '''
                newS = ser.readline().decode('utf8')  # 读取长度，以\n作结束
                '3.1、换GPS：找到报文的开头和结束'
                if '$GNRMC' in newS:
                    if CanRead == 1:
                        # 这里拿到完整的一段报文数据
                        # 输出，并置空重写
                        # print('输出全部：\n',strBW)
                        # 启动进程对文本进行处理

                        # 写文本，生成实时，I/O，用线程处理
                        # text_thread = WriteText('comGetText', strBW, text_filename)
                        # text_thread.start()
                        '''对于继承threading.Thread 类型，调用start()方法就会调用run()'''

                        '''3.2.字段处理'''
                        # deal_process = CheckAndDealProcess(strBW)
                        # deal_process.start()
                        # print(strBW,'原始数据,这里拿到的是一整段数据')
                        # 线程
                        deal_thread = CheckAndDealThread(strBW)
                        deal_thread.start()
                        deal_thread.join(1)  # 等待一秒再处理
                        # 置空重写
                        strBW = newS
                        CanRead = 1
                        '4、查看has_task_queue是否有数据，有数据急救说明急救车任务已经结束了，要重启电脑了'
                        #执行重启电脑的脚本, 队列不为空时，说明将gps数据传递过去时，有请求返回的是急救车没有急救任务
                        if not has_task_queue.empty():
                            restart_windows()
                    else:
                        # 首个'$GNRMC' 走这里
                        strBW = newS
                        CanRead = 1
                else:
                    if CanRead == 1:
                        strBW = strBW + newS  # 一个$GNRMG开始后，后面的报文都是走这里，将一个完整报文拼接起来
        except Exception as e:
            '''5、这个是gps接口断开时，会捕获到的错误，将情况反馈给web端'''
            url = f'https://{REMOTE_IP}/api/srs/ambulance-error'
            try:
                gps_error(url) #传递信息给服务器，说明该gps端口断开
            except Exception as ex:
                pass
            public_write_log(f'gps/{TIME_FORMAT}.log',f'gps接口松动：{e}\nfilname={__file__}\nfunction={sys._getframe().f_code.co_name}\n',format='%(message)s')
            print(str(e))
            print('ser报错，端口松动了')
            time.sleep(5)



