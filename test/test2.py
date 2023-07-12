from util.need import BASE_DIR
from util.need import AUDIO_PID_PATH
from util.need import encode_token
import subprocess
import time
from util.log_ import BaseLog
token = encode_token('car-0001')
print(token)
import serial


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
import base64


def get_ser_port_name():
    import serial.tools.list_ports
    # 获取可用串口列表
    ports = serial.tools.list_ports.comports()
    # 遍历并打印可用串口信息
    for port in ports:
        try:
            ser = serial.Serial(port.device)
            ser.close()
            is_connected = True
        except serial.SerialException:
            is_connected = False

        desc = port.description
        name = port.name
        if ('USB-SERIAL CH340' in desc) and is_connected and name!='COM1':
            # print(name)
            return name
        # print(f"串口名称: {port.name}")
        # print(f"描述: {port.description}")
        # print(f"设备: {port.device}")
        # print(f"厂商: {port.manufacturer}")
        # print(f"产品: {port.product}")
        # print(f"序列号: {port.serial_number}")
        # print(f"是否已连接: {is_connected}")
        # print("--------------------------")
    else:
        #代表搜索不到了
        return None


def check_gps_ser():
    port_name = get_ser_port_name()
    # port_name = None
    co = 2
    while True:
        try:
            if port_name:
                ser = serial.Serial(port_name, 115200)
                if ser.isOpen():
                    # print('gps可用', port_name)
                    return ser
            else:
                ser = serial.Serial(f'COM{co}', 115200)
                if ser.isOpen():
                    port_name = f'COM{co}'
                    # print('gps可用', port_name)
                    return ser
                else:
                    co+=1
        except Exception as e:
            co+=1
        print('卡在这里了吗')
        time.sleep(1)
        # print('等待2秒')

import serial.tools.list_ports
class GpsSerial:
    @classmethod
    def __get_port_name(cls):
        '''
        获取gps插入的串口的名字：
        1、当前使用的gps的芯片是CH340，在port描述中是USB-SERIAL CH340，【注意如果gps型号修改了，就需要重新查询更换的gps的芯片型号】
        2、name就是串口的名字，通过名字去连接串口
        '''
        ports = serial.tools.list_ports.comports()
        # 遍历并打印可用串口信息
        for port in ports:
            try:
                ser = serial.Serial(port.device)
                ser.close()
                is_connected = True
            except serial.SerialException:
                is_connected = False

            desc = port.description
            name = port.name
            if ('USB-SERIAL CH340' in desc) and is_connected and name != 'COM1':
                print('串口名：',name,'  串口描述信息：',desc)
                return name
            # print(f"串口名称: {port.name}")
            # print(f"描述: {port.description}")
            # print(f"设备: {port.device}")
            # print(f"厂商: {port.manufacturer}")
            # print(f"产品: {port.product}")
            # print(f"序列号: {port.serial_number}")
            # print(f"是否已连接: {is_connected}")
            # print("--------------------------")
        else:
            return None
    @classmethod
    def get_serial(cls):
        '''
        1、通过串口名字去连接gps插入的串口
        2、返回生成的ser
        '''
        port_name = cls.__get_port_name()
        co = 2
        while True:
            try:
                if port_name:
                    ser = serial.Serial(port_name, 115200)
                    if ser.isOpen():
                        print('gps可用', port_name)
                        return ser
                else:
                    ser = serial.Serial(f'COM{co}', 115200)
                    if ser.isOpen():
                        port_name = f'COM{co}'
                        print('gps可用', port_name)
                        return ser
                    else:
                        co += 1
            except Exception as e:
                co += 1
            print('ssssss')
            # if co > 20:
            #     raise Exception('请确定gps型号是否发生了变化，当前串口')


if __name__ == '__main__':
    # while True:
        # port_name = get_ser_port_name()
        # ser = serial.Serial(port_name, 115200)
        # print(ser)
        # if ser.inWaiting() > 0:
        #     print('okokokok')
        # ser.close()
    while True:
        ser = check_gps_ser()
        print(ser)
        ser.close()
        time.sleep(1)