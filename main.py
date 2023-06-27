import requests

def where():
    print("\n\n\n")
    print("73 = 福田东(福田区平安国际金融中心大厦) \n")
    print("75 = 福田南(福田区平安国际金融中心大厦) \n")
    print("80 = 福田北(福田区平安国际金融中心大厦) \n")
    print("106 = 罗湖东北(罗湖区华强北) \n")
    print("102 = 罗湖西南(罗湖区华强北) \n")
    print("62 = 石岩梯度塔全景(宝安区梯度塔) \n")
    print("120 = 石岩梯度塔西北(宝安区梯度塔) \n")
    print("121 = 石岩梯度塔西南(宝安区梯度塔) \n")
    print("58 = 龙岗大运中心南(龙岗区大运中心) \n")
    print("46 = 西涌南(龙岗区天文台) \n")
    code = input("请输入你要下载的视频的地区编号：\n")
    return code

def url_date():
    date = input("请输入你要下载的视频的日期(格式：20230627)：")
    return date

def download_mode():
    mode = input("请输入你要下载的模式（1 = 按小时下载，2 = 按天下载）：")
    return mode

def hours_download(url_hour, where, url_date, root):
    minutes = (19, 39, 59)
    for m in minutes:
        URL = "https://weather.121.com.cn/data_cache/video/rt/files/rt_" + where + "_" + url_date + url_hour + m + ".mp4"
        path = root + URL.split('/')[-1]
        hours_download(URL, path)

def days_download(url_date, where, root):
    minutes = (19,39,59)
    for i in range(24):
        for m in minutes:
            URL = "https://weather.121.com.cn/data_cache/video/rt/files/rt_"+ where + "_" + url_date + str(i) + m +".mp4"
            path = root + URL.split('/')[-1]
            hours_download(URL, path)

# 按间距中的绿色按钮以运行脚本。
if __name__ == '__main__':
    UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36 Edg/114.0.1823.58'
    root = input("请输入你要保存视频的文件夹路径 (例如：F:/Downloads)：")
    where = where()
    mode = download_mode()
    url_date = url_date()
    if mode == 1:
        url_hour = input("请输入你要下载的视频的小时(例如：14)：")
        hours_download(url_hour, where, url_date, root)
    elif mode == 2:
        days_download(where, root)
    else:
        print("输入错误！")


# 访问 https://www.jetbrains.com/help/pycharm/ 获取 PyCharm 帮助
