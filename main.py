# 使用requests从https://weather.121.com.cn/data_cache/video/rt/files/rt_80_202306271439.mp4下载视频并保存到“F:/Downloads”目录下
import requests
import os

minutes = (19,39,59)
hour = ['00','01','02','03','04','05','06','07','08','09','10','11','12','13','14','15','16','17','18','19','20','21','22','23']
code = input("请输入你要下载的视频的地区编号:")
date = input("请输入你要下载的视频的日期(格式：20230716)：")
for i in range(24):
    for m in minutes:
        url = "https://weather.121.com.cn/data_cache/video/rt/files/rt_"+ str(code) +"_"+ date + str(hour[i]) + str(m) +".mp4"
        root = "F:/Downloads/"+ code +"/"
        UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.67'
        path = root + url.split('/')[-1]
        try:
            if not os.path.exists(root):
                os.mkdir(root)
            if not os.path.exists(path):
                headers = {'User-Agent': UA}
                r = requests.get(url, headers=headers)
                with open(path, 'wb') as f:
                    f.write(r.content)
                    f.close()
                    print(date + str(hour[i]) + str(m) +"文件保存成功")
            else:
                print("文件已存在")
        except:
            print("爬取失败")