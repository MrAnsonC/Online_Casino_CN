import random
import json
import os
import time
import subprocess, sys

def get_data_file_path():
    # 用于获取保存数据的文件路径
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), '../saving_data.json')

# 保存用户数据
def save_user_data(users):
    file_path = get_data_file_path()
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

# 读取用户数据
def load_user_data():
    file_path = get_data_file_path()
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)
    
def update_balance_in_json(username, new_balance):
    users = load_user_data()  # 先加载现有用户数据
    for user in users:
        if user['user_name'] == username:  # 查找当前用户
            user['cash'] = f"{new_balance:.2f}"  # 更新余额
            break
    save_user_data(users)  # 保存更新后的数据


# Define card suits and ranks
suits = ['♥', '♦', '♣', '♠']
##suits = ['♥', '♦']
ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
##ranks = ['Q', 'K', 'A']
decking = [f"{rank}{suit}" for suit in suits for rank in ranks]

# Define card class
class Card:
    def __init__(self, rank, suit):
        self.rank = rank
        self.suit = suit

    def __str__(self):
        return f"{self.rank}{self.suit}"

    def get_value(self):
        if self.rank in ['J', 'Q', 'K']:
            return 10
        elif self.rank == 'A':
            return 11  # Initially return 11; adjust dynamically in the game logic
        else:
            return int(self.rank)
        
    def adjust_ace_value(self, current_hand_value):
        if self.rank == 'A' and current_hand_value > 21:
            return 1
        return self.get_value()

# Card display (dealer)
def dealer_display(self, dealer_first_card):
    print(f"庄家手牌: {str(dealer_first_card)} + ??  >>> ??")
    return

# Block
def block():
    print("========================================")
def block_end():
    print("=======================END==GAME========")
    time.sleep(3)
    os.system('cls' if os.name == 'nt' else 'clear')

# Side bet input
def get_side_bet_input(message):
    while True:
        try:
            amount = input(message)
            if amount == "":
                return 0
            amount = int(amount)
            if amount < 0:
                block()
                print("下注金额无效，请输入有效的金额。")
                block()
            else:
                return amount
        except ValueError:
            block()
            print("请输入一个有效的数字。")
            block()


# Result of card
def showing_result(player, dealer):
    block()
    print("||>\t 玩家     <|> \t   庄家      <||\n||>\t ",
          player,"\t  <|> \t   ",dealer,"\t     <||")
    block()

# Extract the unique digits
def extract_unique_digits(numbers):
    unique_digits = set()
    approve_digits = {'0' ,'1', '2', '3', '4', '5'}
    
    for char in numbers:
        if char in approve_digits:
            unique_digits.add(char)
            
    return sorted(map(int, unique_digits))

# Define deck class
class Deck:
    def __init__(self, num_decks = 4):
        self.num_decks = num_decks
        self.cards = []
        self.generate_deck()
        self.shuffle()

    def generate_deck(self):
        self.cards = [Card(rank, suit) for _ in range(self.num_decks) for suit in suits for rank in ranks]

    def shuffle(self):
        random.shuffle(self.cards)

    def deal_card(self):
        return self.cards.pop()

# Define player class
class Player:
    def __init__(self, name, initial_money=500):
        self.name = name
        self.money = int(initial_money)
        self.hand = []
        self.current_bet = 0
        self.current_pp = 0
        self.current_21_p_3 = 0 
        self.insurance_bet = 0
        self.current_royal = 0
        self.current_bust_amount = 0
        self.current_fire_3 = 0

    def place_bet(self, amount, pp_amount, twenty_four_amount, royal_match_amount, too_many_amount, fire_3_amount):
        self.current_bet = 0
        self.current_pp = 0
        self.current_21_p_3 = 0
        self.current_royal = 0
        self.current_bust_amount = 0
        self.current_fire_3 = 0
        T_bet = 0
        T_bet = amount + pp_amount + twenty_four_amount + royal_match_amount + too_many_amount + fire_3_amount
        if T_bet > self.money:
            print("Insufficient funds!")
            return False
        self.current_bet += amount
        self.current_pp += pp_amount
        self.current_21_p_3 += twenty_four_amount
        self.current_royal += royal_match_amount
        self.current_bust_amount += too_many_amount
        self.current_fire_3 += fire_3_amount
        self.money -= amount
        self.money -= pp_amount
        self.money -= twenty_four_amount
        self.money -= royal_match_amount
        self.money -= too_many_amount
        self.money -= fire_3_amount
        return True

    def clear_hand(self):
        self.hand = []

    def add_card(self, card):
        self.hand.append(card)

    def get_hand_value(self):
        hand_value = sum(card.get_value() for card in self.hand)
        num_aces = sum(1 for card in self.hand if card.rank == 'A')

        # Adjust for Aces
        while hand_value > 21 and num_aces > 0:
            hand_value -= 10
            num_aces -= 1

        return hand_value

