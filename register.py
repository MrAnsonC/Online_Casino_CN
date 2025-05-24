import json
import os
import time

# 定义存储文件
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'saving_data.json')

# 加载现有用户数据
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as file:
            return json.load(file)
    return []

# 保存用户数据
def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as file:
        json.dump(data, file, indent=4)

# 检查用户名是否已存在
def username_exists(username, data):
    return any(user['user_name'] == username for user in data)

# 主注册功能
def register():
    data = load_data()

    # 输入用户名
    user_name = input("请输入用户名: ")
    if username_exists(user_name, data):
        print("用户名已存在，请选择其他用户名。")
        time.out(5)
        return

    # 输入密码
    password1 = input("请输入密码: ")
    password2 = input("请再次输入密码: ")

    if password1 != password2:
        print("两次输入的密码不一致，请重试。")
        return

    # 创建新用户信息
    new_user = {
        "user_name": user_name,
        "password": password1,
        "cash": "0",
        "lock": "False"
    }

    # 添加新用户并保存
    data.append(new_user)
    save_data(data)
    print(f"用户 {user_name} 注册成功！")
    print(data)  # 打印当前用户数据以确认

def main():
    register()
