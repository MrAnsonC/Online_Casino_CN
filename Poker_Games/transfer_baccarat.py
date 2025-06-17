import os
from . import Combine_Baccarat  # 导入同包内的百家乐模块

def play_game(balance, user):
    # 调用真正的百家乐游戏
    new_balance = Combine_Baccarat.main(balance, user)
    
    # 返回更新后的余额到扑克中心
    return new_balance