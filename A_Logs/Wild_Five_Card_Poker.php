<!-- Wild Five Card Poker 内容页（不含顶部/底部） -->
<div class="wfp-content">
    <!-- 对局总览 + 结果分布 -->
    <div class="dashboard-grid">
        <div class="card">
            <div class="card-header">
                <i class="fas fa-chart-bar"></i>
                <h2>Wild Five Card Poker 对局总览</h2>
            </div>
            <div class="stats-grid-2">
                <div class="stat-item">
                    <div class="stat-value" id="wfp-total">0</div>
                    <div class="stat-label">总手数</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value green" id="wfp-winrate">0%</div>
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
                    <div class="stat-value green" id="wfp-player-wins">0</div>
                    <div class="stat-label">玩家胜</div>
                    <div class="stat-sub" id="wfp-player-pct">0%</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value red" id="wfp-dealer-wins">0</div>
                    <div class="stat-label">庄家胜</div>
                    <div class="stat-sub" id="wfp-dealer-pct">0%</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" style="color:#ffd700;" id="wfp-pushes">0</div>
                    <div class="stat-label">平局</div>
                    <div class="stat-sub" id="wfp-push-pct">0%</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" style="color:#aaa;" id="wfp-folds">0</div>
                    <div class="stat-label">弃牌</div>
                    <div class="stat-sub" id="wfp-fold-pct">0%</div>
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
                <button class="page-btn active" data-page="latest" id="wfpPageLatest">最新25局</button>
                <button class="page-btn" data-page="oldest" id="wfpPageOldest">最旧25局</button>
            </div>
        </div>
        <div class="wfp-table-wrap">
            <table class="wfp-table" id="wfp-history-table">
                <thead>
                    <tr>
                        <th>#</th>
                        <th>时间</th>
                        <th>玩家牌</th>
                        <th>庄家牌</th>
                        <th>公共牌</th>
                        <th>结果</th>
                        <th>赢钱</th>
                    </tr>
                </thead>
                <tbody id="wfp-history-body">
                    <tr><td colspan="7" style="text-align:center;color:#8da0b3;padding:30px 0;"><i class="fas fa-spinner fa-pulse"></i> 加载中...</td></tr>
                </tbody>
            </table>
        </div>
    </div>

    <!-- 模态框 -->
    <div class="modal-overlay" id="wfpDetailModal">
        <div class="modal-content">
            <div class="modal-header">
                <h2><i class="fas fa-cards"></i> Wild Five Card Poker 对局详情</h2>
                <button class="modal-close" id="wfpModalCloseBtn">&times;</button>
            </div>
            <div class="modal-body">
                <div class="detail-layout">
                    <!-- 左侧：手牌信息 -->
                    <div class="detail-left">
                        <div class="hand-section">
                            <div class="hand-label">庄家最终手牌</div>
                            <div class="hand-cards" id="wfp-detail-dealer-aft">—</div>
                        </div>
                        <div class="hand-section">
                            <div class="hand-label">公共牌</div>
                            <div class="hand-cards" id="wfp-detail-public">—</div>
                        </div>
                        <div class="hand-section">
                            <div class="hand-label">玩家最终手牌</div>
                            <div class="hand-cards" id="wfp-detail-player-aft">—</div>
                        </div>
                        <div class="hand-section">
                            <div class="hand-label">庄家原始手牌</div>
                            <div class="hand-cards" id="wfp-detail-dealer-ori">—</div>
                        </div>
                        <div class="hand-section">
                            <div class="hand-label">玩家原始手牌</div>
                            <div class="hand-cards" id="wfp-detail-player-ori">—</div>
                        </div>
                    </div>

                    <!-- 右侧：时间、结果、元数据、牌堆 -->
                    <div class="detail-right">
                        <!-- 时间和结果放最前面 -->
                        <div class="detail-meta-row" style="margin-bottom:10px;">
                            <div class="meta-item">
                                <span class="meta-label">时间</span>
                                <span class="meta-value" id="wfp-detail-time" style="font-size:1rem; background:transparent; padding-left:0;">—</span>
                            </div>
                            <div class="meta-item">
                                <span class="meta-label">结果</span>
                                <span class="meta-value" id="wfp-detail-result" style="font-size:1rem; background:transparent; padding-left:0;">—</span>
                            </div>
                        </div>

                        <div class="detail-meta-row">
                            <div class="meta-item">
                                <span class="meta-label">局号</span>
                                <span class="meta-value" id="wfp-detail-index">—</span>
                            </div>
                            <div class="meta-item">
                                <span class="meta-label">切牌位置</span>
                                <span class="meta-value" id="wfp-detail-cut">—</span>
                            </div>
                        </div>
                        <div class="deck-section">
                            <div class="deck-label">牌堆顺序 (53张)</div>
                            <div class="deck-cards" id="wfp-detail-deck"></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<style>
    .wfp-content .dashboard-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
        gap: 25px;
        margin-bottom: 35px;
    }
    .wfp-content .stats-grid-2 {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 20px;
    }
    .wfp-content .stats-grid-4 {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 16px;
    }
    .wfp-content .stat-item {
        background: rgba(40,55,75,0.5);
        border-radius: 12px;
        padding: 16px 12px;
        text-align: center;
        transition: all 0.25s ease;
    }
    .wfp-content .stat-item:hover {
        background: rgba(50,70,95,0.7);
        transform: scale(1.02);
    }
    .wfp-content .stat-value {
        font-size: 2.4rem;
        font-weight: 700;
        color: #ffcc00;
        text-shadow: 0 0 10px rgba(255,204,0,0.25);
        line-height: 1.2;
    }
    .wfp-content .stat-value.green {
        color: #4ecdc4;
        text-shadow: 0 0 10px rgba(78,205,196,0.25);
    }
    .wfp-content .stat-value.red {
        color: #ff6b6b;
        text-shadow: 0 0 10px rgba(255,107,107,0.25);
    }
    .wfp-content .stat-label {
        font-size: 1rem;
        color: #8da0b3;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-top: 4px;
    }
    .wfp-content .stat-sub {
        font-size: 0.85rem;
        color: #6a7f94;
        margin-top: 2px;
    }
    .wfp-content .card {
        background: rgba(25,35,50,0.7);
        border-radius: 15px;
        padding: 24px;
        box-shadow: 0 8px 25px rgba(0,0,0,0.5);
        backdrop-filter: blur(5px);
        border: 1px solid rgba(255,255,255,0.07);
        transition: transform 0.25s ease;
    }
    .wfp-content .card:hover {
        transform: translateY(-3px);
    }
    .wfp-content .card-header {
        display: flex;
        align-items: center;
        margin-bottom: 18px;
        padding-bottom: 12px;
        border-bottom: 1px solid rgba(255,255,255,0.08);
    }
    .wfp-content .card-header i {
        font-size: 1.6rem;
        margin-right: 14px;
        color: #ffcc00;
    }
    .wfp-content .card-header h2 {
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
    .wfp-content .wfp-table-wrap {
        overflow-x: auto;
        margin-top: 6px;
    }
    .wfp-content .wfp-table {
        table-layout: fixed;
        width: 100%;
    }
    .wfp-content .wfp-table th:nth-child(1),
    .wfp-content .wfp-table td:nth-child(1) { width: 6%; }
    .wfp-content .wfp-table th:nth-child(2),
    .wfp-content .wfp-table td:nth-child(2) { width: 14%; }
    .wfp-content .wfp-table th:nth-child(3),
    .wfp-content .wfp-table td:nth-child(3) { width: 20%; text-align: left; }
    .wfp-content .wfp-table th:nth-child(4),
    .wfp-content .wfp-table td:nth-child(4) { width: 20%; text-align: left; }
    .wfp-content .wfp-table th:nth-child(5),
    .wfp-content .wfp-table td:nth-child(5) { width: 14%; text-align: left; }
    .wfp-content .wfp-table th:nth-child(6),
    .wfp-content .wfp-table td:nth-child(6) { width: 12%; text-align: center; }
    .wfp-content .wfp-table th:nth-child(7),
    .wfp-content .wfp-table td:nth-child(7) { width: 14%; text-align: center; }

    .wfp-content .wfp-table th,
    .wfp-content .wfp-table td {
        padding: 10px 8px;
        word-break: break-word;
    }
    .wfp-content .wfp-table th {
        background: rgba(40,55,75,0.6);
        color: #8da0b3;
        padding: 12px 10px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        border-bottom: 2px solid rgba(255,255,255,0.06);
    }
    .wfp-content .wfp-table td {
        padding: 10px 10px;
        border-bottom: 1px solid rgba(255,255,255,0.04);
        color: #d0d8e0;
        vertical-align: middle;
        cursor: pointer;
        transition: background 0.15s;
    }
    .wfp-content .wfp-table tr:hover td {
        background: rgba(255,204,0,0.06);
    }
    .wfp-content .cards-mini {
        font-family: 'Segoe UI', monospace;
        font-weight: 600;
        letter-spacing: 0.5px;
        font-size: 0.85rem;
    }
    .wfp-content .winnings-positive {
        color: #4ecdc4;
        font-weight: 700;
    }
    .wfp-content .winnings-negative {
        color: #ff6b6b;
        font-weight: 700;
    }
    .wfp-content .winnings-zero {
        color: #8da0b3;
    }
    .wfp-content .wfp-result-badge {
        display: inline-block;
        padding: 2px 14px;
        border-radius: 50px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .wfp-content .wfp-result-badge.win {
        background: rgba(78,205,196,0.25);
        color: #4ecdc4;
    }
    .wfp-content .wfp-result-badge.lose {
        background: rgba(255,107,107,0.25);
        color: #ff6b6b;
    }
    .wfp-content .wfp-result-badge.push {
        background: rgba(255,215,0,0.2);
        color: #ffd700;
    }
    .wfp-content .wfp-result-badge.fold {
        background: rgba(150,150,150,0.2);
        color: #aaa;
    }
    .public-card {
        background: rgba(255,204,0,0.15);
        border-radius: 4px;
        padding: 0 4px;
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
    .hand-cards .public-mark {
        background: rgba(255,204,0,0.2);
        border-radius: 4px;
        padding: 0 4px;
    }

    /* ----- 弃牌标记（无文字） ----- */
    .hand-cards .discard {
        text-decoration: line-through;
        color: #ff6b6b !important;          /* 强制红色 */
        background: rgba(255,0,0,0.2);
        border-radius: 4px;
        padding: 0 4px;
    }
    /* 保留花色原有颜色，但被删除线覆盖，红色更明显 */
    .hand-cards .discard.suit-heart,
    .hand-cards .discard.suit-diamond {
        color: #ff6b6b !important;
    }
    .hand-cards .discard.suit-spade,
    .hand-cards .discard.suit-club {
        color: #ff6b6b !important;
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

    /* 原始手牌区分样式（庄家/玩家） */
    #wfp-detail-dealer-ori {
        background: rgba(78, 205, 196, 0.15) !important;
        border-left: 4px solid #4ecdc4 !important;
    }
    #wfp-detail-player-ori {
        background: rgba(255, 107, 107, 0.15) !important;
        border-left: 4px solid #ff6b6b !important;
    }

    @media (max-width: 768px) {
        .wfp-content .dashboard-grid {
            grid-template-columns: 1fr;
        }
        .wfp-content .stats-grid-4 {
            grid-template-columns: repeat(2, 1fr);
        }
        .wfp-content .detail-layout {
            flex-direction: column;
        }
        .wfp-content .detail-right {
            width: 100%;
        }
        .wfp-content .wfp-table {
            font-size: 0.78rem;
        }
        .wfp-content .wfp-table th,
        .wfp-content .wfp-table td {
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
        .wfp-content .stats-grid-4 {
            grid-template-columns: 1fr 1fr;
        }
        .wfp-content .stats-grid-2 {
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
        const WFP_URL = './Json/Wild_Five_Card_Poker.json';
        let allRecords = [];
        let currentView = 'latest';
        const PAGE_SIZE = 25;

        function parseCard(cardStr) {
            if (!cardStr) return '?';
            if (cardStr === 'JOKER') return '🃏';
            return cardStr;
        }

        // 格式化牌，并标记公共牌（用 {} 包裹）
        function formatCardsWithPublic(cards, publicCards, asHtml = true) {
            if (!cards || !Array.isArray(cards)) return '—';
            if (!publicCards) publicCards = [];
            const publicSet = new Set(publicCards);
            return cards.map(c => {
                const display = parseCard(c);
                const isPublic = publicSet.has(c);
                let suitClass = '';
                if (display.includes('♥')) suitClass = 'suit-heart';
                else if (display.includes('♦')) suitClass = 'suit-diamond';
                else if (display.includes('♠')) suitClass = 'suit-spade';
                else if (display.includes('♣')) suitClass = 'suit-club';
                let content = display;
                if (isPublic) {
                    content = '{' + display + '}';
                }
                if (asHtml) {
                    let extraClass = isPublic ? ' public-mark' : '';
                    return `<span class="card-suit ${suitClass}${extraClass}">${content}</span>`;
                } else {
                    return content;
                }
            }).join(' ');
        }

        // 普通格式化（无公共标记）
        function formatCards(cards, asHtml = true) {
            return formatCardsWithPublic(cards, [], asHtml);
        }

        // ===== 新增：带弃牌标记的格式化（不增加任何文字） =====
        function formatCardsWithDiscard(cards, discardList, asHtml = true) {
            if (!cards || !Array.isArray(cards)) return '—';
            if (!discardList) discardList = [];
            if (!Array.isArray(discardList)) discardList = [discardList];
            const discardSet = new Set(discardList);
            return cards.map(c => {
                const display = parseCard(c);
                const isDiscard = discardSet.has(c);
                let suitClass = '';
                if (display.includes('♥')) suitClass = 'suit-heart';
                else if (display.includes('♦')) suitClass = 'suit-diamond';
                else if (display.includes('♠')) suitClass = 'suit-spade';
                else if (display.includes('♣')) suitClass = 'suit-club';
                let extraClass = isDiscard ? ' discard' : '';
                if (asHtml) {
                    return `<span class="card-suit ${suitClass}${extraClass}">${display}</span>`;
                } else {
                    return display;
                }
            }).join(' ');
        }

        function formatWinnings(val) {
            if (val === undefined || val === null) return '—';
            const num = Number(val);
            if (num === 0) return '<span class="winnings-zero">$0</span>';
            if (num > 0) return `<span class="winnings-positive">+$${num.toFixed(0)}</span>`;
            return `<span class="winnings-negative">-$${Math.abs(num).toFixed(0)}</span>`;
        }

        function getResultBadge(winner) {
            if (winner === 'fold') return '<span class="wfp-result-badge fold">弃牌</span>';
            if (winner === 'player') return '<span class="wfp-result-badge win">玩家胜</span>';
            if (winner === 'dealer') return '<span class="wfp-result-badge lose">庄家胜</span>';
            if (winner === 'push') return '<span class="wfp-result-badge push">平局</span>';
            return '<span class="wfp-result-badge fold">—</span>';
        }

        function renderWfpTable() {
            const tbody = document.getElementById('wfp-history-body');
            if (!allRecords || allRecords.length === 0) {
                tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:#8da0b3;padding:30px 0;">暂无对局数据</td></tr>';
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
            for (const game of displayRecords) {
                const realIndex = allRecords.indexOf(game);
                const winner = game.result?.winner || '';
                const winAmount = game.result?.win_amount;
                const time = game.timestamp ? game.timestamp.replace('T', ' ').slice(0, 19) : '—';
                const publicCards = game.public_cards || [];
                const playerAft = game.player_cards_aft || [];
                const dealerAft = game.dealer_cards_aft || [];
                const playerHtml = formatCardsWithPublic(playerAft, publicCards, true);
                const dealerHtml = formatCardsWithPublic(dealerAft, publicCards, true);
                const publicHtml = formatCards(publicCards, true);
                const badge = getResultBadge(winner);
                const winHtml = formatWinnings(winAmount);
                html += `<tr data-index="${realIndex}">
                    <td>${game.game_id || '—'}</td>
                    <td style="font-size:0.8rem;color:#8da0b3;">${time}</td>
                    <td class="cards-mini">${playerHtml}</td>
                    <td class="cards-mini">${dealerHtml}</td>
                    <td class="cards-mini">${publicHtml}</td>
                    <td>${badge}</td>
                    <td>${winHtml}</td>
                </tr>`;
            }

            tbody.innerHTML = html;

            document.querySelectorAll('#wfp-history-body tr').forEach(row => {
                row.addEventListener('click', function() {
                    const idx = parseInt(this.dataset.index);
                    if (!isNaN(idx) && allRecords[idx]) {
                        openWfpDetailModal(allRecords[idx], idx);
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

            document.getElementById('wfp-total').textContent = total;
            document.getElementById('wfp-winrate').textContent = winRate.toFixed(1) + '%';
            document.getElementById('wfp-player-wins').textContent = playerWins;
            document.getElementById('wfp-dealer-wins').textContent = dealerWins;
            document.getElementById('wfp-pushes').textContent = pushes;
            document.getElementById('wfp-folds').textContent = folds;
            document.getElementById('wfp-player-pct').textContent = playerPct.toFixed(1) + '%';
            document.getElementById('wfp-dealer-pct').textContent = dealerPct.toFixed(1) + '%';
            document.getElementById('wfp-push-pct').textContent = pushPct.toFixed(1) + '%';
            document.getElementById('wfp-fold-pct').textContent = foldPct.toFixed(1) + '%';
        }

        async function loadWfp() {
            try {
                const resp = await fetch(WFP_URL);
                if (!resp.ok) throw new Error('HTTP ' + resp.status);
                const data = await resp.json();

                if (!data.history || !Array.isArray(data.history)) {
                    throw new Error('数据格式错误：缺少 history 数组');
                }
                allRecords = data.history;

                if (data.history_record) {
                    updateStats(data.history_record);
                }

                renderWfpTable();

                document.querySelectorAll('.page-btn').forEach(btn => {
                    btn.classList.toggle('active', btn.dataset.page === currentView);
                });

            } catch (err) {
                console.error('Wild Five Card Poker load error:', err);
                document.getElementById('wfp-history-body').innerHTML =
                    `<tr><td colspan="7" style="text-align:center;color:#ff6b6b;padding:30px 0;"><i class="fas fa-exclamation-triangle"></i> 加载失败: ${err.message}</td></tr>`;
            }
        }

        function openWfpDetailModal(game, index) {
            const publicCards = game.public_cards || [];

            // ===== 原始手牌使用带弃牌标记的函数 =====
            document.getElementById('wfp-detail-dealer-ori').innerHTML = formatCardsWithDiscard(game.dealer_cards_ori, game.dealer_discard, true) || '—';
            document.getElementById('wfp-detail-player-ori').innerHTML = formatCardsWithDiscard(game.player_cards_ori, game.player_discard, true) || '—';

            // 庄家最终（标记公共牌）
            document.getElementById('wfp-detail-dealer-aft').innerHTML = formatCardsWithPublic(game.dealer_cards_aft, publicCards, true) || '—';
            // 公共牌
            document.getElementById('wfp-detail-public').innerHTML = formatCards(publicCards, true) || '—';
            // 玩家最终（标记公共牌）
            document.getElementById('wfp-detail-player-aft').innerHTML = formatCardsWithPublic(game.player_cards_aft, publicCards, true) || '—';

            // 右侧元数据：局号、切牌位置
            document.getElementById('wfp-detail-index').textContent = (index + 1);
            document.getElementById('wfp-detail-cut').textContent = game.cut_position ?? '—';

            // 牌堆
            const deckContainer = document.getElementById('wfp-detail-deck');
            deckContainer.innerHTML = '';
            if (game.deck_order && Array.isArray(game.deck_order)) {
                const cutPos = game.cut_position;
                const total = game.deck_order.length;
                game.deck_order.forEach((card, idx) => {
                    const span = document.createElement('span');
                    span.className = 'deck-card';
                    let offset = (idx - cutPos + total) % total;
                    if (offset >= 0 && offset <= 1) {
                        span.classList.add('color-yellow');
                    } else if (offset >= 2 && offset <= 6) {
                        span.classList.add('color-green');
                    } else if (offset >= 7 && offset <= 11) {
                        span.classList.add('color-red');
                    }
                    let cardDisplay = parseCard(card);
                    let suitClass = '';
                    if (card.includes('♥')) suitClass = 'suit-heart';
                    else if (card.includes('♦')) suitClass = 'suit-diamond';
                    else if (card.includes('♠')) suitClass = 'suit-spade';
                    else if (card.includes('♣')) suitClass = 'suit-club';
                    span.innerHTML = `<span class="${suitClass}">${cardDisplay}</span>`;
                    deckContainer.appendChild(span);
                });
            } else {
                deckContainer.innerHTML = '<span style="color:#6a7f94;">无牌堆数据</span>';
            }

            // 时间和结果（显示在右侧）
            const time = game.timestamp ? game.timestamp.replace('T', ' ').slice(0, 19) : '—';
            document.getElementById('wfp-detail-time').textContent = time;

            const winner = game.result?.winner || '';
            const winAmount = game.result?.win_amount;
            let resultText = '';
            if (winner === 'fold') {
                resultText = '弃牌';
                if (winAmount !== undefined && winAmount !== null) {
                    resultText += ` (赢 $${winAmount.toFixed(0)})`;
                }
            } else if (winner === 'player') {
                resultText = `<span class="highlight-win">玩家胜 (赢 $${(winAmount || 0).toFixed(0)})</span>`;
            } else if (winner === 'dealer') {
                resultText = `<span class="highlight-lose">庄家胜</span>`;
            } else if (winner === 'push') {
                resultText = `<span class="highlight-push">平局 (赢 $${(winAmount || 0).toFixed(0)})</span>`;
            } else {
                resultText = '—';
            }
            document.getElementById('wfp-detail-result').innerHTML = resultText;

            document.getElementById('wfpDetailModal').classList.add('active');
        }

        function closeWfpDetailModal() {
            document.getElementById('wfpDetailModal').classList.remove('active');
        }

        document.addEventListener('DOMContentLoaded', function() {
            loadWfp();

            document.getElementById('wfpPageLatest').addEventListener('click', function() {
                if (currentView === 'latest') return;
                currentView = 'latest';
                renderWfpTable();
                document.querySelectorAll('.page-btn').forEach(btn => {
                    btn.classList.toggle('active', btn.dataset.page === 'latest');
                });
            });
            document.getElementById('wfpPageOldest').addEventListener('click', function() {
                if (currentView === 'oldest') return;
                currentView = 'oldest';
                renderWfpTable();
                document.querySelectorAll('.page-btn').forEach(btn => {
                    btn.classList.toggle('active', btn.dataset.page === 'oldest');
                });
            });

            document.getElementById('wfpModalCloseBtn').addEventListener('click', closeWfpDetailModal);
            document.getElementById('wfpDetailModal').addEventListener('click', function(e) {
                if (e.target === this) closeWfpDetailModal();
            });
            document.addEventListener('keydown', function(e) {
                if (e.key === 'Escape') closeWfpDetailModal();
            });

            // 自动刷新（每秒）
            setInterval(loadWfp, 1000);
        });
    })();
</script>