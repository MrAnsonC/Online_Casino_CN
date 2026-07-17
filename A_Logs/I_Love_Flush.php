<!-- Casino_War.php - 基于 Caribbean_Stud_Poker 修改 -->
<div class="cw-content">
    <!-- 对局总览 + 结果分布 -->
    <div class="dashboard-grid">
        <div class="card">
            <div class="card-header">
                <i class="fas fa-chart-bar"></i>
                <h2>对局总览</h2>
            </div>
            <div class="stats-grid-2">
                <div class="stat-item">
                    <div class="stat-value" id="cw-total">0</div>
                    <div class="stat-label">总手数</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value green" id="cw-winrate">0%</div>
                    <div class="stat-label">玩家胜率</div>
                </div>
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <i class="fas fa-flag-checkered"></i>
                <h2>结果分布</h2>
            </div>
            <div class="stats-grid-4">
                <div class="stat-item">
                    <div class="stat-value green" id="cw-player-wins">0</div>
                    <div class="stat-label">玩家胜</div>
                    <div class="stat-sub" id="cw-player-pct">0%</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value red" id="cw-dealer-wins">0</div>
                    <div class="stat-label">庄家胜</div>
                    <div class="stat-sub" id="cw-dealer-pct">0%</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" style="color:#ffd700;" id="cw-pushes">0</div>
                    <div class="stat-label">平局</div>
                    <div class="stat-sub" id="cw-push-pct">0%</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" style="color:#aaa;" id="cw-folds">0</div>
                    <div class="stat-label">弃牌</div>
                    <div class="stat-sub" id="cw-fold-pct">0%</div>
                </div>
            </div>
        </div>
    </div>

    <!-- 对局记录 -->
    <div class="card" style="margin-bottom:30px;">
        <div class="card-header">
            <i class="fas fa-list-ul"></i>
            <h2>对局记录</h2>
            <div style="margin-left:auto;display:flex;gap:10px;">
                <button class="page-btn active" data-page="latest" id="cwPageLatest">最新25局</button>
                <button class="page-btn" data-page="oldest" id="cwPageOldest">最旧25局</button>
            </div>
        </div>
        <div class="cw-table-wrap">
            <table class="cw-table" id="cw-history-table">
                <thead>
                    <tr>
                        <th>#</th>
                        <th>时间</th>
                        <th>玩家牌</th>
                        <th>庄家牌</th>
                        <th>结果</th>
                        <th>赢钱</th>
                    </tr>
                </thead>
                <tbody id="cw-history-body">
                    <tr><td colspan="6" style="text-align:center;color:#8da0b3;padding:30px 0;"><i class="fas fa-spinner fa-pulse"></i> 加载中...</td></tr>
                </tbody>
            </table>
        </div>
    </div>

    <!-- 模态框 -->
    <div class="modal-overlay" id="cwDetailModal">
        <div class="modal-content">
            <div class="modal-header">
                <h2><i class="fas fa-cards"></i> 对局详情</h2>
                <button class="modal-close" id="cwModalCloseBtn">&times;</button>
            </div>
            <div class="modal-body">
                <div class="detail-layout">
                    <div class="detail-left">
                        <div class="hand-section">
                            <div class="hand-label">庄家手牌</div>
                            <div class="hand-cards" id="cw-detail-dealer">—</div>
                        </div>
                        <div class="hand-section">
                            <div class="hand-label">玩家手牌</div>
                            <div class="hand-cards" id="cw-detail-player">—</div>
                        </div>
                        <div class="hand-section">
                            <span class="footer-label">时间</span>
                            <span class="footer-value" id="cw-detail-time">—</span>
                        </div>
                        <div class="hand-section">
                            <span class="footer-label">结果</span>
                            <span class="footer-value" id="cw-detail-result">—</span>
                        </div>
                    </div>
                    <div class="detail-right">
                        <div class="detail-meta-row">
                            <div class="meta-item">
                                <span class="meta-label">局号</span>
                                <span class="meta-value" id="cw-detail-index">—</span>
                            </div>
                            <div class="meta-item">
                                <span class="meta-label">切牌位置</span>
                                <span class="meta-value" id="cw-detail-cut">—</span>
                            </div>
                        </div>
                        <div class="deck-section">
                            <div class="deck-label">牌堆顺序 (52张)</div>
                            <div class="deck-cards" id="cw-detail-deck"></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<style>
    .cw-content .dashboard-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
        gap: 25px;
        margin-bottom: 35px;
    }
    .cw-content .stats-grid-2 {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 20px;
    }
    .cw-content .stats-grid-4 {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 16px;
    }
    .cw-content .stat-item {
        background: rgba(40,55,75,0.5);
        border-radius: 12px;
        padding: 16px 12px;
        text-align: center;
        transition: all 0.25s ease;
    }
    .cw-content .stat-item:hover {
        background: rgba(50,70,95,0.7);
        transform: scale(1.02);
    }
    .cw-content .stat-value {
        font-size: 2.4rem;
        font-weight: 700;
        color: #ffcc00;
        text-shadow: 0 0 10px rgba(255,204,0,0.25);
        line-height: 1.2;
    }
    .cw-content .stat-value.green {
        color: #4ecdc4;
        text-shadow: 0 0 10px rgba(78,205,196,0.25);
    }
    .cw-content .stat-value.red {
        color: #ff6b6b;
        text-shadow: 0 0 10px rgba(255,107,107,0.25);
    }
    .cw-content .stat-label {
        font-size: 1rem;
        color: #8da0b3;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-top: 4px;
    }
    .cw-content .stat-sub {
        font-size: 0.85rem;
        color: #6a7f94;
        margin-top: 2px;
    }
    .cw-content .card {
        background: rgba(25,35,50,0.7);
        border-radius: 15px;
        padding: 24px;
        box-shadow: 0 8px 25px rgba(0,0,0,0.5);
        backdrop-filter: blur(5px);
        border: 1px solid rgba(255,255,255,0.07);
        transition: transform 0.25s ease;
    }
    .cw-content .card:hover {
        transform: translateY(-3px);
    }
    .cw-content .card-header {
        display: flex;
        align-items: center;
        margin-bottom: 18px;
        padding-bottom: 12px;
        border-bottom: 1px solid rgba(255,255,255,0.08);
    }
    .cw-content .card-header i {
        font-size: 1.6rem;
        margin-right: 14px;
        color: #ffcc00;
    }
    .cw-content .card-header h2 {
        font-size: 1.5rem;
        color: #e0e0e0;
        font-weight: 600;
    }
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
    .cw-content .cw-table-wrap {
        overflow-x: auto;
        margin-top: 6px;
    }
    .cw-content .cw-table {
        table-layout: fixed;
        width: 100%;
    }
    .cw-content .cw-table th:nth-child(1),
    .cw-content .cw-table td:nth-child(1) { width: 6%; }
    .cw-content .cw-table th:nth-child(2),
    .cw-content .cw-table td:nth-child(2) { width: 18%; }
    .cw-content .cw-table th:nth-child(3),
    .cw-content .cw-table td:nth-child(3) { width: 22%; text-align: left; }
    .cw-content .cw-table th:nth-child(4),
    .cw-content .cw-table td:nth-child(4) { width: 22%; text-align: left; }
    .cw-content .cw-table th:nth-child(5),
    .cw-content .cw-table td:nth-child(5) { width: 16%; text-align: center; }
    .cw-content .cw-table th:nth-child(6),
    .cw-content .cw-table td:nth-child(6) { width: 16%; text-align: center; }

    .cw-content .cw-table th,
    .cw-content .cw-table td {
        padding: 10px 8px;
        word-break: break-word;
    }
    .cw-content .cw-table th {
        background: rgba(40,55,75,0.6);
        color: #8da0b3;
        padding: 12px 10px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        border-bottom: 2px solid rgba(255,255,255,0.06);
    }
    .cw-content .cw-table td {
        padding: 10px 10px;
        border-bottom: 1px solid rgba(255,255,255,0.04);
        color: #d0d8e0;
        vertical-align: middle;
        cursor: pointer;
        transition: background 0.15s;
    }
    .cw-content .cw-table tr:hover td {
        background: rgba(255,204,0,0.06);
    }
    .cw-content .cards-mini {
        font-family: 'Segoe UI', monospace;
        font-weight: 600;
        letter-spacing: 0.5px;
        font-size: 0.85rem;
    }
    /* 高亮最左边花色的牌 */
    .cw-content .cards-mini .highlight-suit,
    .cw-content .hand-cards .highlight-suit {
        background-color: rgba(255, 204, 0, 0.25);
        border-radius: 4px;
        padding: 0 4px;
        border: 1px solid #ffcc00;
        font-weight: 700;
    }
    .cw-content .winnings-positive {
        color: #4ecdc4;
        font-weight: 700;
    }
    .cw-content .winnings-negative {
        color: #ff6b6b;
        font-weight: 700;
    }
    .cw-content .winnings-zero {
        color: #8da0b3;
    }
    .cw-content .cw-result-badge {
        display: inline-block;
        padding: 2px 14px;
        border-radius: 50px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .cw-content .cw-result-badge.win {
        background: rgba(78,205,196,0.25);
        color: #4ecdc4;
    }
    .cw-content .cw-result-badge.lose {
        background: rgba(255,107,107,0.25);
        color: #ff6b6b;
    }
    .cw-content .cw-result-badge.push {
        background: rgba(255,215,0,0.2);
        color: #ffd700;
    }
    .cw-content .cw-result-badge.fold {
        background: rgba(150,150,150,0.2);
        color: #aaa;
    }

    /* 模态框通用样式 */
    .modal-overlay {
        display: none;
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
    }
    .modal-overlay.active {
        display: flex;
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
    .detail-meta-row .meta-item {
        flex: 1;
        min-width: 80px;
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
    .deck-cards::-webkit-scrollbar {
        display: none;
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
    .footer-value .highlight-win {
        color: #4ecdc4;
    }
    .footer-value .highlight-lose {
        color: #ff6b6b;
    }
    .footer-value .highlight-push {
        color: #ffd700;
    }

    @media (max-width: 768px) {
        .cw-content .dashboard-grid {
            grid-template-columns: 1fr;
        }
        .cw-content .stats-grid-4 {
            grid-template-columns: repeat(2, 1fr);
        }
        .cw-content .detail-layout {
            flex-direction: column;
        }
        .cw-content .detail-right {
            width: 100%;
        }
        .cw-content .cw-table {
            font-size: 0.78rem;
        }
        .cw-content .cw-table th,
        .cw-content .cw-table td {
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
        .detail-meta-row {
            flex-direction: row;
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
    }
    @media (max-width: 480px) {
        .cw-content .stats-grid-4 {
            grid-template-columns: 1fr 1fr;
        }
        .cw-content .stats-grid-2 {
            grid-template-columns: 1fr;
        }
        .detail-meta-row {
            flex-direction: column;
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
        const CW_URL = './Json/I_Love_Flush.json';
        let allRecords = [];
        let currentView = 'latest';
        const PAGE_SIZE = 25;

        function parseCard(cardStr) {
            if (!cardStr) return '?';
            return cardStr;
        }

        // 增加 highlightFirstSuit 参数
        function formatCards(arr, asHtml = false, highlightFirstSuit = false) {
            if (!arr || !Array.isArray(arr)) return '—';
            let firstSuit = null;
            if (highlightFirstSuit && arr.length > 0) {
                let firstCard = parseCard(arr[0]);
                firstSuit = firstCard.slice(-1); // 假设花色符号在末尾
            }
            if (!asHtml) {
                return arr.map(c => parseCard(c)).join(' ');
            }
            return arr.map(c => {
                let card = parseCard(c);
                let suitClass = '';
                if (card.includes('♥')) suitClass = 'suit-heart';
                else if (card.includes('♦')) suitClass = 'suit-diamond';
                else if (card.includes('♠')) suitClass = 'suit-spade';
                else if (card.includes('♣')) suitClass = 'suit-club';
                // 检查是否与第一个花色相同
                let highlightClass = '';
                if (highlightFirstSuit && firstSuit !== null && card.slice(-1) === firstSuit) {
                    highlightClass = ' highlight-suit';
                }
                return `<span class="card-suit ${suitClass}${highlightClass}">${card}</span>`;
            }).join(' ');
        }

        function formatWinnings(val) {
            if (val === undefined || val === null) return '—';
            const num = Number(val);
            if (num === 0) return '<span class="winnings-zero">$0</span>';
            if (num > 0) return `<span class="winnings-positive">+$${num.toFixed(0)}</span>`;
            return `<span class="winnings-negative">-$${Math.abs(num).toFixed(0)}</span>`;
        }

        function getResultBadge(winner, isFold) {
            if (winner === 'fold' || isFold) return '<span class="cw-result-badge fold">弃牌</span>';
            if (winner === 'player') return '<span class="cw-result-badge win">玩家赢</span>';
            if (winner === 'dealer') return '<span class="cw-result-badge lose">庄家赢</span>';
            if (winner === 'push') return '<span class="cw-result-badge push">平局</span>';
            return '<span class="cw-result-badge fold">—</span>';
        }

        function renderCwTable() {
            const tbody = document.getElementById('cw-history-body');
            if (!allRecords || allRecords.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#8da0b3;padding:30px 0;">暂无对局数据</td></tr>';
                return;
            }

            let displayRecords = [];
            if (currentView === 'latest') {
                const total = allRecords.length;
                const take = Math.min(PAGE_SIZE, total);
                const sliceStart = total - take;
                displayRecords = allRecords.slice(sliceStart).reverse();
            } else {
                const take = Math.min(PAGE_SIZE, allRecords.length);
                displayRecords = allRecords.slice(0, take);
            }

            let html = '';
            if (currentView === 'latest') {
                let idx = allRecords.length;
                for (const game of displayRecords) {
                    const realIndex = allRecords.indexOf(game);
                    const isFold = game.fold === true;
                    const winner = game.result?.winner || '';
                    const winnings = game.result?.winnings ?? 0;
                    const time = game.timestamp ? game.timestamp.replace('T', ' ').slice(0, 19) : '—';
                    // 高亮最左边花色
                    const playerCards = formatCards(game.player_cards, true, true);
                    const dealerCards = formatCards(game.dealer_cards, true, true);
                    const badge = getResultBadge(winner, isFold);
                    const winHtml = formatWinnings(winnings);
                    html += `<tr data-index="${realIndex}">
                        <td>${game.game_id || '—'}</td>
                        <td style="font-size:0.8rem;color:#8da0b3;">${time}</td>
                        <td class="cards-mini">${playerCards}</td>
                        <td class="cards-mini">${dealerCards}</td>
                        <td>${badge}</td>
                        <td>${winHtml}</td>
                    </tr>`;
                    idx--;
                }
            } else {
                let idx = 1;
                for (const game of displayRecords) {
                    const realIndex = allRecords.indexOf(game);
                    const isFold = game.fold === true;
                    const winner = game.result?.winner || '';
                    const winnings = game.result?.winnings ?? 0;
                    const time = game.timestamp ? game.timestamp.replace('T', ' ').slice(0, 19) : '—';
                    const playerCards = formatCards(game.player_cards, true, true);
                    const dealerCards = formatCards(game.dealer_cards, true, true);
                    const badge = getResultBadge(winner, isFold);
                    const winHtml = formatWinnings(winnings);
                    html += `<tr data-index="${realIndex}">
                        <td>${game.game_id || '—'}</td>
                        <td style="font-size:0.8rem;color:#8da0b3;">${time}</td>
                        <td class="cards-mini">${playerCards}</td>
                        <td class="cards-mini">${dealerCards}</td>
                        <td>${badge}</td>
                        <td>${winHtml}</td>
                    </tr>`;
                    idx++;
                }
            }

            tbody.innerHTML = html;

            document.querySelectorAll('#cw-history-body tr').forEach(row => {
                row.addEventListener('click', function() {
                    const idx = parseInt(this.dataset.index);
                    if (!isNaN(idx) && allRecords[idx]) {
                        openCwDetailModal(allRecords[idx], idx);
                    }
                });
            });
        }

        function updateStats(historyRecord) {
            if (!historyRecord) return;
            const total = historyRecord.game || 0;
            const playerWins = historyRecord.player_win || 0;
            const dealerWins = historyRecord.dealer_win || 0;
            const pushes = historyRecord.push || 0;
            const folds = historyRecord.fold || 0;

            const winRate = total > 0 ? (playerWins / total * 100) : 0;
            const playerPct = total > 0 ? (playerWins / total * 100) : 0;
            const dealerPct = total > 0 ? (dealerWins / total * 100) : 0;
            const pushPct = total > 0 ? (pushes / total * 100) : 0;
            const foldPct = total > 0 ? (folds / total * 100) : 0;

            document.getElementById('cw-total').textContent = total;
            document.getElementById('cw-winrate').textContent = winRate.toFixed(1) + '%';
            document.getElementById('cw-player-wins').textContent = playerWins;
            document.getElementById('cw-dealer-wins').textContent = dealerWins;
            document.getElementById('cw-pushes').textContent = pushes;
            document.getElementById('cw-folds').textContent = folds;
            document.getElementById('cw-player-pct').textContent = playerPct.toFixed(1) + '%';
            document.getElementById('cw-dealer-pct').textContent = dealerPct.toFixed(1) + '%';
            document.getElementById('cw-push-pct').textContent = pushPct.toFixed(1) + '%';
            document.getElementById('cw-fold-pct').textContent = foldPct.toFixed(1) + '%';
        }

        async function loadCw() {
            try {
                const resp = await fetch(CW_URL);
                if (!resp.ok) throw new Error('HTTP ' + resp.status);
                const data = await resp.json();

                if (!data.history || !Array.isArray(data.history)) {
                    throw new Error('数据格式错误：缺少 history 数组');
                }
                allRecords = data.history;

                if (data.history_record) {
                    updateStats(data.history_record);
                }

                renderCwTable();

                document.querySelectorAll('.page-btn').forEach(btn => {
                    btn.classList.toggle('active', btn.dataset.page === currentView);
                });

            } catch (err) {
                console.error('CW load error:', err);
                document.getElementById('cw-history-body').innerHTML =
                    `<tr><td colspan="6" style="text-align:center;color:#ff6b6b;padding:30px 0;"><i class="fas fa-exclamation-triangle"></i> 加载失败: ${err.message}</td></tr>`;
            }
        }

        function openCwDetailModal(game, index) {
            // 高亮最左边花色
            document.getElementById('cw-detail-dealer').innerHTML = formatCards(game.dealer_cards, true, true) || '—';
            document.getElementById('cw-detail-player').innerHTML = formatCards(game.player_cards, true, true) || '—';

            document.getElementById('cw-detail-index').textContent = (index + 1);
            document.getElementById('cw-detail-cut').textContent = game.cut_position ?? '—';

            const deckContainer = document.getElementById('cw-detail-deck');
            deckContainer.innerHTML = '';
            if (game.deck_order && Array.isArray(game.deck_order)) {
                const cutPos = game.cut_position;
                const total = game.deck_order.length;
                game.deck_order.forEach((card, idx) => {
                    const span = document.createElement('span');
                    span.className = 'deck-card';
                    let offset = (idx - cutPos + total) % total;
                    if (offset >= 0 && offset <= 6) {
                        span.classList.add('color-green');
                    } else if (offset >= 7 && offset <= 13) {
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

            const time = game.timestamp ? game.timestamp.replace('T', ' ').slice(0, 19) : '—';
            document.getElementById('cw-detail-time').textContent = time;

            const isFold = game.fold === true;
            const winner = game.result?.winner || '';
            const winnings = game.result?.winnings ?? 0;
            let resultText = '';
            if (winner === 'fold' || isFold) {
                resultText = '弃牌';
            } else if (winner === 'player') {
                resultText = `<span class="highlight-win">玩家赢 (赢 $${winnings.toFixed(0)})</span>`;
            } else if (winner === 'dealer') {
                resultText = `<span class="highlight-lose">庄家赢</span>`;
            } else if (winner === 'push') {
                resultText = `<span class="highlight-push">平局 (赢 $${winnings.toFixed(0)})</span>`;
            } else {
                resultText = '—';
            }
            document.getElementById('cw-detail-result').innerHTML = resultText;

            document.getElementById('cwDetailModal').classList.add('active');
        }

        function closeCwDetailModal() {
            document.getElementById('cwDetailModal').classList.remove('active');
        }

        document.addEventListener('DOMContentLoaded', function() {
            loadCw();

            document.getElementById('cwPageLatest').addEventListener('click', function() {
                if (currentView === 'latest') return;
                currentView = 'latest';
                renderCwTable();
                document.querySelectorAll('.page-btn').forEach(btn => {
                    btn.classList.toggle('active', btn.dataset.page === 'latest');
                });
            });
            document.getElementById('cwPageOldest').addEventListener('click', function() {
                if (currentView === 'oldest') return;
                currentView = 'oldest';
                renderCwTable();
                document.querySelectorAll('.page-btn').forEach(btn => {
                    btn.classList.toggle('active', btn.dataset.page === 'oldest');
                });
            });

            document.getElementById('cwModalCloseBtn').addEventListener('click', closeCwDetailModal);
            document.getElementById('cwDetailModal').addEventListener('click', function(e) {
                if (e.target === this) closeCwDetailModal();
            });
            document.addEventListener('keydown', function(e) {
                if (e.key === 'Escape') closeCwDetailModal();
            });

            setInterval(loadCw, 1000);
        });
    })();
</script>