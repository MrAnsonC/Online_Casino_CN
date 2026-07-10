<!-- 欧洲轮盘内容页（不含顶部/底部） -->
<div class="roulette-content">
    <!-- 开奖总览（两行两列） -->
    <div class="dashboard-grid">
        <div class="card">
            <div class="card-header">
                <i class="fas fa-chart-bar"></i>
                <h2>开奖总览</h2>
            </div>
            <div class="stats-grid-2x2">
                <!-- 顺序：总手数、绿色、红色、黑色 -->
                <div class="stat-item">
                    <div class="stat-value" id="r-total">0</div>
                    <div class="stat-label">总手数</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value green" id="r-green">0</div>
                    <div class="stat-label">绿色</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value red" id="r-red">0</div>
                    <div class="stat-label">红色</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" style="color:#222;" id="r-black">0</div>
                    <div class="stat-label">黑色</div>
                </div>
            </div>
        </div>

        <!-- 过去2000局数据（三栏：颜色次数 | 最热/最冷 | 分区百分比） -->
        <div class="card">
            <div class="card-header">
                <i class="fas fa-fire"></i>
                <h2>过去2000局数据</h2>
            </div>
            <div class="data-panel">
                <!-- 左栏：颜色出现次数 -->
                <div class="panel-left">
                    <div class="panel-title">颜色统计</div>
                    <div class="color-stats">
                        <div class="color-stat green"><span class="color-label">绿色</span><span class="color-count" id="r-color-green">0</span></div>
                        <div class="color-stat red"><span class="color-label">红色</span><span class="color-count" id="r-color-red">0</span></div>
                        <div class="color-stat black"><span class="color-label">黑色</span><span class="color-count" id="r-color-black">0</span></div>
                    </div>
                </div>

                <!-- 中栏：最热/最冷数字 -->
                <div class="panel-middle">
                    <div class="hotcold-grid">
                        <div class="hot-col">
                            <div class="hc-title hot">🔥 最热</div>
                            <div id="r-hot-numbers" class="hc-list"></div>
                        </div>
                        <div class="cold-col">
                            <div class="hc-title cold">❄️ 最冷</div>
                            <div id="r-cold-numbers" class="hc-list"></div>
                        </div>
                    </div>
                </div>

                <!-- 右栏：分区百分比表格 -->
                <div class="panel-right">
                    <div class="panel-title">分区占比</div>
                    <div class="sector-table">
                        <div class="sector-row"><span class="sector-label">1 – 12</span><span class="sector-value" id="r-sector-1">0%</span></div>
                        <div class="sector-row"><span class="sector-label">13 – 24</span><span class="sector-value" id="r-sector-2">0%</span></div>
                        <div class="sector-row"><span class="sector-label">25 – 36</span><span class="sector-value" id="r-sector-3">0%</span></div>
                        <div class="sector-row"><span class="sector-label">0</span><span class="sector-value" id="r-sector-0">0%</span></div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- 最近开奖记录（网格） -->
    <div class="card" style="margin-bottom:30px;">
        <div class="card-header">
            <i class="fas fa-history"></i>
            <h2>最近开奖记录</h2>
            <span style="margin-left:auto;font-size:0.85rem;color:#6a7f94;">最新100局</span>
        </div>
        <div class="history-grid" id="r-history-grid">
            <div class="loading-placeholder"><i class="fas fa-spinner fa-pulse"></i> 加载中...</div>
        </div>
    </div>

    <!-- 数字出现次数柱状图（竖向） -->
    <div class="card">
        <div class="card-header">
            <i class="fas fa-chart-bar"></i>
            <h2>数字出现次数 (0-36)</h2>
        </div>
        <div class="bar-chart-wrapper">
            <div class="bar-chart" id="r-bar-chart">
                <div class="loading-placeholder"><i class="fas fa-spinner fa-pulse"></i> 加载中...</div>
            </div>
        </div>
    </div>
</div>

