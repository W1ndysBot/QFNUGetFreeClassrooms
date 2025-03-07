import os
import json
import re
from bs4 import BeautifulSoup
from tqdm import tqdm
from collections import defaultdict
import lxml  # 添加lxml解析器

def extract_classrooms():
    """从HTML文件中提取所有教室名称"""
    # 获取当前脚本所在目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    html_file_path = os.path.join(current_dir, 'all_info.html')
    
    print("正在读取HTML文件...")
    # 读取HTML文件
    with open(html_file_path, 'r', encoding='utf-8') as file:
        html_content = file.read()
    
    print("正在解析HTML内容...")
    # 使用lxml解析器加速解析
    soup = BeautifulSoup(html_content, 'lxml')
    
    # 直接定位到包含教室信息的表格行，跳过不必要的解析
    classrooms = []
    
    # 只选择包含教室信息的单元格，减少处理量
    print("正在提取教室信息...")
    # 直接获取第一列的单元格，这些单元格包含教室名称
    classroom_cells = soup.select('#kbtable tr td:first-child')
    
    # 跳过表头行
    for cell in tqdm(classroom_cells, desc="提取教室", unit="个"):
        classroom_name = cell.get_text().strip()
        if classroom_name and not classroom_name.startswith('教室'):  # 排除表头
            classrooms.append(classroom_name)
    
    return classrooms

def extract_building_name(classroom_name):
    """提取教室所属的楼名称"""
    # 格物楼A、格物楼B等模式
    match = re.match(r'^([\u4e00-\u9fa5]+楼)[A-Z]', classroom_name)
    if match:
        return match.group(1)
    
    # 实验中心A区、实验中心B区等模式
    match = re.match(r'^(实验中心)[A-Z]区', classroom_name)
    if match:
        return match.group(1)
    
    # JA、JB、JC等模式
    match = re.match(r'^J[A-Z]', classroom_name)
    if match:
        return "J楼"
    
    # JS模式
    if classroom_name.startswith('JS'):
        return "JS楼"
    
    # F楼模式
    if classroom_name.startswith('F'):
        return "F楼"
    
    # 其他带"楼"字的模式
    match = re.match(r'^([\u4e00-\u9fa5]+楼)', classroom_name)
    if match:
        return match.group(1)
    
    # 带"教学楼"、"教育楼"等的模式
    match = re.match(r'^([\u4e00-\u9fa5]+教[学育]楼)', classroom_name)
    if match:
        return match.group(1)
    
    # 体育场地相关
    if '篮球场' in classroom_name:
        return "篮球场"
    if '足球场' in classroom_name:
        return "足球场"
    if '排球场' in classroom_name:
        return "排球场"
    if '网球场' in classroom_name:
        return "网球场"
    if '田径场' in classroom_name:
        return "田径场"
    if '体育' in classroom_name or '武术' in classroom_name or '健美操' in classroom_name or '瑜伽' in classroom_name:
        return "体育场馆"
    
    # 如果没有匹配到任何模式，尝试提取前缀
    # 匹配数字前的所有内容作为前缀
    match = re.match(r'^(.*?)[0-9]', classroom_name)
    if match:
        return match.group(1)
    
    # 如果没有数字，尝试提取汉字部分
    match = re.match(r'^([\u4e00-\u9fa5]+)', classroom_name)
    if match:
        return match.group(1)
    
    # 如果以上都不匹配，返回前两个字符作为前缀
    if len(classroom_name) >= 2:
        return classroom_name[:2]
    
    # 如果字符串长度小于2，返回整个字符串
    return classroom_name

def extract_room_info(classroom_name, building_name):
    """提取教室的区域和房间号信息"""
    # 提取区域信息（如A、B等）
    area = ""
    room_number = ""
    
    # 格物楼A104等模式
    match = re.match(f'^{building_name}([A-Z])(\\d+)$', classroom_name)
    if match:
        area = match.group(1)
        room_number = match.group(2)
        return area, room_number
    
    # 实验中心A区A205、A207等模式
    match = re.match(f'^{building_name}([A-Z])区([A-Z]\\d+)、([A-Z]\\d+)$', classroom_name)
    if match:
        area = match.group(1) + "区"
        room_number = f"{match.group(2)}、{match.group(3)}"
        return area, room_number
    
    # JA101等模式
    match = re.match(r'^J([A-Z])(\d+)$', classroom_name)
    if match:
        area = match.group(1)
        room_number = match.group(2)
        return area, room_number
    
    # JS102等模式
    match = re.match(r'^JS(\d+)$', classroom_name)
    if match:
        area = "S"
        room_number = match.group(1)
        return area, room_number
    
    # F413-414等模式
    match = re.match(r'^F(\d+-\d+)$', classroom_name)
    if match:
        area = ""
        room_number = match.group(1)
        return area, room_number
    
    # 数学楼101等模式
    match = re.match(f'^{building_name}(\\d+)$', classroom_name)
    if match:
        area = ""
        room_number = match.group(1)
        return area, room_number
    
    # 化学楼109、111等模式
    match = re.match(f'^{building_name}(\\d+)、(\\d+)$', classroom_name)
    if match:
        area = ""
        room_number = f"{match.group(1)}、{match.group(2)}"
        return area, room_number
    
    # 如果没有匹配到任何模式，返回空区域和原始名称减去楼名的部分
    return "", classroom_name[len(building_name):]

