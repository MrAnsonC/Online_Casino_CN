<?php
// 获取当前页面参数，默认为 welcome
$page = isset($_GET['page']) ? $_GET['page'] : 'welcome';
$allowed = ['welcome','csp', 'casino_holdem', 'djw', '3cp', 'fcp', 'huh', 'lir', 'msp', 'uth', 'u3p', 'uoh', 'sicbo', 'vdp', 'baccarat', 'roulette_europe', 'roulette_american', 'roulette_bigsix', 'wfp'];
if (!in_array($page, $allowed)) {
    $page = 'welcome';
}
?>
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>游戏数据监控</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        /* ===== 全局重置 & 基础 ===== */
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        html, body {
            height: 100%;
            overflow: hidden;
        }
        body {
            background: linear-gradient(135deg, #1a2a3a, #0d1520);
            color: #e0e0e0;
            display: flex;
            flex-direction: column;
        }

        /* ===== 顶栏 ===== */
        .top-header {
            background: rgba(10, 18, 28, 0.95);
            backdrop-filter: blur(6px);
            border-bottom: 2px solid #2a3b4d;
            padding: 12px 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-shrink: 0;
            z-index: 100;
            flex-wrap: wrap;
            gap: 10px;
        }
        .logo {
            font-size: 1.8rem;
            font-weight: 700;
            color: #ffcc00;
            text-shadow: 0 0 10px rgba(255,204,0,0.3);
            letter-spacing: 1px;
        }
        .logo i {
            margin-right: 10px;
        }

        /* ===== 下拉菜单 ===== */
        .nav-menu {
            display: flex;
            gap: 30px;
            flex-wrap: wrap;
        }
        .nav-item {
            position: relative;
            cursor: pointer;
        }
        .nav-item > a {
            color: #c0d0e0;
            font-size: 1.1rem;
            font-weight: 600;
            text-decoration: none;
            padding: 8px 0;
            display: inline-block;
            transition: color 0.2s;
        }
        .nav-item > a:hover {
            color: #ffcc00;
        }
        .dropdown {
            position: absolute;
            top: 100%;
            left: 0;
            background: rgba(20, 30, 45, 0.98);
            backdrop-filter: blur(8px);
            border-radius: 12px;
            padding: 10px 0;
            min-width: 200px;
            box-shadow: 0 12px 35px rgba(0,0,0,0.6);
            border: 1px solid rgba(255,255,255,0.08);
            display: none;
            z-index: 200;
        }
        .nav-item:hover .dropdown {
            display: block;
        }
        .dropdown a {
            display: block;
            padding: 10px 24px;
            color: #d0d8e0;
            text-decoration: none;
            font-size: 0.95rem;
            transition: all 0.2s;
            border-left: 3px solid transparent;
        }
        .dropdown a:hover {
            background: rgba(255,204,0,0.08);
            color: #ffcc00;
            border-left-color: #ffcc00;
        }
        .dropdown a i {
            margin-right: 10px;
            width: 20px;
            text-align: center;
        }

        /* ===== 中间内容 ===== */
        .main-content {
            flex: 1;
            overflow-y: auto;
            padding: 20px 30px 20px 30px;
            background: transparent;
        }
        .main-content::-webkit-scrollbar {
            width: 6px;
        }
        .main-content::-webkit-scrollbar-thumb {
            background: #2a3b4d;
            border-radius: 10px;
        }

        /* ===== 底栏 ===== */
        .bottom-bar {
            background: rgba(10, 18, 28, 0.95);
            backdrop-filter: blur(6px);
            border-top: 2px solid #2a3b4d;
            padding: 10px 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-shrink: 0;
            font-size: 0.95rem;
            color: #8da0b3;
            flex-wrap: wrap;
            gap: 8px;
        }
        .bottom-bar .time {
            color: #ffcc00;
            font-weight: 600;
            font-variant-numeric: tabular-nums;
        }
        .bottom-bar .refresh-btn {
            background: rgba(255,204,0,0.12);
            border: 1px solid #ffcc00;
            color: #ffcc00;
            padding: 6px 20px;
            border-radius: 50px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.3s;
        }
        .bottom-bar .refresh-btn:hover {
            background: rgba(255,204,0,0.25);
        }

        /* ===== 欢迎页 ===== */
        .welcome-box {
            max-width: 700px;
            margin: 60px auto;
            text-align: center;
            background: rgba(25,35,50,0.5);
            backdrop-filter: blur(4px);
            padding: 50px 40px;
            border-radius: 30px;
            border: 1px solid rgba(255,255,255,0.06);
        }
        .welcome-box h2 {
            font-size: 2.8rem;
            color: #ffcc00;
            margin-bottom: 20px;
        }
        .welcome-box p {
            font-size: 1.2rem;
            color: #b0c4d8;
            line-height: 1.8;
        }
        .welcome-box .icon-grid {
            display: flex;
            justify-content: center;
            gap: 40px;
            margin-top: 30px;
            flex-wrap: wrap;
        }
        .welcome-box .icon-grid i {
            font-size: 3.5rem;
            color: #4ecdc4;
            opacity: 0.7;
            transition: 0.3s;
        }
        .welcome-box .icon-grid i:hover {
            opacity: 1;
            transform: scale(1.1);
        }

        /* ===== 响应式 ===== */
        @media (max-width: 768px) {
            .top-header {
                padding: 10px 16px;
                flex-direction: column;
                align-items: stretch;
                gap: 6px;
            }
            .logo {
                font-size: 1.4rem;
                text-align: center;
            }
            .nav-menu {
                justify-content: center;
                gap: 16px;
            }
            .nav-item > a {
                font-size: 1rem;
            }
            .main-content {
                padding: 16px;
            }
            .bottom-bar {
                flex-direction: column;
                text-align: center;
                padding: 8px 16px;
                font-size: 0.85rem;
            }
            .welcome-box {
                padding: 30px 20px;
                margin: 30px 10px;
            }
            .welcome-box h2 {
                font-size: 2rem;
            }
        }
        @media (max-width: 480px) {
            .nav-menu {
                gap: 10px;
                flex-wrap: wrap;
            }
            .nav-item > a {
                font-size: 0.9rem;
            }
            .dropdown {
                min-width: 160px;
            }
        }
    </style>
</head>
<body>

    <!-- ========== 顶栏 ========== -->
    <header class="top-header">
        <div class="logo">
            <i class="fas fa-dice"></i> GameMonitor
        </div>
        <nav class="nav-menu">
            <!-- 扑克 -->
            <div class="nav-item">
                <a href="#">🂡 扑克</a>
                <div class="dropdown">
                    <a href="?page=csp">🂡 加勒比梭哈扑克</a>
                    <a href="?page=djw">🂡 DJ Wild梭哈扑克</a>
                    <a href="?page=casino_holdem">🂡 赌场扑克</a>
                    <a href="?page=huh">🂡 单挑扑克</a>
                    <a href="?page=3cp">🂡 三张牌扑克</a>
                    <a href="?page=fcp">🂡 四张牌扑克</a>
                    <a href="?page=lir">🂡 任逍遥撲克</a>
                    <a href="?page=msp">🂡 密⻄⻄⽐梭哈撲克</a>
                    <a href="?page=uth">🂡 终极德州扑克</a>
                    <a href="?page=u3p">🂡 终极三张牌扑克</a>
                    <a href="?page=uoh">🂡 终极极奥马哈扑克</a>
                    <a href="?page=baccarat">🂡 百家乐</a>
                    <a href="?page=vdp">🂡 视频扑克</a>
                    <a href="?page=wfp">🂡 ⺩牌五張撲克</a>
                </div>
            </div>
            <!-- 轮盘 -->
            <div class="nav-item">
                <a href="#"><i class="fas fa-circle"></i> 轮盘</a>
                <div class="dropdown">
                    <a href="?page=roulette_europe"><i class="fas fa-globe-europe"></i> 欧式轮盘</a>
                    <a href="?page=roulette_american"><i class="fas fa-globe-americas"></i> 美式轮盘</a>
                    <a href="?page=roulette_bigsix"><i class="fas fa-bolt"></i> 大六轮盘</a>
                </div>
            </div>
            <!-- 小游戏 -->
            <div class="nav-item">
                <a href="#"><i class="fas fa-gamepad"></i> 小游戏</a>
                <div class="dropdown">
                    <a href="#"><i class="fas fa-hourglass-start"></i> 即将上线</a>
                </div>
            </div>
            <!-- 其他 -->
            <div class="nav-item">
                <a href="#"><i class="fas fa-ellipsis-h"></i> 其他</a>
                <div class="dropdown">
                    <a href="?page=sicbo"><i class="fas fa-cubes"></i> 骰宝</a>
                </div>
            </div>
        </nav>
    </header>

    <!-- ========== 中间内容 ========== -->
    <main class="main-content" id="mainContent">
        <?php
        // 根据 page 参数加载对应内容
        if ($page === 'welcome') {
            // 默认欢迎页
            echo '
            <div class="welcome-box">
                <h2><i class="fas fa-chart-line"></i> 数据监控中心</h2>
                <p>
                    请从顶部菜单选择游戏，查看实时统计数据。<br>
                    支持 <strong>终极德州扑克</strong> 与 <strong>骰宝</strong> 双游戏。
                </p>
                <div class="icon-grid">
                    <i class="fas fa-cards" title="扑克"></i>
                    <i class="fas fa-circle" title="轮盘"></i>
                    <i class="fas fa-gamepad" title="小游戏"></i>
                    <i class="fas fa-cubes" title="骰宝"></i>
                </div>
                <p style="margin-top:25px;font-size:0.95rem;color:#6a7f94;">
                    <i class="fas fa-arrow-up"></i> 点击菜单中的子项切换
                </p>
            </div>
            ';
        } elseif ($page === 'casino_holdem') {
            include 'Casino_Holdem.php';
        } elseif ($page === 'csp') {
            include 'Caribbean_Stud_Poker.php';
        } elseif ($page === 'djw') {
            include 'DJ_Wild.php';
        } elseif ($page === 'fcp') {
            include 'Four_Card_Poker.php';
        } elseif ($page === '3cp') {
            include 'Three_Card_Poker.php';
        } elseif ($page === 'huh') {
            include 'Heads_Up_Holdem.php';
        } elseif ($page === 'lir') {
            include 'Let_It_Ride.php';
        } elseif ($page === 'msp') {
            include 'Mississippi_Stud_Poker.php';
        } elseif ($page === 'uth') {
            include 'Ultimate_Texas_Holdem.php';
        } elseif ($page === 'u3p') {
            include 'Ultimate_Three_Card_Poker.php';
        } elseif ($page === 'uoh') {
            include 'Ultimate_Omaha_Holdem.php';
        } elseif ($page === 'baccarat') {
            include 'Baccarat.php';
        } elseif ($page === 'vdp') {
            include 'Video_Poker.php';
        } elseif ($page === 'roulette_europe') {
            include 'Roulette_Europe.php';
        } elseif ($page === 'roulette_american') {
            include 'Roulette_American.php';
        } elseif ($page === 'roulette_bigsix') {
            include 'Roulette_BigSix.php';
        }elseif ($page === 'sicbo') {
            include 'Sicbo.php';
        }elseif ($page === 'wfp') {
            include 'Wild_Five_Card_Poker.php';
        }
        ?>
    </main>

    <!-- ========== 底栏 ========== -->
    <footer class="bottom-bar">
        <div>
            <i class="fas fa-clock"></i> 系统时间：
            <span class="time" id="clockDisplay">--:--:--</span>
        </div>
        <div>
            <button class="refresh-btn" id="refreshPageBtn">
                <i class="fas fa-redo"></i> 刷新当前页
            </button>
        </div>
    </footer>

    <script>
        // ===== 底部时钟（每秒更新） =====
        function updateClock() {
            const now = new Date();
            const h = String(now.getHours()).padStart(2, '0');
            const m = String(now.getMinutes()).padStart(2, '0');
            const s = String(now.getSeconds()).padStart(2, '0');
            document.getElementById('clockDisplay').textContent = h + ':' + m + ':' + s;
        }
        updateClock();
        setInterval(updateClock, 1000);

        // ===== 刷新按钮 =====
        document.getElementById('refreshPageBtn').addEventListener('click', function() {
            location.reload();
        });
        
        console.log('主框架加载完成，当前页面：<?php echo $page; ?>');
    </script>

</body>
</html>