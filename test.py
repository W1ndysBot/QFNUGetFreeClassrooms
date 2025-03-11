import requests


def get_free_classrooms():
    url = "http://zhjw.qfnu.edu.cn/jsxsd/kbcx/kbxx_classroom_ifr"

    # 请求头
    headers = {
        "Host": "zhjw.qfnu.edu.cn",
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
        "Referer": "http://zhjw.qfnu.edu.cn/jsxsd/kbcx/kbxx_classroom",
    }

    # POST请求参数
    data = {
        "xnxqh": "2024-2025-2",  # 学年学期，格式为"学年-学期"，如"2024-2025-2"表示2024-2025学年第二学期
        "kbjcmsid": "94786EE0ABE2D3B2E0531E64A8C09931",  # 课表基础模式ID，系统内部标识
        "skyx": "",  # 上课优先级，为空表示不限制
        "xqid": "",  # 校区ID，为空表示不限制校区
        "jzwid": "",  # 教学楼ID，为空表示不限制教学楼
        "skjsid": "",  # 上课教室ID，为空表示不限制具体教室ID
        "skjs": "格物楼A",  # 上课教室名称，这里指定查询"格物楼A"
        "zc1": "3",  # 开始周次，这里是第3周
        "zc2": "3",  # 结束周次，这里是第3周，与zc1相同表示只查询第3周
        "skxq1": "7",  # 开始星期，这里是星期日(7)
        "skxq2": "7",  # 结束星期，这里是星期日(7)，与skxq1相同表示只查询星期日
        "jc1": "",  # 开始节次，为空表示不限制开始节次
        "jc2": "",  # 结束节次，为空表示不限制结束节次
    }

    # 设置Cookie
    cookies = {
        "JSESSIONID": "3078A1EC23756A19CF8EE2D7294CB12C",
        "sto-id-20480": "CNLMMCMKFAAA",
    }

    try:
        response = requests.post(url, headers=headers, data=data, cookies=cookies)
        response.raise_for_status()  # 检查请求是否成功
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"请求发生错误: {e}")
        return None


if __name__ == "__main__":
    result = get_free_classrooms()
    if result:
        if "<title>登录</title>" in result:
            print("登录失效，请重新获取cookie")
        else:
            print(result)
    else:
        print("请求失败")
