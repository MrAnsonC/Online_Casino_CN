<!-- In Or Out 内容页（融合 UTH 表格 + Roulette 统计卡片） -->
<div class="io-content">
    <!-- 总览卡片（三列） -->
    <div class="dashboard-grid">
        <div class="card">
            <div class="card-header">
                <i class="fas fa-chart-bar"></i>
                <h2>开奖总览</h2>
            </div>
            <div class="stats-grid-3">
                <div class="stat-item">
                    <div class="stat-value" id="io-total">0</div>
                    <div class="stat-label">总手数</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value green" id="io-in-count">0</div>
                    <div class="stat-label">In 赢</div>
                    <div class="stat-sub" id="io-in-pct">0%</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value red" id="io-out-count">0</div>
                    <div class="stat-label">Out 赢</div>
                    <div class="stat-sub" id="io-out-pct">0%</div>
                </div>
            </div>
        </div>

        <!-- 位置区间分布卡片（10个区间） -->
        <div class="card">
            <div class="card-header">
                <i class="fas fa-th"></i>
                <h2>位置区间分布</h2>
            </div>
            <div class="sector-grid" id="io-sector-grid">
                <!-- 由 JS 动态生成 -->
            </div>
        </div>
    </div>

    <!-- 对局记录表格（含分页） -->
    <div class="card" style="margin-bottom:30px;">
        <div class="card-header">
            <i class="fas fa-list-ul"></i>
            <h2>对局记录</h2>
            <div style="margin-left:auto;display:flex;gap:10px;">
                <button class="page-btn active" data-page="latest" id="pageLatest">最新25局</button>
                <button class="page-btn" data-page="oldest" id="pageOldest">最旧25局</button>
            </div>
        </div>
        <div class="io-table-wrap">
            <table class="io-table" id="io-history-table">
                <thead>
                    <tr>
                        <th>局号</th>
                        <th>时间</th>
                        <th>目标牌</th>
                        <th>最终牌</th>
                        <th>位置</th>
                        <th>结果</th>
                    </tr>
                </thead>
                <tbody id="io-history-body">
                    <tr><td colspan="6" style="text-align:center;color:#8da0b3;padding:30px 0;"><i class="fas fa-spinner fa-pulse"></i> 加载中...</td></tr>
                </tbody>
            </table>
        </div>
    </div>

    <!-- 棒形图 -->
    <div class="card">
        <div class="card-header">
            <i class="fas fa-chart-bar"></i>
            <h2>目标牌 In/Out 次数</h2>
        </div>
        <div class="bar-chart-wrapper">
            <div class="bar-chart" id="io-bar-chart">
                <div class="loading-placeholder"><i class="fas fa-spinner fa-pulse"></i> 加载中...</div>
            </div>
        </div>
    </div>

    <!-- ===== 模态框（对局详情） ===== -->
    <div class="modal-overlay" id="detailModal">
        <div class="modal-content">
            <div class="modal-header">
                <h2><i class="fas fa-cards"></i> 对局详情</h2>
                <button class="modal-close" id="modalCloseBtn">&times;</button>
            </div>
            <div class="modal-body">
                <div class="detail-layout">
                    <!-- 左列 -->
                    <div class="detail-left">
                        <div class="hand-section">
                            <div class="hand-label">目标牌</div>
                            <div class="hand-cards" id="detail-target">—</div>
                        </div>
                        <div class="hand-section">
                            <div class="hand-label">最终牌</div>
                            <div class="hand-cards" id="detail-final">—</div>
                        </div>
                        <div class="hand-section">
                            <span class="footer-label">最终位置</span>
                            <span class="footer-value" id="detail-position">—</span>
                        </div>
                        <div class="hand-section">
                            <span class="footer-label">时间</span>
                            <span class="footer-value" id="detail-time">—</span>
                        </div>
                        <div class="hand-section">
                            <span class="footer-label">结果</span>
                            <span class="footer-value" id="detail-result">—</span>
                        </div>
                    </div>
                    <!-- 右列：局号 & 切牌位置 + 牌堆顺序 -->
                    <div class="detail-right">
                        <div class="detail-meta-row">
                            <div class="meta-item">
                                <span class="meta-label">局号</span>
                                <span class="meta-value" id="detail-index">—</span>
                            </div>
                            <div class="meta-item">
                                <span class="meta-label">切牌位置</span>
                                <span class="meta-value" id="detail-cut">—</span>
                            </div>
                        </div>
                        <div class="deck-section">
                            <div class="deck-label">牌堆顺序 (52张)</div>
                            <div class="deck-cards" id="detail-deck-cards"></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<style>
    /* ===== 全局 ===== */
    .io-content .dashboard-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
        gap: 25px;
        margin-bottom: 35px;
    }
    .io-content .card {
        background: rgba(25,35,50,0.7);
        border-radius: 15px;
        padding: 24px;
        box-shadow: 0 8px 25px rgba(0,0,0,0.5);
        backdrop-filter: blur(5px);
        border: 1px solid rgba(255,255,255,0.07);
        transition: transform 0.25s ease;
    }
    .io-content .card:hover {
        transform: translateY(-3px);
    }
    .io-content .card-header {
        display: flex;
        align-items: center;
        margin-bottom: 18px;
        padding-bottom: 12px;
        border-bottom: 1px solid rgba(255,255,255,0.08);
    }
    .io-content .card-header i {
        font-size: 1.6rem;
        margin-right: 14px;
        color: #ffcc00;
    }
    .io-content .card-header h2 {
        font-size: 1.5rem;
        color: #e0e0e0;
        font-weight: 600;
    }

    /* ---- 总览三列 ---- */
    .io-content .stats-grid-3 {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 16px;
    }
    .io-content .stats-grid-3 .stat-item {
        background: rgba(40,55,75,0.5);
        border-radius: 12px;
        padding: 16px 12px;
        text-align: center;
        transition: all 0.25s ease;
    }
    .io-content .stats-grid-3 .stat-item:hover {
        background: rgba(50,70,95,0.7);
        transform: scale(1.02);
    }
    .io-content .stat-value {
        font-size: 2.4rem;
        font-weight: 700;
        color: #ffcc00;
        text-shadow: 0 0 10px rgba(255,204,0,0.25);
        line-height: 1.2;
    }
    .io-content .stat-value.green {
        color: #4ecdc4;
        text-shadow: 0 0 10px rgba(78,205,196,0.25);
    }
    .io-content .stat-value.red {
        color: #ff6b6b;
        text-shadow: 0 0 10px rgba(255,107,107,0.25);
    }
    .io-content .stat-label {
        font-size: 1rem;
        color: #8da0b3;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-top: 4px;
    }
    .io-content .stat-sub {
        font-size: 0.85rem;
        color: #6a7f94;
        margin-top: 2px;
    }

    /* ---- 区间分布（10个，每行5个） ---- */
    .io-content .sector-grid {
        display: grid;
        grid-template-columns: repeat(5, 1fr);
        gap: 10px;
    }
    .io-content .sector-item {
        background: rgba(40,55,75,0.4);
        border-radius: 10px;
        padding: 10px 8px;
        text-align: center;
        transition: 0.2s;
    }
    .io-content .sector-item:hover {
        background: rgba(50,70,95,0.6);
        transform: scale(1.02);
    }
    .io-content .sector-item .sector-range {
        font-size: 0.9rem;
        color: #aaa;
        font-weight: 600;
    }
    .io-content .sector-item .sector-count {
        font-size: 1.6rem;
        font-weight: 700;
        color: #ffcc00;
        margin: 4px 0;
    }
    .io-content .sector-item .sector-pct {
        font-size: 0.85rem;
        color: #6a7f94;
    }

    /* ---- 表格 ---- */
    .io-content .io-table-wrap {
        overflow-x: auto;
        margin-top: 6px;
    }
    .io-content .io-table {
        table-layout: fixed;
        width: 100%;
    }
    .io-content .io-table th:nth-child(1),
    .io-content .io-table td:nth-child(1) { width: 12%; }
    .io-content .io-table th:nth-child(2),
    .io-content .io-table td:nth-child(2) { width: 18%; }
    .io-content .io-table th:nth-child(3),
    .io-content .io-table td:nth-child(3) { width: 15%; text-align: center; }
    .io-content .io-table th:nth-child(4),
    .io-content .io-table td:nth-child(4) { width: 15%; text-align: center; }
    .io-content .io-table th:nth-child(5),
    .io-content .io-table td:nth-child(5) { width: 12%; text-align: center; }
    .io-content .io-table th:nth-child(6),
    .io-content .io-table td:nth-child(6) { width: 13%; text-align: center; }

    .io-content .io-table th,
    .io-content .io-table td {
        padding: 10px 8px;
        word-break: break-word;
    }
    .io-content .io-table th {
        background: rgba(40,55,75,0.6);
        color: #8da0b3;
        padding: 12px 10px;
        text-align: center;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        border-bottom: 2px solid rgba(255,255,255,0.06);
    }
    .io-content .io-table td {
        padding: 10px 10px;
        border-bottom: 1px solid rgba(255,255,255,0.04);
        color: #d0d8e0;
        vertical-align: middle;
        cursor: pointer;
        transition: background 0.15s;
    }
    .io-content .io-table tr:hover td {
        background: rgba(255,204,0,0.06);
    }
    .io-content .cards-mini {
        font-family: 'Segoe UI', monospace;
        font-weight: 600;
        letter-spacing: 0.5px;
        font-size: 0.85rem;
    }
    .io-content .io-result-badge {
        display: inline-block;
        padding: 2px 14px;
        border-radius: 50px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .io-content .io-result-badge.in {
        background: rgba(78,205,196,0.25);
        color: #4ecdc4;
    }
    .io-content .io-result-badge.out {
        background: rgba(255,107,107,0.25);
        color: #ff6b6b;
    }

    /* 分页按钮 */
    .page-btn {
        background: rgba(40,55,75,0.5);
        border: 1px solid rgba(255,255,255,0.1);
        color: #8da0b3;
        padding: 6px 16px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s;
        font-family: inherit;
    }
    .page-btn:hover {
        background: rgba(255,204,0,0.15);
        color: #ffcc00;
        border-color: #ffcc00;
    }
    .page-btn.active {
        background: #ffcc00;
        color: #0d1520;
        border-color: #ffcc00;
    }

    /* ---- 棒形图 ---- */
    .io-content .bar-chart-wrapper {
        overflow-x: auto;
        padding: 20px 0;
    }
    .io-content .bar-chart {
        display: flex;
        align-items: flex-end;
        gap: 6px;
        height: 280px;
        min-width: 800px;
        padding: 0 10px;
    }
    .io-content .bar-group {
        display: flex;
        flex-direction: column;
        align-items: center;
        flex: 0 0 70px;
        height: 100%;
        justify-content: flex-end;
    }
    .io-content .bar-pair {
        display: flex;
        gap: 3px;
        align-items: flex-end;
        height: 100%;
    }
    .io-content .bar-column {
        width: 50px;
        border-radius: 4px 4px 0 0;
        transition: height 0.6s ease;
        min-height: 2px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: flex-end;
    }
    .io-content .bar-column.in {
        background: #4ecdc4;
    }
    .io-content .bar-column.out {
        background: #ff6b6b;
    }
    .io-content .bar-count {
        font-size: 1.5rem;
        color: #000000;
        margin-bottom: 20px;
        white-space: nowrap;
    }
    .io-content .bar-label {
        font-size: 2.7rem;
        color: #ffffff;
        margin-top: 4px;
        text-align: center;
        width: 100%;
        font-weight: 600;
    }
    .io-content .loading-placeholder {
        text-align: center;
        padding: 20px 20px;
        color: #8da0b3;
        grid-column: 1 / -1;
    }
    .io-content .loading-placeholder i {
        font-size: 2rem;
        display: block;
        margin-bottom: 10px;
    }

    /* ---- 模态框（修复显示问题） ---- */
    .modal-overlay {
        display: none !important; /* 默认隐藏 */
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0,0,0,0.7);
        backdrop-filter: blur(6px);
        z-index: 1000;
        justify-content: center;
        align-items: center;
        padding: 20px;
        box-sizing: border-box;
    }
    .modal-overlay.active {
        display: flex !important; /* 显示时强制 flex */
    }
    .modal-content {
        background: rgba(20,30,45,0.98);
        border-radius: 24px;
        max-width: 900px;
        width: 100%;
        max-height: 90vh;
        overflow-y: auto;
        box-shadow: 0 20px 60px rgba(0,0,0,0.8);
        border: 1px solid rgba(255,255,255,0.08);
        animation: modalFade 0.3s ease;
    }
    @keyframes modalFade {
        from { opacity: 0; transform: scale(0.95) translateY(10px); }
        to { opacity: 1; transform: scale(1) translateY(0); }
    }
    .modal-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 20px 28px;
        border-bottom: 1px solid rgba(255,255,255,0.08);
    }
    .modal-header h2 {
        font-size: 1.6rem;
        color: #ffcc00;
        margin: 0;
    }
    .modal-header h2 i {
        margin-right: 12px;
    }
    .modal-close {
        background: none;
        border: none;
        color: #8da0b3;
        font-size: 2.2rem;
        cursor: pointer;
        transition: color 0.2s;
        line-height: 1;
    }
    .modal-close:hover {
        color: #ff6b6b;
    }
    .modal-body {
        padding: 28px;
    }
    .detail-layout {
        display: flex;
        gap: 30px;
        flex-wrap: wrap;
    }
    .detail-left {
        flex: 2;
        min-width: 240px;
    }
    .detail-right {
        flex: 1.5;
        min-width: 200px;
        background: rgba(0,0,0,0.2);
        border-radius: 16px;
        padding: 20px;
        align-self: flex-start;
    }
    .hand-section {
        margin-bottom: 20px;
    }
    .hand-section:last-child {
        margin-bottom: 0;
    }
    .hand-label {
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: #8da0b3;
        margin-bottom: 6px;
        font-weight: 600;
    }
    .hand-cards {
        font-size: 1.4rem;
        font-weight: 700;
        color: #e0e0e0;
        background: rgba(0,0,0,0.25);
        padding: 12px 16px;
        border-radius: 12px;
        min-height: 50px;
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 6px;
        word-break: break-all;
    }
    .hand-cards .card-suit {
        display: inline-block;
    }
    .hand-cards .suit-heart, .hand-cards .suit-diamond {
        color: #ff6b6b;
    }
    .hand-cards .suit-spade, .hand-cards .suit-club {
        color: #ccc;
    }

    .detail-meta-row {
        display: flex;
        gap: 20px;
        margin-bottom: 18px;
        flex-wrap: wrap;
    }
    .meta-item {
        display: flex;
        flex-direction: column;
        gap: 4px;
    }
    .meta-label {
        font-size: 0.8rem;
        text-transform: uppercase;
        color: #6a7f94;
        letter-spacing: 0.5px;
    }
    .meta-value {
        font-size: 1.2rem;
        font-weight: 700;
        color: #ffcc00;
        background: rgba(0,0,0,0.2);
        padding: 6px 12px;
        border-radius: 8px;
        display: inline-block;
    }
    .deck-section {
        margin-top: 6px;
    }
    .deck-label {
        font-size: 0.8rem;
        text-transform: uppercase;
        color: #6a7f94;
        letter-spacing: 0.5px;
        margin-bottom: 8px;
    }
    .deck-cards {
        display: flex;
        flex-wrap: wrap;
        gap: 5px;
        padding: 8px 6px;
        background: rgba(0,0,0,0.15);
        border-radius: 10px;
        align-content: flex-start;
        max-height: none;
        overflow-y: visible;
    }
    .deck-card {
        width: 36px;
        height: 22px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        background: rgba(40,55,75,0.6);
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: 600;
        font-family: 'Segoe UI', monospace;
        border: 1px solid rgba(255,255,255,0.06);
        transition: all 0.15s;
        box-sizing: border-box;
        flex-shrink: 0;
    }
    .deck-card.color-yellow {
        background: #ffcc00;
        color: #0d1520;
        border-color: #ffcc00;
        text-shadow: none;
    }
    .deck-card.color-green {
        background: #007900;
        color: #ffffff;
        border-color: #00ff00;
        text-shadow: none;
    }
    .deck-card.color-red {
        background: #ff0000;
        color: #ffffff;
        border-color: #ff0000;
        text-shadow: none;
    }
    .deck-card .suit-heart,
    .deck-card .suit-diamond {
        color: inherit;
    }
    .deck-card .suit-spade,
    .deck-card .suit-club {
        color: inherit;
    }

    .footer-label {
        font-size: 0.8rem;
        text-transform: uppercase;
        color: #6a7f94;
        letter-spacing: 0.5px;
    }
    .footer-value {
        font-size: 1.1rem;
        font-weight: 600;
        color: #e0e0e0;
    }
    .footer-value .highlight-in {
        color: #4ecdc4;
    }
    .footer-value .highlight-out {
        color: #ff6b6b;
    }

    /* 响应式 */
    @media (max-width: 768px) {
        .io-content .dashboard-grid {
            grid-template-columns: 1fr;
        }
        .io-content .stats-grid-3 {
            grid-template-columns: 1fr 1fr;
        }
        .io-content .sector-grid {
            grid-template-columns: repeat(3, 1fr);
        }
        .io-content .detail-layout {
            flex-direction: column;
        }
        .io-content .detail-right {
            width: 100%;
        }
        .io-content .io-table {
            font-size: 0.78rem;
        }
        .io-content .io-table th,
        .io-content .io-table td {
            padding: 6px 6px;
        }
        .modal-content {
            max-width: 100%;
            margin: 10px;
        }
        .modal-body {
            padding: 20px;
        }
        .hand-cards {
            font-size: 1.1rem;
            padding: 10px 12px;
        }
        .deck-card {
            width: 28px;
            height: 36px;
            font-size: 0.65rem;
        }
        .deck-cards {
            gap: 3px;
            padding: 6px 4px;
        }
        .page-btn {
            font-size: 0.75rem;
            padding: 4px 10px;
        }
        .bar-group {
            flex: 0 0 24px;
        }
        .bar-column {
            width: 10px;
        }
        .bar-chart {
            height: 200px;
            min-width: 600px;
        }
    }
    @media (max-width: 480px) {
        .io-content .stats-grid-3 {
            grid-template-columns: 1fr;
        }
        .io-content .sector-grid {
            grid-template-columns: repeat(2, 1fr);
        }
        .bar-group {
            flex: 0 0 20px;
        }
        .bar-column {
            width: 8px;
        }
        .bar-chart {
            min-width: 400px;
        }
        .deck-card {
            width: 24px;
            height: 32px;
            font-size: 0.55rem;
        }
        .deck-cards {
            gap: 2px;
            padding: 4px 3px;
        }
    }
