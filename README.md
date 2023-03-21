# 5G---
急救车端的推流脚本
需要使用到的结构：
1、ppid_file目录
  里面有audio_pid.txt 文件，存放的是{‘main’:pid值，'play':pid值}
  main：是audio.py 中在__main__的主进程，play是拉取医院端开启的播放音频的进程
  在util目录下的need.py中有一个专门检查网络中断的函数，当网络中断时，util下的restart_audio.py会先杀死main和play两个进程
  再，重新启动audio.py
2、util目录
3、audio.py 用来播放医院端的麦克风，播放前需要先推送before-play-audio.mp4文件
4、camaro.py 用来获取急救车的麦克风和摄像头，推送到医院端
5、screen.py 用来获取救护仪器的屏幕，推送到医院端
6、gps.py 用来获取急救车的定位信息，发送给医院端