# Define dealer class
class Dealer:
    def __init__(self):
        self.hand = []

    def clear_hand(self):
        self.hand = []

    def add_card(self, card):
        self.hand.append(card)

    def get_hand_value(self):
        if not self.hand:
            return 0

        hand_value = sum(card.get_value() for card in self.hand)
        num_aces = sum(1 for card in self.hand if card.rank == 'A')

        # Adjust for Aces
        while hand_value > 21 and num_aces > 0:
            hand_value -= 10
            num_aces -= 1

        return hand_value

    def should_hit(self):
        return self.get_hand_value() < 17

# Define blackjack game class
class BlackjackGame:
    def __init__(self):
        self.deck = Deck()
        self.player = Player("Player", initial_money=500)
        self.dealer = Dealer()

    def reset_game(self):
        self.player.clear_hand()
        self.dealer.clear_hand()

    def deal_initial_cards(self):
        self.player.add_card(self.deck.deal_card())
        self.dealer.add_card(self.deck.deal_card())
        self.player.add_card(self.deck.deal_card())
        self.dealer.add_card(self.deck.deal_card())

    def player_turn(self, dealer_first_card):
        block(), block()
        print(f"玩家手牌: {' + '.join(str(card) for card in self.player.hand)}  >>> {self.player.get_hand_value()}")
        double_surrender_allow = True
        while True:
            if self.player.hand[1].rank == 'A' and self.player.hand[0].get_value() == 10 or self.player.hand[0].rank == 'A' and self.player.hand[1].get_value() == 10:
                return 2
            else:
                if self.player.get_hand_value() == 21:
                    break
                else:
                    if double_surrender_allow == True:
                        dealer_display(self, dealer_first_card)
                        block()
                        print("① 要牌 ② 停牌 ③ 加倍 ④ 投降输一半")
                        action = input("选择动作: ").lower()
                    else:
                        dealer_display(self, dealer_first_card)
                        block()
                        print("① 要牌 ② 停牌")
                        action = input("选择动作: ").lower()
                        
            if action == "1":
                double_surrender_allow = False
                self.player.add_card(self.deck.deal_card())
                time.sleep(1)
                hand_value = self.player.get_hand_value()

                block()
                print(f"玩家要牌: {' + '.join(str(card) for card in self.player.hand)}  >>> {hand_value}")

                if hand_value > 21:
                    time.sleep(2)
                    return -1  # Player busts

            elif action == "2":
                break

            elif action == "3" and double_surrender_allow == True:
                if self.player.money >= self.player.current_bet:
                    self.player.money -= self.player.current_bet
                    self.player.current_bet *= 2
                    self.player.add_card(self.deck.deal_card())
                    hand_value = self.player.get_hand_value()
                    block()
                    time.sleep(1)
                    print(f"加倍: {' + '.join(str(card) for card in self.player.hand)}  >>> {hand_value}")
                    time.sleep(2)
                    if self.player.get_hand_value() > 21:
                        return -1  # Player bustsbreak
                    else:
                        break
                else:
                    print("资金不足，无法加倍下注！")

            elif action == "4" and double_surrender_allow == True:
                self.player.money += self.player.current_bet / 2
                block()
                print("投降输一半！明智的选择。")
                return -0.5  # Player surrenders

            else:
                block()
                if double_surrender_allow == True:                    
                    print("输入无效，请输入有效的数字")
                else:
                    if action == "4":          
                        print("无法投降. 请输入 ① 或 ②")
                    elif action == "3":
                        print("无法加倍. 请输入 ① 或 ②")
                    else:
                        print("请输入一个有效的数字。")
                block()
                print(f"玩家手牌: {' + '.join(str(card) for card in self.player.hand)}  >>> {self.player.get_hand_value()}")

        return 0  # Player stands

    def dealer_turn(self):
        block(), block()
        print(f"庄家手牌: {' + '.join(str(card) for card in self.dealer.hand)}  >>> {self.dealer.get_hand_value()}")
        while self.dealer.should_hit():
            time.sleep(1)
            self.dealer.add_card(self.deck.deal_card())
            block()
            print(f"庄家要牌: {' + '.join(str(card) for card in self.dealer.hand)}  >>> {self.dealer.get_hand_value()}")
        time.sleep(2)

    def settle_bets(self, result):
        player_hand_value = self.player.get_hand_value()
        dealer_hand_value = self.dealer.get_hand_value()
        dealer_card_count = len(self.dealer.hand)
        if result == -1:  # Player busts
            block(), block()
            print(f"庄家手牌: {' + '.join(str(card) for card in self.dealer.hand)}  >>> {self.dealer.get_hand_value()}")
            showing_result(player_hand_value, dealer_hand_value)
            print("玩家爆牌! 庄家胜利！ ")
        elif result == -0.5:  # Player surrenders
            block(), block()
            print(f"庄家手牌: {' + '.join(str(card) for card in self.dealer.hand)}  >>> {self.dealer.get_hand_value()}")
            showing_result(player_hand_value, dealer_hand_value)
            print("玩家投降。")
        elif result == 2:  # Player Blackjack
            block()
            showing_result("BJ", dealer_hand_value)
            print("\n\t你赢了21点!     \n")
            self.player.money += self.player.current_bet * 2.5
            self.player.money += self.player.current_bust_amount
        else:
            if dealer_hand_value > 21:
                showing_result(player_hand_value, dealer_hand_value)
                print("庄家爆牌! 玩家胜利！")
                self.player.money += self.player.current_bet * 2
            elif player_hand_value > dealer_hand_value:
                showing_result(player_hand_value, dealer_hand_value)
                print("你赢了！")
                self.player.money += self.player.current_bet * 2
            elif player_hand_value < dealer_hand_value:
                showing_result(player_hand_value, dealer_hand_value)
                print("庄家胜利！")
            else:
                showing_result(player_hand_value, dealer_hand_value)
                print("和牌。")
                self.player.money += self.player.current_bet

        if dealer_hand_value > 21:
            if self.player.current_bust_amount != 0:
                multiplier = {
                    3: 1,
                    4: 2,
                    5: 10,
                    6: 50,
                    7: 100
                }

                # Calculate winnings
                win_multiplier = multiplier.get(dealer_card_count, 250)
                winnings = self.player.current_bust_amount * (win_multiplier + 1)

                # Update player's money
                self.player.money += self.player.current_bust_amount * (win_multiplier + 1)

                # Block and print messages
                block()
                print("恭喜你! 庄家爆牌!!")
                print(f"赔 1 : {win_multiplier}. 你赢了: {winnings}")

        # Clear current bet after settling
        self.player.current_bet = 0
        block_end(), block()
        
    def play_round(self):
        self.reset_game()
        self.deal_initial_cards()

        player_hand_value = self.player.get_hand_value()
        dealer_hand_value = self.dealer.get_hand_value()

        ## Side-bet  Perfect pair
        if self.player.current_pp != 0:
            if self.player.hand[0].rank == self.player.hand[1].rank:
                block()
                if self.player.hand[0].suit == self.player.hand[1].suit:
                    if self.player.hand[0].rank == "A":
                        print("恭喜你赢了完美对子A ！！！\n支付 1 : 50. 你赢了:",self.player.current_pp*50)
                        self.player.money += self.player.current_pp*50
                    else:
                        print("恭喜你赢了完美对子！！\n支付 1 : 10. 你赢了:",self.player.current_pp*10)
                        self.player.money += self.player.current_pp*10
                elif self.player.hand[0].suit == "♥" and self.player.hand[1].suit == "♦" or self.player.hand[0].suit == "♦" and self.player.hand[1].suit == "♥" or self.player.hand[0].suit == '♠' and self.player.hand[1].suit == '♣' or self.player.hand[0].suit == '♣' and self.player.hand[1].suit == '♠':
                    print("恭喜你赢了同色对子！！\n支付 1 : 6. 你赢了:",self.player.current_pp*6)
                    self.player.money += self.player.current_pp*25
                else:
                    print("恭喜你赢了完美对子！\n支付 1 : 4. 你赢了:",self.player.current_pp*4)
                    self.player.money += self.player.current_pp*4

        ## Side-bet  21+3
        if self.player.current_21_p_3 != 0:
            straight = False
            suit = False
            
            ranks = [self.player.hand[0].rank, self.player.hand[1].rank, self.dealer.hand[0].rank]
            ranks.sort()

            valid_straights = {
                ('10', 'J', 'Q'),
                ('J', 'Q', 'K'),
                ('2', '3', 'A'),
                ('2', '3', '4'),
                ('3', '4', '5'),
                ('4', '5', '6'),
                ('5', '6', '7'),
                ('6', '7', '8'),
                ('7', '8', '9'),
                ('8', '9', '10'),
                ('9', '10', 'J'),
                ('10', 'J', 'Q'),
                ('J', 'K', 'Q'),
                ('K', 'Q', 'A')
            }

            if any(tuple(ranks[i:i+3]) in valid_straights for i in range(len(ranks)-2)):
                straight = True

            if self.player.hand[0].suit == self.player.hand[1].suit == self.dealer.hand[0].suit:
                suit = True

            if straight and suit:
                block()
                print("恭喜你赢了21+3! (同花顺)\n支付 1 : 40. 你赢了: ",self.player.current_21_p_3*40)
                self.player.money += self.player.current_21_p_3 * 40
            elif suit:
                block()
                print("恭喜你赢了21+3! (同花)\n支付 1 : 5. 你赢了: ",self.player.current_21_p_3*5)
                self.player.money += self.player.current_21_p_3 * 5
            elif straight:
                block()
                print("恭喜你赢了21+3! (顺子)\n支付 1 : 10. 你赢了: ",self.player.current_21_p_3*10)
                self.player.money += self.player.current_21_p_3 * 10

            if self.player.hand[0].rank == self.player.hand[1].rank == self.dealer.hand[0].rank:
                block()
                if self.player.hand[0].suit == self.player.hand[1].suit == self.dealer.hand[0].suit:
                    print("恭喜你赢了21+3! (3张同花同数)\n支付 1 : 100. 你赢了: ",self.player.current_21_p_3*100)
                    self.player.money += self.player.current_21_p_3 * 100
                else:
                    print("恭喜你赢了21+3! (3张同数)\n支付 1 : 30. 你赢了: ",self.player.current_21_p_3*30)
                    self.player.money += self.player.current_21_p_3 * 30

        ## Side-bet  Royal Match
        if self.player.current_royal != 0:
            if self.player.hand[0].suit == self.player.hand[1].suit:
                block()
                if self.player.hand[0].rank == "Q" and self.player.hand[1].rank == "K" or self.player.hand[1].rank == "Q" and self.player.hand[0].rank == "K":
                    winning_royal = self.player.current_royal*25
                    print("\n你有同花 Q 和 K!!")
                    print("支付 1 : 25. 你赢了:",winning_royal,"\n")
                    self.player.money += self.player.current_royal * 25
                else:
                    print("恭喜你赢了皇家同花! \n(同花)支付 2 : 5. 你赢了:",self.player.current_royal*2.5)
                    self.player.money += self.player.current_royal * 2.5

        ##Side bet  Fire 3
        if self.player.current_fire_3 != 0:
            if self.dealer.hand[0].rank == "J" or self.dealer.hand[0].rank == "Q" or self.dealer.hand[0].rank == "K":
                dealer_hand_values = 10
            elif self.dealer.hand[0].rank == "A":
                test_1_or_11 = player_hand_value + 1
                if test_1_or_11 > 18 and test_1_or_11 < 22:
                    dealer_hand_values = 1
                else:
                    dealer_hand_values = 11
            else:
                dealer_hand_values = self.dealer.hand[0].rank
            three_cards_total = player_hand_value + int(dealer_hand_values)
            if three_cards_total > 18 and three_cards_total < 22:
                block()
                if three_cards_total == 19:
                    print("恭喜你赢了最火3总和! (19)\n支付 1 : 1. 你赢了: ",self.player.current_fire_3*2)
                    self.player.money += self.player.current_fire_3*2
                elif three_cards_total == 20:
                    print("恭喜你赢了最火3总和! (20)\n支付 1 : 2. 你赢了: ",self.player.current_fire_3*3)
                    self.player.money += self.player.current_fire_3*3
                else:
                    if self.player.hand[0].suit == self.player.hand[1].suit == self.dealer.hand[0].suit:
                        print("恭喜你赢了最火3总和! (21)\n支付 1 : 20. 你赢了: ",self.player.current_fire_3*20)
                        self.player.money += self.player.current_fire_3*21
                    elif self.player.hand[0].rank == 7 and self.player.hand[1].rank == 7 and self.dealer.hand[0].rank == 7:
                        print("恭喜你赢了最火3总和! (21)\n支付 1 : 100. 你赢了: ",self.player.current_fire_3*100)
                        self.player.money += self.player.current_fire_3*101
                    else:
                        print("恭喜你赢了最火3总和! (21)\n支付 1 : 4. 你赢了: ",self.player.current_fire_3*4)
                        self.player.money += self.player.current_fire_3*4
            
            

        # Check for dealer blackjack immediately after dealing initial cards
        if self.dealer.hand[1].rank == 'A' and self.dealer.hand[0].get_value() == 10:
            block()
            print(f"玩家手牌: {' + '.join(str(card) for card in self.player.hand)}   数值: {self.player.get_hand_value()}")
            print(f"庄家手牌: {' + '.join(str(card) for card in self.dealer.hand)}   数值: {self.dealer.get_hand_value()}")

            if self.player.get_hand_value() == 21:
                showing_result("BJ", "BJ")
                print("玩家和庄家都是21点! 和牌。")
                self.player.money += self.player.current_bet
            else:
                showing_result(player_hand_value, "BJ")
                block()
                print("\n\t 庄家是21点!\n")
            block_end()
            return
        
        choice_bj = "no"
        self.player.insurance_bet = 0
        
        if self.dealer.hand[0].rank == 'A' and self.player.get_hand_value() == 21:
            block()
            block()
            choice_bj = "continue"
            block
            print("你是21点! \n但庄家的第一张牌为A. 你想......")
            print(" ① 直接以1：1赢下这局 \n ② 以1：1.5赢下这局,前提庄家不是21点")
            choice_bj = input("输入你的选择： ")
            if choice_bj == "1":
                self.player.money += self.player.current_bet * 2
                self.player.current_bet = 0
                if self.dealer.get_hand_value() == 21:
                    showing_result("BJ", "BJ")
                else:
                    showing_result("BJ", dealer_hand_value)
                return
            else:
                choice_bj == "nope"

        if self.dealer.hand[0].rank == 'A' and choice_bj == "no" :
            block()
            block()
            print("庄家的第一张牌为A. 你想......")
            print(" ① 已本金的50%购买保险 ② 不买保险? ")
            choice = input("你的选择是： ")
            if choice == "1":
                insurance_amount = self.player.current_bet * (1/2)
                if self.player.money >= insurance_amount:
                    self.player.money -= insurance_amount
                    self.player.insurance_bet = insurance_amount

        if self.dealer.hand[0].rank == 'A' and self.dealer.hand[1].get_value() == 10:
            print(f"玩家手牌: {' + '.join(str(card) for card in self.player.hand)}   数值: {self.player.get_hand_value()}")
            print(f"庄家手牌: {' + '.join(str(card) for card in self.dealer.hand)}   数值: {self.dealer.get_hand_value()}")
            block()
            block()
            if self.player.insurance_bet > 0:
                print("\n\t庄家是21点!\n")
                showing_result(player_hand_value, "BJ")
                print("Insurance pays 2:1.")
                self.player.money += self.player.insurance_bet * 2
            elif choice_bj == "nope":
                showing_result("BJ", "BJ")
                print("\n玩家和庄家都是21点! 和牌\n")
                self.player.money += self.player.current_bet
            else:
                print("\n\t庄家是21点!\n")
                showing_result(player_hand_value, "BJ")
                print("庄家胜利！")
            block_end()
            return

        # Call player_turn with dealer's first card
        player_result = self.player_turn(self.dealer.hand[0])
        
        self.dealer_turn()
        self.settle_bets(player_result)
        self.player.current_bet = 0

    def display_deck(self):
        suits = ['♥', '♦', '♣', '♠']
        ranks = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
        card_count = {suit: {rank: 0 for rank in ranks} for suit in suits}
        total_count = {rank: 0 for rank in ranks}

        # Count the cards remaining in the deck
        for card in self.deck.cards:
            card_count[card.suit][card.rank] += 1

        for suit in suits:
            for rank in ranks:
                total_count[rank] += card_count[suit][rank]

        # Print table header
        print("\n   A  2  3  4  5  6  7  8  9  X  J  Q  K")
        # print("\n   A  2  3  4  5  6  7  8  9  X  J  Q  K  ||  T")

        # Print each row for suits with counts
        for suit in suits:
            row = [str(card_count[suit][rank]) for rank in ranks]
            total = sum(card_count[suit][rank] for rank in ranks)
            print(f"{suit}  {'  '.join(row)}")
            # print(f"{suit}  {'  '.join(row)}  || {total}")
        # print("================================================")
        block()
        total_row = [f"{total_count[rank]:02}" for rank in ranks]
        total_sum = sum(total_count[rank] for rank in ranks)
        print(f"  {' '.join(total_row)}")
        # print(f"   {' '.join(total_row)} || {total_sum}")
        print()

