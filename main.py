# 使用requests从https://weather.121.com.cn/data_cache/video/rt/files/rt_80_202306271439.mp4下载视频并保存到“F:/Downloads”目录下
import os
import time
from datetime import datetime

import requests

# 文件保存路径请修改20行的root参数，code为地区代码，date为日期

hour = time.localtime(time.time()).tm_hour
today = datetime.now().strftime("%Y%m%d")
minutes = (19, 39, 59)
code = input("请输入你要下载的视频的地区编号:")
date = input("请输入你要下载的视频的日期(格式：" + today + ")：")

# 视频保存路径
root = "F:/Downloads/" + code + "/" + date + "/"

# 判断路径是否存在，不在则创建目录
if not os.path.exists(root):
    os.mkdir(root)

for i in range(hour):
    if int(i) < 10:
        i = "0" + str(i)
    for m in minutes:
        url = "https://weather.121.com.cn/data_cache/video/rt/files/video_" + str(code) + "_" + date + str(i) + str(
            m) + ".mp4"
        UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0'
        path = root + url.split('/')[-1]
        try:
            if not os.path.exists(root):
                os.mkdir(root)
            if not os.path.exists(path):
                headers = {'User-Agent': UA}
                r = requests.get(url, headers=headers)
                response = requests.head(url, headers=headers)
                if response.status_code == 200:
                    file_size = int(response.headers.get('Content-Length', -1))
                    if file_size < 1048576:
                        print(date + str(i) + str(m) + " 文件大小小于1MB，跳过")
                    else:
                        with open(path, 'wb') as f:
                            f.write(r.content)
                            f.close()
                            print(f"{date[:4]}-{date[4:6]}-{date[6:]}" + " " + str(i) + ":" + str(m) + " 文件保存成功")
                else:
                    print(f"{date[:4]}-{date[4:6]}-{date[6:]}" + " " + str(i) + ":" + str(m) + " 源文件不存在")
            else:
                print("文件已存在")
        except:
            print("出现异常")
