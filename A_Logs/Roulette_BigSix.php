<!-- Big Six 内容页（不含顶部/底部） -->
<div class="roulette-content">
    <!-- 开奖总览 -->
    <div class="dashboard-grid">
        <div class="card">
            <div class="card-header">
                <i class="fas fa-chart-bar"></i>
                <h2>开奖总览</h2>
            </div>
            <div class="stats-grid-bigsix">
                <div class="stat-item">
                    <div class="stat-value" id="bs-total">0</div>
                    <div class="stat-label">总手数</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" style="color:#ff6b6b;" id="bs-1">0</div>
                    <div class="stat-label">1</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" style="color:#4ecdc4;" id="bs-3">0</div>
                    <div class="stat-label">3</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" style="color:#ffd93d;" id="bs-6">0</div>
                    <div class="stat-label">6</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" style="color:#6c5ce7;" id="bs-12">0</div>
                    <div class="stat-label">12</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" style="color:#fd79a8;" id="bs-25">0</div>
                    <div class="stat-label">25</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" style="color:#fdcb6e;" id="bs-crown">0</div>
                    <div class="stat-label">👑</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" style="color:#a29bfe;" id="bs-money">0</div>
                    <div class="stat-label">💵</div>
                </div>
            </div>
        </div>

        <!-- 最热/最冷结果 -->
        <div class="card">
            <div class="card-header">
                <i class="fas fa-fire"></i>
                <h2>过去54局最热 / 最冷结果</h2>
            </div>
            <div class="hotcold-grid">
                <div class="hot-col">
                    <div class="hc-title hot">🔥 最热</div>
                    <div id="bs-hot-numbers" class="hc-list"></div>
                </div>
                <div class="cold-col">
                    <div class="hc-title cold">❄️ 最冷</div>
                    <div id="bs-cold-numbers" class="hc-list"></div>
                </div>
            </div>
        </div>
    </div>

    <!-- 最近开奖记录（网格） -->
    <div class="card" style="margin-bottom:30px;">
        <div class="card-header">
            <i class="fas fa-history"></i>
            <h2>最近开奖记录</h2>
            <span style="margin-left:auto;font-size:0.85rem;color:#6a7f94;">最新54局</span>
        </div>
        <div class="history-grid" id="bs-history-grid">
            <div class="loading-placeholder"><i class="fas fa-spinner fa-pulse"></i> 加载中...</div>
        </div>
    </div>

    <!-- 结果出现次数柱状图（竖向） -->
    <div class="card">
        <div class="card-header">
            <i class="fas fa-chart-bar"></i>
            <h2>结果出现次数</h2>
        </div>
        <div class="bar-chart-wrapper">
            <div class="bar-chart" id="bs-bar-chart">
                <div class="loading-placeholder"><i class="fas fa-spinner fa-pulse"></i> 加载中...</div>
            </div>
        </div>
    </div>
</div>