<style>
    /* 基础样式（与之前一致） */
    .roulette-content .dashboard-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
        gap: 25px;
        margin-bottom: 35px;
    }

    /* ---- 开奖总览：两行两列 ---- */
    .roulette-content .stats-grid-2x2 {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 16px;
    }
    .roulette-content .stats-grid-2x2 .stat-item {
        background: rgba(40,55,75,0.5);
        border-radius: 12px;
        padding: 16px 12px;
        text-align: center;
        transition: all 0.25s ease;
    }
    .roulette-content .stats-grid-2x2 .stat-item:hover {
        background: rgba(50,70,95,0.7);
        transform: scale(1.02);
    }
    .roulette-content .stat-value {
        font-size: 2.4rem;
        font-weight: 700;
        color: #ffcc00;
        text-shadow: 0 0 10px rgba(255,204,0,0.25);
        line-height: 1.2;
    }
    .roulette-content .stat-value.green {
        color: #4ecdc4;
        text-shadow: 0 0 10px rgba(78,205,196,0.25);
    }
    .roulette-content .stat-value.red {
        color: #ff6b6b;
        text-shadow: 0 0 10px rgba(255,107,107,0.25);
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

    /* ---- 过去2000局数据面板（三栏） ---- */
    .roulette-content .data-panel {
        display: grid;
        grid-template-columns: 1fr 2fr 1fr;
        gap: 20px;
        align-items: stretch;
    }
    .roulette-content .panel-left,
    .roulette-content .panel-right {
        background: rgba(0,0,0,0.2);
        border-radius: 12px;
        padding: 16px;
        display: flex;
        flex-direction: column;
    }
    .roulette-content .panel-middle {
        background: rgba(0,0,0,0.2);
        border-radius: 12px;
        padding: 16px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .roulette-content .panel-title {
        font-size: 1rem;
        font-weight: 600;
        color: #aaa;
        text-align: center;
        margin-bottom: 12px;
        letter-spacing: 1px;
        text-transform: uppercase;
        border-bottom: 1px solid rgba(255,255,255,0.1);
        padding-bottom: 8px;
    }

    /* 左栏：颜色统计 */
    .roulette-content .color-stats {
        display: flex;
        flex-direction: column;
        gap: 12px;
    }
    .roulette-content .color-stat {
        display: flex;
        justify-content: space-between;
        padding: 8px 14px;
        background: rgba(40,55,75,0.4);
        border-radius: 8px;
        font-size: 1rem;
        font-weight: 600;
    }
    .roulette-content .color-stat .color-label {
        color: #e0e0e0;
    }
    .roulette-content .color-stat .color-count {
        color: #ffcc00;
    }
    .roulette-content .color-stat.green .color-label { color: #4ecdc4; }
    .roulette-content .color-stat.red .color-label { color: #ff6b6b; }
    .roulette-content .color-stat.black .color-label { color: #bbb; }

    /* 中栏：最热/最冷（沿用原有样式） */
    .roulette-content .hotcold-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 16px;
    }
    .roulette-content .hot-col, .roulette-content .cold-col {
        background: rgba(0,0,0,0.2);
        border-radius: 12px;
        padding: 12px;
    }
    .roulette-content .hc-title {
        font-size: 1.1rem;
        font-weight: 700;
        text-align: center;
        margin-bottom: 10px;
        letter-spacing: 1px;
    }
    .roulette-content .hc-title.hot { color: #ff6b6b; }
    .roulette-content .hc-title.cold { color: #4ecdc4; }
    .roulette-content .hc-list {
        display: flex;
        flex-direction: column;
        gap: 6px;
    }
    .roulette-content .hc-item {
        display: flex;
        justify-content: space-between;
        padding: 4px 12px;
        background: rgba(40,55,75,0.4);
        border-radius: 6px;
        font-size: 0.95rem;
    }
    .roulette-content .hc-item .num {
        font-weight: 700;
        color: #e0e0e0;
    }
    .roulette-content .hc-item .count {
        color: #ffcc00;
        font-weight: 600;
    }

    /* 右栏：分区百分比表格 */
    .roulette-content .sector-table {
        display: flex;
        flex-direction: column;
        gap: 10px;
        flex: 1;
        justify-content: center;
    }
    .roulette-content .sector-row {
        display: flex;
        justify-content: space-between;
        padding: 8px 14px;
        background: rgba(40,55,75,0.4);
        border-radius: 8px;
        font-size: 1rem;
        font-weight: 600;
    }
    .roulette-content .sector-row .sector-label {
        color: #e0e0e0;
    }
    .roulette-content .sector-row .sector-value {
        color: #ffcc00;
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
    }
    .roulette-content .history-item:hover {
        transform: scale(1.08);
    }
    .roulette-content .history-item.color-red {
        background: #8b0000;
        color: #fff;
        border: 1px solid #ff6b6b;
    }
    .roulette-content .history-item.color-black {
        background: #222;
        color: #fff;
        border: 1px solid #888;
    }
    .roulette-content .history-item.color-green {
        background: #006400;
        color: #fff;
        border: 1px solid #4ecdc4;
    }

    /* 竖向柱状图 */
    .roulette-content .bar-chart-wrapper {
        overflow-x: auto;
        padding: 20px 0;
    }
    .roulette-content .bar-chart {
        display: flex;
        align-items: flex-end;
        gap: 4px;
        height: 280px;
        min-width: 600px;
        padding: 0 10px;
    }
    .roulette-content .bar-item {
        display: flex;
        flex-direction: column;
        align-items: center;
        flex: 0 0 44px;
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
    .roulette-content .bar-column.red { background: #ff6b6b; }
    .roulette-content .bar-column.black { background: #777; }
    .roulette-content .bar-column.green { background: #4ecdc4; }

    .roulette-content .bar-label {
        font-size: 0.7rem;
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
        .roulette-content .stats-grid-2x2 {
            grid-template-columns: 1fr 1fr;
        }
        .roulette-content .data-panel {
            grid-template-columns: 1fr;
            gap: 16px;
        }
        .roulette-content .hotcold-grid {
            grid-template-columns: 1fr 1fr;
        }
        .roulette-content .history-grid {
            grid-template-columns: repeat(auto-fill, minmax(50px,1fr));
        }
        .roulette-content .bar-item {
            flex: 0 0 22px;
        }
        .roulette-content .bar-chart {
            height: 220px;
            gap: 3px;
        }
        .roulette-content .bar-label {
            font-size: 0.6rem;
        }
        .roulette-content .bar-count {
            font-size: 0.55rem;
        }
    }
</style>

<script>
    (function() {
        const DATA_URL = './Json/Roulette_Europe.json';
        let record2Data = [];

        function getColorClass(color) {
            if (color === 'Red') return 'red';
            if (color === 'Black') return 'black';
            if (color === 'Green') return 'green';
            return '';
        }

        // 颜色映射（用于统计）
        function getColorName(color) {
            if (color === 'Red') return 'red';
            if (color === 'Black') return 'black';
            if (color === 'Green') return 'green';
            return '';
        }

        // 计算颜色计数
        function computeColorCounts(records) {
            let red = 0, black = 0, green = 0;
            for (const rec of records) {
                const c = rec.color;
                if (c === 'Red') red++;
                else if (c === 'Black') black++;
                else if (c === 'Green') green++;
            }
            return { red, black, green };
        }

        // 计算分区计数 (1-12, 13-24, 25-36, 0)
        function computeSectorCounts(records) {
            let s1=0, s2=0, s3=0, s0=0;
            for (const rec of records) {
                const num = parseInt(rec.result, 10);
                if (num === 0) s0++;
                else if (num >= 1 && num <= 12) s1++;
                else if (num >= 13 && num <= 24) s2++;
                else if (num >= 25 && num <= 36) s3++;
            }
            return { s1, s2, s3, s0 };
        }

        function renderOverview(data) {
            document.getElementById('r-total').textContent = data.Total || 0;
            document.getElementById('r-red').textContent = data.Red || 0;
            document.getElementById('r-black').textContent = data.Black || 0;
            document.getElementById('r-green').textContent = data.Green || 0;
        }

        function computeNumberCounts(records) {
            const counts = {};
            for (const rec of records) {
                const num = rec.result;
                counts[num] = (counts[num] || 0) + 1;
            }
            return counts;
        }

        function renderHotCold(counts) {
            const entries = Object.entries(counts);
            if (entries.length === 0) {
                document.getElementById('r-hot-numbers').innerHTML = '<div class="hc-item">无数据</div>';
                document.getElementById('r-cold-numbers').innerHTML = '<div class="hc-item">无数据</div>';
                return;
            }
            entries.sort((a, b) => b[1] - a[1]);
            const hot5 = entries.slice(0, 5);
            const cold5 = entries.slice(-5).reverse();
            const hotHtml = hot5.map(([num, count]) =>
                `<div class="hc-item"><span class="num">${num}</span><span class="count">${count} 次</span></div>`
            ).join('');
            const coldHtml = cold5.map(([num, count]) =>
                `<div class="hc-item"><span class="num">${num}</span><span class="count">${count} 次</span></div>`
            ).join('');
            document.getElementById('r-hot-numbers').innerHTML = hotHtml;
            document.getElementById('r-cold-numbers').innerHTML = coldHtml;
        }

        function renderHistoryGrid(records) {
            const container = document.getElementById('r-history-grid');
            container.innerHTML = '';
            if (!records || records.length === 0) {
                container.innerHTML = '<div class="loading-placeholder">暂无数据</div>';
                return;
            }
            const recent = records.slice(-100).reverse();
            for (const rec of recent) {
                const div = document.createElement('div');
                div.className = `history-item color-${getColorClass(rec.color)}`;
                div.textContent = rec.result;
                container.appendChild(div);
            }
        }

        // 更新颜色统计（左栏）
        function renderColorStats(colorCounts) {
            document.getElementById('r-color-green').textContent = colorCounts.green;
            document.getElementById('r-color-red').textContent = colorCounts.red;
            document.getElementById('r-color-black').textContent = colorCounts.black;
        }

        // 更新分区百分比（右栏）
        function renderSectorStats(sectorCounts, total) {
            if (total === 0) {
                document.getElementById('r-sector-1').textContent = '0%';
                document.getElementById('r-sector-2').textContent = '0%';
                document.getElementById('r-sector-3').textContent = '0%';
                document.getElementById('r-sector-0').textContent = '0%';
                return;
            }
            const pct = (count) => ((count / total) * 100).toFixed(1) + '%';
            document.getElementById('r-sector-1').textContent = pct(sectorCounts.s1);
            document.getElementById('r-sector-2').textContent = pct(sectorCounts.s2);
            document.getElementById('r-sector-3').textContent = pct(sectorCounts.s3);
            document.getElementById('r-sector-0').textContent = pct(sectorCounts.s0);
        }

        function renderBarChart(counts) {
            const container = document.getElementById('r-bar-chart');
            container.innerHTML = '';
            const numbers = [];
            for (let i = 0; i <= 36; i++) {
                const key = String(i);
                numbers.push({ num: key, count: counts[key] || 0 });
            }
            const maxCount = Math.max(...numbers.map(n => n.count), 1);
            const redNumbers = [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36];
            const blackNumbers = [2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35];
            const greenNumbers = ['0'];

            for (const item of numbers) {
                const num = item.num;
                let color = 'black';
                if (redNumbers.includes(Number(num))) color = 'red';
                else if (blackNumbers.includes(Number(num))) color = 'black';
                else if (greenNumbers.includes(num)) color = 'green';

                const pct = (item.count / maxCount * 100).toFixed(1);
                const barItem = document.createElement('div');
                barItem.className = 'bar-item';
                barItem.innerHTML = `
                    <div class="bar-count">${item.count}</div>
                    <div class="bar-column ${color}" style="height:${pct}%;"></div>
                    <div class="bar-label">${num}</div>
                `;
                container.appendChild(barItem);
            }
        }

        async function loadData() {
            try {
                const resp = await fetch(DATA_URL);
                if (!resp.ok) throw new Error('HTTP ' + resp.status);
                const data = await resp.json();

                const record2 = data.Record2 || {};
                const keys = Object.keys(record2).sort((a,b) => {
                    const numA = parseInt(a.replace('_Data',''));
                    const numB = parseInt(b.replace('_Data',''));
                    return numA - numB;
                });
                const records = keys.map(k => ({
                    result: record2[k].result,
                    color: record2[k].color
                }));
                record2Data = records;

                renderOverview(data);
                const counts = computeNumberCounts(records);
                renderHotCold(counts);
                renderHistoryGrid(records);
                renderBarChart(counts);

                // 新增渲染：颜色统计 & 分区百分比
                const colorCounts = computeColorCounts(records);
                renderColorStats(colorCounts);

                const sectorCounts = computeSectorCounts(records);
                const total = records.length;
                renderSectorStats(sectorCounts, total);

            } catch (err) {
                console.error('加载失败:', err);
                document.getElementById('r-history-grid').innerHTML =
                    `<div class="loading-placeholder" style="color:#ff6b6b;"><i class="fas fa-exclamation-triangle"></i> 加载失败: ${err.message}</div>`;
                document.getElementById('r-bar-chart').innerHTML =
                    `<div class="loading-placeholder" style="color:#ff6b6b;"><i class="fas fa-exclamation-triangle"></i> 加载失败</div>`;
            }
        }

        document.addEventListener('DOMContentLoaded', function() {
            loadData();
            setInterval(loadData, 1000);
        });
    })();
</script>