def classify_classrooms_by_building(classrooms):
    """按楼名称对教室进行分类"""
    print("正在按楼名称对教室进行分类...")
    
    # 使用defaultdict来存储分类结果
    classified = defaultdict(list)
    
    for classroom in tqdm(classrooms, desc="分类教室", unit="个"):
        # 提取楼名称
        building_name = extract_building_name(classroom)
        
        # 提取区域和房间号
        area, room_number = extract_room_info(classroom, building_name)
        
        # 如果房间号为空，设置为"无编号"
        if not room_number:
            room_number = "无编号"
        
        # 将教室添加到对应楼名称的列表中
        classified[building_name].append({
            "name": classroom,
            "area": area,
            "room_number": room_number
        })
    
    # 将defaultdict转换为普通dict
    return dict(classified)

def save_classrooms_to_json(classified_classrooms):
    """将分类后的教室列表保存为JSON文件"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    output_file_path = os.path.join(current_dir, 'classrooms.json')
    
    # 创建包含分类教室列表的字典
    data = {
        "buildings": []
    }
    
    # 将分类结果转换为所需的格式
    for building_name, rooms in classified_classrooms.items():
        # 按区域分组
        areas = defaultdict(list)
        for room in rooms:
            areas[room["area"]].append(room)
        
        # 构建楼的数据结构
        building_data = {
            "name": building_name,
            "areas": []
        }
        
        # 添加每个区域的数据
        for area_name, area_rooms in areas.items():
            area_data = {
                "name": area_name,
                "rooms": sorted(area_rooms, key=lambda x: x["room_number"])
            }
            building_data["areas"].append(area_data)
        
        # 按区域名称排序
        building_data["areas"].sort(key=lambda x: x["name"])
        
        # 添加到buildings列表
        data["buildings"].append(building_data)
    
    # 按楼名称排序
    data["buildings"].sort(key=lambda x: x["name"])
    
    print("正在保存到JSON文件...")
    # 保存为JSON文件
    with open(output_file_path, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)
    
    # 计算总教室数和区域数
    total_rooms = sum(sum(len(area["rooms"]) for area in building["areas"]) for building in data["buildings"])
    total_areas = sum(len(building["areas"]) for building in data["buildings"])
    print(f"已成功提取 {total_rooms} 个教室，分类为 {len(data['buildings'])} 栋楼，{total_areas} 个区域，并保存到 {output_file_path}")

def print_classified_summary(classified_classrooms):
    """打印分类后的教室摘要"""
    print("\n教室分类摘要:")
    for building_name, rooms in sorted(classified_classrooms.items(), key=lambda x: len(x[1]), reverse=True):
        # 按区域分组
        areas = defaultdict(list)
        for room in rooms:
            areas[room["area"]].append(room)
        
        print(f"{building_name}: 共{len(rooms)}个教室，{len(areas)}个区域")
        
        # 打印每个区域的前几个教室
        for area_name, area_rooms in sorted(areas.items()):
            if area_name:
                print(f"  - {area_name}区: {len(area_rooms)}个教室")
            else:
                print(f"  - 主区: {len(area_rooms)}个教室")
            
            # 只打印前2个教室作为示例
            for room in area_rooms[:2]:
                print(f"    * {room['name']}")
            if len(area_rooms) > 2:
                print(f"    * ... 等{len(area_rooms)-2}个教室")

if __name__ == "__main__":
    print("开始提取教室列表...")
    # 提取教室列表
    classrooms = extract_classrooms()
    
    # 对教室进行楼名称分类
    classified_classrooms = classify_classrooms_by_building(classrooms)
    
    # 保存到JSON文件
    save_classrooms_to_json(classified_classrooms)
    
    # 打印分类摘要
    print_classified_summary(classified_classrooms)