<style>
    /* 基础样式继承自 Roulette_Europe，额外增加 Big Six 特有样式 */
    .roulette-content .dashboard-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
        gap: 25px;
        margin-bottom: 35px;
    }
    .roulette-content .stats-grid-bigsix {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 12px;
    }
    .roulette-content .stat-item {
        background: rgba(40,55,75,0.5);
        border-radius: 12px;
        padding: 14px 8px;
        text-align: center;
        transition: all 0.25s ease;
    }
    .roulette-content .stat-item:hover {
        background: rgba(50,70,95,0.7);
        transform: scale(1.02);
    }
    .roulette-content .stat-value {
        font-size: 2.2rem;
        font-weight: 700;
        color: #ffcc00;
        text-shadow: 0 0 10px rgba(255,204,0,0.25);
        line-height: 1.2;
    }
    .roulette-content .stat-label {
        font-size: 1rem;
        color: #8da0b3;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-top: 4px;
    }
    .roulette-content .card {
        background: rgba(25,35,50,0.7);
        border-radius: 15px;
        padding: 24px;
        box-shadow: 0 8px 25px rgba(0,0,0,0.5);
        backdrop-filter: blur(5px);
        border: 1px solid rgba(255,255,255,0.07);
        transition: transform 0.25s ease;
    }
    .roulette-content .card:hover {
        transform: translateY(-3px);
    }
    .roulette-content .card-header {
        display: flex;
        align-items: center;
        margin-bottom: 18px;
        padding-bottom: 12px;
        border-bottom: 1px solid rgba(255,255,255,0.08);
    }
    .roulette-content .card-header i {
        font-size: 1.6rem;
        margin-right: 14px;
        color: #ffcc00;
    }
    .roulette-content .card-header h2 {
        font-size: 1.5rem;
        color: #e0e0e0;
        font-weight: 600;
    }

    /* 最热/最冷 */
    .roulette-content .hotcold-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 20px;
    }
    .roulette-content .hot-col, .roulette-content .cold-col {
        background: rgba(0,0,0,0.2);
        border-radius: 12px;
        padding: 16px;
    }
    .roulette-content .hc-title {
        font-size: 1.2rem;
        font-weight: 700;
        text-align: center;
        margin-bottom: 12px;
        letter-spacing: 1px;
    }
    .roulette-content .hc-title.hot { color: #ff6b6b; }
    .roulette-content .hc-title.cold { color: #4ecdc4; }
    .roulette-content .hc-list {
        display: flex;
        flex-direction: column;
        gap: 8px;
    }
    .roulette-content .hc-item {
        display: flex;
        justify-content: space-between;
        padding: 6px 12px;
        background: rgba(40,55,75,0.4);
        border-radius: 8px;
        font-size: 1rem;
    }
    .roulette-content .hc-item .num {
        font-weight: 700;
        color: #e0e0e0;
    }
    .roulette-content .hc-item .count {
        color: #ffcc00;
        font-weight: 600;
    }

    /* 历史网格 */
    .roulette-content .history-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(60px, 1fr));
        gap: 10px;
    }
    .roulette-content .history-item {
        aspect-ratio: 1/1;
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        font-size: 1.2rem;
        transition: all 0.2s;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        cursor: default;
        color: #fff;
    }
    .roulette-content .history-item:hover {
        transform: scale(1.08);
    }
    /* Big Six 专用颜色 */
    .roulette-content .history-item.color-1 { background: #ff6b6b; }
    .roulette-content .history-item.color-3 { background: #4ecdc4; }
    .roulette-content .history-item.color-6 { background: #ffd93d; color: #222; }
    .roulette-content .history-item.color-12 { background: #6c5ce7; }
    .roulette-content .history-item.color-25 { background: #fd79a8; }
    .roulette-content .history-item.color-crown { background: #fdcb6e; color: #222; }
    .roulette-content .history-item.color-money { background: #a29bfe; }

    /* ===== 竖向柱状图 ===== */
    .roulette-content .bar-chart-wrapper {
        overflow-x: auto;
        padding: 20px 0;
    }
    .roulette-content .bar-chart {
        display: flex;
        align-items: flex-end;
        gap: 8px;
        height: 280px;
        min-width: 500px;
        padding: 0 10px;
    }
    .roulette-content .bar-item {
        display: flex;
        flex-direction: column;
        align-items: center;
        flex: 0 0 60px;
        height: 100%;
        justify-content: flex-end;
    }
    .roulette-content .bar-column {
        width: 100%;
        border-radius: 4px 4px 0 0;
        transition: height 0.6s ease;
        min-height: 2px;
        position: relative;
    }
    /* 柱状图颜色对应结果 */
    .roulette-content .bar-column.color-1 { background: #ff6b6b; }
    .roulette-content .bar-column.color-3 { background: #4ecdc4; }
    .roulette-content .bar-column.color-6 { background: #ffd93d; }
    .roulette-content .bar-column.color-12 { background: #6c5ce7; }
    .roulette-content .bar-column.color-25 { background: #fd79a8; }
    .roulette-content .bar-column.color-crown { background: #fdcb6e; }
    .roulette-content .bar-column.color-money { background: #a29bfe; }

    .roulette-content .bar-label {
        font-size: 0.8rem;
        color: #aaa;
        margin-top: 4px;
        text-align: center;
        width: 100%;
    }
    .roulette-content .bar-count {
        font-size: 0.95rem;
        color: #ccc;
        margin-bottom: 2px;
        text-align: center;
        width: 100%;
        opacity: 0.8;
    }

    .roulette-content .loading-placeholder {
        text-align: center;
        padding: 30px 10px;
        color: #8da0b3;
        grid-column: 1 / -1;
    }
    .roulette-content .loading-placeholder i {
        font-size: 2rem;
        display: block;
        margin-bottom: 10px;
    }

    @media (max-width: 768px) {
        .roulette-content .stats-grid-bigsix {
            grid-template-columns: repeat(4, 1fr);
        }
        .roulette-content .hotcold-grid {
            grid-template-columns: 1fr;
        }
        .roulette-content .history-grid {
            grid-template-columns: repeat(auto-fill, minmax(50px,1fr));
        }
        .roulette-content .bar-item {
            flex: 0 0 40px;
        }
        .roulette-content .bar-chart {
            height: 220px;
            gap: 4px;
        }
        .roulette-content .bar-label {
            font-size: 0.7rem;
        }
        .roulette-content .bar-count {
            font-size: 0.7rem;
        }
    }
</style>

<script>
    (function() {
        const DATA_URL = './Json/Big_Six.json';
        let recordData = [];

        // 为每个结果分配固定颜色类
        function getColorClass(result) {
            const map = {
                '1': '1',
                '3': '3',
                '6': '6',
                '12': '12',
                '25': '25',
                '👑': 'crown',
                '💵': 'money'
            };
            return map[result] || '';
        }

        // 渲染总览
        function renderOverview(data) {
            document.getElementById('bs-total').textContent = data.Total || 0;
            document.getElementById('bs-1').textContent = data['1'] || 0;
            document.getElementById('bs-3').textContent = data['3'] || 0;
            document.getElementById('bs-6').textContent = data['6'] || 0;
            document.getElementById('bs-12').textContent = data['12'] || 0;
            document.getElementById('bs-25').textContent = data['25'] || 0;
            document.getElementById('bs-crown').textContent = data['👑'] || 0;
            document.getElementById('bs-money').textContent = data['💵'] || 0;
        }

        // 从记录中计算各结果出现次数
        function computeResultCounts(records) {
            const counts = {};
            for (const rec of records) {
                const r = rec.result;
                counts[r] = (counts[r] || 0) + 1;
            }
            return counts;
        }

        // 渲染最热/最冷（基于记录）
        function renderHotCold(counts) {
            const entries = Object.entries(counts);
            if (entries.length === 0) {
                document.getElementById('bs-hot-numbers').innerHTML = '<div class="hc-item">无数据</div>';
                document.getElementById('bs-cold-numbers').innerHTML = '<div class="hc-item">无数据</div>';
                return;
            }
            entries.sort((a, b) => b[1] - a[1]);
            const hot5 = entries.slice(0, 5);
            const cold5 = entries.slice(-5).reverse();
            const hotHtml = hot5.map(([result, count]) =>
                `<div class="hc-item"><span class="num">${result}</span><span class="count">${count} 次</span></div>`
            ).join('');
            const coldHtml = cold5.map(([result, count]) =>
                `<div class="hc-item"><span class="num">${result}</span><span class="count">${count} 次</span></div>`
            ).join('');
            document.getElementById('bs-hot-numbers').innerHTML = hotHtml;
            document.getElementById('bs-cold-numbers').innerHTML = coldHtml;
        }

        // 渲染历史网格
        function renderHistoryGrid(records) {
            const container = document.getElementById('bs-history-grid');
            container.innerHTML = '';
            if (!records || records.length === 0) {
                container.innerHTML = '<div class="loading-placeholder">暂无数据</div>';
                return;
            }
            // 取最新（倒序，保持最近的在前面）
            const recent = records.slice(-54).reverse();
            for (const rec of recent) {
                const div = document.createElement('div');
                const cls = getColorClass(rec.result);
                div.className = `history-item color-${cls}`;
                div.textContent = rec.result;
                container.appendChild(div);
            }
        }

        // 渲染柱状图（显示所有可能结果，即使计数为0）
        function renderBarChart(counts) {
            const container = document.getElementById('bs-bar-chart');
            container.innerHTML = '';
            const allResults = ['1', '3', '6', '12', '25', '👑', '💵'];
            const maxCount = Math.max(...allResults.map(r => counts[r] || 0), 1);

            for (const result of allResults) {
                const count = counts[result] || 0;
                const pct = (count / maxCount * 100).toFixed(1);
                const cls = getColorClass(result);
                const barItem = document.createElement('div');
                barItem.className = 'bar-item';
                barItem.innerHTML = `
                    <div class="bar-count">${count}</div>
                    <div class="bar-column color-${cls}" style="height:${pct}%;"></div>
                    <div class="bar-label">${result}</div>
                `;
                container.appendChild(barItem);
            }
        }

        // 加载数据
        async function loadData() {
            try {
                const resp = await fetch(DATA_URL);
                if (!resp.ok) throw new Error('HTTP ' + resp.status);
                const data = await resp.json();

                // 提取记录（54_Record）
                const recordObj = data['54_Record'] || {};
                const keys = Object.keys(recordObj).sort((a, b) => {
                    const numA = parseInt(a.replace('_Data', ''));
                    const numB = parseInt(b.replace('_Data', ''));
                    return numA - numB;
                });
                const records = keys.map(k => ({
                    result: recordObj[k].result
                }));
                recordData = records;

                renderOverview(data);
                const counts = computeResultCounts(records);
                renderHotCold(counts);
                renderHistoryGrid(records);
                renderBarChart(counts);

            } catch (err) {
                console.error('加载失败:', err);
                document.getElementById('bs-history-grid').innerHTML =
                    `<div class="loading-placeholder" style="color:#ff6b6b;"><i class="fas fa-exclamation-triangle"></i> 加载失败: ${err.message}</div>`;
                document.getElementById('bs-bar-chart').innerHTML =
                    `<div class="loading-placeholder" style="color:#ff6b6b;"><i class="fas fa-exclamation-triangle"></i> 加载失败</div>`;
            }
        }

        document.addEventListener('DOMContentLoaded', function() {
            loadData();
            setInterval(loadData, 1000);
        });
    })();
</script>