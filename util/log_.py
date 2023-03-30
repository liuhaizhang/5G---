import logging
import os
import time

#日志文件存放位置
DIR_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),'logs')

#gps脚本的日志
class BaseLog:
    def __init__(self,log_file,format='%(asctime)s - %(filename)s[line:%(lineno)d] - %(levelname)s: \n %(message)s'):
        # 第一步，创建一个logger
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.INFO)  # Log等级总开关  此时是INFO

        # 第二步，创建一个handler，用于写入日志文件
        self.logfile = os.path.join(DIR_PATH,log_file)
        dir_path = os.path.dirname(self.logfile) #判断日志文件的上级目录是否存在
        if not os.path.exists(dir_path):
            os.makedirs(dir_path) #创建目录
        fh = logging.FileHandler(self.logfile, mode='a+')  # open的打开模式这里可以进行参考
        fh.setLevel(logging.DEBUG)  # 输出到file的log等级的开关

        # 第三步，再创建一个handler，用于输出到控制台
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)  # 输出到console的log等级的开关

        # 第四步，定义handler的输出格式（时间，文件，行数，错误级别，错误提示）
        self.format = format
        formatter = logging.Formatter(self.format)
        fh.setFormatter(formatter) #写入文件的日志格式
        ch.setFormatter(formatter) #输出在控制台的日志格式

        # 第五步，将logger添加到handler里面
        self.logger.addHandler(fh)
        # self.logger.addHandler(ch) #打印到控制台的日志关闭掉
    def set_log(self,content='',level='error'):
        if level in ['info','debug','warning','error','critical']:
            log = getattr(self.logger,level)
            log(f'content: {content}')
        else:
            log = getattr(self.logger, 'error')
            log(f'content: {content}')

    def end_log(self,content = f'-----------end-----------\n\n'):

        #在日志文件中写入回车
        with open(self.logfile,mode='a+') as fp:
            fp.write(content)

    def start_log(self,content = f'\n-----------start: {time.strftime("%Y-%m-%d %H:%M:%S")}------------\n'):
        # 在日志文件中写入回车

        with open(self.logfile, mode='a+') as fp:
            fp.write(content)


# # 日志级别
# logger.debug('logger debug message')
# logger.info(' logger info message')
# logger.warning(' logger warning message')
# logger.error(' logger error message')
# logger.critical(' logger critical message')
# DEBUG：详细的信息,通常只出现在诊断问题上
# INFO：确认一切按预期运行
# WARNING（默认）：一个迹象表明,一些意想不到的事情发生了,或表明一些问题在不久的将来(例如。磁盘空间低”)。这个软件还能按预期工作。
# ERROR：更严重的问题,软件没能执行一些功能
# CRITICAL：一个严重的错误,这表明程序本身可能无法继续运行