# Main program loop
def main(balance, username):
    fst_log_in = True
    game = BlackjackGame()
    game.player.money = balance
    
    while True:
        if fst_log_in:
            side_bet_choice = 0
            os.system('cls' if os.name == 'nt' else 'clear')
            print(" 欢迎玩21点\n")
            print("以下是一些变注的特色玩法:")
            print("① 完美对子 ② 21+3  ③ 皇家同花")
            print("   ④ 爆!    ⑤ 最火3总和\n")
            print("不输入 = 无附加边注")
            
            while True:
                side_bet_choice = input("选择边注代码:  ")
                if side_bet_choice == "":
                    side_bet_choice = "0"
                result = extract_unique_digits(side_bet_choice)
                if result:
                    break
                else:
                    block()
                    print("你只能输入 1, 2, 3, 4, 5")
                    block()
                    
            os.system('cls' if os.name == 'nt' else 'clear')
            
        os.system('cls' if os.name == 'nt' else 'clear')

        if balance <= 0:
            print("你已经输光了本金，游戏结束。")
            return balance

        if len(game.deck.cards) < 45 or fst_log_in:
            fst_log_in = False
            for i in range(20):
                if i != 20:
                    os.system('cls' if os.name == 'nt' else 'clear')
                    print("。。。洗牌中。。。")
                    print(*random.sample(decking, 6))
                    time.sleep(0.07)
            game.deck.generate_deck()
            game.deck.shuffle()
            os.system('cls' if os.name == 'nt' else 'clear')

        print(" 21点")
        print(f"当前余额： {int(game.player.money)}")
        
        while True:
            bet_amount = input("输入您的下注金额(0退出): ")
            if bet_amount.lower() == "dev":
                game.display_deck()
                continue 
            try:
                bet_amount = int(bet_amount)
                if bet_amount < 0:
                    print("下注金额无效，请输入有效的金额。")
                else:
                    break
            except ValueError:
                block()
                print("请输入一个有效的数字。")
                block()

        if bet_amount == 0:
            block()
            block()
            print("感谢你的游玩!")
            print("=======================MAKE=BY=HSC======")
            time.sleep(2.5)
            break
                
        ## Side bet 
        if 1 in result:
            pp_amount = get_side_bet_input("输入您的[完美对子]下注金额: ")
        else:
            pp_amount = 0

        if 2 in result:
            Twenty4_amount = get_side_bet_input("输入您的[21+3]下注金额: ")
        else:
            Twenty4_amount = 0

        if 3 in result:
            royal_match_amount = get_side_bet_input("输入您的[皇家同花]下注金额: ")
        else:
            royal_match_amount = 0

        if 4 in result:
            too_many_amount = get_side_bet_input("输入您的[爆!]下注金额: ")
        else:
            too_many_amount = 0

        if 5 in result:
            fire_3_amount = get_side_bet_input("输入您的[最火3总和]下注金额: ")
        else:
            fire_3_amount = 0

        if game.player.place_bet(bet_amount, pp_amount, Twenty4_amount, royal_match_amount, too_many_amount, fire_3_amount):
            game.play_round()
        else:
            block()
            print("下注金额无效，请输入有效的金额。")
            continue

        if username != "demo_player":
            update_balance_in_json(username, game.player.money)

    return game.player.money

if __name__ == "__main__":
    main(100, "demo_player")