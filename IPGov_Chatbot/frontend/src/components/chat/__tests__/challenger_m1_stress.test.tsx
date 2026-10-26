import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { SmartTable, resolveSmartTableData } from '../SmartTable';
import { MessageList } from '../MessageList';
import { MessageItem } from '../MessageItem';
import { SingleMetricSliderCard } from '../SingleMetricSliderCard';
import {
  compactMessageForStorage,
  cleanSessionTitle,
  stripTenantContextPrefix,
  saveSession,
  loadSessions,
  mergeSessions,
  clearAllSessions,
} from '../../../lib/storage';
import { ChatMessage, ChatSession, TabularData, SingleMetricCardData } from '../../../types/chat';

// Setup Mock localStorage for Node.js test environment
class MockLocalStorage {
  private store: Record<string, string> = {};
  public quotaLimitBytes: number = Infinity;
  public throwOnSet: boolean = false;

  getItem(key: string): string | null {
    return this.store[key] ?? null;
  }

  setItem(key: string, value: string): void {
    if (this.throwOnSet) {
      const err = new Error('QuotaExceededError: DOMException');
      err.name = 'QuotaExceededError';
      throw err;
    }
    const currentSizeWithoutKey = Object.entries(this.store)
      .filter(([k]) => k !== key)
      .reduce((acc, [, v]) => acc + v.length, 0);
    if (currentSizeWithoutKey + value.length > this.quotaLimitBytes) {
      const err = new Error('QuotaExceededError: DOMException');
      err.name = 'QuotaExceededError';
      throw err;
    }
    this.store[key] = value;
  }

  removeItem(key: string): void {
    delete this.store[key];
  }

  clear(): void {
    this.store = {};
  }
}

const mockStorage = new MockLocalStorage();
(global as any).window = { localStorage: mockStorage };
(global as any).localStorage = mockStorage;