</style>

<script>
    (function() {
        const DATA_URL = './Json/In_Or_Out.json';
        let allRecords = [];
        let currentView = 'latest';
        const PAGE_SIZE = 25;

        // ---- 工具 ----
        function formatCard(cardStr) {
            if (!cardStr) return '—';
            return cardStr;
        }

        function getSectorIndex(pos) {
            if (pos === undefined || pos === null) return -1;
            if (pos >= 1 && pos <= 5) return 0;
            if (pos >= 6 && pos <= 10) return 1;
            if (pos >= 11 && pos <= 15) return 2;
            if (pos >= 16 && pos <= 20) return 3;
            if (pos >= 21 && pos <= 25) return 4;
            if (pos >= 26 && pos <= 30) return 5;
            if (pos >= 31 && pos <= 35) return 6;
            if (pos >= 36 && pos <= 40) return 7;
            if (pos >= 41 && pos <= 45) return 8;
            if (pos >= 46 && pos <= 49) return 9;
            return -1;
        }
        function getSectorLabel(idx) {
            const ranges = ['1-5','6-10','11-15','16-20','21-25','26-30','31-35','36-40','41-45','46-49'];
            return ranges[idx] || '';
        }

        // 判断 In/Out：位置为单数 → In，双数 → Out
        function getResult(game) {
            const pos = game.final_card?.number_of_it_position;
            if (pos === undefined || pos === null) return '—';
            return (pos % 2 === 1) ? 'In' : 'Out';
        }

        // ---- 渲染统计 ----
        function renderOverview(historyRecord) {
            if (!historyRecord) return;
            const total = historyRecord.game || 0;
            const inWins = historyRecord.inner_win || 0;
            const outWins = historyRecord.outer_win || 0;
            const inPct = total > 0 ? (inWins / total * 100) : 0;
            const outPct = total > 0 ? (outWins / total * 100) : 0;

            document.getElementById('io-total').textContent = total;
            document.getElementById('io-in-count').textContent = inWins;
            document.getElementById('io-out-count').textContent = outWins;
            document.getElementById('io-in-pct').textContent = inPct.toFixed(1) + '%';
            document.getElementById('io-out-pct').textContent = outPct.toFixed(1) + '%';
        }

        function renderSectors(positionObj) {
            const container = document.getElementById('io-sector-grid');
            container.innerHTML = '';
            if (!positionObj) {
                container.innerHTML = '<div class="loading-placeholder">无数据</div>';
                return;
            }
            const total = Object.values(positionObj).reduce((a,b) => a + b, 0) || 1;
            const sectorCounts = new Array(10).fill(0);
            for (const [posStr, count] of Object.entries(positionObj)) {
                const pos = parseInt(posStr, 10);
                const idx = getSectorIndex(pos);
                if (idx >= 0) sectorCounts[idx] += count;
            }
            for (let i = 0; i < 10; i++) {
                const count = sectorCounts[i];
                const pct = (count / total * 100).toFixed(1);
                const div = document.createElement('div');
                div.className = 'sector-item';
                div.innerHTML = `
                    <div class="sector-range">${getSectorLabel(i)}</div>
                    <div class="sector-count">${count}</div>
                    <div class="sector-pct">${pct}%</div>
                `;
                container.appendChild(div);
            }
        }

        // ---- 表格渲染 ----
        function renderTable() {
            const tbody = document.getElementById('io-history-body');
            if (!allRecords || allRecords.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#8da0b3;padding:30px 0;">暂无对局数据</td></tr>';
                return;
            }
            let displayRecords = [];
            if (currentView === 'latest') {
                const total = allRecords.length;
                const take = Math.min(PAGE_SIZE, total);
                displayRecords = allRecords.slice(total - take).reverse();
            } else {
                const take = Math.min(PAGE_SIZE, allRecords.length);
                displayRecords = allRecords.slice(0, take);
            }

            let html = '';
            for (const game of displayRecords) {
                const realIndex = allRecords.indexOf(game);
                const result = getResult(game);
                const time = game.timestamp ? game.timestamp.replace('T', ' ').slice(0, 19) : '—';
                const target = formatCard(game.target_card);
                const finalCard = formatCard(game.final_card?.card_name);
                const pos = game.final_card?.number_of_it_position ?? '—';

                const badge = result === 'In' ? '<span class="io-result-badge in">In</span>' :
                               result === 'Out' ? '<span class="io-result-badge out">Out</span>' : '—';

                html += `<tr data-index="${realIndex}">
                    <td>${game.game_id || '—'}</td>
                    <td style="font-size:0.8rem;color:#8da0b3;">${time}</td>
                    <td class="cards-mini">${target}</td>
                    <td class="cards-mini">${finalCard}</td>
                    <td>${pos}</td>
                    <td>${badge}</td>
                </tr>`;
            }
            tbody.innerHTML = html;

            // 绑定点击事件（带调试日志）
            document.querySelectorAll('#io-history-body tr').forEach(row => {
                row.addEventListener('click', function() {
                    const idx = parseInt(this.dataset.index);
                    console.log('点击行，索引:', idx);
                    if (!isNaN(idx) && allRecords[idx]) {
                        openDetailModal(allRecords[idx]);
                    } else {
                        console.warn('无效索引或数据不存在');
                    }
                });
            });
        }

        // ---- 棒形图 ----
        function renderBarChart(chanceObj) {
            const container = document.getElementById('io-bar-chart');
            container.innerHTML = '';
            if (!chanceObj) {
                container.innerHTML = '<div class="loading-placeholder">无数据</div>';
                return;
            }
            const order = ['2','3','4','5','6','7','8','9','10','J','Q','K','A'];
            let maxVal = 1;
            const data = {};
            for (const rank of order) {
                const entry = chanceObj[rank] || { In: 0, Out: 0 };
                data[rank] = entry;
                if (entry.In > maxVal) maxVal = entry.In;
                if (entry.Out > maxVal) maxVal = entry.Out;
            }
            if (maxVal === 0) maxVal = 1;

            for (const rank of order) {
                const entry = data[rank] || { In: 0, Out: 0 };
                const inH = (entry.In / maxVal * 100).toFixed(1);
                const outH = (entry.Out / maxVal * 100).toFixed(1);

                const group = document.createElement('div');
                group.className = 'bar-group';
                const pair = document.createElement('div');
                pair.className = 'bar-pair';

                const inBar = document.createElement('div');
                inBar.className = 'bar-column in';
                inBar.style.height = inH + '%';
                inBar.innerHTML = `<div class="bar-count">${entry.In}</div>`;
                pair.appendChild(inBar);

                const outBar = document.createElement('div');
                outBar.className = 'bar-column out';
                outBar.style.height = outH + '%';
                outBar.innerHTML = `<div class="bar-count">${entry.Out}</div>`;
                pair.appendChild(outBar);

                group.appendChild(pair);
                const label = document.createElement('div');
                label.className = 'bar-label';
                label.textContent = rank;
                group.appendChild(label);
                container.appendChild(group);
            }
        }

        // ---- 模态框 ----
        function openDetailModal(game) {
            console.log('打开模态框，数据:', game);
            try {
                // 左列
                document.getElementById('detail-target').textContent = formatCard(game.target_card) || '—';
                const finalCard = formatCard(game.final_card?.card_name);
                const pos = game.final_card?.number_of_it_position ?? '—';
                document.getElementById('detail-final').textContent = finalCard + ' (位置 ' + pos + ')';
                document.getElementById('detail-position').textContent = pos;
                const time = game.timestamp ? game.timestamp.replace('T', ' ').slice(0, 19) : '—';
                document.getElementById('detail-time').textContent = time;

                const result = getResult(game);
                const resultText = result === 'In' ? '<span class="highlight-in">In</span>' :
                                   result === 'Out' ? '<span class="highlight-out">Out</span>' : '—';
                document.getElementById('detail-result').innerHTML = resultText;

                // 右列
                document.getElementById('detail-index').textContent = game.game_id || '—';
                document.getElementById('detail-cut').textContent = game.cut_position ?? '—';

                // 牌堆
                const deckContainer = document.getElementById('detail-deck-cards');
                deckContainer.innerHTML = '';
                if (game.deck_order && Array.isArray(game.deck_order)) {
                    const total = game.deck_order.length;
                    const cutPos = game.cut_position;
                    let finalIdx = -1;
                    const finalCardName = game.final_card?.card_name;
                    if (finalCardName) {
                        finalIdx = game.deck_order.indexOf(finalCardName);
                    }
                    let finalOffset = -1;
                    if (finalIdx !== -1 && cutPos !== undefined && cutPos !== null) {
                        finalOffset = (finalIdx - cutPos + total) % total;
                    }

                    game.deck_order.forEach((card, idx) => {
                        const span = document.createElement('span');
                        span.className = 'deck-card';
                        let offset = -1;
                        if (cutPos !== undefined && cutPos !== null) {
                            offset = (idx - cutPos + total) % total;
                        }

                        if (idx === finalIdx) {
                            span.classList.add('color-green');
                        } else if (offset === 0) {
                            span.classList.add('color-yellow');
                        } else if (offset > 0 && finalOffset !== -1 && offset < finalOffset) {
                            span.classList.add('color-red');
                        }

                        let suitClass = '';
                        if (card.includes('♥')) suitClass = 'suit-heart';
                        else if (card.includes('♦')) suitClass = 'suit-diamond';
                        else if (card.includes('♠')) suitClass = 'suit-spade';
                        else if (card.includes('♣')) suitClass = 'suit-club';
                        span.innerHTML = `<span class="${suitClass}">${card}</span>`;
                        deckContainer.appendChild(span);
                    });
                } else {
                    deckContainer.innerHTML = '<span style="color:#6a7f94;">无牌堆数据</span>';
                }

                // 显示模态框
                const modal = document.getElementById('detailModal');
                modal.classList.add('active');
                console.log('模态框已打开');
            } catch (e) {
                console.error('打开模态框时出错:', e);
                alert('打开详情失败，请查看控制台错误信息。');
            }
        }

        function closeDetailModal() {
            document.getElementById('detailModal').classList.remove('active');
        }

        // ---- 加载数据 ----
        async function loadData() {
            try {
                const resp = await fetch(DATA_URL);
                if (!resp.ok) throw new Error('HTTP ' + resp.status);
                const data = await resp.json();

                allRecords = data.history || [];

                if (data.history_record) {
                    renderOverview(data.history_record);
                    renderSectors(data.history_record.position);
                    renderBarChart(data.history_record.chance_in_or_out);
                } else {
                    document.getElementById('io-sector-grid').innerHTML = '<div class="loading-placeholder">无统计记录</div>';
                    document.getElementById('io-bar-chart').innerHTML = '<div class="loading-placeholder">无统计记录</div>';
                }

                renderTable();

                document.querySelectorAll('.page-btn').forEach(btn => {
                    btn.classList.toggle('active', btn.dataset.page === currentView);
                });

            } catch (err) {
                console.error('加载失败:', err);
                document.getElementById('io-history-body').innerHTML =
                    `<tr><td colspan="6" style="text-align:center;color:#ff6b6b;padding:30px 0;"><i class="fas fa-exclamation-triangle"></i> 加载失败: ${err.message}</td></tr>`;
            }
        }

        // ---- 事件绑定 ----
        document.addEventListener('DOMContentLoaded', function() {
            loadData();

            document.getElementById('pageLatest').addEventListener('click', function() {
                if (currentView === 'latest') return;
                currentView = 'latest';
                renderTable();
                document.querySelectorAll('.page-btn').forEach(btn => {
                    btn.classList.toggle('active', btn.dataset.page === 'latest');
                });
            });
            document.getElementById('pageOldest').addEventListener('click', function() {
                if (currentView === 'oldest') return;
                currentView = 'oldest';
                renderTable();
                document.querySelectorAll('.page-btn').forEach(btn => {
                    btn.classList.toggle('active', btn.dataset.page === 'oldest');
                });
            });

            document.getElementById('modalCloseBtn').addEventListener('click', closeDetailModal);
            document.getElementById('detailModal').addEventListener('click', function(e) {
                if (e.target === this) closeDetailModal();
            });
            document.addEventListener('keydown', function(e) {
                if (e.key === 'Escape') closeDetailModal();
            });

            // 每秒自动刷新（可根据需要调整）
            setInterval(loadData, 1000);
        });
    })();
</script>