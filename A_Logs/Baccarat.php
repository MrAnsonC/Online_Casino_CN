<!-- 百家乐内容页（不含顶部/底部） -->
<div class="baccarat-content">
    <div class="dashboard-grid">
        <!-- 卡片：结果累计 -->
        <div class="card">
            <div class="card-header">
                <i class="fas fa-chart-bar"></i>
                <h2>结果累计</h2>
            </div>
            <div class="stats-grid-3">
                <div class="stat-item player">
                    <div class="stat-value" id="b-player">0</div>
                    <div class="stat-label">玩家 (Player)</div>
                </div>
                <div class="stat-item tie">
                    <div class="stat-value" id="b-tie">0</div>
                    <div class="stat-label">和 (Tie)</div>
                </div>
                <div class="stat-item banker">
                    <div class="stat-value" id="b-banker">0</div>
                    <div class="stat-label">庄家 (Banker)</div>
                </div>
            </div>
        </div>

        <!-- 卡片：最长连统计 -->
        <div class="card">
            <div class="card-header">
                <i class="fas fa-flag-checkered"></i>
                <h2>最长连统计</h2>
            </div>
            <div class="stats-grid-3">
                <div class="stat-item">
                    <div class="stat-value" id="b-lplayer">0</div>
                    <div class="stat-label">玩家连</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" id="b-ltie">0</div>
                    <div class="stat-label">和连</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" id="b-lbanker">0</div>
                    <div class="stat-label">庄家连</div>
                </div>
            </div>
        </div>
    </div>

    <!-- 数据说明（可选） -->
    <div class="card" style="margin-bottom:20px;">
        <div class="card-header">
            <i class="fas fa-info-circle"></i>
            <h2>数据说明</h2>
        </div>
        <p style="color:#b0c4d8; padding:10px 0;">
            累计结果为历史总计数，最长连表示该结果连续出现的最大次数。
        </p>
    </div>
</div>

<style>
    /* ===== 百家乐专用样式 ===== */
    .baccarat-content .dashboard-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
        gap: 25px;
        margin-bottom: 35px;
    }
    .baccarat-content .stats-grid-3 {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 16px;
    }
    .baccarat-content .stat-item {
        background: rgba(40,55,75,0.5);
        border-radius: 12px;
        padding: 16px 12px;
        text-align: center;
        transition: all 0.25s ease;
    }
    .baccarat-content .stat-item:hover {
        background: rgba(50,70,95,0.7);
        transform: scale(1.02);
    }
    .baccarat-content .stat-value {
        font-size: 2.4rem;
        font-weight: 700;
        color: #ffcc00;
        text-shadow: 0 0 10px rgba(255,204,0,0.25);
        line-height: 1.2;
    }
    .baccarat-content .stat-label {
        font-size: 1rem;
        color: #8da0b3;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-top: 4px;
    }
    .baccarat-content .card {
        background: rgba(25,35,50,0.7);
        border-radius: 15px;
        padding: 24px;
        box-shadow: 0 8px 25px rgba(0,0,0,0.5);
        backdrop-filter: blur(5px);
        border: 1px solid rgba(255,255,255,0.07);
        transition: transform 0.25s ease;
    }
    .baccarat-content .card:hover {
        transform: translateY(-3px);
    }
    .baccarat-content .card-header {
        display: flex;
        align-items: center;
        margin-bottom: 18px;
        padding-bottom: 12px;
        border-bottom: 1px solid rgba(255,255,255,0.08);
    }
    .baccarat-content .card-header i {
        font-size: 1.6rem;
        margin-right: 14px;
        color: #ffcc00;
    }
    .baccarat-content .card-header h2 {
        font-size: 1.5rem;
        color: #e0e0e0;
        font-weight: 600;
    }

    /* 个性化颜色（可选） */
    .baccarat-content .stat-item.player .stat-value { color: #4ecdc4; }
    .baccarat-content .stat-item.tie .stat-value { color: #ffd166; }
    .baccarat-content .stat-item.banker .stat-value { color: #ff6b6b; }

    @media (max-width: 768px) {
        .baccarat-content .stats-grid-3 {
            grid-template-columns: 1fr;
        }
        .baccarat-content .dashboard-grid {
            grid-template-columns: 1fr;
        }
    }
    @media (max-width: 480px) {
        .baccarat-content .stat-value {
            font-size: 1.8rem;
        }
    }
</style>

<script>
    (function() {
        // 注意：文件名与给定 JSON 一致（Baccarant.json）
        const BACCARAT_URL = './Json/Baccarant.json';

        async function loadBaccarat() {
            try {
                const resp = await fetch(BACCARAT_URL);
                if (!resp.ok) throw new Error('HTTP ' + resp.status);
                const data = await resp.json();

                // 更新累计结果
                document.getElementById('b-player').textContent = data.Player ?? 0;
                document.getElementById('b-tie').textContent = data.Tie ?? 0;
                document.getElementById('b-banker').textContent = data.Banker ?? 0;

                // 更新最长连
                document.getElementById('b-lplayer').textContent = data.L_Player ?? 0;
                document.getElementById('b-ltie').textContent = data.L_Tie ?? 0;
                document.getElementById('b-lbanker').textContent = data.L_Banker ?? 0;

            } catch (err) {
                console.error('Baccarat load error:', err);
                // 可简单显示错误信息（这里不破坏界面）
            }
        }

        document.addEventListener('DOMContentLoaded', function() {
            loadBaccarat();
            setInterval(loadBaccarat, 1000); // 每秒刷新
        });
    })();
</script>