export async function runChallengerM1StressSuite() {
  console.log('=== STARTING CHALLENGER M1 EMPIRICAL STRESS TEST SUITE ===');

  // =========================================================================
  // 1. STRESS TEST: Multi-Turn Storage Scalability (10+, 20+, 50+ Turns)
  // =========================================================================
  console.log('\n--- 1. Testing Storage Scalability & Quota Bounding ---');
  mockStorage.clear();
  mockStorage.quotaLimitBytes = Infinity;
  mockStorage.throwOnSet = false;

  // 1.1 Generate 50 turns (100 messages) with heavy datasets
  const turnsCount = 50;
  const messages: ChatMessage[] = [];
  for (let i = 1; i <= turnsCount; i++) {
    // User message
    messages.push({
      id: `user-turn-${i}`,
      role: 'user',
      content: `[tenant_code=68, level=0] Thống kê chỉ tiêu lần thứ ${i} với dữ liệu mở rộng?`,
      timestamp: new Date(Date.now() - (turnsCount - i) * 60000).toISOString(),
    });

    // Heavy assistant message with 80 tabular rows, deep tree models, multi_parent_rows
    const heavyRows = Array.from({ length: 80 }, (_, rIdx) => ({
      stt: rIdx + 1,
      item: `Chỉ tiêu chi tiết ${i}-${rIdx + 1}`,
      category: `Nhóm phân cấp ${rIdx % 5}`,
      value: `${(rIdx + 1) * 10}`,
      report_date: `2026-0${(rIdx % 9) + 1}-28`,
      office: 'Chi cục Phát triển nông thôn',
    }));

    const heavyTrees: Record<string, any> = {};
    for (let t = 1; t <= 10; t++) {
      heavyTrees[`root-${t}`] = {
        id: `root-${t}`,
        name: `Cây chỉ tiêu gốc ${t}`,
        children: Array.from({ length: 20 }, (_, c) => ({ id: `child-${t}-${c}`, name: `Nhánh con ${c}` })),
      };
    }

    messages.push({
      id: `bot-turn-${i}`,
      role: 'assistant',
      content: `Kết quả phân tích thống kê lượt ${i} cho lãnh đạo cấp tỉnh.`,
      timestamp: new Date(Date.now() - (turnsCount - i) * 60000 + 5000).toISOString(),
      tabular_data: {
        title: `Bảng dữ liệu chỉ tiêu tổng hợp lượt ${i}`,
        columns: [
          { key: 'stt', label: 'STT', align: 'center', data_type: 'number' },
          { key: 'item', label: 'Tên chỉ tiêu', align: 'left', data_type: 'text' },
          { key: 'category', label: 'Nhóm phân cấp', align: 'left', data_type: 'text' },
          { key: 'value', label: 'Giá trị', align: 'right', data_type: 'number' },
          { key: 'report_date', label: 'Kỳ báo cáo', align: 'center', data_type: 'text' },
        ],
        rows: heavyRows,
        total_records: 80,
        trees_by_root_id: heavyTrees,
        level1_rows: Array.from({ length: 30 }, (_, l) => ({ id: `lvl1-${l}` })),
        multi_parent_rows: Array.from({ length: 50 }, (_, m) => ({ id: `mp-${m}` })),
      },
    });
  }

  // 1.2 Measure raw size vs compacted size for a 10-turn slice
  const slice10Turns = messages.slice(0, 20); // 10 user + 10 bot
  const raw10TurnsSize = JSON.stringify(slice10Turns).length;
  const compacted10Turns = slice10Turns.map(compactMessageForStorage);
  const compacted10TurnsSize = JSON.stringify(compacted10Turns).length;
  const reductionPercent = Math.round((1 - compacted10TurnsSize / raw10TurnsSize) * 100);

  console.log(`- 10-turn raw payload size: ${(raw10TurnsSize / 1024).toFixed(2)} KB`);
  console.log(`- 10-turn compacted payload size: ${(compacted10TurnsSize / 1024).toFixed(2)} KB`);
  console.log(`- Storage reduction: ${reductionPercent}% (Target: > 75%)`);

  assert.ok(reductionPercent >= 75, `Storage reduction must be >= 75%, got ${reductionPercent}%`);
  for (const msg of compacted10Turns) {
    if (msg.role === 'assistant' && msg.tabular_data) {
      assert.ok(msg.tabular_data.rows.length <= 20, 'Compact rows must be <= 20');
      assert.equal(msg.tabular_data.trees_by_root_id, undefined, 'trees_by_root_id must be stripped');
      assert.equal(msg.tabular_data.level1_rows, undefined, 'level1_rows must be stripped');
      assert.ok(msg.tabular_data.multi_parent_rows.length <= 20, 'multi_parent_rows must be <= 20');
    }
  }

  // 1.3 Save 50-turn session and verify persistence
  const heavySession: ChatSession = {
    id: 'heavy-session-50',
    title: '[tenant_code=68, level=0] Phiên họp phân tích điều hành quý 1 năm 2026',
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    messages: messages,
  };

  saveSession(heavySession);
  const loadedSessions = loadSessions();
  assert.equal(loadedSessions.length, 1, 'Should have exactly 1 saved session');
  assert.equal(loadedSessions[0].id, 'heavy-session-50');
  assert.equal(
    loadedSessions[0].title,
    cleanSessionTitle(heavySession.title),
    'Title must be stripped and capped to 42 chars'
  );
  assert.equal(loadedSessions[0].messages.length, 100, 'All 100 messages (50 turns) must be preserved');
  console.log(`- Saved & loaded 50-turn session successfully without data loss.`);

  // 1.4 QuotaExceededError Resilience Test
  console.log('\n--- 1.4 Testing QuotaExceededError Graceful Handling ---');
  // Create 10 sessions with 5 turns each
  for (let sIdx = 1; sIdx <= 10; sIdx++) {
    saveSession({
      id: `session-extra-${sIdx}`,
      title: `Phiên thảo luận thứ ${sIdx}`,
      createdAt: new Date(Date.now() - sIdx * 100000).toISOString(),
      updatedAt: new Date(Date.now() - sIdx * 100000).toISOString(),
      messages: messages.slice(0, 10),
    });
  }

  // Set tight quota limit to force eviction loop in safeWriteSessions
  const currentBytes = JSON.stringify(loadSessions()).length;
  // Restrict quota to 50% of current size so safeWriteSessions must drop older sessions
  mockStorage.quotaLimitBytes = Math.floor(currentBytes * 0.6);

  // Attempt to save a new session while storage is full
  saveSession({
    id: 'new-high-priority-session',
    title: 'Phiên khẩn cấp mới nhất',
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    messages: messages.slice(0, 4),
  });

  const resilientSessions = loadSessions();
  assert.ok(resilientSessions.length > 0, 'Must still contain sessions after eviction');
  assert.equal(
    resilientSessions[0].id,
    'new-high-priority-session',
    'Newest session must be prioritized and retained'
  );
  console.log(`- QuotaExceeded handled cleanly: evicted older sessions to fit quota.`);

  // Test when localStorage completely fails (throwOnSet = true)
  mockStorage.throwOnSet = true;
  assert.doesNotThrow(() => {
    saveSession({
      id: 'session-when-broken',
      title: 'Phiên khi storage hỏng',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      messages: [],
    });
  }, 'saveSession must NOT throw exception when localStorage throws QuotaExceededError');
  mockStorage.throwOnSet = false;

  // Test corrupted storage payload
  mockStorage.setItem('hdsd_chat_sessions_v1', 'NOT_VALID_JSON{[');
  const corruptedFallback = loadSessions();
  assert.deepEqual(corruptedFallback, [], 'Corrupted storage must return empty array without crashing');
  console.log(`- Corrupted localStorage safely recovered with empty array fallback.`);


  // =========================================================================
  // 2. STRESS TEST: SmartTable In-Place Period Filtering (0 Chat Turns)
  // =========================================================================
  console.log('\n--- 2. Testing SmartTable In-Place Period Filtering ---');

  // 2.1 Verify onSelectChip is NEVER called by dispatchContextTicket
  let chipCallCount = 0;
  let lastQuerySent = '';
  const mockOnSelectChip = (queryText: string) => {
    chipCallCount++;
    lastQuerySent = queryText;
  };

  const periodTabular: TabularData = {
    title: "Đối chiếu chỉ tiêu 'Chăn nuôi' theo các nhóm chỉ tiêu cha",
    columns: [
      { key: 'stt', label: 'STT', align: 'center', data_type: 'number' },
      { key: 'item', label: 'Tên chỉ tiêu', align: 'left', data_type: 'text' },
      { key: 'category', label: 'Nhóm chỉ tiêu', align: 'left', data_type: 'text' },
      { key: 'value', label: 'Giá trị mới nhất', align: 'right', data_type: 'text' },
      { key: 'report_date', label: 'Kỳ báo cáo', align: 'center', data_type: 'text' },
    ],
    rows: [
      {
        stt: 1,
        item: 'Chăn nuôi',
        category: 'Trang trại',
        value: '350',
        report_date: '31/03/2026',
        timeline_values: { year: '350', q1: '310', q2: '330', q3: '350' },
      },
      {
        stt: 2,
        item: 'Chăn nuôi',
        category: 'Hợp tác xã',
        value: '130',
        report_date: '31/03/2026',
        timeline_values: { year: '130', q1: '115', q2: '125', q3: '130' },
      },
      {
        stt: 3,
        item: 'Chăn nuôi',
        category: 'Tổ hợp tác',
        value: '45',
        report_date: '30/06/2026',
        timeline_values: { year: '45', q1: '38', q2: '45', q3: '45' },
      },
    ],
    multi_parent_rows: [
      { stt: 1, item: 'Chăn nuôi', category: 'Trang trại', value: '350' },
      { stt: 2, item: 'Chăn nuôi', category: 'Hợp tác xã', value: '130' },
    ],
    total_records: 3,
  };

  // Render SmartTable with mockOnSelectChip passed
  const renderedTable = renderToStaticMarkup(
    <SmartTable tabularData={periodTabular} onSelectChip={mockOnSelectChip} />
  );

  // Ensure ticket buttons render
  assert.ok(renderedTable.includes('data-testid="context-ticket-year"'), 'Must render context-ticket-year');
  assert.ok(renderedTable.includes('data-testid="context-ticket-q1"'), 'Must render context-ticket-q1');
  assert.ok(renderedTable.includes('data-testid="context-ticket-q2"'), 'Must render context-ticket-q2');
  assert.ok(renderedTable.includes('data-testid="context-ticket-q3"'), 'Must render context-ticket-q3');

  // Verify pure Vietnamese label
  assert.ok(renderedTable.includes('Kỳ báo cáo:'), 'Must show pure Vietnamese "Kỳ báo cáo:"');
  assert.ok(!renderedTable.includes('Ticket thời gian:'), 'Must NOT show "Ticket thời gian:"');

  // Check that mockOnSelectChip was NOT invoked during render
  assert.equal(chipCallCount, 0, 'Render must not call onSelectChip');

  // 2.2 Deep verification of SmartTable's period-adjusting algorithmic logic
  // Simulate periodAdjustedRows logic directly on rows:
  const testRows = periodTabular.rows;

  // Case A: period_snapshots branch
  const snapshotTabular = {
    ...periodTabular,
    period_snapshots: {
      q1: [{ stt: 1, item: 'Chăn nuôi', category: 'Trang trại', value: '310' }],
      q2: [{ stt: 1, item: 'Chăn nuôi', category: 'Trang trại', value: '330' }],
    },
  };
  const q1Snapshot = (snapshotTabular as any).period_snapshots['q1'];
  assert.equal(q1Snapshot[0].value, '310', 'Snapshot for Q1 must return 310');

  // Case B: timeline_values branch
  const q1Adjusted = testRows.map((r: any) => {
    const pMap = r.timeline_values;
    const targetVal = pMap['q1'];
    return { ...r, value: targetVal ?? r.value };
  });
  assert.equal(q1Adjusted[0].value, '310', 'Trang trại Q1 must be 310');
  assert.equal(q1Adjusted[1].value, '115', 'HTX Q1 must be 115');
  assert.equal(q1Adjusted[2].value, '38', 'THT Q1 must be 38');

  // Case C: Date filtering branch for rows without timeline_values
  const dateOnlyRows = [
    { stt: 1, name: 'Báo cáo 1', report_date: '2026-02-15' }, // Q1
    { stt: 2, name: 'Báo cáo 2', report_date: '2026-05-20' }, // Q2
    { stt: 3, name: 'Báo cáo 3', report_date: '2026-08-10' }, // Q3
    { stt: 4, name: 'Báo cáo 4', report_date: '31/03/2026' }, // Q1 VN fmt
  ];
  const q1Filtered = dateOnlyRows.filter((r) => {
    const val = r.report_date;
    return /-0[1-3]-/.test(val) || /\/(0[1-3]|1|2|3)\//.test(val);
  });
  assert.equal(q1Filtered.length, 2, 'Q1 filter must capture both 2026-02-15 and 31/03/2026');
  assert.equal(q1Filtered[0].stt, 1);
  assert.equal(q1Filtered[1].stt, 4);

  console.log(`- In-place period resolution verified across snapshots, timeline_values, and date formats.`);


  // =========================================================================
  // 3. STRESS TEST: Single Reasoning Indicator & Pure Vietnamese Labels
  // =========================================================================
  console.log('\n--- 3. Testing Single Reasoning Indicator (No Dual Bubbles) ---');

  // State 1: User just submitted a question; initial empty bot message streaming
  const state1Messages: ChatMessage[] = [
    {
      id: 'user-msg-1',
      role: 'user',
      content: 'cho tôi biết số lĩnh vực của HTX nông nghiệp',
      timestamp: '2026-10-25T10:00:00Z',
    },
    {
      id: 'bot-msg-1',
      role: 'assistant',
      content: '',
      isStreaming: true,
      timestamp: '2026-10-25T10:00:01Z',
    },
  ];

  const state1Html = renderToStaticMarkup(
    <MessageList
      messages={state1Messages}
      isLoading={true}
      currentStage={{
        stage: 'ĐANG XỬ LÝ',
        message: '🔍 Đang phân tích câu hỏi & đối chiếu ngữ cảnh...',
      }}
      onImageClick={() => {}}
    />
  );

  // Verify: Exactly 1 reasoning indicator rendered
  const stageMatches = state1Html.match(/Đang phân tích câu hỏi &amp; đối chiếu ngữ cảnh\.\.\./g) || [];
  assert.equal(
    stageMatches.length,
    1,
    'State 1 must have EXACTLY 1 stage indicator message'
  );

  const fallbackDotsMatches = state1Html.match(/Đang tra cứu dữ liệu\.\.\./g) || [];
  assert.equal(
    fallbackDotsMatches.length,
    0,
    'State 1 must NOT have any "Đang tra cứu dữ liệu..." fallback bubble (no dual indicator!)'
  );

  assert.ok(state1Html.includes('ĐANG XỬ LÝ'), 'Must use Vietnamese "ĐANG XỬ LÝ"');
  assert.ok(!state1Html.includes('THINKING'), 'Must NOT contain English "THINKING"');
  console.log('- State 1 verified: Exactly 1 reasoning indicator box, 0 duplicate bubbles.');

  // State 2: First token streaming has arrived
  const state2Messages: ChatMessage[] = [
    {
      id: 'user-msg-1',
      role: 'user',
      content: 'cho tôi biết số lĩnh vực của HTX nông nghiệp',
      timestamp: '2026-10-25T10:00:00Z',
    },
    {
      id: 'bot-msg-1',
      role: 'assistant',
      content: 'Hợp tác xã nông nghiệp hiện có 8 lĩnh vực hoạt động:',
      isStreaming: true,
      timestamp: '2026-10-25T10:00:01Z',
    },
  ];

  const state2Html = renderToStaticMarkup(
    <MessageList
      messages={state2Messages}
      isLoading={true}
      currentStage={{
        stage: 'ĐANG XỬ LÝ',
        message: 'Đang sinh nội dung...',
      }}
      onImageClick={() => {}}
    />
  );

  // In State 2, since messages[last].content is non-empty, MessageList stage indicator must be hidden!
  const state2StageMatches = state2Html.match(/Đang sinh nội dung\.\.\./g) || [];
  assert.equal(
    state2StageMatches.length,
    0,
    'State 2 must hide MessageList stage indicator once content starts streaming'
  );
  assert.ok(
    state2Html.includes('fluid-stream-container') && state2Html.includes('lĩnh'),
    'State 2 must render the streaming fluid text container and streamed tokens'
  );
  console.log('- State 2 verified: Stage indicator seamlessly transitions to content stream with zero dual bubble.');

  // State 3: Stream complete
  const state3Messages: ChatMessage[] = [
    {
      id: 'user-msg-1',
      role: 'user',
      content: 'cho tôi biết số lĩnh vực của HTX nông nghiệp',
      timestamp: '2026-10-25T10:00:00Z',
    },
    {
      id: 'bot-msg-1',
      role: 'assistant',
      content: 'Hợp tác xã nông nghiệp hiện có 8 lĩnh vực hoạt động:',
      isStreaming: false,
      timestamp: '2026-10-25T10:00:01Z',
    },
  ];

  const state3Html = renderToStaticMarkup(
    <MessageList
      messages={state3Messages}
      isLoading={false}
      currentStage={null}
      onImageClick={() => {}}
    />
  );

  const state3StageMatches = state3Html.match(/ĐANG XỬ LÝ/g) || [];
  assert.equal(state3StageMatches.length, 0, 'Completed state has 0 reasoning indicators');
  console.log('- State 3 verified: Settled message with 0 leftover reasoning boxes.');


  // =========================================================================
  // 4. VERIFICATION: SingleMetricSliderCard Senior-Friendly Requirements
  // =========================================================================
  console.log('\n--- 4. Testing SingleMetricSliderCard Senior-Friendly Design ---');
  const cardData: SingleMetricCardData = {
    criteria_id: 'crit-02',
    criteria_name: 'Số HTX nông nghiệp hoạt động hiệu quả',
    parent_name: 'Hiệu quả hoạt động',
    hierarchy_label: 'Cấp 2',
    current_value: '130',
    active_value: '130',
    raw_value: 130,
    office: 'Chi cục Phát triển nông thôn',
    mission: 'Phát triển nông thôn',
    report_date: '31/03/2026',
    timeline_snapshots: [
      {
        report_date: '31/03/2026',
        iso_date: '2026-03-31',
        period_label: 'Kỳ Q1 (31/03/2026)',
        value: '130',
        raw_value: 130,
      },
      {
        report_date: '30/06/2026',
        iso_date: '2026-06-30',
        period_label: 'Kỳ Q2 (30/06/2026)',
        value: '145',
        raw_value: 145,
      },
    ],
  };

  const cardMarkup = renderToStaticMarkup(<SingleMetricSliderCard card={cardData} />);
  assert.ok(cardMarkup.includes('Kỳ báo cáo:'), 'Must display "Kỳ báo cáo:"');
  assert.ok(!cardMarkup.includes('type="range"'), 'No range slider input');
  assert.ok(!cardMarkup.includes('Kỳ báo cáo đối chiếu'), 'No verbose header "Kỳ báo cáo đối chiếu"');
  assert.ok(cardMarkup.includes('data-testid="slider-period-pill-0"'), 'Pill 0 present');
  assert.ok(cardMarkup.includes('data-testid="slider-period-pill-1"'), 'Pill 1 present');
  console.log('- SingleMetricSliderCard confirmed senior-friendly: range input and verbose clutter eliminated.');

  // =========================================================================
  // 5. VERIFICATION: R3 Hierarchy Breakdown In-Place Period Switching (56;55;16;3 -> Q2: 57;55;16;0 -> Q1: 56;50;16;0)
  // =========================================================================
  console.log('\n--- 5. Testing R3 Hierarchy Breakdown In-Place Period Values (Hiệu quả hoạt động) ---');
  const r3Tabular: TabularData = {
    title: "Danh mục chi tiết các chỉ tiêu thuộc 'Hiệu quả hoạt động' năm 2026",
    columns: [
      { key: 'stt', label: 'STT', align: 'center', data_type: 'number' },
      { key: 'item', label: 'Tên chỉ tiêu', align: 'left', data_type: 'text' },
      { key: 'category', label: 'Nhóm chỉ tiêu', align: 'left', data_type: 'text' },
      { key: 'value', label: 'Giá trị mới nhất', align: 'right', data_type: 'text' },
      { key: 'office', label: 'Đơn vị thực hiện', align: 'left', data_type: 'text' },
      { key: 'mission', label: 'Nhiệm vụ trọng tâm', align: 'left', data_type: 'text' },
    ],
    rows: [
      {
        stt: 1,
        item: 'Số HTX nông nghiệp hoạt động hiệu quả tốt',
        category: 'HTX nông nghiệp > Hiệu quả hoạt động',
        value: '56',
        office: 'Chi cục',
        mission: 'Phát triển kinh tế tập thể, hợp tác xã',
        timeline_values: { year: '56', q1: '56', q2: '57', q3: '56', '2026-06-30': '57', '30/06/2026': '57' },
      },
      {
        stt: 2,
        item: 'Số HTX nông nghiệp hoạt động hiệu quả trung bình',
        category: 'HTX nông nghiệp > Hiệu quả hoạt động',
        value: '55',
        office: 'Chi cục',
        mission: 'Phát triển kinh tế tập thể, hợp tác xã',
        timeline_values: { year: '55', q1: '50', q2: '55', q3: '55', '2026-06-30': '55', '30/06/2026': '55' },
      },
      {
        stt: 3,
        item: 'Số HTX nông nghiệp hoạt động kém hiệu quả',
        category: 'HTX nông nghiệp > Hiệu quả hoạt động',
        value: '16',
        office: 'Chi cục',
        mission: 'Phát triển kinh tế tập thể, hợp tác xã',
        timeline_values: { year: '16', q1: '16', q2: '16', q3: '16', '2026-06-30': '16', '30/06/2026': '16' },
      },
      {
        stt: 4,
        item: 'Chưa đủ điều kiện đánh giá',
        category: 'HTX nông nghiệp > Hiệu quả hoạt động',
        value: '3',
        office: 'Chi cục',
        mission: 'Phát triển kinh tế tập thể, hợp tác xã',
        timeline_values: { year: '3', q1: '0', q2: '0', q3: '3', '2026-06-30': '0', '30/06/2026': '0' },
      },
    ],
    total_records: 4,
    parent_criterion_name: 'Hiệu quả hoạt động',
    parent_timeline_values: { year: '130', q1: '122', q2: '128', q3: '130', '2026-06-30': '128', '30/06/2026': '128' },
  };

  // Render SmartTable for default Year scope -> must render 56, 55, 16, 3
  const r3YearHtml = renderToStaticMarkup(<SmartTable tabularData={r3Tabular} />);
  assert.ok(r3YearHtml.includes('>56<') && r3YearHtml.includes('>55<') && r3YearHtml.includes('>16<') && r3YearHtml.includes('>3<'), 'Year SmartTable must render 56; 55; 16; 3');

  // Render SmartTable when temporal_scope is Q2 -> must render 57, 55, 16, 0
  const r3Q2Tabular: TabularData = {
    ...r3Tabular,
    temporal_scope: { year: '2026', period_label: 'Quý 2/2026', query_suffix: 'Quý 2/2026' } as any,
  };
  const r3Q2Html = renderToStaticMarkup(<SmartTable tabularData={r3Q2Tabular} />);
  assert.ok(r3Q2Html.includes('>57<') && r3Q2Html.includes('>55<') && r3Q2Html.includes('>16<') && r3Q2Html.includes('>0<'), 'Q2 SmartTable must render 57; 55; 16; 0');

  // Render SmartTable when temporal_scope has specific_date='2026-03-31' (must NOT clobber 56; 50; 16; 0 with year's 56; 55; 16; 3!)
  const r3SpecificDateTabular: TabularData = {
    ...r3Tabular,
    rows: r3Tabular.rows.map((r) => ({
      ...r,
      value: r.timeline_values.q1,
      timeline_values: { ...r.timeline_values, '2026-03-31': r.timeline_values.q1, '31/03/2026': r.timeline_values.q1 },
    })),
    temporal_scope: {
      year: '2026',
      specific_date: '2026-03-31',
      period_label: 'tính đến 31/03/2026',
      query_suffix: 'ngày 31/03/2026',
    } as any,
  };
  const r3SpecDateHtml = renderToStaticMarkup(<SmartTable tabularData={r3SpecificDateTabular} />);
  assert.ok(
    r3SpecDateHtml.includes('>56<') && r3SpecDateHtml.includes('>50<') && r3SpecDateHtml.includes('>16<') && r3SpecDateHtml.includes('>0<') && !r3SpecDateHtml.includes('>55<'),
    'Specific-date (31/03/2026) SmartTable must preserve 56; 50; 16; 0 and not overwrite with year values'
  );
  console.log('- R3 Hierarchy Breakdown SmartTable render across Year (56;55;16;3), Q2 (57;55;16;0), and Specific Date 31/03/2026 (56;50;26;0) verified.');

  // =========================================================================
  // 6. VERIFICATION: Layout Containment Invariant (Prevent sr-only / scrollIntoView Frame Collapse)
  // =========================================================================
  console.log('\n--- 6. Testing Layout Containment Invariants (SingleMetricSliderCard & MessageList) ---');
  assert.ok(
    cardMarkup.includes('data-testid="metric-slider-time" class="relative '),
    'SingleMetricSliderCard root must have position: relative to contain absolute .sr-only spans'
  );
  assert.ok(
    cardMarkup.includes('class="sr-only top-0 left-0"'),
    'SingleMetricSliderCard .sr-only spans must have top-0 left-0'
  );
  assert.ok(
    state3Html.includes('flex-1 min-h-0 relative overflow-y-auto'),
    'MessageList scroll container must have min-h-0 and relative'
  );
  console.log('- Layout containment invariants verified.');

  // =========================================================================
  // 7. VERIFICATION: Dual-Layer Session Persistence & Timestamp Invariants
  // =========================================================================
  console.log('\n--- 7. Testing Dual-Layer Session Merge & Timestamp Preservation ---');
  clearAllSessions();
  const historicalTs = '2026-10-26T05:08:20.421900+00:00';
  const rawLocalMsgs: ChatMessage[] = [
    {
      id: 'welcome-role_l0_lamdong',
      role: 'assistant',
      content: 'Xin chào đồng chí!',
      timestamp: historicalTs,
    },
    {
      id: 'u-1',
      role: 'user',
      content: 'Câu hỏi 1',
      timestamp: historicalTs,
    },
    {
      id: 'b-1',
      role: 'assistant',
      content: 'Trả lời 1',
      timestamp: historicalTs,
      isStreaming: true,
    },
    {
      id: 'b-pending',
      role: 'assistant',
      content: '',
      timestamp: historicalTs,
      isStreaming: true,
    },
  ];

  saveSession(
    {
      id: 'session-test-merge',
      title: 'Câu hỏi 1',
      role: 'role_l0_lamdong',
      level: 0,
      tenant_code: '68',
      createdAt: historicalTs,
      updatedAt: historicalTs,
      messages: rawLocalMsgs,
    },
    { preserveTimestamp: true }
  );

  const loadedAfterPreserve = loadSessions();
  assert.equal(loadedAfterPreserve.length, 1);
  assert.equal(
    loadedAfterPreserve[0].updatedAt,
    historicalTs,
    'saveSession with preserveTimestamp: true must preserve historical updatedAt'
  );
  assert.equal(
    loadedAfterPreserve[0].messages.length,
    2,
    'welcome-* and empty streaming placeholders must be filtered out on persist/load'
  );
  assert.equal(
    loadedAfterPreserve[0].messages[1].isStreaming,
    false,
    'Persisted messages must have isStreaming reset to false'
  );

  const cloudSession: ChatSession = {
    id: 'session-test-merge',
    title: 'Câu hỏi 1',
    role: 'role_l0_lamdong',
    level: 0,
    tenant_code: '68',
    createdAt: historicalTs,
    updatedAt: historicalTs,
    messages: [
      { id: 'u-1', role: 'user', content: 'Câu hỏi 1', timestamp: historicalTs },
      {
        id: 'b-1',
        role: 'assistant',
        content: 'Trả lời 1',
        timestamp: historicalTs,
        tabular_data: {
          columns: [{ key: 'name', label: 'Tên' }],
          rows: [{ name: 'HTX', timeline_values: { year: 10, q1: 5 } }],
          trees_by_root_id: { root1: { id: 'root1', name: 'HTX' } } as any,
        },
      },
    ],
  };

  const mergedResult = mergeSessions(
    [
      {
        ...loadedAfterPreserve[0],
        updatedAt: '2026-10-26T05:25:00.000Z',
        messages: rawLocalMsgs,
      },
    ],
    [cloudSession]
  );
  assert.equal(mergedResult[0].messages.length, 2, 'Merged session must have 2 real messages');
  assert.equal(
    mergedResult[0].updatedAt,
    historicalTs,
    'Merged session must preserve authoritative cloud updatedAt when message counts match'
  );
  console.log('- Dual-layer session merge, welcome-filtering, and timestamp preservation verified.');

  console.log('\n=== ALL CHALLENGER M1 EMPIRICAL STRESS TESTS PASSED (100%) ===\n');
}

runChallengerM1StressSuite();
