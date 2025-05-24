import os
import time

# 管理员登录
def admin_login():
    admins = {
        "admin": "admin123"  # 你可以添加更多管理员
    }
    os.system('cls' if os.name == 'nt' else 'clear')
    print(" 充值 请呼叫管理员处理\n")
    
    for attempt in range(3):  # 允许3次登录尝试
        username = input("请输入管理员用户名: ")
        password = input("请输入管理员密码: ")
        os.system('cls' if os.name == 'nt' else 'clear')

        if username in admins and admins[username] == password:
            print(f"欢迎, {username}! 您已成功登录。\n")
            return True

        print("错误的用户名或密码，请重试。\n")

    print("登录失败！请联系系统管理员。")
    return False

# 用户充值功能
def charge_user(username, type):
    # 充值金额
    if type == "charge":
        try:
            charge_amount = float(input(f"请输入充值金额 (当前余额: {username['cash']}): "))
            print(f"成功为 {username['user_name']} 充值 {charge_amount:.2f} 元。")
            time.sleep(3)
            return charge_amount  # 返回充值金额
        except ValueError:
            print("无效的金额！")
            return 0  # 返回 0 避免 None 返回值
    else:
        try:
            charge_amount = float(input(f"请输入提款金额 (当前余额: {username['cash']}): "))
            print(f"成功为 {username['user_name']} 提款 {charge_amount:.2f} 元。")
            time.sleep(3)
            return charge_amount  # 返回充值金额
        except ValueError:
            print("无效的金额！")
            return 0  # 返回 0 避免 None 返回值

# 主要函数
def main(username, type):
    if admin_login():
        return charge_user(username, type)  # 确保返回充值金额
    else:
        print("管理员登录失败，无法进行充值操作。")
        return 0  # 登录失败时返回 0