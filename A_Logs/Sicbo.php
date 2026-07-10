<!-- 骰宝内容页（不含顶部/底部） -->
<div class="sicbo-content">
    <!-- 概览 -->
    <div class="dashboard-grid">
        <div class="card">
            <div class="card-header">
                <i class="fas fa-chart-pie"></i>
                <h2>100局概览</h2>
            </div>
            <div class="stats-grid-3">
                <div class="stat-item">
                    <div class="stat-value" id="s-small">0</div>
                    <div class="stat-label">小 (4-10)</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" id="s-big">0</div>
                    <div class="stat-label">大 (11-17)</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" id="s-triple">0</div>
                    <div class="stat-label">★ 围骰</div>
                </div>
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <i class="fas fa-fire"></i>
                <h2>历史累计</h2>
            </div>
            <div class="stats-grid-4">
                <div class="stat-item">
                    <div class="stat-value" id="s-h-small">0</div>
                    <div class="stat-label">小</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" id="s-h-big">0</div>
                    <div class="stat-label">大</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" id="s-h-triple">0</div>
                    <div class="stat-label">围骰</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" id="s-h-total">0</div>
                    <div class="stat-label">总局数</div>
                </div>
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <i class="fas fa-crown"></i>
                <h2>围骰分布</h2>
            </div>
            <div class="triple-grid" id="s-triple-dist">
                <div class="triple-item t1"><i class="fas fa-dice-one dice-icon"></i><div class="stat-value" id="s-t1">0</div><div class="stat-label">1</div></div>
                <div class="triple-item t2"><i class="fas fa-dice-two dice-icon"></i><div class="stat-value" id="s-t2">0</div><div class="stat-label">2</div></div>
                <div class="triple-item t3"><i class="fas fa-dice-three dice-icon"></i><div class="stat-value" id="s-t3">0</div><div class="stat-label">3</div></div>
                <div class="triple-item t4"><i class="fas fa-dice-four dice-icon"></i><div class="stat-value" id="s-t4">0</div><div class="stat-label">4</div></div>
                <div class="triple-item t5"><i class="fas fa-dice-five dice-icon"></i><div class="stat-value" id="s-t5">0</div><div class="stat-label">5</div></div>
                <div class="triple-item t6"><i class="fas fa-dice-six dice-icon"></i><div class="stat-value" id="s-t6">0</div><div class="stat-label">6</div></div>
            </div>
        </div>
    </div>

    <!-- 历史记录 -->
    <div class="card" style="margin-bottom:30px;">
        <div class="card-header">
            <i class="fas fa-history"></i>
            <h2>最近开奖记录</h2>
        </div>
        <div class="history-grid" id="s-history-container">
            <div class="loading-placeholder"><i class="fas fa-spinner fa-pulse"></i> 加载中...</div>
        </div>
    </div>

    <!-- 点数统计 -->
    <div class="point-stats">
        <div class="point-category">
            <h3>小点数 (4-10)</h3>
            <div id="s-points-small"></div>
        </div>
        <div class="point-category">
            <h3>大点数 (11-17)</h3>
            <div id="s-points-big"></div>
        </div>
        <div class="point-category">
            <h3>围骰统计</h3>
            <div id="s-points-triple"></div>
        </div>
    </div>
</div>

