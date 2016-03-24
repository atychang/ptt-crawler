# ptt-crawler
A crawler for web ptt

### 說明
以ptt_crawler.cfg中的index為起點開始抓, 抓到該版的最新一篇貼文
預設為[1, 1], 代表從board_name/index1.html中的第1篇文章開始抓, 抓到最後一筆

同時也會將下次要以哪篇文章為起點的index記錄下來
所以下次執行程式時就從該篇文章開始抓, 抓到最新的一篇貼文

文章會以以下兩種方式儲存:
1. json格式 (posts/board_name/[M|G].[unsigned_integer].A.[HEX{3}].json)
2. mysql (預設為開啟, 可使用參數```--no-database```來關閉)

### 輸出格式
1. json
```
{
    "board": 版名,
    "url": [M|G].[unsigned_integer].A.[HEX{3}],
    "author": 作者,
    "title": 文章標題,
    "datetime": 發文時間,
    "ip": 發文者 IP,
    "content": 文章內容,
    "pushes": [
        {
            "status": 推/噓/→,
            "userid": 推文者 ID,
            "content": 推文內容,
            "datetime": 推文時間
        }
    ]
}
```
2. mysql
table schema請參考ptt.sql

### 注意事項
如需使用mysql, 請建立```my.cnf```, 預設路徑為```~/.my.cnf```, 請自行更改
```
# in my.cnf
[client]
host = localhost
port = 3306
database = dbname
user = username
password = password
default-character-set = utf8
```

### 執行環境
Python 3.4.3

### Pre-Install
1. [mysqlclient](https://github.com/PyMySQL/mysqlclient-python)
2. [beautifulsoup4](http://www.crummy.com/software/BeautifulSoup/bs4/doc/#problems-after-installation)

### 執行方法
```shell
$ python3 ptt_crawler.py (-b | --board) BOARD_NAME [--no-database]
```

### 範例
```shell
$ python3 ptt_crawler.py gossiping # store both file and database
or
$ python3 ptt_crawler.py tainan --no-database # only store file
```

Inspired by [PTTcrawler](https://github.com/wy36101299/PTTcrawler).