<style>
    /* 骰宝专用样式 */
    .sicbo-content .dashboard-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
        gap: 25px;
        margin-bottom: 35px;
    }
    .sicbo-content .stats-grid-3 {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 16px;
    }
    .sicbo-content .stats-grid-4 {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 16px;
    }
    .sicbo-content .stat-item {
        background: rgba(40,55,75,0.5);
        border-radius: 12px;
        padding: 16px 12px;
        text-align: center;
        transition: all 0.25s ease;
    }
    .sicbo-content .stat-item:hover {
        background: rgba(50,70,95,0.7);
        transform: scale(1.02);
    }
    .sicbo-content .stat-value {
        font-size: 2.4rem;
        font-weight: 700;
        color: #ffcc00;
        text-shadow: 0 0 10px rgba(255,204,0,0.25);
        line-height: 1.2;
    }
    .sicbo-content .stat-label {
        font-size: 1rem;
        color: #8da0b3;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-top: 4px;
    }
    .sicbo-content .stat-sub {
        font-size: 0.85rem;
        color: #6a7f94;
        margin-top: 2px;
    }
    .sicbo-content .card {
        background: rgba(25,35,50,0.7);
        border-radius: 15px;
        padding: 24px;
        box-shadow: 0 8px 25px rgba(0,0,0,0.5);
        backdrop-filter: blur(5px);
        border: 1px solid rgba(255,255,255,0.07);
        transition: transform 0.25s ease;
    }
    .sicbo-content .card:hover {
        transform: translateY(-3px);
    }
    .sicbo-content .card-header {
        display: flex;
        align-items: center;
        margin-bottom: 18px;
        padding-bottom: 12px;
        border-bottom: 1px solid rgba(255,255,255,0.08);
    }
    .sicbo-content .card-header i {
        font-size: 1.6rem;
        margin-right: 14px;
        color: #ffcc00;
    }
    .sicbo-content .card-header h2 {
        font-size: 1.5rem;
        color: #e0e0e0;
        font-weight: 600;
    }
    /* 围骰网格 */
    .sicbo-content .triple-grid {
        display: grid;
        grid-template-columns: repeat(6, 1fr);
        gap: 14px;
    }
    .sicbo-content .triple-item {
        background: rgba(40,55,75,0.5);
        border-radius: 12px;
        padding: 14px 8px;
        text-align: center;
        transition: all 0.25s ease;
        border: 2px solid transparent;
    }
    .sicbo-content .triple-item:hover {
        transform: scale(1.05);
        background: rgba(50,70,95,0.7);
    }
    .sicbo-content .triple-item .dice-icon {
        font-size: 1.6rem;
        display: block;
        margin-bottom: 4px;
    }
    .sicbo-content .triple-item .stat-value {
        font-size: 2rem;
    }
    .sicbo-content .triple-item.t1 { border-color: #ff6b6b; }
    .sicbo-content .triple-item.t2 { border-color: #4ecdc4; }
    .sicbo-content .triple-item.t3 { border-color: #ffd166; }
    .sicbo-content .triple-item.t4 { border-color: #6a0572; }
    .sicbo-content .triple-item.t5 { border-color: #1a936f; }
    .sicbo-content .triple-item.t6 { border-color: #118ab2; }

    /* 历史记录网格 */
    .sicbo-content .history-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(72px, 1fr));
        gap: 12px;
    }
    .sicbo-content .history-item {
        background: rgba(40,55,75,0.5);
        border-radius: 10px;
        aspect-ratio: 1/1;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        transition: all 0.25s ease;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        padding: 4px;
    }
    .sicbo-content .history-item:hover {
        transform: translateY(-4px) scale(1.04);
        background: rgba(50,70,95,0.7);
    }
    .sicbo-content .history-item.small-point {
        background: rgba(255,215,0,0.25);
        border: 1px solid #ffd700;
    }
    .sicbo-content .history-item.big-point {
        background: rgba(255,69,0,0.25);
        border: 1px solid #ff4500;
    }
    .sicbo-content .history-item.triple-point {
        background: rgba(50,205,50,0.25);
        border: 1px solid #32cd32;
    }
    .sicbo-content .history-item .dice-value {
        font-size: 1.5rem;
        font-weight: 700;
        color: #fff;
        line-height: 1.2;
    }
    .sicbo-content .history-item .dice-sum {
        font-size: 0.75rem;
        color: #aaa;
        margin-top: 2px;
    }
    .sicbo-content .history-item.small-point .dice-value,
    .sicbo-content .history-item.small-point .dice-sum { color: #ffd700; }
    .sicbo-content .history-item.big-point .dice-value,
    .sicbo-content .history-item.big-point .dice-sum { color: #ff6b6b; }
    .sicbo-content .history-item.triple-point .dice-value,
    .sicbo-content .history-item.triple-point .dice-sum { color: #4ecdc4; }

    /* 点数统计 */
    .sicbo-content .point-stats {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 20px;
        margin-top: 10px;
    }
    .sicbo-content .point-category {
        background: rgba(25,35,50,0.6);
        border-radius: 15px;
        padding: 20px;
        border: 1px solid rgba(255,255,255,0.05);
    }
    .sicbo-content .point-category h3 {
        color: #ffcc00;
        margin-bottom: 14px;
        font-size: 1.2rem;
        padding-bottom: 8px;
        border-bottom: 1px solid rgba(255,255,255,0.06);
    }
    .sicbo-content .point-item {
        display: flex;
        justify-content: space-between;
        padding: 10px 0;
        border-bottom: 1px dashed rgba(255,255,255,0.06);
    }
    .sicbo-content .point-item:last-child {
        border-bottom: none;
    }
    .sicbo-content .point-label {
        color: #c0d0e0;
    }
    .sicbo-content .point-value {
        font-weight: 700;
        color: #ffcc00;
    }

    .sicbo-content .loading-placeholder {
        text-align: center;
        padding: 30px 10px;
        color: #8da0b3;
        grid-column: 1 / -1;
    }
    .sicbo-content .loading-placeholder i {
        font-size: 2rem;
        display: block;
        margin-bottom: 10px;
    }

    @media (max-width: 768px) {
        .sicbo-content .stats-grid-3 { grid-template-columns: 1fr; }
        .sicbo-content .stats-grid-4 { grid-template-columns: repeat(2,1fr); }
        .sicbo-content .triple-grid { grid-template-columns: repeat(3,1fr); }
        .sicbo-content .point-stats { grid-template-columns: 1fr; }
        .sicbo-content .history-grid { grid-template-columns: repeat(auto-fill, minmax(60px,1fr)); }
    }
    @media (max-width: 480px) {
        .sicbo-content .stats-grid-4 { grid-template-columns: 1fr; }
        .sicbo-content .triple-grid { grid-template-columns: repeat(2,1fr); }
        .sicbo-content .history-item .dice-value { font-size: 1.1rem; }
    }
</style>

<script>
    // ===== 骰宝数据加载逻辑 =====
    (function() {
        const SICBO_URL = './Json/Sicbo.json';
        
        // 计算最近最多100局的统计（小、大、围骰）
        function computeRecentStats(records) {
            let small = 0, big = 0, triple = 0;
            const entries = Object.entries(records || {});
            entries.sort((a, b) => parseInt(a[0]) - parseInt(b[0]));
            const recent = entries.slice(-107);

            for (const [key, val] of recent) {
                if (!Array.isArray(val) || val.length < 3) continue;
                const [d1, d2, d3] = val;
                const sum = d1 + d2 + d3;
                if (d1 === d2 && d2 === d3) {
                    triple++;
                } else if (sum >= 4 && sum <= 10) {
                    small++;
                } else if (sum >= 11 && sum <= 17) {
                    big++;
                }
            }
            return { small, big, triple };
        }

        function renderSicboPointStats(data) {
            const smallContainer = document.getElementById('s-points-small');
            let htmlSmall = '';
            for (let i = 4; i <= 10; i++) {
                const val = data['H_' + i] ?? 0;
                htmlSmall += `<div class="point-item"><span class="point-label">${i}点</span><span class="point-value">${val}</span></div>`;
            }
            smallContainer.innerHTML = htmlSmall;

            const bigContainer = document.getElementById('s-points-big');
            let htmlBig = '';
            for (let i = 11; i <= 17; i++) {
                const val = data['H_' + i] ?? 0;
                htmlBig += `<div class="point-item"><span class="point-label">${i}点</span><span class="point-value">${val}</span></div>`;
            }
            bigContainer.innerHTML = htmlBig;

            const tripleContainer = document.getElementById('s-points-triple');
            let htmlTriple = '';
            for (let i = 1; i <= 6; i++) {
                const val = data['H_T' + i] ?? 0;
                htmlTriple += `<div class="point-item"><span class="point-label">围骰 ${i}</span><span class="point-value">${val}</span></div>`;
            }
            tripleContainer.innerHTML = htmlTriple;
        }

        function renderSicboHistory(records) {
            const container = document.getElementById('s-history-container');
            container.innerHTML = '';
            const entries = Object.entries(records || {});
            if (entries.length === 0) {
                container.innerHTML = '<div class="loading-placeholder" style="grid-column:1/-1;">暂无历史数据</div>';
                return;
            }
            entries.sort((a, b) => parseInt(a[0]) - parseInt(b[0]));
            const recent = entries.slice(-105);
            for (const [key, val] of recent) {
                if (!Array.isArray(val) || val.length < 3) continue;
                const [d1, d2, d3] = val;
                const sum = d1 + d2 + d3;
                const isTriple = (d1 === d2 && d2 === d3);
                const item = document.createElement('div');
                item.className = 'history-item';
                if (isTriple) item.classList.add('triple-point');
                else if (sum >= 4 && sum <= 10) item.classList.add('small-point');
                else if (sum >= 11 && sum <= 17) item.classList.add('big-point');
                item.innerHTML = `<div class="dice-value">${d1}${d2}${d3}</div><div class="dice-sum">${sum}点</div>`;
                container.appendChild(item);
            }
        }

        async function loadSicbo() {
            try {
                const resp = await fetch(SICBO_URL);
                if (!resp.ok) throw new Error('HTTP ' + resp.status);
                const data = await resp.json();

                const recentStats = computeRecentStats(data['500_Record'] || {});
                document.getElementById('s-small').textContent = recentStats.small;
                document.getElementById('s-big').textContent = recentStats.big;
                document.getElementById('s-triple').textContent = recentStats.triple;

                document.getElementById('s-h-small').textContent = data.H_Small ?? 0;
                document.getElementById('s-h-big').textContent = data.H_Big ?? 0;
                document.getElementById('s-h-triple').textContent = data.H_Triple ?? 0;
                const total = (data.H_Small || 0) + (data.H_Big || 0) + (data.H_Triple || 0);
                document.getElementById('s-h-total').textContent = total;

                for (let i = 1; i <= 6; i++) {
                    document.getElementById('s-t' + i).textContent = data['H_T' + i] ?? 0;
                }

                renderSicboPointStats(data);
                renderSicboHistory(data['500_Record'] || {});

            } catch (err) {
                console.error('Sicbo load error:', err);
                const container = document.getElementById('s-history-container');
                container.innerHTML =
                    `<div class="error-placeholder" style="grid-column:1/-1;text-align:center;color:#ff6b6b;padding:30px 0;"><i class="fas fa-exclamation-triangle"></i> 加载失败: ${err.message}</div>`;
            }
        }

        document.addEventListener('DOMContentLoaded', function() {
            loadSicbo();
            setInterval(loadSicbo, 1000);
        });
    })();
</script>